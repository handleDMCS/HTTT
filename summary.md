# Book Exchange Prototype Summary

Implemented a FastAPI + SQLite + vanilla frontend prototype for the book club exchange idea.

What is included:
- Member registration with 20 starting points.
- Courier volunteering for members who want to earn delivery points.
- Book catalog entries with title, genre, author, publication year, condition, owner, and exchange mode.
- Permanent exchange and loan flows with different point values.
- Transaction requests with direct pickup or courier delivery.
- Two-sided transaction confirmation before points are applied.
- Courier reward of +2 points when a courier delivery transaction completes.
- Demo seed button for quick sample data.

Files:
- `backend/main.py`: all models, database setup, API routes, point logic, and frontend mounting.
- `backend/pyproject.toml`: uv project dependencies.
- `mock_frontend/index.html`: one-page prototype UI.

How to run:
```bash
cd backend
uv run uvicorn main:app --reload
# Open http://localhost:8000
```
