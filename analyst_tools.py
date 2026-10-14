
import json

from crewai.tools import tool

from clean_data import clean_dataset


@tool("Clean Facebook Dataset")
def clean_facebook_dataset() -> str:
    """Clean the Facebook dataset and return its saved path and row counts."""
    result = clean_dataset()
    return json.dumps(result, ensure_ascii=False)