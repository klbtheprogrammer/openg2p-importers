import json
import logging

import jq
import requests

_logger = logging.getLogger(__name__)


class ODKClient:
    def __init__(
        self,
        env,
        base_url,
        username,
        password,
        project_id,
        form_id,
        target_registry,
        json_formatter=".",
    ):

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
        response = requests.post(login_url, headers=headers, data=data)
        if response.status_code == 200:
            self.session = response.json()["token"]
        else:
            raise Exception(f"Login failed: {response.text}")

    def test_connection(self):
        if not self.session:
            raise Exception("Session not created")
        info_url = f"{self.base_url}/v1/users/current"
        headers = {"Authorization": f"Bearer {self.session}"}
        response = requests.get(info_url, headers=headers)
        if response.status_code == 200:
            user = response.json()
            _logger.info(f'Connected to ODK Central as {user["displayName"]}')
            return True
        else:
            raise Exception(f"Connection test failed: {response}")

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
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()

        for member in data["value"]:
            try:
                mapped_json = jq.compile(self.json_formatter).input(member).text()
                mapped_dict = json.loads(mapped_json)

                if self.target_registry == "individual":
                    mapped_dict.update({"is_registrant": True, "is_group": False})
                elif self.target_registry == "group":
                    mapped_dict.update({"is_registrant": True, "is_group": True})

                # TODO: Handle many one2many based on requirements
                # phone one2many

                if "phone_number_ids" in mapped_dict:
                    mapped_dict["phone_number_ids"] = [
                        (
                            0,
                            0,
                            {
                                "phone_no": phone.get("phone_no", None),
                                "date_collected": phone.get("date_collected", None),
                                "disabled": phone.get("disabled", None),
                            },
                        )
                        for phone in mapped_dict["phone_number_ids"]
                    ]

                # Membership one2many
                if (
                    "group_membership_ids" in mapped_dict
                    and self.target_registry == "group"
                ):
                    individual_ids = []
                    head_added = False

                    for individual_mem in mapped_dict.get("group_membership_ids"):
                        # Create individual partner
                        individual = (
                            self.env["res.partner"]
                            .sudo()
                            .create(
                                {
                                    "family_name": individual_mem.get("name", None),
                                    "given_name": individual_mem.get("name", None),
                                    "name": individual_mem.get("name", None),
                                    "is_registrant": True,
                                    "is_group": False,
                                    "gender": self.get_gender(
                                        individual_mem.get("sex", None)
                                    ),
                                    "age": individual_mem.get("age", None),
                                }
                            )
                        )
                        if individual:
                            kind = None
                            if (
                                individual_mem.get("relationship_with_household_head")
                                == 1
                                and not head_added
                            ):
                                kind = self.get_or_create_kind("Head")
                                head_added = True

                            individual_data = {"individual": individual.id}
                            if kind:
                                individual_data["kind"] = [(4, kind.id)]

                            individual_ids.append((0, 0, individual_data))

                    mapped_dict["group_membership_ids"] = individual_ids

                # Reg_ids one2many
                if "reg_ids" in mapped_dict:
                    mapped_dict["reg_ids"] = [
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
                        for reg_id in mapped_dict["reg_ids"]
                    ]

                # update value into the res_partner table
                self.env["res.partner"].sudo().create(mapped_dict)
                data.update({"updated": True})

            except AttributeError as ex:
                _logger.error("Attribute Error", ex)
            except Exception as ex:
                _logger.error("An exception occurred", ex)

        return data

    def get_or_create_kind(self, kind_str):
        kind = self.env["g2p.group.membership.kind"].search(
            [("name", "=", kind_str)], limit=1
        )
        if kind:
            return kind
        else:
            return (
                self.env["g2p.group.membership.kind"].sudo().create({"name": kind_str})
            )

    def get_gender(self, gender_val):
        if gender_val in [1, 2]:
            gender_str = "male" if gender_val == 1 else "female"
            gender = (
                self.env["gender.type"]
                .sudo()
                .search([("code", "ilike", gender_str)], limit=1)
            )
            if gender:
                return gender.code
            else:
                return None
        else:
            return None
