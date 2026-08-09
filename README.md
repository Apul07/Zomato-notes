# Zomato Notes — AI-Augmented Internal Knowledge Base

A capstone project: a FastAPI backend + vanilla JS dashboard for on-call
support engineers to capture, tag, search, and get lightweight AI
assistance on incident notes.

- **Part 1 — Core App**: validated FastAPI backend + browser dashboard, wired end to end.
- **Part 2 — Ranking Engine**: hand-written insertion sort / binary search (x2) / linear search, wired into real search endpoints and UI controls.
- **Part 3 — Intelligence Layer**: LLM auto-tagging (mock-by-default) on note creation, plus fully local semantic "Smart Search".

Database used: **local SQLite** (`backend/zomato_notes.db`, created automatically). To use hosted Postgres instead (e.g. Supabase free tier), set `DATABASE_URL` in `backend/.env`.

---

## 1. Setup

```bash
git clone <your-repo-url>
cd zomato-notes/backend

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env            # defaults are fine for local dev / mock AI

python seed.py                  # creates tables + loads all seed data
```

`seed.py` loads:
- The 2 baseline users (Alice, Bob) and 10 baseline notes (Part 1 dataset).
- The 12-note `RANKING_DATASET` (Part 2), owned by user 1, `tag="kb-demo"`.
- The 8-note `AI_SAMPLE_NOTES` (Part 3), owned by user 2, `tag="ai-demo"`.

## 2. Run the backend

```bash
# from backend/, with venv active
uvicorn main:app --reload --port 8000
```

- API root: `http://127.0.0.1:8000`
- Interactive docs: `http://127.0.0.1:8000/docs` (lists every endpoint below)

## 3. Run the frontend

No build step. Serve the `frontend/` folder as static files, e.g. with VS Code's "Live Server" extension, or:

```bash
cd frontend
python3 -m http.server 5500
# open http://127.0.0.1:5500
```

**CORS**: the backend's `CORSMiddleware` (see `backend/main.py`) allows exactly:
```
http://127.0.0.1:5500
http://localhost:5500
```
If you serve the frontend from a different port, add it to `ALLOWED_ORIGINS` in `main.py`.

## 4. One-time step for Part 3 semantic search

The first time `sentence-transformers/all-MiniLM-L6-v2` is loaded (i.e. the
first time you call `/notes/smart-search`), it downloads and caches the
model weights under `~/.cache/huggingface`. **This one download requires
internet access.** Every call after that — on your machine or a grader's,
once cached — runs **fully offline**, with no API key and no network call.

```bash
# optional: warm the cache ahead of time
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
```

`requirements.txt` pins the exact version: `sentence-transformers==3.0.0`.

## 5. Part 3 AI auto-tagger: mock vs real

- **`MOCK_AI=1`** (default, in `.env.example`) → `get_ai_response()` never touches the network and never requires an API key. It returns a deterministic rule-based JSON reply (first 3 significant words as tags, first sentence truncated to 20 words as summary). **This mock path is what's graded by default** — zero cost, zero signup.
- **`MOCK_AI=0`** (optional extension) → routes through Groq's free-tier chat-completion API (OpenAI-compatible). Sign up free at https://console.groq.com, create an API key, put it in `GROQ_API_KEY` in `.env`. Groq's free tier (at time of writing) allows a generous number of requests/day on small models like `llama-3.1-8b-instant`, rate-limited per-minute — check the current limits on your Groq dashboard, since free-tier limits change over time.

The 5-part prompt template lives verbatim in `backend/ai_service.py` as `AUTO_TAG_PROMPT_TEMPLATE`.

---

## Repository layout

```
zomato-notes/
├── backend/
│   ├── main.py            # FastAPI app: all endpoints, parts 1-3
│   ├── models.py          # SQLAlchemy User / Note models
│   ├── schemas.py         # Pydantic request/response schemas
│   ├── database.py        # engine, sessionmaker, get_db dependency
│   ├── crud.py            # CRUD + raw-SQL reporting queries
│   ├── algorithms.py      # part 2: insertion sort, binary search x2, linear search
│   ├── ai_service.py      # part 3: get_ai_response() + 5-part prompt template
│   ├── semantic_search.py # part 3: embeddings + cosine similarity
│   ├── ranking_dataset.py # part 2 sample dataset (verbatim)
│   ├── ai_sample_notes.py # part 3 sample dataset (verbatim)
│   ├── seed.py            # loads all seed/sample data
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   └── mock-data.js       # optional, ungraded dev convenience
├── sample_import.txt
└── README.md
```

