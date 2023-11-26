# models/odk_client.py

import json

import jq
import requests

from odoo.http import request


class ODKClient:
    # _name = "foo.sync"
    # _collection = "base.rest.registry.services"
    # _usage = "sync"

    # _name="odkclient"
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
        print(base_url)

        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.project_id = project_id
        self.form_id = form_id
        self.session = None
        self.env = env
        self.json_formatter = json_formatter
        self.target_registry = target_registry
        # self.component = {}

    def login(self):
        login_url = f"{self.base_url}/v1/sessions"
        headers = {"Content-Type": "application/json"}
        data = json.dumps({"email": self.username, "password": self.password})
        response = requests.post(login_url, headers=headers, data=data)
        if response.status_code == 200:
            print("RESPONSE", response.json())
            self.session = response.json()["token"]
        else:
            raise Exception(f"Login failed: {response.text}")

    def test_connection(self):
        if not self.session:
            raise Exception("Session not created")
        info_url = f"{self.base_url}/v1/users/self"
        headers = {"Authorization": f"Bearer {self.session}"}
        response = requests.get(info_url, headers=headers)
        if response.status_code == 200:
            user = response.json()
            print(f'Connected to ODK Central as {user["displayName"]}')
        else:
            raise Exception(f"Connection test failed: {response}")

    def get_header_token(self):
        if self.header_token is None:
            self.header_token = self._get_odk_login_token()
        return self.header_token

    def import_delta_records(
        self,
        last_sync_timestamp=None,
        skip=0,
        top=100,
    ):
        url = f"{self.base_url}/v1/projects/{self.project_id}/forms/{self.form_id}.svc/Submissions"
        print("last_sync_timestamp", last_sync_timestamp)
        if last_sync_timestamp:
            startdate = last_sync_timestamp.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            print("startdate", startdate)
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
        if request and request.session:
            session_id = request.session.sid
        else:
            # establish login code here.
            payload = {
                "jsonrpc": "2.0",
                "params": {
                    "db": "openg2p_odoo",
                    "login": "shibu@openg2p.org",
                    "password": "shi-123",
                },
            }
            response = requests.post(
                "http://localhost:8069/session/auth/login",
                headers={"Content-Type": "application/json"},
                params=payload,
                json=payload,
            )
            print("Response for login", response.text)
            if response.status_code == 200:
                result = response.json()
                if "error" in result:
                    error_message = result["error"]["data"]["message"]
                    print(f"Login failed: {error_message}")
                elif "session" in result:
                    session_id = result["session"]["sid"]
                    user_id = result["user_context"]["uid"]
                    print(
                        f"Login successful! Session ID: {session_id}, User ID: {user_id}"
                    )

                else:
                    print("Error connecting to Odoo server.")
        headers = {
            "Content-Type": "application/json",
            "Cookie": "session_id=" + session_id,
        }

        # base_url = http.request.httprequest.base_url
        # print("base_url : ", base_url)
        print("target_registry", self.target_registry)
        for record in data["value"]:
            print("data", data)
            # record = data["value"][0]
            # print("Formatter : ", self.json_formatter)
            mapped_json = jq.compile(self.json_formatter).input(record).text()

            print("Mapped : ", mapped_json)
            try:

                service_response = requests.post(
                    "http://localhost:8069/api/v1/registry/" + self.target_registry,
                    headers=headers,
                    data=mapped_json,
                )
                service_response.raise_for_status()
                print("Response", service_response.content)
                print("Response", service_response.text)
            except AttributeError as ex:
                print("Attribute Error", ex)
            except Exception as ex:
                print("An exception occurred", ex)

        return data

    def count(self):
        url = f"{self.url}/Submissions"
        params = {"$top": 0, "$count": "true"}
        response = requests.get(
            url, headers=self.get_header_token(), params=params, verify=SSL_VERIFY
        )
        response.raise_for_status()
        data = response.json()
        return data["@odata.count"]
