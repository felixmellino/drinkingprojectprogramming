"""Assert the tap-to-explain flow, including successful dialog dismissal."""
def assert_blocked(page, label, *words, inline=False):
    button = next(b for b in page.button if b.label == label)
    assert not button.disabled
    button.click().run()
    assert not page.exception
    messages = page.warning if inline else page.error
    text = " ".join(item.value for item in messages).lower()
    assert text
    for word in words:
        assert word.lower() in text, text
    if not inline:
        next(b for b in page.button if b.key == "action_feedback_ok").click().run()
        assert not page.exception