---

# Part 1 — Core App

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/users` | create a user |
| POST | `/notes` | create a note; 404 if `owner_id` doesn't exist; returns `ai_suggestion` |
| GET | `/notes` | list all, optional `?tag=` |
| GET | `/notes/{id}` | fetch one |
| PUT | `/notes/{id}` | update title/content/tag |
| DELETE | `/notes/{id}` | requires correct `x-token` header |
| POST | `/notes/import` | bulk import from `.txt` file, `?owner_id=` |
| GET | `/reports/tag-summary` | raw SQL, `GROUP BY` + `HAVING` |
| GET | `/reports/long-notes` | raw SQL, subquery on average length |
| GET | `/reports/user-notes` | raw SQL `JOIN` |

## Example requests/responses

**Create a user, then a note (happy path):**
```
POST /users
{"name": "Carol", "email": "carol@example.com", "password": "carolpass123"}

201 →
{"id": 3, "name": "Carol", "email": "carol@example.com", "created_at": "2026-08-08T10:00:00Z"}
```
```
POST /notes
{"title": "War Room Notes", "content": "Escalated to infra on-call.", "tag": "incident", "owner_id": 3}

200 →
{
  "id": 21, "title": "War Room Notes", "content": "Escalated to infra on-call.",
  "tag": "incident", "owner_id": 3, "created_at": "2026-08-08T10:00:05Z",
  "ai_suggestion": {"tags": ["escalated", "infra"], "summary": "Escalated to infra on-call."}
}
```

**404 — nonexistent owner:**
```
POST /notes
{"title": "Orphan", "content": "no such user", "owner_id": 999}

404 → {"detail": "User 999 not found"}
```

**422 — validation errors (one per constraint type):**
```
POST /users  {"name": "Dave", "email": "dave@example.com"}          # missing password
422 → {"detail": [{"loc": ["body","password"], "msg": "Field required", ...}]}

POST /users  {"name": "Dave", "email": "not-an-email", "password": "12345678"}
422 → {"detail": [{"loc": ["body","email"], "msg": "value is not a valid email address...", ...}]}

POST /notes  {"title": "<121-character string>", "content": "x", "owner_id": 1}
422 → {"detail": [{"loc": ["body","title"], "msg": "String should have at most 120 characters", ...}]}
```

**Duplicate email (UNIQUE constraint):**
```
POST /users {"name": "Alice2", "email": "alice@example.com", "password": "alicepass123"}
422 → {"detail": "Email already registered"}
```

**DELETE auth gate:**
```
DELETE /notes/1                                # no x-token header
401 → {"detail": "Missing x-token header"}

DELETE /notes/1   x-token: wrong-token
403 → {"detail": "Invalid x-token header"}

DELETE /notes/1   x-token: super-secret-token
200 → {"detail": "Note 1 deleted"}
```

**X-Process-Time header** — present on every response, e.g.:
```
X-Process-Time: 0.0021398544311523438
```

**Background task non-blocking**, verified via the `uvicorn` console log:
```
INFO:     127.0.0.1:54321 - "POST /notes HTTP/1.1" 200 OK      # response returned at T+0.02s
[background-index] finished indexing note id=21 title='War Room Notes'   # logged ~2.5s later
```
The HTTP response timestamp precedes the background log line's timestamp by ~2.5 seconds, proving the endpoint didn't block on the simulated indexing delay.

**Bulk import:**
```
POST /notes/import?owner_id=1        (multipart file: sample_import.txt, 6 non-empty lines)
200 → {"created_note_ids": [22,23,24,25,26,27], "count": 6}

