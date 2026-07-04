from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings

# 1. โหลดข้อมูลจาก .env ด้วย Pydantic Settings
class Settings(BaseSettings):
    database_url: str

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings() # type: ignore

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection():
    """ตรวจสอบว่าเชื่อมต่อ PostgreSQL ได้หรือไม่"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        print(f"Database connection error: {e}")
        return False