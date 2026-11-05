"""Connect-account page: setup, connected, and OAuth return states."""
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

ENV = {"CREATOR_INSIGHTS_PUBLIC_DEMO": "1", "SUPABASE_URL": "", "SUPABASE_SECRET_KEY": "", "SUPABASE_SERVICE_ROLE_KEY": "",
       "INSTAGRAM_APP_ID": "", "INSTAGRAM_APP_SECRET": "", "TIKTOK_CLIENT_KEY": "", "TIKTOK_CLIENT_SECRET": "", "OAUTH_REDIRECT_URI": ""}


def videos():
    return pd.DataFrame({"id": list("abc"), "title": ["one", "two", ""], "created": pd.date_range("2026-10-01 09:00", periods=3, freq="D", tz="UTC"),
                         "views": [100, 200, None], "likes": [10, 20, 30], "comments": [1, 2, 3], "shares": [0, 1, None], "url": "https://example.com/v"})


class ConnectPageTests(unittest.TestCase):
    def run_app(self, env=None, before=None):
        with patch.dict("os.environ", {**ENV, **(env or {})}):
            app = AppTest.from_file("app.py", default_timeout=30)
            if before:
                before(app)
            app.session_state.page = "חיבור חשבון"
            return app.run()

    def test_not_configured_is_friendly_and_hides_developer_setup(self):
        app = self.run_app()
        self.assertFalse(app.exception)
        self.assertTrue(any("יהיה זמין בקרוב" in s.value for s in app.subheader))
        self.assertEqual(len(app.metric), 0)
        # Visitors never see developer setup or secret names.
        self.assertNotIn("INSTAGRAM_APP_SECRET", str(app))
        self.assertNotIn("developers.facebook.com", str(app))

    def test_configured_shows_sign_in_button(self):
        app = self.run_app({"INSTAGRAM_APP_ID": "id", "INSTAGRAM_APP_SECRET": "secret-value-123", "OAUTH_REDIRECT_URI": "https://app.example.com/"})
        self.assertFalse(app.exception)
        self.assertTrue(any("התחברות ל-Instagram" in s.value for s in app.subheader))
        self.assertNotIn("secret-value-123", str(app))

    def test_connected_session_is_analysed(self):
        app = self.run_app(before=lambda a: a.session_state.__setitem__("social", {"platform": "instagram", "token": "t", "name": "@creator", "videos": videos()}))
        self.assertFalse(app.exception)
        self.assertEqual([m.label for m in app.metric][:4], ["אינטראקציות", "לייקים", "תגובות", "צפיות"])
        self.assertTrue(any("מה האפליקציה מצאה" in s.value for s in app.subheader))

    def test_invalid_oauth_return_is_rejected(self):
        def before(app):
            app.query_params["code"] = "abc"
            app.query_params["state"] = "never-issued"
        app = self.run_app(before=before)
        self.assertFalse(app.exception)
        self.assertTrue(any("פג תוקף" in e.value for e in app.error))
        self.assertNotIn("social", app.session_state)


if __name__ == "__main__":
    unittest.main()
