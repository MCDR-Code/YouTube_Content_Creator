"""The approval gate. Plain code, no agent.

Videos are registered as "pending". Only the professor's review page calls approve() or reject().
No agent has a tool that can reach this module. The uploader re-reads the record from the
database right before uploading and refuses anything that is not approved.

Every action is written to the events table with the time and who did it.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from ycc.storage import OUTPUT

DB = OUTPUT / "ycc.db"
STATUSES = ("pending", "changes_requested", "approved", "rejected", "uploaded")
EXTRA_COLUMNS = {"poster": "TEXT", "cost_usd": "REAL", "changes_note": "TEXT"}


class NotApproved(RuntimeError):
    pass


def _conn(db: Path | None = None) -> sqlite3.Connection:
    path = db or DB
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS videos (
        id TEXT PRIMARY KEY, week INTEGER, kind TEXT, path TEXT, thumbnails TEXT, variants TEXT,
        title TEXT, description TEXT, tags TEXT, ai_disclosure INTEGER, made_for_kids INTEGER,
        professor_spots TEXT, fact_check_passed INTEGER,
        status TEXT DEFAULT 'pending', chosen_variant INTEGER, professor_note TEXT,
        approved_by TEXT, approved_at TEXT, uploaded_at TEXT, youtube_id TEXT, privacy TEXT);
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, video_id TEXT, action TEXT, actor TEXT, detail TEXT);
    """)
    have = {r[1] for r in c.execute("PRAGMA table_info(videos)").fetchall()}
    for col, kind in EXTRA_COLUMNS.items():  # older databases from earlier runs
        if col not in have:
            c.execute(f"ALTER TABLE videos ADD COLUMN {col} {kind}")
    return c


def log_event(video_id: str, action: str, actor: str, detail: str = "", db: Path | None = None) -> None:
    with _conn(db) as c:
        c.execute("INSERT INTO events (time, video_id, action, actor, detail) VALUES (?,?,?,?,?)",
                  (time.strftime("%Y-%m-%d %H:%M:%S"), video_id, action, actor, detail))


def register_video(v: dict, db: Path | None = None) -> bool:
    """Add or replace a video as pending. An uploaded video is never replaced. Returns False if skipped."""
    old = get(v["id"], db)
    if old and old["status"] == "uploaded":
        log_event(v["id"], "skipped_rebuild", "system", "already uploaded; kept as is", db)
        return False
    with _conn(db) as c:
        c.execute("""INSERT OR REPLACE INTO videos (id, week, kind, path, thumbnails, variants, title, description,
                     tags, ai_disclosure, made_for_kids, professor_spots, fact_check_passed, status, poster, cost_usd)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, 'pending', ?, ?)""",
                  (v["id"], v["week"], v["kind"], v["path"], json.dumps(v.get("thumbnails", [])),
                   json.dumps(v.get("variants", [])), v["title"], v["description"], json.dumps(v.get("tags", [])),
                   int(v.get("ai_disclosure", True)), int(v.get("made_for_kids", False)),
                   json.dumps(v.get("professor_spots", [])), int(v.get("fact_check_passed", True)),
                   v.get("poster"), float(v.get("cost_usd") or 0)))
    log_event(v["id"], "rebuilt" if old else "registered", "system", "waiting for the professor", db)
    return True


def list_all(db: Path | None = None) -> list[dict]:
    with _conn(db) as c:
        rows = c.execute("SELECT * FROM videos ORDER BY week DESC, kind, id").fetchall()
    return [_row(r) for r in rows]


def request_changes(video_id: str, approver: str, notes: str, db: Path | None = None) -> None:
    """The professor asks for changes. The notes go to the Scriptwriter on the next revise step."""
    notes = (notes or "").strip()
    if not notes:
        raise ValueError("Please write what should change.")
    v = get(video_id, db)
    if not v:
        raise KeyError(video_id)
    if v["status"] == "uploaded":
        raise NotApproved("Already uploaded.")
    with _conn(db) as c:
        c.execute("UPDATE videos SET status='changes_requested', changes_note=?, approved_by=NULL, approved_at=NULL "
                  "WHERE id=?", (notes[:2000], video_id))
    log_event(video_id, "changes_requested", approver or "professor", notes[:300], db)


