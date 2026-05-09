from backend.domain.game import Game, SerializedBattleField
from backend.domain.user import User


def test_game_serialize_with_optional_black():
    board = {"a1": None}
    game = Game(
        battle_field=SerializedBattleField(data=board),
        white_user=User(name="w", team="white"),
        black_user=None,
        whose_move="white",
    )
    data = game.serialize()
    assert data["whose_move"] == "white"
    assert data["battle_field"] == board
    assert data["white_user"] == {"name": "w", "team": "white"}
    assert data["black_user"] is None
