

import pytest

import data.db as db
from tests.test_chug_duel_ui import service, open_page, button  # noqa: F401


@pytest.mark.parametrize('game', ['chug_duel', 'reaction', 'quiz', 'time'])
def test_duel_lobbies_share_setup_guide_and_empty_history(service, monkeypatch, game):
    state = dict(duels=[], available_points=20, outgoing=True, incoming=True,
                 open=True, test_mode=False, boost_ends_at=None)
    for name in ('quiz_status', 'reaction_status', 'time_status'):
        monkeypatch.setattr(db, name, lambda *_: state)
    app = open_page(selected=game)
    assert not app.exception
    html = [m.value for m in app.markdown]
    heading = next(i for i, value in enumerate(html) if 'class="duel-heading"' in value)
    setup = next(i for i, value in enumerate(html) if 'class="duel-setup-heading"' in value)
    guide = next(i for i, value in enumerate(html) if 'class="duel-guide"' in value)
    assert heading < setup < guide
    assert button(app, 'Challenge') and button(app, 'All games')
    assert [e.label for e in app.expander] == ['Rules & limits', 'Recent matches']
    assert any('No matches yet.' in value for value in html)
    # The action still receives the existing default opponent and stake/drink values.
    if game in {'reaction', 'quiz'}:
        assert app.radio(key=f'pill_radio_{game}_stake').value == (1 if game == 'reaction' else 3)


def test_result_card_html_outcomes_and_escaping():
    from minigames_ui import result_card_html
    won = result_card_html("won", "+3", "season points from <b>Ana</b>", note="Best of 3")
    assert "game-result-won" in won and ">You won<" in won and ">+3<" in won and "Best of 3" in won
    assert "<b>Ana</b>" not in won and "&lt;b&gt;Ana&lt;/b&gt;" in won
    assert ">You lost<" in result_card_html("lost", "−3", "x") and ">Draw<" in result_card_html("draw", "±0", "x")
    assert "game-result-note" not in result_card_html("draw", "±0", "x")
