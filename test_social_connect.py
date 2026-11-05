import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx
import pandas as pd

import social_connect as sc

CONFIG = sc.OAuthConfig("client-id", "client-secret-value", "https://app.example.com/")


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


class ConfigAndStateTests(unittest.TestCase):
    def test_not_configured_without_all_values(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(sc.get_config("instagram", {}))
            self.assertIsNone(sc.get_config("tiktok", {"TIKTOK_CLIENT_KEY": "k", "OAUTH_REDIRECT_URI": "https://a.example"}))

    def test_configured_and_redirect_validation(self):
        values = {"INSTAGRAM_APP_ID": "i", "INSTAGRAM_APP_SECRET": "s", "OAUTH_REDIRECT_URI": "https://a.example/"}
        self.assertEqual(sc.get_config("instagram", values).client_id, "i")
        with self.assertRaises(sc.SocialError):
            sc.get_config("instagram", {**values, "OAUTH_REDIRECT_URI": "http://evil.example/"})
        self.assertIsNotNone(sc.get_config("instagram", {**values, "OAUTH_REDIRECT_URI": "http://localhost:8501/"}))

    def test_state_is_single_use_and_platform_bound(self):
        state = sc.new_state("tiktok")
        self.assertTrue(sc.is_pending(state))
        self.assertEqual(sc.consume_state(state), "tiktok")
        self.assertIsNone(sc.consume_state(state))
        self.assertIsNone(sc.consume_state("never-issued"))

    def test_state_expires(self):
        state = sc.new_state("instagram")
        with patch("social_connect.time.time", return_value=__import__("time").time() + sc.STATE_TTL + 5):
            self.assertIsNone(sc.consume_state(state))

    def test_auth_urls_carry_state_and_scopes(self):
        instagram = parse_qs(urlsplit(sc.auth_url("instagram", CONFIG, "abc")).query)
        self.assertEqual(instagram["state"], ["abc"])
        self.assertEqual(instagram["scope"], ["instagram_business_basic"])
        self.assertNotIn("client_secret", sc.auth_url("instagram", CONFIG, "abc"))
        tiktok = parse_qs(urlsplit(sc.auth_url("tiktok", CONFIG, "abc")).query)
        self.assertEqual(tiktok["client_key"], ["client-id"])
        self.assertIn("video.list", tiktok["scope"][0])
        self.assertNotIn("client-secret-value", sc.auth_url("tiktok", CONFIG, "abc"))


class ExchangeAndFetchTests(unittest.TestCase):
    def test_exchange_instagram_and_tiktok(self):
        seen = {}

        def handler(request):
            seen[request.url.host] = request.content.decode()
            return httpx.Response(200, json={"access_token": "tok-123", "user_id": 1})

        with client_for(handler) as client:
            self.assertEqual(sc.exchange_code("instagram", CONFIG, "the-code", client), "tok-123")
            self.assertEqual(sc.exchange_code("tiktok", CONFIG, "the-code", client), "tok-123")
        self.assertIn("code=the-code", seen["api.instagram.com"])
        self.assertIn("client_key=client-id", seen["open.tiktokapis.com"])

    def test_exchange_errors_hide_secrets(self):
        with client_for(lambda r: httpx.Response(400, json={"error": "client-secret-value leaked?"})) as client:
            with self.assertRaises(sc.SocialError) as caught:
                sc.exchange_code("instagram", CONFIG, "x", client)
        self.assertNotIn("client-secret-value", str(caught.exception))
        with client_for(lambda r: httpx.Response(200, json={})) as client:
            with self.assertRaises(sc.SocialError):
                sc.exchange_code("tiktok", CONFIG, "x", client)

        def boom(request):
            raise httpx.ConnectError("down")

        with client_for(boom) as client:
            with self.assertRaises(sc.SocialError):
                sc.exchange_code("tiktok", CONFIG, "x", client)

    def test_fetch_instagram_keeps_only_videos(self):
        def handler(request):
            if request.url.path.endswith("/me"):
                return httpx.Response(200, json={"username": "creator"})
            return httpx.Response(200, json={"data": [
                {"id": "1", "caption": "First reel\nmore", "media_type": "VIDEO", "permalink": "https://i/1", "timestamp": "2026-10-01T10:30:00+0000", "like_count": 40, "comments_count": 5},
                {"id": "2", "caption": "Photo", "media_type": "IMAGE", "permalink": "https://i/2", "timestamp": "2026-10-02T10:30:00+0000", "like_count": 9, "comments_count": 1}]})

        with client_for(handler) as client:
            name, videos = sc.fetch_videos("instagram", "tok", client)
        self.assertEqual(name, "@creator")
        self.assertEqual(list(videos.id), ["1"])
        self.assertEqual(videos.iloc[0].title, "First reel")

    def test_fetch_tiktok_normalises_counts(self):
        def handler(request):
            self.assertEqual(request.headers["Authorization"], "Bearer tok")
            if "user/info" in request.url.path:
                return httpx.Response(200, json={"data": {"user": {"display_name": "Dana"}}})
            return httpx.Response(200, json={"data": {"videos": [
                {"id": "a", "title": "t1", "create_time": 1761993000, "share_url": "https://t/a", "view_count": 1000, "like_count": 90, "comment_count": 10, "share_count": 5},
                {"id": "b", "title": "t2", "create_time": 1762079400, "share_url": "https://t/b", "view_count": 300, "like_count": 20, "comment_count": 1, "share_count": 0}]}})

        with client_for(handler) as client:
            name, videos = sc.fetch_videos("tiktok", "tok", client)
        self.assertEqual(name, "Dana")
        self.assertEqual(len(videos), 2)
        self.assertEqual(sc.interactions(videos.iloc[1]), 105.0)

    def test_analyze_video_is_descriptive(self):
        videos = pd.DataFrame({"id": list("abcde"), "title": "", "created": pd.date_range("2026-10-01 09:00", periods=5, freq="D", tz="UTC"),
                               "views": 0, "likes": [10, 20, 30, 40, 50], "comments": 0, "shares": 0, "url": ""})
        reference = pd.DataFrame({"total_interactions": [100, 120, 140]})
        result = sc.analyze_video(videos.iloc[4], videos, reference)
        self.assertEqual((result["rank"], result["count"]), (1, 5))
        self.assertAlmostEqual(result["vs_account_median"], 50 / 30 - 1)
        self.assertEqual(result["best_hour"], 9)


if __name__ == "__main__":
    unittest.main()
