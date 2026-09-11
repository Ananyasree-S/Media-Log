import sqlite3
from datetime import date
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI()
DB = "media.db"

MEDIA_TYPES = ["Book", "Movie", "Show", "Anime", "Documentary", "Podcast", "Game", "Other"]
MEDIA_STATUSES = ["Completed", "Reading", "Watching", "Dropped", "Want to Read", "Want to Watch", "On Hold"]


def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                title          TEXT NOT NULL,
                type           TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'Completed',
                rating         INTEGER,
                date_completed TEXT,
                liked          TEXT DEFAULT '',
                disliked       TEXT DEFAULT '',
                notes          TEXT DEFAULT '',
                created_at     TEXT NOT NULL DEFAULT (date('now'))
            )
        """)

init_db()


class EntryIn(BaseModel):
    title: str
    type: str
    status: str = "Completed"
    rating: Optional[int] = None
    date_completed: Optional[str] = None
    liked: str = ""
    disliked: str = ""
    notes: str = ""


@app.get("/api/types")
def get_types():
    return MEDIA_TYPES


@app.get("/api/statuses")
def get_statuses():
    return MEDIA_STATUSES


@app.get("/api/entries")
def list_entries(
    type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    year: Optional[str] = None,
):
    with get_conn() as conn:
        query = "SELECT * FROM entries WHERE 1=1"
        params = []
        if type:
            query += " AND type=?"; params.append(type)
        if status:
            query += " AND status=?"; params.append(status)
        if search:
            query += " AND title LIKE ?"; params.append(f"%{search}%")
        if year:
            query += " AND date_completed LIKE ?"; params.append(f"{year}%")
        query += " ORDER BY created_at DESC, id DESC"
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/entries", status_code=201)
def create_entry(e: EntryIn):
    if not e.title.strip():
        raise HTTPException(400, "title cannot be empty")
    if e.type not in MEDIA_TYPES:
        raise HTTPException(400, f"type must be one of {MEDIA_TYPES}")
    if e.rating is not None and e.rating not in range(1, 6):
        raise HTTPException(400, "rating must be between 1 and 5")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO entries (title, type, status, rating, date_completed, liked, disliked, notes) VALUES (?,?,?,?,?,?,?,?)",
            (e.title.strip(), e.type, e.status, e.rating, e.date_completed, e.liked, e.disliked, e.notes),
        )
        return {"id": cur.lastrowid, **e.model_dump()}


@app.put("/api/entries/{entry_id}")
def update_entry(entry_id: int, e: EntryIn):
    if not e.title.strip():
        raise HTTPException(400, "title cannot be empty")
    if e.type not in MEDIA_TYPES:
        raise HTTPException(400, f"type must be one of {MEDIA_TYPES}")
    if e.rating is not None and e.rating not in range(1, 6):
        raise HTTPException(400, "rating must be between 1 and 5")
    with get_conn() as conn:
        res = conn.execute(
            "UPDATE entries SET title=?, type=?, status=?, rating=?, date_completed=?, liked=?, disliked=?, notes=? WHERE id=?",
            (e.title.strip(), e.type, e.status, e.rating, e.date_completed, e.liked, e.disliked, e.notes, entry_id),
        )
        if res.rowcount == 0:
            raise HTTPException(404, "Not found")
    return {"id": entry_id, **e.model_dump()}


@app.delete("/api/entries/{entry_id}")
def delete_entry(entry_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM entries WHERE id=?", (entry_id,))
    return {"ok": True}


@app.get("/api/stats")
def get_stats():
    with get_conn() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM entries").fetchall()]

    total = len(rows)
    completed = sum(1 for r in rows if r["status"] == "Completed")
    rated = [r["rating"] for r in rows if r["rating"]]
    avg_rating = round(sum(rated) / len(rated), 1) if rated else None

    by_type = {}
    for r in rows:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1

    rating_dist = {str(i): 0 for i in range(1, 6)}
    for r in rows:
        if r["rating"]:
            rating_dist[str(r["rating"])] += 1

    this_year = str(date.today().year)
    this_year_count = sum(1 for r in rows if (r.get("date_completed") or "").startswith(this_year))

    return {
        "total": total,
        "completed": completed,
        "avg_rating": avg_rating,
        "this_year": this_year_count,
        "by_type": by_type,
        "rating_dist": rating_dist,
    }


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    with open("templates/index.html", encoding="utf-8") as f:
        return f.read()
