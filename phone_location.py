"""The "Use my location" button: reads the phone's GPS in the browser (R-L01).

Thin Streamlit glue around components/phone_location/index.html. Checking
what the browser sent back lives in core/location.py's parse_phone_reading.
"""

from pathlib import Path

from streamlit.components.v1 import declare_component

_phone_location = declare_component(
    "phone_location", path=str(Path(__file__).parent / "components" / "phone_location")
)


def phone_location_button(key: str):
    """Show the button. Returns whatever the browser last sent for this key
    (a dict with lat/lng/accuracy_m or an error), or None before any click."""
    return _phone_location(key=key, default=None)
