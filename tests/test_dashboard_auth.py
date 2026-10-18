import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard_server import (  # noqa: E402
    SESSION_TTL_SECONDS,
    _create_session_token,
    _valid_session_token,
    create_dashboard_app,
)


class DashboardSessionTokenTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "DASHBOARD_USERNAME": "operator",
                "DASHBOARD_PASSWORD": "a-long-test-password",
                "SESSION_SECRET": "a-test-only-session-secret",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_session_token_is_signed_and_expires(self):
        token = _create_session_token("operator", "a-long-test-password", now=1000)
        self.assertIsNotNone(token)
        self.assertTrue(
            _valid_session_token(token, "operator", "a-long-test-password", now=1000)
        )
        self.assertFalse(
            _valid_session_token(token, "operator", "a-long-test-password", now=1000 + SESSION_TTL_SECONDS)
        )
        self.assertFalse(
            _valid_session_token(token + "tampered", "operator", "a-long-test-password", now=1000)
        )

    def test_changing_dashboard_credentials_invalidates_existing_session(self):
        token = _create_session_token("operator", "a-long-test-password", now=1000)
        self.assertFalse(_valid_session_token(token, "operator", "new-password", now=1001))


class DashboardLoginFlowTests(unittest.IsolatedAsyncioTestCase):
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
        self.client = TestClient(TestServer(create_dashboard_app()))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.environment.stop()

    async def test_login_page_and_unauthenticated_route_behavior(self):
        page = await self.client.get("/login")
        self.assertEqual(page.status, 200)
        page_text = await page.text()
        self.assertIn('name="username"', page_text)
        self.assertIn('name="password"', page_text)

        dashboard = await self.client.get("/", allow_redirects=False)
        self.assertEqual(dashboard.status, 303)
        self.assertEqual(dashboard.headers["Location"], "/login")

        api = await self.client.get("/api/logs")
        self.assertEqual(api.status, 401)
        self.assertEqual((await api.json())["error"], "Authentication required.")

        health = await self.client.get("/health")
        self.assertEqual(health.status, 200)

    async def test_invalid_login_shows_generic_error_without_echoing_password(self):
        response = await self.client.post(
            "/login",
            data={"username": "operator", "password": "wrong-secret"},
            allow_redirects=False,
        )
        self.assertEqual(response.status, 401)
        page_text = await response.text()
        self.assertIn("Username or password is incorrect.", page_text)
        self.assertNotIn("wrong-secret", page_text)

    async def test_valid_login_allows_dashboard_and_logout_clears_session(self):
        response = await self.client.post(
            "/login",
            data={"username": "operator", "password": "a-long-test-password"},
            allow_redirects=False,
        )
        self.assertEqual(response.status, 303)
        self.assertEqual(response.headers["Location"], "/")
        cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertNotIn("Secure", cookie)

        dashboard = await self.client.get("/")
        self.assertEqual(dashboard.status, 200)
        self.assertIn("Sign out", await dashboard.text())

        api = await self.client.get("/api/logs")
        self.assertEqual(api.status, 200)

        logout = await self.client.post("/logout", allow_redirects=False)
        self.assertEqual(logout.status, 303)
        self.assertEqual(logout.headers["Location"], "/login")
        self.assertIn("Max-Age=0", logout.headers["Set-Cookie"])

        api_after_logout = await self.client.get("/api/logs")
        self.assertEqual(api_after_logout.status, 401)

    async def test_https_proxy_sets_secure_cookie(self):
        response = await self.client.post(
            "/login",
            data={"username": "operator", "password": "a-long-test-password"},
            headers={"X-Forwarded-Proto": "https"},
            allow_redirects=False,
        )
        self.assertEqual(response.status, 303)
        self.assertIn("Secure", response.headers["Set-Cookie"])


if __name__ == "__main__":
    unittest.main()
