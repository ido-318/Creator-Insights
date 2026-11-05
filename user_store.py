"""Per-user encrypted SQLite storage.

- Users are separated by an opaque key: HMAC(master key, platform + account id). No account id, name,
  platform or caption is stored in clear text.
- Every sensitive value is encrypted with AES-256-GCM using a key derived for that one user, and the
  ciphertext is bound to the owner (associated data), so a row can't be read as another user's.
- The master key comes only from the environment or secrets. It is never generated or stored next
  to the database. Without it, storage is off and the app works session-only.
"""
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_NAME = "DATA_ENCRYPTION_KEY"
PATH_NAME = "CREATOR_INSIGHTS_DB"
DEFAULT_PATH = Path(__file__).resolve().parent / ".runtime" / "creator_insights.db"
KEEP_SNAPSHOTS = 30


class StorageError(RuntimeError):
    """A safe message. Never includes keys, tokens or stored content."""


def generate_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _master(values):
    raw = str((values or {}).get(KEY_NAME, os.environ.get(KEY_NAME, ""))).strip()
    if not raw:
        return None
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (ValueError, TypeError):
        raise StorageError("The storage key is not valid base64.") from None
    if len(key) != 32:
        raise StorageError("The storage key must be 32 random bytes (base64).")
    return key


def _derive(master, info):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(master)


class UserStore:
    def __init__(self, path, master):
        self.path = Path(path)
        self._master = master
        self._id_key = _derive(master, b"creator-insights/id")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT, 0o600)
            os.close(fd)
        os.chmod(self.path, 0o600)
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_key TEXT PRIMARY KEY,
                    nonce BLOB NOT NULL,
                    profile BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_key TEXT NOT NULL REFERENCES users(user_key) ON DELETE CASCADE,
                    nonce BLOB NOT NULL,
                    payload BLOB NOT NULL
                );
                CREATE INDEX IF NOT EXISTS snapshots_user ON snapshots(user_key, id);
            """)

    @classmethod
    def from_config(cls, values=None):
        """None when no key is configured (storage off). Raises StorageError for a bad key."""
        master = _master(values)
        if master is None:
            return None
        path = str((values or {}).get(PATH_NAME, os.environ.get(PATH_NAME, ""))).strip() or DEFAULT_PATH
        try:
            return cls(path, master)
        except (OSError, sqlite3.Error):
            raise StorageError("The storage file could not be opened.") from None

    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA foreign_keys = ON")
        return _Closing(db)

    def user_key(self, platform, account_id):
        message = f"{platform}:{account_id}".encode()
        return hmac.new(self._id_key, message, hashlib.sha256).hexdigest()

    def _cipher(self, user_key):
        return AESGCM(_derive(self._master, b"creator-insights/user/" + user_key.encode()))

    def _seal(self, user_key, data, purpose):
        nonce = os.urandom(12)
        aad = f"{user_key}|{purpose}".encode()
        return nonce, self._cipher(user_key).encrypt(nonce, json.dumps(data, ensure_ascii=False).encode(), aad)

    def _open(self, user_key, nonce, blob, purpose):
        aad = f"{user_key}|{purpose}".encode()
        try:
            return json.loads(self._cipher(user_key).decrypt(nonce, blob, aad))
        except (InvalidTag, ValueError):
            raise StorageError("Stored data could not be verified for this user.") from None

    def save_snapshot(self, user_key, platform, name, videos):
        """Remember a user's latest videos. Returns the snapshot id."""
        profile = {"platform": platform, "name": name}
        records = json.loads(videos.assign(created=videos["created"].astype(str)).to_json(orient="records", force_ascii=False))
        payload = {"platform": platform, "taken_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "videos": records}
        pn, pb = self._seal(user_key, profile, "profile")
        sn, sb = self._seal(user_key, payload, "snapshot")
        with self._db() as db:
            db.execute("INSERT INTO users(user_key, nonce, profile) VALUES (?, ?, ?) ON CONFLICT(user_key) DO UPDATE SET nonce = excluded.nonce, profile = excluded.profile", (user_key, pn, pb))
            cursor = db.execute("INSERT INTO snapshots(user_key, nonce, payload) VALUES (?, ?, ?)", (user_key, sn, sb))
            db.execute("DELETE FROM snapshots WHERE user_key = ? AND id NOT IN (SELECT id FROM snapshots WHERE user_key = ? ORDER BY id DESC LIMIT ?)", (user_key, user_key, KEEP_SNAPSHOTS))
            return cursor.lastrowid

    def snapshots(self, user_key, limit=10):
        """This user's snapshots, newest first. Never returns another user's rows."""
        with self._db() as db:
            rows = db.execute("SELECT nonce, payload FROM snapshots WHERE user_key = ? ORDER BY id DESC LIMIT ?", (user_key, limit)).fetchall()
        return [self._open(user_key, nonce, blob, "snapshot") for nonce, blob in rows]

    def delete_user(self, user_key):
        """Erase everything stored for one user. Returns how many snapshots were removed."""
        with self._db() as db:
            count = db.execute("SELECT COUNT(*) FROM snapshots WHERE user_key = ?", (user_key,)).fetchone()[0]
            db.execute("DELETE FROM snapshots WHERE user_key = ?", (user_key,))
            db.execute("DELETE FROM users WHERE user_key = ?", (user_key,))
        return count


class _Closing:
    """sqlite3 connection that commits on success and always closes."""

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, kind, value, trace):
        try:
            self.db.commit() if kind is None else self.db.rollback()
        finally:
            self.db.close()
