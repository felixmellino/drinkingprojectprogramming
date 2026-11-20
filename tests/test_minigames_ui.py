

def test_result_card_html_outcomes_and_escaping():
    from minigames_ui import result_card_html
    won = result_card_html("won", "+3", "season points from <b>Ana</b>", note="Best of 3")
    assert "game-result-won" in won and ">You won<" in won and ">+3<" in won and "Best of 3" in won
    assert "<b>Ana</b>" not in won and "&lt;b&gt;Ana&lt;/b&gt;" in won
    assert ">You lost<" in result_card_html("lost", "−3", "x") and ">Draw<" in result_card_html("draw", "±0", "x")
    assert "game-result-note" not in result_card_html("draw", "±0", "x")