def get(video_id: str, db: Path | None = None) -> dict | None:
    with _conn(db) as c:
        r = c.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
    return _row(r) if r else None


def list_week(week: int, db: Path | None = None) -> list[dict]:
    with _conn(db) as c:
        rows = c.execute("SELECT * FROM videos WHERE week=? ORDER BY kind, id", (week,)).fetchall()
    return [_row(r) for r in rows]


def list_weeks(db: Path | None = None) -> list[int]:
    with _conn(db) as c:
        return [r[0] for r in c.execute("SELECT DISTINCT week FROM videos ORDER BY week").fetchall()]


def events(video_id: str | None = None, db: Path | None = None) -> list[dict]:
    with _conn(db) as c:
        q = "SELECT * FROM events" + (" WHERE video_id=?" if video_id else "") + " ORDER BY id"
        return [dict(r) for r in c.execute(q, (video_id,) if video_id else ()).fetchall()]


def _row(r) -> dict:
    d = dict(r)
    for k in ("thumbnails", "variants", "tags", "professor_spots"):
        d[k] = json.loads(d[k] or "[]")
    return d


def approve(video_id: str, approver: str, title: str, description: str, chosen_variant: int,
            note: str = "", db: Path | None = None) -> None:
    approver = (approver or "").strip()
    if not approver:
        raise ValueError("The approver's name is required.")
    v = get(video_id, db)
    if not v:
        raise KeyError(video_id)
    if v["status"] == "uploaded":
        raise NotApproved("Already uploaded; it cannot be re-approved.")
    with _conn(db) as c:
        c.execute("""UPDATE videos SET status='approved', approved_by=?, approved_at=?, title=?, description=?,
                     chosen_variant=?, professor_note=? WHERE id=?""",
                  (approver, time.strftime("%Y-%m-%d %H:%M:%S"), title.strip()[:100], description.strip()[:5000],
                   chosen_variant, note.strip(), video_id))
    log_event(video_id, "approved", approver, f"variant {chosen_variant}; title: {title[:80]}", db)


def reject(video_id: str, approver: str, note: str = "", db: Path | None = None) -> None:
    v = get(video_id, db)
    if v and v["status"] == "uploaded":
        raise NotApproved("Already uploaded.")
    with _conn(db) as c:
        c.execute("UPDATE videos SET status='rejected', professor_note=?, approved_by=NULL, approved_at=NULL "
                  "WHERE id=?", (note.strip(), video_id))
    log_event(video_id, "rejected", approver or "professor", note, db)


def withdraw(video_id: str, approver: str, db: Path | None = None) -> None:
    """Take back an approval before upload. Not allowed after upload."""
    v = get(video_id, db)
    if not v or v["status"] != "approved":
        raise NotApproved("Only an approved, not yet uploaded video can be withdrawn.")
    with _conn(db) as c:
        c.execute("UPDATE videos SET status='pending', approved_by=NULL, approved_at=NULL WHERE id=?", (video_id,))
    log_event(video_id, "approval_withdrawn", approver or "professor", "", db)


def require_approved(video_id: str, db: Path | None = None) -> dict:
    """The gate. Re-reads the record right before an upload."""
    v = get(video_id, db)
    if not v:
        raise NotApproved(f"{video_id} is not registered.")
    if v["status"] != "approved" or not v["approved_by"] or not v["approved_at"]:
        raise NotApproved(f"{video_id} is '{v['status']}', not approved by the professor. Upload refused.")
    return v


def mark_uploaded(video_id: str, youtube_id: str, privacy: str, db: Path | None = None) -> None:
    with _conn(db) as c:
        c.execute("UPDATE videos SET status='uploaded', uploaded_at=?, youtube_id=?, privacy=? WHERE id=?",
                  (time.strftime("%Y-%m-%d %H:%M:%S"), youtube_id, privacy, video_id))
    log_event(video_id, "uploaded", "uploader", f"youtube id {youtube_id}, privacy {privacy}", db)
