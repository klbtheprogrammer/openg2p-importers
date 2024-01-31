import logging
from datetime import datetime, timedelta

from odoo import fields, models

from .odk_client import ODKClient

_logger = logging.getLogger(__name__)


class OdkConfig(models.Model):
    _name = "odk.config"
    _description = "ODK Configuration"

    name = fields.Char(required=True)
    base_url = fields.Char(string="Base URL", required=True)
    username = fields.Char(required=True)
    password = fields.Char(required=True)
    project = fields.Char(required=False)
    form_id = fields.Char(string="Form ID", required=False)
    json_formatter = fields.Text(string="JSON Formatter", required=False)
    target_registry = fields.Selection(
        [("individual", "Individual"), ("group", "Group")]
    )
    last_sync_time = fields.Datetime(string="Last synced on", required=False)
    cron_id = fields.Many2one("ir.cron", string="Cron Job", required=False)
    job_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("started", "Started"),
            ("running", "Running"),
            ("completed", "Completed"),
        ],
        string="Status",
        required=True,
        default="draft",
    )

    interval_hours = fields.Integer(string="Interval in hours", required=False)
    start_datetime = fields.Datetime(string="Start Time", required=False)
    end_datetime = fields.Datetime(string="End Time", required=False)

    def test_connection(self):
        for config in self:
            client = ODKClient(
                self.env, config.base_url, config.username, config.password
            )
            client.login()
            client.test_connection()

    def import_records(self):
        for config in self:
            client = ODKClient(
                self.env,
                config.base_url,
                config.username,
                config.password,
                config.project,
                config.form_id,
                config.target_registry,
                config.json_formatter,
            )
            client.login()
            # try:
            client.import_delta_records(last_sync_timestamp=config.last_sync_time)
            config.update({"last_sync_time": fields.Datetime.now()})

    def import_records_by_id(self, _id):
        config = self.env["odk.config"].browse(_id)
        client = ODKClient(
            self.env,
            config.base_url,
            config.username,
            config.password,
            config.project,
            config.form_id,
            config.target_registry,
            config.json_formatter,
        )
        client.login()
        # try:
        client.import_delta_records(last_sync_timestamp=config.last_sync_time)
        config.update({"last_sync_time": fields.Datetime.now()})

        # except ex:
        #     print("Error",ex)

    def odk_import_action_trigger(self):
        for rec in self:
            if rec.job_status == "draft" or rec.job_status == "completed":
                _logger.info("Job Started")
                rec.job_status = "started"
                ir_cron = self.env["ir.cron"].sudo()
                rec.cron_id = ir_cron.create(
                    {
                        "name": "ODK Pull Cron " + rec.name + " #" + str(rec.id),
                        "active": True,
                        "interval_number": rec.interval_hours,
                        "interval_type": "minutes",
                        "model_id": self.env["ir.model"]
                        .search([("model", "=", "odk.config")])
                        .id,
                        "state": "code",
                        "code": "model.import_records_by_id(" + str(rec.id) + ")",
                        "doall": False,
                        "numbercall": -1,
                    }
                )
                rec.job_status = "running"
                now_datetime = datetime.now()
                rec.update(
                    {
                        "start_datetime": now_datetime
                        - timedelta(hours=rec.interval_hours),
                        "end_datetime": now_datetime,
                    }
                )

            elif rec.job_status == "started" or rec.job_status == "running":
                _logger.info("Job Stopped")
                rec.job_status = "completed"
                rec.sudo().cron_id.unlink()
                rec.cron_id = None