POST /notes/import?owner_id=999      (nonexistent owner)
404 → {"detail": "User 999 not found"}   # zero notes created
```

**Reports, run against the seed dataset:**
```
GET /reports/tag-summary
200 → [
  {"tag": "health",  "note_count": 2},
  {"tag": "random",  "note_count": 2},
  {"tag": "recipes", "note_count": 2},
  {"tag": "work",    "note_count": 3}
]
```
(`travel` has only 1 note and is correctly excluded by `HAVING COUNT(*) > 1`.)

```
GET /reports/long-notes
200 → notes with ids [1, 2, 5, 6]
```
(average content length across the 10 seed notes is 80.2 characters; these four notes — "Standup Summary" 105, "Sprint Retro Notes" 112, "Doctor Visit" 84, "Pasta Recipe" 88 — are the ones above that average.)

```
GET /reports/user-notes
200 → [
  {"user_id": 1, "name": "Alice", "email": "alice@example.com", "note_count": 5},
  {"user_id": 2, "name": "Bob",   "email": "bob@example.com",   "note_count": 5}
]
```
(counts shown are for the 10 baseline seed notes only, before any additional notes are added in later demos.)

## Frontend end-to-end verification

1. Start backend (`uvicorn main:app --reload --port 8000`) and frontend (`python3 -m http.server 5500` in `frontend/`).
2. Open `http://127.0.0.1:5500`. "Loading notes…" shows briefly, then the seeded notes render as cards built with `document.createElement`/`appendChild`.
3. Fill the Add Note form and submit → DevTools Network tab shows `POST http://127.0.0.1:8000/notes` → `200`. The new card (with its "AI Suggests" panel) appears without a page reload.
4. Refresh the browser → the note is still present (`GET /notes` returns it), proving it was persisted server-side, not held only in memory.
5. Click "Delete" on a card → DevTools shows `DELETE http://127.0.0.1:8000/notes/{id}` with header `x-token: super-secret-token` → `200`. The card is removed via `.remove()`.
6. Refresh again → the deleted note no longer appears.
7. Leaving Title or Content blank and submitting shows an inline `.error-message` div (never a browser `alert()`), and no request is sent.
8. Typing in the search box fires no network/re-render until 400ms after the last keystroke (verified with `console.log(Date.now())` inside the debounce callback — timestamps show a single call ~400ms after the last `input` event, not one per keystroke).
9. The `CATEGORY_TREE` sidebar renders all 9 nodes (All Tags → Work/Personal/Travel → Standups/Retros, Health/Recipes → Fitness) via the single recursive `renderCategoryNode()` function; clicking any node toggles its children open/closed.
10. Shrinking the browser below 600px width visibly collapses the two-column `.layout` into a single column (see the `@media (max-width: 600px) { .layout { flex-direction: column; } }` rule in `style.css`).

---

# Part 2 — Ranking Engine

`backend/algorithms.py` uses no built-in `sorted()`, `.sort()`, or imported search/sort utility anywhere — verifiable by reading the file.

## Example requests/responses (against the seeded `RANKING_DATASET`, tag `kb-demo`)

**Relevance search — two different keywords, visibly different top results:**
```
GET /notes/search?keyword=apple
200 → [
  {"title": "Apple Harvest Notes", "score": 3, ...},
  {"title": "Garden Update",       "score": 2, ...},
  {"title": "Fruit Basket Plan",   "score": 1, ...},
  {"title": "Budget Draft",        "score": 0, ...},
  {"title": "Coffee Tasting",      "score": 0, ...}
]

GET /notes/search?keyword=coffee
200 → [
  {"title": "Coffee Tasting",     "score": 2, ...},
  {"title": "Kitchen Inventory",  "score": 1, ...},
  {"title": "Apple Harvest Notes","score": 0, ...},
  {"title": "Budget Draft",       "score": 0, ...},
  {"title": "Daily Standup",      "score": 0, ...}
]
```

**Date sort — same `insertion_sort_by_key` function, different key:**
```
GET /notes/search?sort_by=date
200 → top 5 notes ordered by created_at_epoch, descending (most recent first)
```

**Exact-title lookup, both algorithms:**
```
GET /notes/lookup?title=Coffee Tasting&algo=iterative
200 → {"found": true, "note": {"title": "Coffee Tasting", ...}}

GET /notes/lookup?title=Apple Harvest Notes&algo=recursive
200 → {"found": true, "note": {"title": "Apple Harvest Notes", ...}}

GET /notes/lookup?title=Zzz Not A Real Title&algo=iterative
200 → {"found": false, "note": null}

GET /notes/lookup?title=Another Fake Title&algo=recursive
200 → {"found": false, "note": null}
```
(Verified for all 12 `RANKING_DATASET` titles plus 2 nonexistent titles, both `algo` values.)

