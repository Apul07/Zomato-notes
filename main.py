"""
main.py
Zomato Notes — FastAPI backend. All endpoints from Parts 1, 2, and 3.
"""
import logging
import os
import time

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

import algorithms
import crud
import models
import schemas
from ai_service import get_ai_suggestion
from database import Base, SessionLocal, engine, get_db
from semantic_search import rank_by_similarity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zomato_notes")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Zomato Notes API")

# ---------------------------------------------------------------------------
# CORS — only the documented local frontend origin(s) may call this API.
# Update this list if you serve the frontend from a different origin.
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Custom middleware: X-Process-Time header on every response.
# ---------------------------------------------------------------------------
class ProcessTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        response.headers["X-Process-Time"] = str(duration)
        return response


app.add_middleware(ProcessTimeMiddleware)


# ---------------------------------------------------------------------------
# Auth-gate dependency for deletions: custom x-token header.
# ---------------------------------------------------------------------------
EXPECTED_TOKEN = os.getenv("NOTES_DELETE_TOKEN", "super-secret-token")


def require_delete_token(x_token: str | None = Header(default=None)):
    if x_token is None:
        raise HTTPException(status_code=401, detail="Missing x-token header")
    if x_token != EXPECTED_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid x-token header")
    return True


# ---------------------------------------------------------------------------
# Background task helper (non-blocking simulated indexing step).
# ---------------------------------------------------------------------------
def simulate_indexing(note_id: int, title: str):
    time.sleep(2.5)
    logger.info("[background-index] finished indexing note id=%s title=%r", note_id, title)


# =============================== Users ====================================

@app.post("/users", response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = crud.get_user_by_email(db, user.email)
    if existing:
        raise HTTPException(status_code=422, detail="Email already registered")
    return crud.create_user(db, user)


# =============================== Notes CRUD ================================

@app.post("/notes", response_model=schemas.NoteCreateResponse)
def create_note(
    note: schemas.NoteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    owner = crud.get_user(db, note.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail=f"User {note.owner_id} not found")

    db_note = crud.create_note(db, note)

    # Background "indexing" job — response returns before this finishes.
    background_tasks.add_task(simulate_indexing, db_note.id, db_note.title)

    # Part 3: server-side AI auto-tag suggestion (mock mode by default).
    ai_suggestion = get_ai_suggestion(db_note.content)

    result = schemas.NoteCreateResponse.model_validate(db_note)
    result.ai_suggestion = ai_suggestion
    return result


@app.get("/notes", response_model=list[schemas.NoteOut])
def list_notes(tag: str | None = None, db: Session = Depends(get_db)):
    return crud.get_notes(db, tag=tag)


@app.get("/notes/{note_id}", response_model=schemas.NoteOut)
def get_note(note_id: int, db: Session = Depends(get_db)):
    db_note = crud.get_note(db, note_id)
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    return db_note


@app.put("/notes/{note_id}", response_model=schemas.NoteOut)
def update_note(note_id: int, note_update: schemas.NoteUpdate, db: Session = Depends(get_db)):
    db_note = crud.update_note(db, note_id, note_update)
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    return db_note


@app.delete("/notes/{note_id}")
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(require_delete_token),
):
    deleted = crud.delete_note(db, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"detail": f"Note {note_id} deleted"}


# ============================ Bulk import ==================================

@app.post("/notes/import")
async def import_notes(owner_id: int, file: UploadFile, db: Session = Depends(get_db)):
    owner = crud.get_user(db, owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail=f"User {owner_id} not found")

    raw_bytes = await file.read()
    text_content = raw_bytes.decode("utf-8")
    lines = [line.strip() for line in text_content.splitlines() if line.strip()]

    created = []
    for line in lines:
        note = schemas.NoteCreate(title=line[:120], content=line, tag="imported", owner_id=owner_id)
        db_note = crud.create_note(db, note)
        created.append(db_note.id)

    return {"created_note_ids": created, "count": len(created)}


# =========================== Raw-SQL reports ================================

@app.get("/reports/tag-summary")
def tag_summary(db: Session = Depends(get_db)):
    return crud.raw_tag_summary(db)


@app.get("/reports/long-notes")
def long_notes(db: Session = Depends(get_db)):
    return crud.raw_long_notes(db)


@app.get("/reports/user-notes")
def user_notes(db: Session = Depends(get_db)):
    return crud.raw_user_notes(db)


# ======================= Part 2: Ranking Engine endpoints ===================

def _note_to_dict(note: models.Note) -> dict:
    return {
        "id": note.id,
        "title": note.title,
        "content": note.content,
        "tag": note.tag,
        "owner_id": note.owner_id,
        "created_at": note.created_at,
    }


@app.get("/notes/search")
def search_notes(
    keyword: str | None = None,
    sort_by: str | None = Query(default=None, description="'date' for date sort"),
    db: Session = Depends(get_db),
):
    all_notes = [_note_to_dict(n) for n in crud.get_notes(db)]

    if sort_by == "date":
        for n in all_notes:
            n["created_at_epoch"] = n["created_at"].timestamp()
        ranked = algorithms.insertion_sort_by_key(all_notes, key="created_at_epoch")
        return ranked[:5]

    if not keyword:
        raise HTTPException(status_code=400, detail="Provide ?keyword= or ?sort_by=date")

    kw = keyword.lower()
    for n in all_notes:
        n["score"] = n["content"].lower().count(kw)

    ranked = algorithms.insertion_sort_by_key(all_notes, key="score")
    return ranked[:5]


@app.get("/notes/lookup")
def lookup_note(title: str, algo: str = "iterative", db: Session = Depends(get_db)):
    ordered_notes = db.query(models.Note).order_by(models.Note.title.asc()).all()
    sorted_titles = [n.title for n in ordered_notes]

    if algo == "recursive":
        idx = algorithms.binary_search_recursive(sorted_titles, title, 0, len(sorted_titles) - 1)
    else:
        idx = algorithms.binary_search_iterative(sorted_titles, title)

    if idx == -1:
        return {"found": False, "note": None}

    return {"found": True, "note": _note_to_dict(ordered_notes[idx])}


@app.get("/notes/quick-find")
def quick_find(tag: str, db: Session = Depends(get_db)):
    notes = [_note_to_dict(n) for n in crud.get_notes(db, tag=tag)]
    match = algorithms.linear_search(notes, key="tag", value=tag)
    if match is None:
        return {"found": False, "note": None}
    return {"found": True, "note": match}


# ===================== Part 3: Smart (semantic) search ======================

@app.get("/notes/smart-search")
def smart_search(q: str, db: Session = Depends(get_db)):
    notes = [_note_to_dict(n) for n in crud.get_notes(db, tag="ai-demo")]
    if not notes:
        # Fall back to all notes if the ai-demo set hasn't been seeded yet.
        notes = [_note_to_dict(n) for n in crud.get_notes(db)]
    ranked = rank_by_similarity(q, notes, top_n=3)
    return ranked