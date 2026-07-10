from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from auth.config import auth_settings
from auth.router import router as auth_router
from database import Base, check_db_connection, engine

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[auth_settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=auth_settings.session_secret_key)
app.include_router(auth_router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/health/db")
def health_check_db():
    """ตรวจสอบสถานะการเชื่อมต่อ PostgreSQL"""
    if check_db_connection():
        return {"status": "ok", "database": "connected"}
    raise HTTPException(status_code=503, detail="Database not connected")
