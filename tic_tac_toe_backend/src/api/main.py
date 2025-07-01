"""
FastAPI backend for Tic Tac Toe.
Initializes CORS, SQLAlchemy ORM with SQLite, and exposes a health check endpoint.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine, get_db
from .game_service import (
    start_new_game,
    apply_move,
    get_board_state,
    get_next_turn,
    get_leaderboard,
)
from .models import Game, User, GameStatus

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

app = FastAPI(
    title="Tic Tac Toe Backend API",
    description="Backend for multiplayer Tic Tac Toe with user management and persistent results.",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Pydantic schemas ----
class StartGameRequest(BaseModel):
    """Request body for starting a new game."""
    player_x_id: int = Field(..., description="User ID for player X")
    player_o_id: Optional[int] = Field(None, description="User ID for player O (if playing PVP), else null")

class GameResponse(BaseModel):
    """Response schema for a created or fetched game."""
    game_id: int
    player_x_id: int
    player_o_id: Optional[int]
    status: str
    result: str

class MakeMoveRequest(BaseModel):
    """Request body for making a move."""
    game_id: int = Field(..., description="Game ID to which move is being applied")
    player_symbol: str = Field(..., description="Player symbol ('X' or 'O')")
    row: int = Field(..., ge=0, le=2, description="Row index for move")
    col: int = Field(..., ge=0, le=2, description="Column index for move")

class MoveResponse(BaseModel):
    """Response schema after making a move."""
    success: bool
    error: Optional[str] = None
    move_number: Optional[int] = None
    board: Optional[List[List[Optional[str]]]] = None
    game_status: Optional[str] = None
    game_result: Optional[str] = None

class GameStateResponse(BaseModel):
    """Response for game state request."""
    game_id: int
    board: List[List[Optional[str]]]
    moves: List[Dict]
    current_turn: str
    status: str
    result: str

class LeaderboardEntry(BaseModel):
    """Single leaderboard entry."""
    user_id: int
    username: str
    wins: int

class LeaderboardResponse(BaseModel):
    """Leaderboard API response."""
    leaderboard: List[LeaderboardEntry]

@app.on_event("startup")
def on_startup():
    """
    Create all tables in the SQLite database at application startup (if not already present).
    """
    Base.metadata.create_all(bind=engine)

# PUBLIC_INTERFACE
@app.get("/")
def health_check():
    """Check service health."""
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get leaderboard",
    description="Returns a leaderboard of top players and their win counts."
)
def leaderboard(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get the leaderboard of top players by number of wins.
    """
    results = get_leaderboard(db, limit=limit)
    return LeaderboardResponse(leaderboard=[
        LeaderboardEntry(**entry) for entry in results
    ])


# PUBLIC_INTERFACE
@app.get(
    "/game_state",
    response_model=GameStateResponse,
    summary="Get state of a game",
    description="Fetches the complete board, moves, and metadata for a specified game id.",
)
def get_game_state(
    game_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the complete state of a game (board, moves, whose turn, status/result) for the given game_id.
    """
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    board = get_board_state(game)
    moves = [
        {
            "move_number": m.move_number,
            "player": m.player,
            "row": m.row,
            "col": m.col,
            "timestamp": m.timestamp,
        }
        for m in sorted(game.moves, key=lambda m: m.move_number)
    ]
    return GameStateResponse(
        game_id=game.id,
        board=board,
        moves=moves,
        current_turn=get_next_turn(game),
        status=game.status.value,
        result=game.result.value
    )


# PUBLIC_INTERFACE
@app.post(
    "/make_move",
    response_model=MoveResponse,
    summary="Make a move",
    description="Apply a move for the current player. Returns success, error message (if any), updated board, and game status/result."
)
def make_move(
    payload: MakeMoveRequest,
    db: Session = Depends(get_db)
):
    """
    Apply a move for the current player.

    - **game_id**: Game to play in
    - **player_symbol**: "X" or "O"
    - **row**, **col**: Location for the move
    """
    game = db.query(Game).filter(Game.id == payload.game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status != GameStatus.ongoing:
        return MoveResponse(success=False, error="Game is finished", board=get_board_state(game), game_status=game.status.value, game_result=game.result.value)
    ok, err, move = apply_move(
        db, game, payload.player_symbol, payload.row, payload.col
    )
    if not ok:
        return MoveResponse(success=False, error=err, board=get_board_state(game), game_status=game.status.value, game_result=game.result.value)
    db.refresh(game)
    return MoveResponse(
        success=True,
        move_number=move.move_number if move else None,
        board=get_board_state(game),
        game_status=game.status.value,
        game_result=game.result.value,
    )


# PUBLIC_INTERFACE
@app.post(
    "/start_game",
    response_model=GameResponse,
    summary="Start a new Tic Tac Toe game",
    description="Creates a new Tic Tac Toe game with specified player X and optional player O."
)
def start_game(
    payload: StartGameRequest,
    db: Session = Depends(get_db)
):
    """
    Starts a new Tic Tac Toe game.

    - **player_x_id**: User id for player X
    - **player_o_id**: (optional) User id for player O
    """
    # Check users exist
    px = db.query(User).filter(User.id == payload.player_x_id).first()
    if not px:
        raise HTTPException(status_code=404, detail="Player X does not exist")
    po = None
    if payload.player_o_id is not None:
        po = db.query(User).filter(User.id == payload.player_o_id).first()
        if not po:
            raise HTTPException(status_code=404, detail="Player O does not exist")
    game = start_new_game(db, payload.player_x_id, payload.player_o_id)
    return GameResponse(
        game_id=game.id,
        player_x_id=game.player_x_id,
        player_o_id=game.player_o_id,
        status=game.status.value,
        result=game.result.value,
    )
