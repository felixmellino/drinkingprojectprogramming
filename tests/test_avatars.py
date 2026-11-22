"""Profile pictures replace the initials placeholders (A11, revised 22 November 2026)."""
from datetime import timedelta
from io import BytesIO

from PIL import Image

import standings_ui
from activity_ui import feed_html
from core.activity import CHECKIN, ActivityEvent
from map_ui import territory_sheet_rows
from profile_picture_ui import avatar_html, avatar_src
from tests.test_scoring_v1 import START, season


def picture(size=512, colour="orange"):
    output = BytesIO()
    Image.new("RGB", (size, size), colour).save(output, "JPEG")
    return output.getvalue()


def test_avatar_is_a_small_jpeg_not_the_stored_picture():
    source = avatar_src(picture(512))
    assert source.startswith("data:image/jpeg;base64,")
    import base64
    with Image.open(BytesIO(base64.b64decode(source.split(",", 1)[1]))) as small:
        assert small.size == (128, 128)
    assert avatar_src(b"not a picture") is None and avatar_src(None) is None


def test_avatar_html_shows_the_picture_or_escaped_initials():
    source = avatar_src(picture())
    assert f'<img src="{source}"' in avatar_html("Mia", source, cls="x")
    fallback = avatar_html("<b>Mia</b>", None, cls="x")
    assert "<img" not in fallback and "&lt;" in fallback
    assert "<img" not in avatar_html("Mia", 'javascript:alert(1)" onerror="x', cls="x"), "only our JPEG data URLs"


def test_ranking_podium_and_rows_use_pictures():
    source = avatar_src(picture())
    rows = [("m1", 9), ("m2", 7), ("m3", 5), ("m4", 3)]
    names = {"m1": "Mia", "m2": "Leo", "m3": "Ben", "m4": "Nils"}
    podium = standings_ui._podium_place(1, "m1", 9, names, "m2", team_mode=False, picture=source)
    row = standings_ui._row(4, "m4", 3, rows, names, "m2", team_mode=False, picture=source)
    plain = standings_ui._row(4, "m4", 3, rows, names, "m2", team_mode=False)
    assert source in podium and source in row
    assert "<img" not in plain and ">NI<" in plain


def test_feed_checkins_use_pictures():
    source = avatar_src(picture())
    event = ActivityEvent(CHECKIN, START + timedelta(minutes=1), "e1", "m1", "m1", None, points=1,
                          drink_type="beer", size="small")
    html = feed_html([event], member_names={"m1": "Mia"}, team_names={}, territory_names={}, me_member="m2",
                     me_competitor="m2", season=season(), now=START + timedelta(minutes=5), pictures={"m1": source})
    assert source in html
    html = feed_html([event], member_names={"m1": "Mia"}, team_names={}, territory_names={}, me_member="m2",
                     me_competitor="m2", season=season(), now=START + timedelta(minutes=5))
    assert "<img" not in html and ">MI<" in html


def test_territory_list_rows_point_at_the_owners_picture():
    base = {"detail": "", "ranking": [], "needed": 2, "owner_points": 3, "my_points": 1}
    rows = territory_sheet_rows([
        {**base, "id": "a", "name": "A", "status": "theirs", "owner": "Leo", "owner_id": "m2"},
        {**base, "id": "b", "name": "B", "status": "free", "owner": None, "owner_id": None},
    ])
    photos = {row["id"]: row["photo"] for row in rows}
    assert photos == {"a": "m2", "b": None}
