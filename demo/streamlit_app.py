"""Public read-only entrypoint for hosted demos (for example Streamlit Community Cloud).

Deploy with this file as the main file. It enables public demo mode, which shows the
saved artifacts only and disables agent runs, cloud sync and settings writes.
"""
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent.parent
os.environ["CREATOR_INSIGHTS_PUBLIC_DEMO"] = "1"
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
