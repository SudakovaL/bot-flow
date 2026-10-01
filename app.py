"""Единый runtime: FastAPI + статический чат. Запуск: python app.py"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import agent_runtime
import ai_client
import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")
STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    log.info("DB ready: %s | AI configured: %s", db.db_path().name, ai_client.is_configured())
    yield


app = FastAPI(title="Тихий сервис — чат-бот", lifespan=lifespan)


class ChatIn(BaseModel):
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")
    message: str = Field(default="", max_length=2000)
    action: str = Field(default="", max_length=64)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_configured": ai_client.is_configured()}


@app.post("/api/chat")
def chat(body: ChatIn):
    return agent_runtime.dispatch(body.session_id, body.message, body.action)


app.mount("/static", StaticFiles(directory=STATIC), name="static")

if __name__ == "__main__":
    uvicorn.run("app:app", host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
