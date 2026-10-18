import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dashboard_server


class AccountJsonImportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "DASHBOARD_USERNAME": "operator",
                "DASHBOARD_PASSWORD": "a-long-test-password",
                "SESSION_SECRET": "a-test-only-session-secret",
            },
        )
        self.environment.start()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_path_patch = patch.object(
            dashboard_server,
            "data_path",
            side_effect=lambda filename: str(Path(self.temp_dir.name) / filename),
        )
        self.data_path_patch.start()
        self.original_callbacks = dashboard_server.bot_state.refresh_callbacks
        dashboard_server.bot_state.refresh_callbacks = {}
        self.client = TestClient(TestServer(dashboard_server.create_dashboard_app()))
        await self.client.start_server()
        login = await self.client.post(
            "/login",
            data={"username": "operator", "password": "a-long-test-password"},
            allow_redirects=False,
        )
        self.assertEqual(login.status, 303)

    async def asyncTearDown(self):
        await self.client.close()
        dashboard_server.bot_state.refresh_callbacks = self.original_callbacks
        self.data_path_patch.stop()
        self.temp_dir.cleanup()
        self.environment.stop()

    async def test_import_adds_accounts_and_skips_duplicates_and_invalid_rows(self):
        accounts_path = Path(self.temp_dir.name) / "accounts.json"
        accounts_path.write_text(
            json.dumps([{"uid": "saved-uid", "password": "old-password"}]),
            encoding="utf-8",
        )

        response = await self.client.post(
            "/api/accounts/import",
            json={
                "accounts": [
                    {"uid": "saved-uid", "password": "new-password"},
                    {"token": "private-token-one"},
                    {"token": "private-token-one"},
                    {"uid": "uid-without-password"},
                    {"uid": "new-uid", "password": "new-password"},
                    "not-an-account",
                ]
            },
        )

        self.assertEqual(response.status, 200)
        result = await response.json()
        self.assertEqual(result["imported"], 2)
        self.assertEqual(result["duplicates"], 2)
        self.assertEqual(result["invalid"], 2)
        self.assertEqual(len(result["issues"]), 4)
        self.assertNotIn("private-token-one", await response.text())

        saved_accounts = json.loads(accounts_path.read_text(encoding="utf-8"))
        self.assertEqual(
            saved_accounts,
            [
                {"uid": "saved-uid", "password": "old-password"},
                {"token": "private-token-one"},
                {"uid": "new-uid", "password": "new-password"},
            ],
        )

    async def test_accepts_accounts_wrapper_and_rejects_malformed_structure(self):
        valid_response = await self.client.post(
            "/api/accounts/import",
            json={"accounts": [{"uid": "wrapped-uid", "password": "wrapped-password"}]},
        )
        self.assertEqual(valid_response.status, 200)
        self.assertEqual((await valid_response.json())["imported"], 1)

        single_response = await self.client.post(
            "/api/accounts/import",
            json={"uid": "single-uid", "password": "single-password"},
        )
        self.assertEqual(single_response.status, 200)
        self.assertEqual((await single_response.json())["imported"], 1)

        invalid_response = await self.client.post(
            "/api/accounts/import",
            json={"accounts": "not-a-list"},
        )
        self.assertEqual(invalid_response.status, 400)
        self.assertFalse((await invalid_response.json())["status"] == "ok")

    async def test_import_route_requires_dashboard_login(self):
        await self.client.post("/logout", allow_redirects=False)
        response = await self.client.post(
            "/api/accounts/import",
            json=[{"uid": "unauthorized-uid", "password": "secret"}],
        )
        self.assertEqual(response.status, 401)


if __name__ == "__main__":
    unittest.main()
