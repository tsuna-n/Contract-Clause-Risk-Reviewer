from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from database import *

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}



@app.get("/health/db")
def health_check_db():
    """ตรวจสอบสถานะการเชื่อมต่อ PostgreSQL"""
    if check_db_connection():
        return {"status": "ok", "database": "connected"}
    raise HTTPException(status_code=503, detail="Database not connected")
