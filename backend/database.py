"""
Database connection, session management and table initialization.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Support serverless platforms (e.g., Vercel / AWS Lambda) where root FS is read-only
if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    if not DATABASE_URL or DATABASE_URL.startswith("sqlite"):
        tmp_db = "/tmp/water_quality.db"
        src_db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "water_quality.db")
        if not os.path.exists(tmp_db) and os.path.exists(src_db):
            try:
                import shutil
                shutil.copy(src_db, tmp_db)
            except Exception as e:
                pass
        DATABASE_URL = f"sqlite:///{tmp_db}"
elif not DATABASE_URL:
    DATABASE_URL = "sqlite:///./data/water_quality.db"

# For SQLite, check_same_thread=False is needed for multi-threaded FastAPI
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency that yields a database session and ensures it closes after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

