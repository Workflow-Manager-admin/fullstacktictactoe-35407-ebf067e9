"""
SQLAlchemy database initialization and ORM session handling for the Tic Tac Toe FastAPI backend.
Uses SQLite as the database.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
import os

# PUBLIC_INTERFACE
def get_database_url():
    """Get SQLite DB URL from environment (if provided), otherwise use default file db."""
    db_url = os.environ.get('SQLITE_URL')
    if db_url:
        return db_url
    return 'sqlite:///./tic_tac_toe.db'

DATABASE_URL = get_database_url()

# For SQLite, connect_args is required to avoid threading issues in testing/development
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()

# PUBLIC_INTERFACE
def get_db():
    """
    Dependency for FastAPI endpoints to get a SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
