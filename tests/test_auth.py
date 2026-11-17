from core.auth import authenticate, hash_pin, verify_pin
from core.models import Player


def test_correct_pin_authenticates():
    pin_hash = hash_pin("1234")
    assert verify_pin("1234", pin_hash) is True


def test_wrong_pin_is_rejected():
    pin_hash = hash_pin("1234")
    assert verify_pin("0000", pin_hash) is False


def test_pin_hash_never_contains_the_plaintext_pin():
    pin_hash = hash_pin("1234")
    assert "1234" not in pin_hash


def test_authenticate_returns_player_on_correct_pin():
    player = Player(id="p1", display_name="mia", first_name="Mia", last_name="Silva", pin_hash=hash_pin("1234"))
    assert authenticate("mia", "1234", [player]) == player


def test_authenticate_returns_none_on_wrong_pin():
    player = Player(id="p1", display_name="mia", first_name="Mia", last_name="Silva", pin_hash=hash_pin("1234"))
    assert authenticate("mia", "0000", [player]) is None


def test_authenticate_returns_none_for_unknown_name():
    player = Player(id="p1", display_name="mia", first_name="Mia", last_name="Silva", pin_hash=hash_pin("1234"))
    assert authenticate("someone_else", "1234", [player]) is None
