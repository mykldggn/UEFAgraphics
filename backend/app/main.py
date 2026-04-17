import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import leagues, infographics

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Set soccerdata cache dir before any imports that trigger it
os.environ.setdefault("SOCCERDATA_DIR", str(Path(settings.SOCCERDATA_DIR).resolve()))
Path(settings.SOCCERDATA_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.CACHE_DIR).mkdir(parents=True, exist_ok=True)

app = FastAPI(title="UEFAgraphics API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leagues.router)
app.include_router(infographics.router)


@app.get("/health")
def health():
    return {"status": "ok"}
