"""
FastAPI backend for Tic Tac Toe.
Initializes CORS, SQLAlchemy ORM with SQLite, and exposes a health check endpoint.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine

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
