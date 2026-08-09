"""
crud.py
Plain CRUD helpers plus the raw-SQL reporting queries.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

import models
import schemas


# ---------- Users ----------

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = models.User(name=user.name, email=user.email, password=user.password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# ---------- Notes ----------

def create_note(db: Session, note: schemas.NoteCreate) -> models.Note:
    db_note = models.Note(
        title=note.title, content=note.content, tag=note.tag, owner_id=note.owner_id
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note


def get_notes(db: Session, tag: str | None = None):
    query = db.query(models.Note)
    if tag:
        query = query.filter(models.Note.tag == tag)
    return query.all()


def get_note(db: Session, note_id: int):
    return db.query(models.Note).filter(models.Note.id == note_id).first()


def update_note(db: Session, note_id: int, note_update: schemas.NoteUpdate):
    db_note = get_note(db, note_id)
    if not db_note:
        return None
    data = note_update.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(db_note, field, value)
    db.commit()
    db.refresh(db_note)
    return db_note


def delete_note(db: Session, note_id: int) -> bool:
    db_note = get_note(db, note_id)
    if not db_note:
        return False
    db.delete(db_note)
    db.commit()
    return True


# ---------- Raw-SQL reporting endpoints ----------

def raw_tag_summary(db: Session):
    """Tags with MORE THAN 1 note, each with its note count. Raw SQL, GROUP BY + HAVING."""
    sql = text(
        """
        SELECT tag, COUNT(*) AS note_count
        FROM notes
        WHERE tag IS NOT NULL
        GROUP BY tag
        HAVING COUNT(*) > 1
        ORDER BY tag
        """
    )
    rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def raw_long_notes(db: Session):
    """Notes whose content length is above the average content length. Raw SQL subquery."""
    sql = text(
        """
        SELECT id, title, content, tag, owner_id
        FROM notes
        WHERE LENGTH(content) > (SELECT AVG(LENGTH(content)) FROM notes)
        ORDER BY id
        """
    )
    rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def raw_user_notes(db: Session):
    """Each user alongside their total note count. Raw SQL JOIN."""
    sql = text(
        """
        SELECT u.id AS user_id, u.name, u.email, COUNT(n.id) AS note_count
        FROM users u
        LEFT JOIN notes n ON n.owner_id = u.id
        GROUP BY u.id, u.name, u.email
        ORDER BY u.id
        """
    )
    rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]