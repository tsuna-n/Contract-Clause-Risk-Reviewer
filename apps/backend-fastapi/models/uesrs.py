from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from app.api.deps import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)  # Google "sub" claim
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
