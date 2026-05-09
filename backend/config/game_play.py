"""Параметры игровой логики, задаются в репозитории (не через переменные окружения)."""

from dataclasses import dataclass

from backend.domain import battle_fields


@dataclass(frozen=True, slots=True)
class GamePlayConfig:
    """Пауза перед авто-покиданием партии после потери всех WebSocket (секунды)."""

    disconnect_abandon_delay_seconds: int = 120


game_play_config = GamePlayConfig()

# Стартовая позиция новых партий (matchmaking / очередь).
# Пресеты: MateTrainingBattleField, EnPassantTrainingBattleField, CastleTrainingBattleField
# в backend/domain/battle_fields.py — импортируйте нужный класс и подставьте сюда одной строкой.
# START_BATTLE_FIELD_CLASS = battle_fields.DefaultBattleField
# START_BATTLE_FIELD_CLASS = battle_fields.MateTrainingBattleField
# START_BATTLE_FIELD_CLASS = battle_fields.EnPassantTrainingBattleField
START_BATTLE_FIELD_CLASS = battle_fields.CastleTrainingBattleField
