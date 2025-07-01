"""
Core game logic and service functions for Tic Tac Toe FastAPI backend.
Handles: game creation, move validation, turn management, win/draw calculation, and history.

Relies on: SQLAlchemy models (User, Game, Move, Result) and session management from db.py.
"""

from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Tuple, List, Dict

from .models import User, Game, Move, Result, GameStatus, GameResult

BOARD_SIZE = 3

# PUBLIC_INTERFACE
def start_new_game(db: Session, player_x_id: int, player_o_id: Optional[int] = None) -> Game:
    """
    Create and return a new Game instance, with player_x and optionally player_o.
    """
    new_game = Game(
        player_x_id=player_x_id,
        player_o_id=player_o_id,
        status=GameStatus.ongoing,
        result=GameResult.undecided
    )
    db.add(new_game)
    db.commit()
    db.refresh(new_game)
    return new_game

# PUBLIC_INTERFACE
def get_board_state(game: Game) -> List[List[Optional[str]]]:
    """
    Reconstructs the 3x3 board as a list of lists from all moves in the game.
    Returns a 3x3 nested list (each element either None, "X", or "O").
    """
    board = [[None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    for move in sorted(game.moves, key=lambda m: m.move_number):
        board[move.row][move.col] = move.player
    return board

# PUBLIC_INTERFACE
def get_next_turn(game: Game) -> str:
    """
    Returns the player symbol ("X" or "O") whose turn it is to play.
    """
    if not game.moves or len(game.moves) == 0:
        return "X"
    return "O" if game.moves[-1].player == "X" else "X"

# PUBLIC_INTERFACE
def is_valid_move(game: Game, row: int, col: int) -> Tuple[bool, str]:
    """
    Checks if the move is within boundaries and cell is empty.
    Returns (True, "") if valid, or (False, "reason") if not.
    """
    if row < 0 or row >= BOARD_SIZE or col < 0 or col >= BOARD_SIZE:
        return False, "Move out of bounds!"
    board = get_board_state(game)
    if board[row][col] is not None:
        return False, "Cell already occupied!"
    if game.status != GameStatus.ongoing:
        return False, "Game is not ongoing!"
    return True, ""

# PUBLIC_INTERFACE
def apply_move(db: Session, game: Game, player_symbol: str, row: int, col: int) -> Tuple[bool, Optional[str], Optional[Move]]:
    """
    Validates and applies a move for the given player ("X" or "O").
    Returns (success, error_message, Move or None).
    Also updates game state/result if this move finishes the game.
    """
    # Check turn
    expected_turn = get_next_turn(game)
    if player_symbol != expected_turn:
        return False, f"It is {expected_turn}'s turn.", None

    # Validate move
    valid, msg = is_valid_move(game, row, col)
    if not valid:
        return False, msg, None

    move_number = len(game.moves) + 1
    move = Move(
        game_id=game.id,
        player=player_symbol,
        row=row,
        col=col,
        move_number=move_number
    )
    db.add(move)
    db.commit()
    db.refresh(move)

    # Reload game.moves (or append for in-memory)
    db.refresh(game)
    # After the move, check for a win or draw
    result = evaluate_game_result(game)

    if result != GameResult.undecided:
        # Update game status and result
        game.status = GameStatus.finished
        game.result = result
        db.commit()
        db.refresh(game)
        # Record Result row for history/leaderboard
        winner = None
        if result == GameResult.x_win:
            winner = "X"
        elif result == GameResult.o_win:
            winner = "O"
        else:
            winner = None  # draw
        res = Result(
            game_id=game.id,
            winner=winner,
            finished_at=datetime.utcnow()
        )
        db.add(res)
        db.commit()
    else:
        # Game is still ongoing
        game.status = GameStatus.ongoing
        game.result = GameResult.undecided
        db.commit()

    return True, None, move

# PUBLIC_INTERFACE
def evaluate_game_result(game: Game) -> GameResult:
    """
    Checks the game board for win/draw/undecided status.
    Returns a GameResult enum value.
    """
    board = get_board_state(game)
    lines = []

    # Rows and columns
    for i in range(BOARD_SIZE):
        lines.append([board[i][j] for j in range(BOARD_SIZE)])  # Row
        lines.append([board[j][i] for j in range(BOARD_SIZE)])  # Col
    # Diagonals
    lines.append([board[i][i] for i in range(BOARD_SIZE)])
    lines.append([board[i][BOARD_SIZE - 1 - i] for i in range(BOARD_SIZE)])

    for line in lines:
        if line == ["X"] * BOARD_SIZE:
            return GameResult.x_win
        if line == ["O"] * BOARD_SIZE:
            return GameResult.o_win

    # Check for draw (all cells filled)
    if all(board[i][j] is not None for i in range(BOARD_SIZE) for j in range(BOARD_SIZE)):
        return GameResult.draw
    return GameResult.undecided

# PUBLIC_INTERFACE
def get_game_history(db: Session, user_id: int) -> List[Dict]:
    """
    Returns a list of the user's finished games (as dicts), including result, opponent, and finished_at.
    """
    # A player can be X or O
    games = db.query(Game).filter(
        (
            (Game.player_x_id == user_id) | (Game.player_o_id == user_id)
        )
        & (Game.status == GameStatus.finished)
    ).order_by(Game.id.desc()).all()

    game_ids = [g.id for g in games]
    results = db.query(Result).filter(Result.game_id.in_(game_ids)).all()
    result_map = {r.game_id: r for r in results}

    history = []
    for g in games:
        opponent_id = g.player_o_id if g.player_x_id == user_id else g.player_x_id
        result_obj = result_map.get(g.id)
        history.append({
            "game_id": g.id,
            "you_are": "X" if g.player_x_id == user_id else "O",
            "opponent_id": opponent_id,
            "winner": result_obj.winner if result_obj else None,
            "finished_at": result_obj.finished_at if result_obj else None,
            "result": g.result.value
        })
    return history

# PUBLIC_INTERFACE
def get_leaderboard(db: Session, limit: int = 10) -> List[Dict]:
    """
    Returns the top players by win count (aggregated from the results table),
    sorted by number of wins.
    """
    from sqlalchemy import func

    x_wins = db.query(Game.player_x_id.label('user_id'), func.count(Result.id).label('wins')) \
        .join(Result, Game.id == Result.game_id) \
        .filter(Result.winner == "X") \
        .group_by(Game.player_x_id)

    o_wins = db.query(Game.player_o_id.label('user_id'), func.count(Result.id).label('wins')) \
        .join(Result, Game.id == Result.game_id) \
        .filter(Result.winner == "O") \
        .group_by(Game.player_o_id)

    union_query = x_wins.union_all(o_wins).subquery()

    win_totals = db.query(
        union_query.c.user_id, func.sum(union_query.c.wins).label("total_wins")
    ).group_by(
        union_query.c.user_id
    ).order_by(
        func.sum(union_query.c.wins).desc()
    ).limit(limit).all()

    leaderboard = []
    for entry in win_totals:
        user = db.query(User).filter(User.id == entry.user_id).first()
        leaderboard.append({
            "user_id": entry.user_id,
            "nickname": user.nickname if user else "Anonymous",
            "wins": entry.total_wins
        })
    return leaderboard
