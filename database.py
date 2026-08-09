"""
database.py
Engine, sessionmaker, and the get_db dependency.

Defaults to a local SQLite file (zero signup, works offline). If you'd
rather use a hosted Postgres (e.g. Supabase free tier), set DATABASE_URL
in your .env file to something like:
    postgresql://user:password@host:5432/dbname
and this module will pick it up automatically.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./zomato_notes.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()