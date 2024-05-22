import json
import logging
from datetime import datetime

import pyjq
import requests

from odoo import _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ODKClient:
    def __init__(
        self,
        env,
        _id,
        base_url,
        username,
        password,
        project_id,
        form_id,
        target_registry,
        json_formatter=".",
    ):
        self.id = _id
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.project_id = project_id
        self.form_id = form_id
        self.session = None
        self.env = env
        self.json_formatter = json_formatter
        self.target_registry = target_registry

    def login(self):
        login_url = f"{self.base_url}/v1/sessions"
        headers = {"Content-Type": "application/json"}
        data = json.dumps({"email": self.username, "password": self.password})
        try:
            response = requests.post(login_url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            if response.status_code == 200:
                self.session = response.json()["token"]
        except Exception as e:
            _logger.exception("Login failed: %s", e)
            raise ValidationError(f"Login failed: {e}") from e

    def test_connection(self):
        if not self.session:
            raise ValidationError(_("Session not created"))
        info_url = f"{self.base_url}/v1/users/current"
        headers = {"Authorization": f"Bearer {self.session}"}
        try:
            response = requests.get(info_url, headers=headers, timeout=10)
            response.raise_for_status()
            if response.status_code == 200:
                user = response.json()
                _logger.info(f'Connected to ODK Central as {user["displayName"]}')
                return True
        except Exception as e:
            _logger.exception("Connection test failed: %s", e)
            raise ValidationError(f"Connection test failed: {e}") from e

    def import_delta_records(
        self,
        last_sync_timestamp=None,
        skip=0,
        top=100,
    ):
        url = f"{self.base_url}/v1/projects/{self.project_id}/forms/{self.form_id}.svc/Submissions"
        if last_sync_timestamp:
            startdate = last_sync_timestamp.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            params = {
                "$top": top,
                "$skip": skip,
                "$count": "true",
                "$expand": "*",
                "$filter": "__system/submissionDate ge " + startdate,
            }
        else:
            params = {"$top": top, "$skip": skip, "$count": "true", "$expand": "*"}

        headers = {"Authorization": f"Bearer {self.session}"}
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
        except Exception as e:
            _logger.exception("Failed to parse response: %s", e)
            raise ValidationError(f"Failed to parse response: {e}") from e
        data = response.json()

        for member in data["value"]:
            try:
                mapped_json = pyjq.compile(self.json_formatter).all(member)[0]

                if self.target_registry == "individual":
                    mapped_json.update({"is_registrant": True, "is_group": False})
                elif self.target_registry == "group":
                    mapped_json.update({"is_registrant": True, "is_group": True})

                #priority_needs Many2many
                
                if "priority_needs_ids" in mapped_json:
                    priority_needs_names = mapped_json.get("priority_needs_ids").split()
                    pneeds = []

                    for name in priority_needs_names:
                        priority_need = self.env['g2p.priority_needs'].search([('code', '=', name)], limit=1)
                        if priority_need:
                            pneeds.append((4, priority_need.id))

                    mapped_json["priority_needs_ids"] = pneeds

                # #support_in_displacement_situation_ids Many2many
                
                if "support_in_displacement_situation_ids" in mapped_json:
                    support_in_displacement = mapped_json.get("support_in_displacement_situation_ids").split()
                    support = []

                    for name in support_in_displacement:
                        support_displacement = self.env['g2p.support_displacement_situation'].search([('code', '=', name)], limit=1)
                        if support_displacement:
                            support.append((4, support_displacement.id))

                    mapped_json["support_in_displacement_situation_ids"] = support

                # #prevents_financial_provider_access_ids Many2many
                
                if "prevents_financial_provider_access_ids" in mapped_json and mapped_json["prevents_financial_provider_access_ids"] != None:
                    prevents_financial_provider = mapped_json.get("prevents_financial_provider_access_ids").split()
                    fin= []

                    for name in prevents_financial_provider:
                        financial_access = self.env['g2p.prevents_financial_provider_access'].search([('code', '=', name)], limit=1)
                        if financial_access:
                            fin.append((4, financial_access.id))

                    mapped_json["prevents_financial_provider_access_ids"] = fin

                #Many2one fileds for regions, zone, & woreda
                region_id, zone_id, woreda_id, origin_region_id, origin_zone_id, origin_woreda_id = self.get_admin_records(mapped_json)
                mapped_json.update({
                    "region": region_id,
                    "zone": zone_id,
                    "woreda": woreda_id,
                    "origin_region": origin_region_id,
                    "origin_zone": origin_zone_id,
                    "origin_woreda": origin_woreda_id,
                })


                # TODO: Handle many one2many based on requirements
                # phone one2many
                if "phone_number_ids" in mapped_json:
                    mapped_json["phone_number_ids"] = [
                        (
                            0,
                            0,
                            {
                                "phone_no": phone.get("phone_no", None),
                                "date_collected": phone.get("date_collected", None),
                                "disabled": phone.get("disabled", None),
                            },
                        )
                        for phone in mapped_json["phone_number_ids"]
                    ]

                # Membership one2many
                if "group_membership_ids" in mapped_json and self.target_registry == "group":
                    individual_ids = []
                    relationships_ids = []
                    for individual_mem in mapped_json.get("group_membership_ids"):
                        individual_data = self.get_individual_data(individual_mem)
                        individual = self.env["res.partner"].sudo().create(individual_data)
                        if individual:
                            kind = self.get_member_kind(individual_mem)
                            individual_data = {"individual": individual.id}

                            if kind:
                                individual_data["kind"] = [(4, kind.id)]

                            relationship = self.get_member_relationship(individual.id, individual_mem)

                            if relationship:
                                relationships_ids.append((0, 0, relationship))

                            individual_ids.append((0, 0, individual_data))

                    mapped_json["related_1_ids"] = relationships_ids
                    mapped_json["group_membership_ids"] = individual_ids

                # Reg_ids one2many
                if "reg_ids" in mapped_json:
                    mapped_json["reg_ids"] = [
                        (
                            0,
                            0,
                            {
                                "id_type": self.env["g2p.id.type"]
                                .search(
                                    [("name", "=", reg_id.get("id_type", None))],
                                )[0]
                                .id,
                                "value": reg_id.get("value", None),
                                "expiry_date": reg_id.get("expiry_date", None),
                            },
                        )
                        for reg_id in mapped_json["reg_ids"]
                    ]

                updated_mapped_json = self.get_addl_data(mapped_json)

                # update value into the res_partner table
                self.env["res.partner"].sudo().create(updated_mapped_json)
                data.update({"form_updated": True})
            except AttributeError as ex:
                data.update({"form_failed": True})
                _logger.error("Attribute Error", ex)
            except Exception as ex:
                data.update({"form_failed": True})
                _logger.error("An exception occurred", ex)

        return data

    def get_member_kind(self, record):
        kind = None
        return kind

    def get_member_relationship(self, source_id, record):
        # TODO: Add Member Relationship code
        relationship = None
        return relationship

    def get_gender(self, gender_val):
        if gender_val:
            gender = self.env["gender.type"].sudo().search([("code", "=", gender_val)], limit=1)
            if gender:
                return gender.code
            else:
                return None
        else:
            return None

    def get_dob(self, record):
        dob = record.get("birthdate", None)
        if dob:
            return dob

        age = record.get("age", None)
        if age:
            now = datetime.now()
            birth_year = now.year - age
            return now.replace(year=birth_year).strftime("%Y-%m-%d")

    def get_individual_data(self, record):
        name = record.get("name", None)
        given_name = name.split(" ")[0]
        family_name = name.split(" ")[-1]
        dob = self.get_dob(record)
        addl_name = " ".join(name.split(" ")[1:-1])
        gender = self.get_gender(record.get("gender"))

        vals = {
            "name": name,
            "given_name": given_name,
            "family_name": family_name,
            "addl_name": addl_name,
            "is_registrant": True,
            "is_group": False,
            "birthdate": dob,
            "gender": gender,
        }

        return vals

    def get_addl_data(self, mapped_json):
        # Override this method to add more data

        return mapped_json
    
    def get_admin_records(self, record):
        region_name = record.get("region")
        zone_name = record.get("zone")
        woreda_name = record.get("woreda")
        origin_region_name = record.get("origin_region"),
        origin_zone_name = record.get("origin_zone"),
        origin_woreda_name = record.get("origin_woreda"),

        region_id = self.env['g2p.region'].search([('code', '=', region_name)], limit=1).id
        zone_id = self.env['g2p.zone'].search([('code', '=', zone_name)], limit=1).id
        woreda_id = self.env['g2p.woreda'].search([('code', '=', woreda_name)], limit=1).id
        origin_region_id = self.env['g2p.region'].search([('code', '=', origin_region_name)], limit=1).id
        origin_zone_id = self.env['g2p.zone'].search([('code', '=', origin_zone_name)], limit=1).id
        origin_woreda_id = self.env['g2p.woreda'].search([('code', '=', origin_woreda_name)], limit=1).id


        return region_id, zone_id, woreda_id, origin_region_id, origin_zone_id, origin_woreda_id
