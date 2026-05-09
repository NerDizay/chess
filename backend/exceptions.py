class ChessError(Exception):
    pass


class InvalidStepError(ChessError):
    def __init__(self, step: int, min_step: int, max_step: int) -> None:
        message = f"Invalid step {step}. Allowed range: {min_step}..{max_step}."
        super().__init__(message)


class InvalidCellError(ChessError):
    def __init__(self, cell: str) -> None:
        message = f"Invalid cell '{cell}'. Use algebraic notation like 'e4'."
        super().__init__(message)


class InvalidKnightDeltaError(ChessError):
    def __init__(self, d_col: int, d_row: int) -> None:
        message = (
            f"Invalid knight delta ({d_col}, {d_row}). "
            "Knight moves must be one of (2,1), (2,-1), (-2,1), (-2,-1), "
            "(1,2), (1,-2), (-1,2), (-1,-2)."
        )
        super().__init__(message)


class InvalidTeamError(ChessError):
    def __init__(self, team: str) -> None:
        message = f"Invalid team '{team}'. Team must be 'black' or 'white'."
        super().__init__(message)


class InvalidUserNameError(ChessError):
    def __init__(self, name: str, max_length: int) -> None:
        message = (
            f"Invalid user name '{name}'. "
            f"Name must be non-empty and at most {max_length} characters long."
        )
        super().__init__(message)


class UserNotFoundError(ChessError):
    def __init__(self, user_id: str | int) -> None:
        super().__init__(f"User with id {user_id} not found.")


class GameNotFoundError(ChessError):
    def __init__(self, game_id: int) -> None:
        super().__init__(f"Game with id {game_id} not found.")


class GameForbiddenError(ChessError):
    def __init__(self) -> None:
        super().__init__("Not a participant of this game.")


class InvalidMoveError(ChessError):
    def __init__(self, message: str = "Illegal move.") -> None:
        super().__init__(message)


class InvalidGameUserAssignmentError(ChessError):
    def __init__(self, expected_team: str, actual_team: str, role: str) -> None:
        message = (
            f"Invalid team for {role}: expected '{expected_team}', got '{actual_team}'."
        )
        super().__init__(message)
