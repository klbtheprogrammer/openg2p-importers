from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from odoo.addons.g2p_odk_importer.models.odk_client import ODKClient


class TestODKClient(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_mock = MagicMock()
        cls.base_url = "http://example.com"
        cls.username = "test_user"
        cls.password = "test_password"
        cls.project_id = 5
        cls.form_id = "test_form_id"
        cls.target_registry = "group"
        cls.json_formatter = "."

    @patch("requests.post")
    def test_login_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_response

        odk_client = ODKClient(
            self.env_mock,
            self.base_url,
            self.username,
            self.password,
            self.project_id,
            self.form_id,
            self.target_registry,
            self.json_formatter,
        )

        odk_client.login()
        self.assertEqual(odk_client.session, "test_token")

    @patch("requests.post")
    def test_login_failure(self, mock_post):
        mock_post.side_effect = Exception("Test Error")

        odk_client = ODKClient(
            self.env_mock,
            self.base_url,
            self.username,
            self.password,
            self.project_id,
            self.form_id,
            self.target_registry,
            self.json_formatter,
        )

        with self.assertRaises(ValidationError):
            odk_client.login()

    @patch("requests.get")
    def test_test_connection_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"displayName": "test_user"}
        mock_get.return_value = mock_response

        odk_client = ODKClient(
            self.env_mock,
            self.base_url,
            self.username,
            self.password,
            self.project_id,
            self.form_id,
            self.target_registry,
            self.json_formatter,
        )

        odk_client.session = "test_token"
        self.assertTrue(odk_client.test_connection())

    @patch("requests.get")
    def test_test_connection_failure(self, mock_get):
        mock_get.side_effect = Exception("Connection Error")

        odk_client = ODKClient(
            self.env_mock,
            self.base_url,
            self.username,
            self.password,
            self.project_id,
            self.form_id,
            self.target_registry,
            self.json_formatter,
        )

        odk_client.session = "test_token"

        with self.assertRaises(ValidationError):
            odk_client.test_connection()

    @patch("requests.get")
    def test_import_delta_records_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": [{"name": "John Doe"}]}
        mock_get.return_value = mock_response

        odk_client = ODKClient(
            self.env_mock,
            self.base_url,
            self.username,
            self.password,
            self.project_id,
            self.form_id,
            self.target_registry,
            self.json_formatter,
        )

        odk_client.session = "test_token"
        result = odk_client.import_delta_records()
        self.assertTrue(result.get("form_updated"))

    @patch("requests.get")
    def test_import_delta_records_failure(self, mock_get):
        mock_get.side_effect = Exception("import Error")

        odk_client = ODKClient(
            self.env_mock,
            self.base_url,
            self.username,
            self.password,
            self.project_id,
            self.form_id,
            self.target_registry,
            self.json_formatter,
        )

        odk_client.session = "test_token"
        with self.assertRaises(ValidationError):
            odk_client.import_delta_records()
