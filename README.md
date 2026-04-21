# UEFAgraphics

Football analytics web app — server-side PNG infographics for players, teams, and leagues across Europe's top competitions.

## Features

| Infographic | Description |
|---|---|
| Shot Map | xG-weighted scatter on a half-pitch; avg distance annotation |
| Radar (Pizza) | Per-90 percentile chart vs league peers — Goals, xG, npxG, xA, xGChain, xGBuildup |
| Career xG | Cumulative xG vs goals over a player's career with per-season bar breakdown |
| Summary Card | Season totals: Goals, Assists, xG, xA, npxG, minutes |
| xG Timeline | Match-by-match xG for & against, cumulative |
| Team Season Card | League position, W/D/L, top scorers |
| League Table | Standings with GF/GA/GD, points, last-5 form pills |
| Position Race | League position at every matchday, interactive line chart |
| Leaders | Top 10 in Goals, Assists, xG, Key Passes, Shots |

## Data Sources

| Source | Used for |
|---|---|
| [Understat](https://understat.com) | Shot data, player stats, xG/xA/npxG/xGChain/xGBuildup, team history |
| [football-data.org](https://football-data.org) | League standings, team lists, top scorers (free key) |

No scraping of sites that prohibit it. Understat is a public stats site; football-data.org provides a free API tier with no daily limit.

## Leagues Supported

EPL · La Liga · Bundesliga · Serie A · Ligue 1 · Russian Premier League (Understat)  
Plus: Championship, Primeira Liga, Eredivisie, Champions League, Europa League (standings only)

## Stack

**Backend** — Python 3.9+, FastAPI, matplotlib, mplsoccer, pandas, curl_cffi  
**Frontend** — React 18, TypeScript, Vite, Tailwind CSS, Recharts

## Local Setup

### Backend
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your football-data.org key
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

API runs on `http://localhost:8000`, frontend on `http://localhost:5173`.

### Environment Variables

```
FOOTBALL_DATA_KEY=your_key_here   # free at football-data.org
FRONTEND_URL=http://localhost:5173
CACHE_DIR=./cache
```

## Deployment

- **Backend** — Railway (Dockerfile included)
- **Frontend** — Vercel (`vite build` → static)