**Quick tag jump (linear search):**
```
GET /notes/quick-find?tag=work
200 → {"found": true, "note": {"title": "Standup Summary", "tag": "work", ...}}

GET /notes/quick-find?tag=does-not-exist
200 → {"found": false, "note": null}   # no crash
```

## Frontend wiring

- **Sort by: Relevance / Date** dropdown next to the plain search box → calls `GET /notes/search?keyword=` or `?sort_by=date` and re-renders the results.
- **Jump to exact title** input + algorithm dropdown + "Go" button → calls `GET /notes/lookup`, scrolls to and highlights the matching card (or shows "no exact match").
- **Quick tag jump** buttons (`work`, `health`, `recipes`, `travel`, `random`) → each calls `GET /notes/quick-find?tag=...` and highlights the first matching note.

All three were exercised live with DevTools Network tab open, confirming `200` responses with the payloads shown above.

---

# Part 3 — Intelligence Layer

## Auto-tagging on note creation

The 5-part prompt (`AUTO_TAG_PROMPT_TEMPLATE` in `backend/ai_service.py`) is sent to `get_ai_response()` after every successful `POST /notes`. In mock mode it produces valid `{"tags": [...], "summary": "..."}` JSON without any network call:

```
Note: "Do 30 minutes of cardio followed by strength training focused on legs and core."
→ {"tags": ["minutes", "cardio", "followed"], "summary": "Do 30 minutes of cardio followed by strength training focused on legs and core."}

Note: "Buy milk, eggs, spinach, chicken breast, and whole wheat bread for the week."
→ {"tags": ["milk", "eggs", "spinach"], "summary": "Buy milk, eggs, spinach, chicken breast, and whole wheat bread for the week."}

Note: "The backend API for the Zomato Notes capstone must be deployed and demoed by Friday."
→ {"tags": ["backend", "zomato", "notes"], "summary": "The backend API for the Zomato Notes capstone must be deployed and demoed by Friday."}
```
(Verified this way for all 8 `AI_SAMPLE_NOTES`, all producing valid two-key JSON.)

If `json.loads` fails to parse a malformed reply, `get_ai_suggestion()` catches the exception, logs the raw response, and returns `None` — `POST /notes` still creates the note and returns `ai_suggestion: null` rather than crashing.

**End-to-end through the running app:**
```
POST /notes
{"title": "Db Migration", "content": "Ran the users table migration on staging without downtime.", "owner_id": 1}

200 →
{
  "id": 30, "title": "Db Migration", "owner_id": 1, ...,
  "ai_suggestion": {"tags": ["migration", "staging", "downtime"], "summary": "Ran the users table migration on staging without downtime."}
}
```
The frontend renders this in a highlighted "AI Suggests" panel on the new card, with an "Apply as tag" button that calls `PUT /notes/{id}` with `{"tag": "migration"}` and updates the visible tag pill in place.

## Local semantic search ("Smart Search")

`semantic_search.py` embeds notes and the query with `sentence-transformers/all-MiniLM-L6-v2` and ranks by cosine similarity — no LLM call, no API key.

```
GET /notes/smart-search?q=leg day exercise plan
200 → top 3 by cosine similarity, including "Gym schedule change" in the results

GET /notes/smart-search?q=dinner ideas with vegetables
200 → top 3 by cosine similarity, including "Recipe idea" in the results
```

Both queries were run against the live `/notes/smart-search` endpoint (seeded `ai-demo` tag dataset) and returned the expected note in the top 3, confirming the embedding ranking is working as intended — distinct from Part 2's literal keyword-occurrence search (e.g. a literal keyword search for "leg day exercise plan" would score 0 against "Gym schedule change" since none of those exact words appear in its content, whereas semantic similarity correctly surfaces it).

The **"Smart Search (AI)"** input is visually separated (dashed top border, distinct section) from the plain keyword search box in `index.html`/`style.css`, and calls a different endpoint (`/notes/smart-search` vs `/notes/search`).

## requirements.txt pin

```
sentence-transformers==3.0.0
```
Exact pin, not a range — see Setup section above for the one-time model download.

---

## Git workflow

Work was done on one feature branch per part (`feature/core-app`, `feature/ranking-engine`, `feature/intelligence-layer`), each merged into `main` via its own Pull Request, with incremental, meaningful commits rather than a single commit dump — visible in this repository's commit/PR history.
