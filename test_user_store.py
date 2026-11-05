import os
import sqlite3
import stat
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import pandas as pd

import user_store as us


def videos(title):
    return pd.DataFrame({"id": ["1"], "title": [title], "created": pd.to_datetime(["2026-10-01T09:00:00Z"]),
                         "views": [10], "likes": [5], "comments": [1], "shares": [0], "url": ["https://example.com/secret-url"]})


class UserStoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "db.sqlite"
        self.key = us.generate_key()
        self.store = us.UserStore.from_config({us.KEY_NAME: self.key, us.PATH_NAME: str(self.path)})

    def test_disabled_without_key_and_rejects_bad_keys(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(us.UserStore.from_config({}))
        for bad in ("not base64 !!", "c2hvcnQ="):
            with self.assertRaises(us.StorageError):
                us.UserStore.from_config({us.KEY_NAME: bad, us.PATH_NAME: str(self.path)})

    def test_round_trip_and_history_limit(self):
        user = self.store.user_key("instagram", "12345")
        for i in range(us.KEEP_SNAPSHOTS + 5):
            self.store.save_snapshot(user, "instagram", "@dana", videos(f"caption {i}"))
        history = self.store.snapshots(user, limit=100)
        self.assertEqual(len(history), us.KEEP_SNAPSHOTS)
        self.assertEqual(history[0]["videos"][0]["title"], f"caption {us.KEEP_SNAPSHOTS + 4}")

    def test_users_never_see_each_other(self):
        a, b = self.store.user_key("instagram", "1"), self.store.user_key("instagram", "2")
        self.assertNotEqual(a, b)
        self.assertNotEqual(self.store.user_key("tiktok", "1"), a)
        self.store.save_snapshot(a, "instagram", "@alice", videos("alice private caption"))
        self.store.save_snapshot(b, "instagram", "@bob", videos("bob private caption"))
        self.assertEqual([s["videos"][0]["title"] for s in self.store.snapshots(a)], ["alice private caption"])
        self.assertEqual([s["videos"][0]["title"] for s in self.store.snapshots(b)], ["bob private caption"])

    def test_database_file_holds_no_plain_text(self):
        user = self.store.user_key("tiktok", "open-id-777")
        self.store.save_snapshot(user, "tiktok", "@secretname", videos("very secret caption"))
        raw = self.path.read_bytes()
        for needle in (b"secretname", b"secret caption", b"open-id-777", b"tiktok", b"secret-url"):
            self.assertNotIn(needle, raw)
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)

    def test_swapped_rows_fail_verification(self):
        a, b = self.store.user_key("instagram", "1"), self.store.user_key("instagram", "2")
        self.store.save_snapshot(a, "instagram", "@alice", videos("alice"))
        self.store.save_snapshot(b, "instagram", "@bob", videos("bob"))
        with sqlite3.connect(self.path) as db:  # an attacker with file access re-labels Bob's row as Alice's
            db.execute("UPDATE snapshots SET user_key = ? WHERE user_key = ?", (a, b))
        with self.assertRaises(us.StorageError):
            self.store.snapshots(a)

    def test_wrong_master_key_cannot_read(self):
        user = self.store.user_key("instagram", "1")
        self.store.save_snapshot(user, "instagram", "@alice", videos("alice"))
        other = us.UserStore.from_config({us.KEY_NAME: us.generate_key(), us.PATH_NAME: str(self.path)})
        with self.assertRaises(us.StorageError):
            other.snapshots(user)

    def test_delete_user_erases_everything(self):
        a, b = self.store.user_key("instagram", "1"), self.store.user_key("instagram", "2")
        self.store.save_snapshot(a, "instagram", "@alice", videos("alice"))
        self.store.save_snapshot(a, "instagram", "@alice", videos("alice 2"))
        self.store.save_snapshot(b, "instagram", "@bob", videos("bob"))
        self.assertEqual(self.store.delete_user(a), 2)
        self.assertEqual(self.store.snapshots(a), [])
        self.assertEqual(len(self.store.snapshots(b)), 1)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users WHERE user_key = ?", (a,)).fetchone()[0], 0)

    def test_sql_injection_attempt_is_inert(self):
        self.store.save_snapshot(self.store.user_key("instagram", "1"), "instagram", "@alice", videos("alice"))
        self.assertEqual(self.store.snapshots("x' OR '1'='1"), [])


if __name__ == "__main__":
    import unittest.mock
    unittest.main()
