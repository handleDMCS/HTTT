---
name: rapid-prototyping
description: >
  Opinionated stack for hackathons and time-boxed sprints: FastAPI + uv (single file) + SQLite via SQLModel for the backend, vanilla HTML/CSS/JS in ./mock_frontend/ for the frontend. Trigger on any time pressure or demo context — "just get it working", "we have X hours", "MVP by end of day".
---

# Rapid Prototyping Skill

## Context

You are helping build a **functional prototype in a 24-hour hackathon**. The only goal is a working demo by the end of the sprint. Polish, scalability, and best practices are explicitly out of scope. Speed and clarity win.

---

## Project Idea

Before implementing features, read `IDEA.md` to understand the project idea and intended direction.

---

## Stack (non-negotiable)

| Layer    | Choice                          | Rationale                                  |
|----------|---------------------------------|--------------------------------------------|
| Backend  | **FastAPI** + **uv**            | Fast to write, fast to run, typed          |
| Database | **SQLite** via **SQLModel**     | Zero config, file-based, ORM+schema in one |
| Frontend | **Vanilla HTML + CSS + JS**     | Zero build step, instant iteration         |

Do not suggest React, TypeScript, Docker, auth systems, or any other abstraction unless the user explicitly asks. Every added layer is a liability in a hackathon.

---

## Project Structure

```
HTTT/
├── IDEA.md              # project idea, scope, and feature direction
├── backend/
│   ├── main.py          # entire backend: models, DB, routes
│   ├── db.sqlite3       # auto-created on first run
│   └── pyproject.toml
└── mock_frontend/
    ├── index.html       # main page
    └── *.html           # one file per additional mock page
```

Every file the user will edit lives at the top of one of these two directories. Nothing else.

---

## Backend Rules

- **One file only: `main.py`**. All routes, models, logic, and startup code go in this single file. No `routers/`, no `services/`, no `schemas/` subdirectory. This reduces friction and keeps everything visible at a glance.
- Use `uv` for package management. Provide a `pyproject.toml` (not `requirements.txt`).
- Enable CORS broadly (`allow_origins=["*"]`) — this is a prototype, not production.
- Use **SQLite + SQLModel** for persistence. DB file is `db.sqlite3` in the project root. Define all models and create tables at startup.
- Keep the code linear and readable. Avoid abstractions that obscure what the endpoint does.
- **Every function must have a docstring** in this exact format:
```python
"""
tl;dr: {purpose of the function}
input:
* arg_1: {description}
* arg_n: {description}
output:
* {what it returns}
"""
```
For functions with no arguments (e.g. startup hooks), omit the `input` block. For functions that return nothing, write `output: * None`.

**Minimal bootstrap:**
```bash
mkdir my-project && cd my-project
mkdir mock_frontend
uv init backend && cd backend
uv add fastapi uvicorn sqlmodel
uv run uvicorn main:app --reload
```

**`main.py` skeleton:**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Field, Session, SQLModel, create_engine, select
from typing import Optional

# --- DB setup ---
DATABASE_URL = "sqlite:///db.sqlite3"
engine = create_engine(DATABASE_URL)

# --- Models ---
class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

# --- App ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

@app.on_event("startup")
def on_startup():
    """
    tl;dr: Create all DB tables on startup if they don't exist yet.
    output:
    * None
    """
    SQLModel.metadata.create_all(engine)

# --- Routes ---
@app.get("/api/items")
def list_items():
    """
    tl;dr: Return all items from the database.
    output:
    * list of Item records
    """
    with Session(engine) as session:
        return session.exec(select(Item)).all()

@app.post("/api/items")
def create_item(item: Item):
    """
    tl;dr: Insert a new item into the database.
    input:
    * item: Item object with a name field
    output:
    * the created Item with its assigned id
    """
    with Session(engine) as session:
        session.add(item)
        session.commit()
        session.refresh(item)
        return item

# Mount frontend (keep last — catches all unmatched routes)
app.mount("/", StaticFiles(directory="../mock_frontend", html=True), name="frontend")
```

---

## Frontend Rules

- **Directory: `./mock_frontend/`** — all HTML files live here.
- **One file per page/view** — no bundler, no framework, no npm.
- **Bare-minimum UI**: a form, a list, a button. If it works, it's done. No animations, no responsiveness, no dark mode.
- Fetch data from the FastAPI backend via `fetch("/api/...")`.
- Inline `<style>` and `<script>` in each HTML file — no external `.css` or `.js` files unless there are more than ~100 lines of JS.

**`mock_frontend/index.html` skeleton:**
```html
<!DOCTYPE html>
<html>
<head>
  <title>Demo</title>
  <style>
    body { font-family: sans-serif; max-width: 600px; margin: 2rem auto; }
    button { padding: 0.5rem 1rem; cursor: pointer; }
    ul { padding: 0; list-style: none; }
    li { padding: 0.4rem 0; border-bottom: 1px solid #eee; }
  </style>
</head>
<body>
  <h1>App Name</h1>

  <form id="form">
    <input id="input" placeholder="Enter something" required />
    <button type="submit">Add</button>
  </form>

  <ul id="list"></ul>

  <script>
    async function load() {
      const res = await fetch('/api/items');
      const data = await res.json();
      document.getElementById('list').innerHTML =
        data.map(i => `<li>${i.name}</li>`).join('');
    }

    document.getElementById('form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const val = document.getElementById('input').value;
      await fetch('/api/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: val })
      });
      e.target.reset();
      load();
    });

    load();
  </script>
</body>
</html>
```

---

## What to Deliver (Checklist)

When the user describes a feature or app, produce:

- [ ] `backend/main.py` — complete and runnable, all backend logic inside
- [ ] `backend/pyproject.toml` — with all dependencies listed
- [ ] `mock_frontend/index.html` — and any additional pages needed
- [ ] A 3-line "How to run" block at the end of your response

**How to run (template):**
```bash
cd backend
uv run uvicorn main:app --reload
# Open http://localhost:8000
```

---

## Mindset

> "Does it demo? Ship it."

- If a feature is not needed for the demo, don't build it.
- If two approaches exist, pick the simpler one, always.
- Comments in code should explain *what* the block does, not *why* it's architected that way — there is no architecture.
- If the user asks for something complex (e.g., "add auth"), implement a stub that unblocks the demo (e.g., a hardcoded token check) and note it explicitly.
