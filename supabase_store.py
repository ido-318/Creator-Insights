"""Optional, server-only Supabase Data API persistence; offline by default."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from urllib.parse import urlsplit

import httpx
import pandas as pd
from dotenv import load_dotenv

from dashboard_data import ARTIFACTS, COLUMNS, ROOT, flow_history, load_local, validate_frame


class StoreError(RuntimeError):
    """Safe user-facing error that never includes credentials or response bodies."""


@dataclass(frozen=True)
class StoreConfig:
    url: str
    key: str = field(repr=False)


def get_config(secrets=None):
    load_dotenv(ROOT / ".env")
    values = secrets or {}
    url = str(values.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))).rstrip("/")
    key = str(values.get("SUPABASE_SECRET_KEY", os.getenv("SUPABASE_SECRET_KEY", "")))
    key = key or str(values.get("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")))
    if not url and not key:
        return None
    parts = urlsplit(url)
    if not key or parts.scheme != "https" or not parts.hostname or parts.path or parts.query or parts.fragment or parts.username or parts.password:
        raise StoreError("יש להגדיר כתובת SUPABASE_URL תקינה ב־HTTPS ומפתח שרת ב־SUPABASE_SECRET_KEY.")
    if key.startswith("sb_publishable_"):
        raise StoreError("לסנכרון נדרש מפתח שרת סודי, ולא מפתח publishable.")
    return StoreConfig(url, key)


class SupabaseStore:
    def __init__(self, config):
        self.config = config

    def _request(self, method, route, **kwargs):
        headers = {"apikey": self.config.key, "Content-Type": "application/json"}
        if not self.config.key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.config.key}"
        try:
            response = httpx.request(method, f"{self.config.url}/rest/v1/{route}", headers=headers, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            hint = "בדקו את מפתח השרת והרשאות המסד." if code in (401, 403) else "בדקו שהמיגרציה הותקנה ושהפרויקט פעיל."
            raise StoreError(f"Supabase החזיר שגיאה {code}. {hint}") from None
        except (httpx.RequestError, ValueError):
            raise StoreError("לא ניתן לקבל תשובה תקינה מ־Supabase. בדקו את החיבור והכתובת.") from None

    def check(self):
        self._request("GET", "creator_snapshots", params={"select": "id", "limit": "1"})

    def sync(self, snapshot):
        return self._request("POST", "rpc/save_creator_snapshot", json={"payload": snapshot})

    def latest(self):
        rows = self._request("GET", "creator_snapshots", params={
            "select": "id,captured_at,row_count,posts,training,reports", "order": "captured_at.desc,id.desc", "limit": "1",
        })
        if not rows:
            raise StoreError("עדיין אין תמונת מצב בענן. סנכרנו תחילה את התוצרים המקומיים.")
        row = rows[0]
        try:
            df = validate_frame(pd.DataFrame(row["posts"]))
            if len(df) != row["row_count"]:
                raise ValueError("row count mismatch")
            return df, row["training"], row["reports"], row["captured_at"]
        except (KeyError, TypeError, ValueError):
            raise StoreError("תמונת המצב בענן אינה תואמת למבנה הנתונים הנדרש.") from None


def build_snapshot(artifacts=ARTIFACTS):
    """Capture a validated dataset. Training/report files are stored as-is, not rerun."""
    from handoff_integrity import verify_handoff
    from evaluation_tools import review_model_results

    history = flow_history(artifacts)
    if history and history[0].get("status") != "completed":
        raise StoreError("הריצה האחרונה לא הושלמה. יש להשלים ריצה תקינה לפני סנכרון התוצרים.")
    verify_handoff(artifacts)
    review_model_results(artifacts, write_report=False)
    df, training, reports = load_local(artifacts)
    if training is None:
        raise StoreError("אין סיכום אימון לסנכרון. השלימו את תהליך המידול.")
    content = {"posts": json.loads(df[COLUMNS].to_json(orient="records")), "training": training, "reports": reports}
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    return {
        "id": hashlib.sha256(encoded).hexdigest(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(df),
        **content,
    }

