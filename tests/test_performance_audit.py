"""Performance boundaries: no auth caching, no original-image loss or client race."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from time import sleep
from unittest.mock import Mock

from PIL import Image
import pytest

import data.db as db
from core.checkin_photo import photo_thumbnail
from scripts.audit_app_performance import requests_trace, route


def jpeg(size):
    output=BytesIO()
    Image.effect_noise(size,75).convert('RGB').save(output,'JPEG',quality=90)
    return output.getvalue()


def test_gallery_thumbnail_is_smaller_and_leaves_original_intact():
    original=jpeg((1200,1600))
    small=photo_thumbnail(original)
    assert len(small)<len(original)/3
    with Image.open(BytesIO(small)) as image:
        assert image.size==(360,480) and image.format=='JPEG'
        assert not image.getexif()
    with Image.open(BytesIO(original)) as image:
        assert image.size==(1200,1600)
    assert photo_thumbnail(jpeg((32,24))) is not None
    tiny=jpeg((32,24))
    assert photo_thumbnail(tiny) is tiny


@pytest.mark.parametrize('raw',[None,b'',b'not an image',b'\xff\xd8\xff'])
def test_invalid_thumbnail_does_not_crash_the_gallery(raw):
    assert photo_thumbnail(raw) is None


def test_parallel_cold_client_initialization_constructs_one_pool(monkeypatch):
    client=object()
    def create():
        sleep(.02)
        return client
    factory=Mock(side_effect=create)
    monkeypatch.setattr(db,'_client',None)
    monkeypatch.setattr(db,'_create_client',factory)
    with ThreadPoolExecutor(max_workers=8) as pool:
        clients=list(pool.map(lambda _:db.get_client(),range(24)))
    assert all(item is client for item in clients)
    factory.assert_called_once()


def test_failed_client_initialization_is_not_cached(monkeypatch):
    client=object()
    monkeypatch.setattr(db,'_client',None)
    factory=Mock(side_effect=[RuntimeError('offline'),client])
    monkeypatch.setattr(db,'_create_client',factory)
    with pytest.raises(RuntimeError): db.get_client()
    assert db.get_client() is client and factory.call_count==2


def test_lobby_cards_load_in_three_rounds_not_one_chain_per_card(monkeypatch):
    """Round 1 overlaps every card's scores with the picture permission check;
    round 2 asks for all leaders' names at once; round 3 is one picture batch."""
    from threading import Barrier
    from types import SimpleNamespace
    from tests.test_scoring_v1 import entry,season
    import lobby_ui
    barrier=Barrier(3,timeout=2)  # two cards' entry reads + the permission check
    def entries(_):
        barrier.wait()
        return [entry('one','me','beer','small',0)]
    def access(_):
        barrier.wait()
        return ['relationships']
    name_requests,picture_requests=[],[]
    def names(pairs):
        name_requests.append(list(pairs))
        return {pair:{'player_id':'player-'+pair[1],'display_name':'Mia'} for pair in pairs}
    def pictures(viewer,owners,access=None):
        picture_requests.append((viewer,owners,access))
        return {'player-a':b'photo'}
    monkeypatch.setattr(db,'list_drink_entries',entries)
    monkeypatch.setattr(db,'list_season_transfers',lambda _: [])
    monkeypatch.setattr(db,'list_membership_names',names)
    monkeypatch.setattr(lobby_ui,'picture_access',access)
    monkeypatch.setattr(lobby_ui,'load_pictures',pictures)
    cards=[(SimpleNamespace(id='a',game_mode='individual'),season(),'active'),
           (SimpleNamespace(id='b',game_mode='individual'),season(),'past')]
    result=lobby_ui.load_summaries('player',cards)
    assert [r[1:] for r in result]==[(True,'Mia',b'photo'),(True,'Mia',None)]
    assert name_requests==[[('me','a'),('me','b')]]
    assert picture_requests==[('player',['player-a'],['relationships'])], 'only the active card shows a picture'


