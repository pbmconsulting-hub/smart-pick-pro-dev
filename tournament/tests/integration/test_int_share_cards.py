"""Integration tests for tournament.share_cards."""

from tournament.share_cards import generate_win_share_card


def test_generate_win_share_card_svg_payload(isolated_db):
    card = generate_win_share_card(
        display_name="AcePlayer",
        tournament_name="Pro Court Friday",
        score=187.45,
        rank=1,
    )
    assert card["format"] == "svg"
    assert card["filename"].endswith(".svg")
    assert "<svg" in card["svg"]
    assert "AcePlayer" in card["svg"]

