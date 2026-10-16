"""Native Streamlit themes. Saved configuration applies to this local workspace."""
from copy import deepcopy
from pathlib import Path
import re
import tempfile
import tomllib

import tomli_w

CONFIG_PATH = Path(__file__).resolve().parent / ".streamlit/config.toml"
PALETTES = {
    "אוקיינוס": ("#087F8C", "#4263EB"),
    "איריס": ("#6546C7", "#087F8C"),
    "שקיעה": ("#B45309", "#B33F62"),
}


def read_config(path=CONFIG_PATH):
    return tomllib.loads(path.read_text(encoding="utf-8"))


def contrast(first, second):
    def luminance(color):
        rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        rgb = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
        return sum(v * weight for v, weight in zip(rgb, (.2126, .7152, .0722)))
    a, b = sorted((luminance(first), luminance(second)))
    return (b + .05) / (a + .05)


def build_theme(config, primary, secondary, dark=False):
    for color in (primary, secondary):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("יש לבחור צבע תקין בפורמט HEX.")
    if contrast(primary, "#FFFFFF") < 4.5:
        raise ValueError("הצבע הראשי בהיר מדי לטקסט לבן. בחרו גוון כהה יותר.")
    result = deepcopy(config)
    theme = result.setdefault("theme", {})
    theme.update({
        "base": "dark" if dark else "light",
        "primaryColor": primary,
        "linkColor": "#8EDDE5" if dark else primary,
        "backgroundColor": "#101925" if dark else "#FBFCFE",
        "secondaryBackgroundColor": "#1B293B" if dark else "#F0F4F8",
        "textColor": "#EDF3FC" if dark else "#172B4D",
        "borderColor": "#304157" if dark else "#DFE6EE",
        "chartCategoricalColors": [primary, secondary, "#D19134", "#A181CD"],
        "sidebar": {
            "backgroundColor": "#152131" if dark else "#F0F4F8",
            "secondaryBackgroundColor": "#1B293B" if dark else "#FFFFFF",
        },
    })
    return result


def export_theme(config):
    """A theme download must never export server/auth/connection configuration."""
    return tomli_w.dumps({"theme": config["theme"]})


def save_theme(config, path=CONFIG_PATH):
    """Atomic replacement; never change global process configuration or secrets."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as file:
        file.write(tomli_w.dumps(config).encode("utf-8"))
        temporary = Path(file.name)
    temporary.replace(path)

