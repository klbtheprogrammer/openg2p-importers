from odoo import api, fields, models

from .odk_client import ODKClient


class OdkImport(models.Model):
    _name = "odk.import"
    _description = "ODK Import"

    name = fields.Char(required=True)
    odk_config_id = fields.Many2one(
        comodel_name="odk.config", string="ODK Configuration", required=True
    )

    @api.model
    def run_import(self):
        records = []
        odk_configs = self.env["odk.config"].search([])

        for odk_config in odk_configs:
            odk_client = ODKClient(
                odk_config.base_url, odk_config.username, odk_config.password
            )
            odk_client.login()

            form_ids = odk_client.get_form_ids()

            for form_id in form_ids:
                records += odk_client.get_delta_records(form_id)

        partner_obj = self.env["res.partner"]

        for record in records:
            partner = partner_obj.search([("odk_id", "=", record["id"])])
            if partner:
                partner.write({"name": record["name"]})
            else:
                partner_obj.create({"name": record["name"], "odk_id": record["id"]})

        return True

    def import_records(self):
        for import_record in self:
            client = ODKClient(
                import_record.odk_config_id.base_url,
                import_record.odk_config_id.username,
                import_record.odk_config_id.password,
            )
            client.login()
            client.import_delta_records()
