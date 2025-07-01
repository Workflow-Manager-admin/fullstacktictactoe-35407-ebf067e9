"""
SQLAlchemy models for the Tic Tac Toe FastAPI backend: User, Game, Move, Result.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum

from .db import Base

class GameStatus(PyEnum):
    ongoing = "ongoing"
    finished = "finished"

class GameResult(PyEnum):
    draw = "draw"
    x_win = "x_win"
    o_win = "o_win"
    undecided = "undecided"

# PUBLIC_INTERFACE
class User(Base):
    """Database model for a user.

    A player is identified by a nickname (chosen or generated for anonymous).
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    # Nickname (required, not necessarily unique, but indexed). 
    nickname = Column(String, nullable=False, index=True)
    # For unique/old compatibility (some endpoints may still reference it; keep for now, but optional)
    username = Column(String, unique=True, nullable=True, index=True)  # DEPRECATED

    games = relationship("Game", back_populates="creator")

# PUBLIC_INTERFACE
class Game(Base):
    """Database model for a tic tac toe game."""
    __tablename__ = 'games'

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    player_x_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    player_o_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    status = Column(Enum(GameStatus), default=GameStatus.ongoing)
    result = Column(Enum(GameResult), default=GameResult.undecided)
    moves = relationship("Move", back_populates="game", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[player_x_id], back_populates="games")

# PUBLIC_INTERFACE
class Move(Base):
    """Database model for an individual game move."""
    __tablename__ = 'moves'

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False)
    player = Column(String, nullable=False)  # 'X' or 'O'
    row = Column(Integer, nullable=False)
    col = Column(Integer, nullable=False)
    move_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    game = relationship("Game", back_populates="moves")

# PUBLIC_INTERFACE
class Result(Base):
    """Database model for a game's result and summary (for leaderboard/history)."""
    __tablename__ = 'results'

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False, unique=True)
    winner = Column(String, nullable=True)  # 'X', 'O', or None for draw
    finished_at = Column(DateTime, default=datetime.utcnow)

    # Optionally link back to game (if needed for querying)
    # game = relationship("Game", backref="result")