def test_lobby_name_failure_marks_only_individual_leader_cards_unavailable(monkeypatch):
    from types import SimpleNamespace
    from tests.test_scoring_v1 import entry,season
    import lobby_ui
    monkeypatch.setattr(db,'list_drink_entries',lambda _: [entry('one','me','beer','small',0)])
    monkeypatch.setattr(db,'list_season_transfers',lambda _: [])
    monkeypatch.setattr(db,'list_membership_names',Mock(side_effect=RuntimeError('offline')))
    monkeypatch.setattr(lobby_ui,'picture_access',lambda _: None)
    load_pictures=Mock()
    monkeypatch.setattr(lobby_ui,'load_pictures',load_pictures)
    cards=[(SimpleNamespace(id='a',game_mode='individual'),season(),'active'),
           (SimpleNamespace(id='c',game_mode='individual'),None,'setup')]
    result=lobby_ui.load_summaries('player',cards)
    assert [r[1:] for r in result]==[(False,None,None),(True,None,None)]
    load_pictures.assert_not_called()


@pytest.mark.parametrize('multiplier,expected',[(1.25,'×1.25'),(1.5,'×1.5'),(None,'×1.5')])
def test_photo_caption_uses_saved_historical_focus_tier(monkeypatch,multiplier,expected):
    from dataclasses import replace
    import streamlit as st
    from photo_history_ui import photo_metadata
    from tests.test_scoring_v1 import entry,season
    model=replace(entry('one','me','beer','small',0),focus_attempt_id='saved',focus_multiplier=multiplier)
    caption=Mock()
    monkeypatch.setattr(st,'caption',caption)
    monkeypatch.setattr(st,'markdown',Mock())
    photo_metadata(dict(entry=model,season=season(),location='matched',captured_at=None,
                        submitted_at=model.submitted_at.isoformat(),timezone_name='UTC'))
    assert expected in caption.call_args.args[0]


def test_audit_never_records_ids_query_values_headers_or_response_content():
    import httpx
    transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'secret':'not logged'}))
    original=httpx.Client.send
    with httpx.Client(transport=transport) as client:
        with requests_trace() as trace:
            client.get('https://project.supabase.co/storage/v1/object/private/user-id/photo.jpg?token=secret',
                       headers={'Authorization':'Bearer secret'})
    assert httpx.Client.send is original
    assert trace[0][0]=='Supabase Storage object' and trace[0][1]==200
    assert 'secret' not in str(trace) and 'user-id' not in str(trace)
    assert route(httpx.URL('https://project.supabase.co/rest/v1/rpc/accept_scoring_checkin?actor=id'))=='Supabase RPC: accept_scoring_checkin'


def test_batched_history_keeps_pagination_and_bounds_each_id_filter(monkeypatch):
    from types import SimpleNamespace

    client = Mock()
    query = client.table.return_value.select.return_value
    selected = query.in_.return_value
    ordered = selected.order.return_value.order.return_value
    paged = ordered.range.return_value
    paged.execute.side_effect = [SimpleNamespace(data=[{"id": i} for i in range(500)]),
                                 SimpleNamespace(data=[{"id": 500}]),
                                 SimpleNamespace(data=[{"id": 501}])]
    monkeypatch.setattr(db, "get_client", lambda: client)
    ids = [f"season-{i}" for i in range(51)]
    rows = db._rows_for_ids("drink_entries", "season_id", ids + [ids[0]], "submitted_at", "id")

    assert [row["id"] for row in rows] == list(range(502))
    assert [call.args[1] for call in query.in_.call_args_list] == [ids[:50], ids[:50], ids[50:]]
    assert [call.args for call in ordered.range.call_args_list] == [(0, 499), (500, 999), (0, 499)]


def test_recent_checkin_query_includes_a_capture_older_than_the_cooldown(monkeypatch):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    client = Mock()
    account = client.table.return_value.select.return_value.eq.return_value
    recent_or_saved = account.or_.return_value
    recent_or_saved.order.return_value.order.return_value.range.return_value.execute.return_value = (
        SimpleNamespace(data=[])
    )
    monkeypatch.setattr(db, "get_client", lambda: client)
    since = datetime(2026, 11, 21, 18, tzinfo=timezone.utc)
    assert db.list_drink_entries_for_membership("member", since=since, capture_id="previous") == []
    client.table.return_value.select.return_value.eq.assert_called_once_with("membership_id", "member")
    account.or_.assert_called_once_with(f"submitted_at.gte.{since.isoformat()},id.eq.previous")
