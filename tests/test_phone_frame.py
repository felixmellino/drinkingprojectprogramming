"""The presenter phone frame (static/phone.html) shows the real app at phone size."""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "static" / "phone.html").read_text(encoding="utf-8")


def test_streamlit_serves_only_the_static_folder():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert config["server"]["enableStaticServing"] is True
    assert sorted(path.name for path in (ROOT / "static").iterdir()) == ["phone.html"], \
        "everything in static/ is public; keep only the frame there"


def test_frame_embeds_the_same_site_app_with_camera_and_location():
    frame = re.search(r'<iframe[^>]*id="app"[^>]*>', PAGE).group(0)
    assert 'src="../../"' in frame, "relative: works locally and on Streamlit Cloud (/~/+/)"
    allow = re.search(r'allow="([^"]+)"', frame).group(1)
    assert {"camera", "geolocation"} <= {item.strip() for item in allow.split(";")}


def test_screen_is_phone_sized():
    assert "--phone-w: 393px" in PAGE and "--phone-h: 852px" in PAGE


def test_nothing_is_loaded_from_other_sites():
    assert not re.search(r'(src|href)="https?://', PAGE), "no CDN, fonts or tracking"
    assert "<script src" not in PAGE


def test_reload_button_exists_for_a_stuck_screen():
    assert 'id="reload"' in PAGE and "location.reload()" in PAGE
