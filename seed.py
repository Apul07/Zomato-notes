"""
seed.py
Loads all seed/sample data into the database:
  - SEED_USERS / SEED_NOTES (Part 1 baseline dataset)
  - RANKING_DATASET (Part 2), as Notes owned by user 1, tag "kb-demo"
  - AI_SAMPLE_NOTES (Part 3), as Notes owned by user 2, tag "ai-demo"

Run with:  python seed.py
Re-running wipes and recreates all tables first, so it's always safe
to re-seed from a clean slate.
"""
from database import Base, SessionLocal, engine
from models import Note, User
from ranking_dataset import RANKING_DATASET
from ai_sample_notes import AI_SAMPLE_NOTES

SEED_USERS = [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "password": "alicepass123"},
    {"id": 2, "name": "Bob", "email": "bob@example.com", "password": "bobpass123"},
]

SEED_NOTES = [
    {"id": 1, "owner_id": 1, "title": "Standup Summary", "tag": "work",
     "content": "Discussed sprint progress, blockers on the payments API integration, and the plan for the demo on Friday."},
    {"id": 2, "owner_id": 1, "title": "Sprint Retro Notes", "tag": "work",
     "content": "Retro highlighted communication gaps between frontend and backend teams and agreed on daily syncs going forward."},
    {"id": 3, "owner_id": 2, "title": "One on One", "tag": "work",
     "content": "Quick check-in, no blockers, discussed career growth goals for next quarter."},
    {"id": 4, "owner_id": 1, "title": "Morning Run", "tag": "health",
     "content": "Ran 5km along the river trail before breakfast, felt great."},
    {"id": 5, "owner_id": 2, "title": "Doctor Visit", "tag": "health",
     "content": "Annual checkup went well, blood pressure normal, scheduled next visit in six months."},
    {"id": 6, "owner_id": 1, "title": "Pasta Recipe", "tag": "recipes",
     "content": "Boil pasta, saute garlic in olive oil, add tomatoes, basil, and a pinch of chili flakes."},
    {"id": 7, "owner_id": 2, "title": "Smoothie Recipe", "tag": "recipes",
     "content": "Blend banana, spinach, almond milk, and a spoon of peanut butter for breakfast."},
    {"id": 8, "owner_id": 1, "title": "Flight Booking", "tag": "travel",
     "content": "Booked a round trip flight for the December vacation, window seat confirmed."},
    {"id": 9, "owner_id": 2, "title": "Random Thought", "tag": "random",
     "content": "Maybe the library needs a better recommendation system based on reading history."},
    {"id": 10, "owner_id": 1, "title": "Quote To Remember", "tag": "random",
     "content": "Done is better than perfect, keep shipping."},
]


def seed():
    print("Dropping and recreating all tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Seeding users...")
        for u in SEED_USERS:
            db.add(User(id=u["id"], name=u["name"], email=u["email"], password=u["password"]))
        db.commit()

        print("Seeding baseline notes...")
        for n in SEED_NOTES:
            db.add(Note(id=n["id"], owner_id=n["owner_id"], title=n["title"],
                         tag=n["tag"], content=n["content"]))
        db.commit()

        next_id = 11  # continue autoincrement-friendly ids after the baseline 10

        print("Seeding Part 2 ranking dataset (owner_id=1, tag='kb-demo')...")
        for item in RANKING_DATASET:
            db.add(Note(id=next_id, owner_id=1, title=item["title"],
                         tag="kb-demo", content=item["content"]))
            next_id += 1
        db.commit()

        print("Seeding Part 3 AI sample notes (owner_id=2, tag='ai-demo')...")
        for item in AI_SAMPLE_NOTES:
            db.add(Note(id=next_id, owner_id=2, title=item["title"],
                         tag="ai-demo", content=item["content"]))
            next_id += 1
        db.commit()

        total_users = db.query(User).count()
        total_notes = db.query(Note).count()
        print(f"Done. Seeded {total_users} users and {total_notes} notes.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()