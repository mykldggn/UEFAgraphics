import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.routers import leagues, infographics, matches

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Set soccerdata cache dir before any imports that trigger it
os.environ.setdefault("SOCCERDATA_DIR", str(Path(settings.SOCCERDATA_DIR).resolve()))
Path(settings.SOCCERDATA_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.CACHE_DIR).mkdir(parents=True, exist_ok=True)

app = FastAPI(title="UEFAgraphics API", version="1.0.0")


class NoCacheJsonMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        ct = response.headers.get("content-type", "")
        if "json" in ct:
            response.headers["Cache-Control"] = "no-store"
        return response


app.add_middleware(NoCacheJsonMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leagues.router)
app.include_router(infographics.router)
app.include_router(matches.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug/fotmob")
def debug_fotmob():
    """Test whether FotMob API is reachable from this server."""
    from datetime import date
    from app.services import fotmob_service as fotmob
    today = date.today().isoformat().replace("-", "")
    try:
        raw = fotmob._get("matches", {"date": today})
        if raw is None:
            return {"ok": False, "error": "null response"}
        leagues = raw.get("leagues", [])
        total = sum(len(lg.get("matches", [])) for lg in leagues)
        return {"ok": True, "date": today, "leagues": len(leagues), "total_matches": total}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.get("/debug/matches-today")
def debug_matches_today():
    """Test what the matches/today endpoint actually returns."""
    from datetime import date
    from app.routers.matches import _fdorg_matches
    today = date.today().isoformat()
    matches = _fdorg_matches(today)
    return {"date": today, "count": len(matches), "matches": matches[:5]}
