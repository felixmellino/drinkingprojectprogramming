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
    assert 'const APP_URL = "../../";' in PAGE, "relative: works locally and on Streamlit Cloud (/~/+/)"
    assert "app.src = APP_URL + appPath(location.search);" in PAGE
    allow = re.search(r'allow="([^"]+)"', frame).group(1)
    assert {"camera", "geolocation"} <= {item.strip() for item in allow.split(";")}


def test_screen_is_phone_sized():
    assert "--phone-w: 393px" in PAGE and "--phone-h: 852px" in PAGE


def test_nothing_is_loaded_from_other_sites():
    assert not re.search(r'(src|href)="https?://', PAGE), "no CDN, fonts or tracking"
    assert "<script src" not in PAGE


def test_reload_button_exists_for_a_stuck_screen():
    assert 'id="reload"' in PAGE and "location.reload()" in PAGE


def test_laptops_are_sent_to_the_frame_by_the_theme_reader():
    """tests/phone_frame.cjs checks the decision itself; here: it is wired in and guarded."""
    component = (ROOT / "components" / "theme_switch" / "index.html").read_text(encoding="utf-8")
    reader = component[component.index("} else {"):component.index("const FRAME")]
    assert "openPhoneFrame();" in reader, "runs in the invisible reader on the first page of a visit"
    assert '"(hover: hover) and (pointer: fine)"' in component and "innerWidth >= 700" in component
    assert 'method: "HEAD"' in component and "response.ok" in component, "only when the frame page exists"
    assert 'query.has("full")' in component, "?full keeps the wide view"
