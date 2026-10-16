"""Serialize supported workspace operations and bound UI subprocess lifetimes."""
from contextlib import contextmanager
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

from filelock import FileLock, Timeout

from app_security import redact_secrets

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"


class WorkspaceBusy(RuntimeError):
    pass


@contextmanager
def workspace_lock(artifacts=ARTIFACTS, *, name="workspace"):
    artifacts = Path(artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    lock = FileLock(artifacts / f"{name}.lock", timeout=0, mode=0o600)
    try:
        lock.acquire()
    except Timeout:
        raise WorkspaceBusy("פעולה אחרת כבר משתמשת בתוצרים. המתינו לסיומה ונסו שוב.") from None
    try:
        yield
    finally:
        lock.release()


def _stop_process_group(process):
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass
    process.wait()


def run_ui_flow(artifacts=ARTIFACTS, *, timeout=1800, secret_values=None):
    """One UI launch at a time; the Flow itself owns the shared workspace lock."""
    artifacts = Path(artifacts)
    with workspace_lock(artifacts, name="ui_run"):
        # Raw third-party diagnostics stay in a private temporary file, not artifacts.
        with tempfile.TemporaryFile() as raw:
            process = subprocess.Popen(
                [sys.executable, "-u", str(artifacts.parent / "project_flow.py")],
                cwd=artifacts.parent, stdin=subprocess.DEVNULL, stdout=raw,
                stderr=subprocess.STDOUT, start_new_session=(os.name == "posix"),
            )
            try:
                result = process.wait(timeout=timeout)
            except BaseException:
                _stop_process_group(process)
                raise
            finally:
                raw.seek(0, os.SEEK_END)
                size = raw.tell()
                raw.seek(max(0, size - 1024 * 1024))
                data = raw.read(1024 * 1024)
                if size > 1024 * 1024:
                    data = data.partition(b"\n")[2]
                safe_log = redact_secrets(data.decode("utf-8", errors="replace"), secret_values)
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=artifacts, delete=False) as log:
                    temporary = Path(log.name)
                    log.write(safe_log)
                try:
                    temporary.replace(artifacts / "latest_ui_run.log")
                finally:
                    temporary.unlink(missing_ok=True)
            return result
