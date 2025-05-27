from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("NEON_DB_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ✅ Define get_db for dependency injection
def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
