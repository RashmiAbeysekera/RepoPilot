# RepoPilot AI

An AI-powered software engineering assistant that will eventually connect to
GitHub repositories, index source code, and help developers understand and
work with unfamiliar codebases.

This is an incremental learning project — each day adds a new layer of the
full-stack architecture.

---

## Project Status

**Day 2 — Repository Management**

The full-stack chain is working end-to-end:

```
Next.js UI
    ↓  HTTP / fetch
FastAPI backend
    ↓  SQLAlchemy ORM
PostgreSQL / Supabase
```

Users can add GitHub repository URLs, view saved repositories, and delete them.

---

## Technology Explained

### PostgreSQL
PostgreSQL is a relational database — it stores data in structured tables
with rows and columns, enforces data types, and supports relationships between
tables. We use Supabase to host our PostgreSQL database in the cloud so we
don't need to run a local database server.

### Supabase
Supabase is a hosted platform built on top of PostgreSQL. It gives us a
production-ready PostgreSQL database without any DevOps setup. We connect to
it using a standard PostgreSQL connection string (`DATABASE_URL`).

### SQLAlchemy
SQLAlchemy is a Python library for working with relational databases. Instead
of writing raw SQL strings by hand, we define Python classes (called "models")
that map to database tables. SQLAlchemy then generates the SQL for us. This
makes queries safer (protected from SQL injection), more readable, and easier
to maintain as the schema evolves.

### Alembic
Alembic is a database migration tool that works with SQLAlchemy. A "migration"
is a versioned script that changes the database schema (e.g. creating a table,
adding a column). Alembic can compare our Python models to the actual database
and auto-generate the migration scripts. This means we never manually write
`CREATE TABLE` SQL — we define the Python model, run Alembic, and it handles
the rest.

---

## Current Architecture

```
frontend/          Next.js 16 + React 19 + TypeScript
    ↓
backend/
  app/
    core/          Config + SQLAlchemy database layer
    models/        SQLAlchemy ORM models (repositories table)
    schemas/       Pydantic request/response validation
    services/      Business logic (CRUD operations)
    api/           FastAPI route handlers
  alembic/         Database migration scripts
  tests/           pytest test suite
    ↓
Supabase PostgreSQL
```

---

## Current Features

- `GET  /api/health` — backend + database health check
- `POST /api/repositories` — add a GitHub repository
- `GET  /api/repositories` — list all saved repositories
- `GET  /api/repositories/{id}` — get a repository by ID
- `DELETE /api/repositories/{id}` — delete a repository
- Duplicate URL detection (400 response with clear message)
- Frontend repository form and list UI
- Alembic migration for the `repositories` table
- 20 backend tests (all passing)

---

## Future Features (Not Yet Implemented)

The following are **planned only** — none of them exist yet:

- GitHub API integration (fetch real repo metadata)
- GitHub OAuth login
- Repository source code ingestion
- Embeddings and vector search (pgvector)
- Retrieval-Augmented Generation (RAG) over source code
- Gemini API for AI-powered Q&A
- AI agents for codebase investigation
- GitHub webhook integration
- Docker and production deployment

---

## Running Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Supabase project (or any PostgreSQL database)

---

### Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Copy the environment file and fill in your values:

```bash
cp .env.example .env
# Edit .env with your DATABASE_URL
```

> **Password note:** If your PostgreSQL password contains special characters
> like `@`, `#`, or `%`, you must URL-encode them in the connection string.
> For example: `@` → `%40`, `#` → `%23`

---

### Run Database Migrations

Alembic manages the database schema. Run this once to create the tables:

```bash
# From the backend/ directory
alembic -c alembic.ini upgrade head
```

This creates the `repositories` table in your PostgreSQL database.

To see current migration status:

```bash
alembic -c alembic.ini current
```

---

### Start the Backend

```bash
# From the backend/ directory (with venv active)
uvicorn app.main:app --reload
```

Runs at [http://localhost:8000](http://localhost:8000).
Interactive API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

---

### Frontend Setup

```bash
cd frontend
npm install
```

Copy the environment file:

```bash
cp .env.local.example .env.local
```

Start the development server:

```bash
npm run dev
```

Runs at [http://localhost:3000](http://localhost:3000).

---

## Environment Variables

Neither `.env` file is committed to Git. Copy the example files and fill in real values.

**`backend/.env`** (copy from `backend/.env.example`)

| Variable          | Description                                                              |
| ----------------- | ------------------------------------------------------------------------ |
| `DATABASE_URL`    | PostgreSQL connection string (URL-encode special characters in passwords) |
| `FRONTEND_ORIGIN` | Frontend origin for CORS (default: `http://localhost:3000`)              |

**`frontend/.env.local`** (copy from `frontend/.env.local.example`)

| Variable             | Description                      |
| -------------------- | -------------------------------- |
| `NEXT_PUBLIC_API_URL` | Base URL of the FastAPI backend |

---

## Running Tests

```bash
# From the project root (with backend venv active)
backend\venv\Scripts\pytest backend\tests\ -v
```

Or from within `backend/` with venv active:

```bash
pytest tests/ -v
```

---

## Git Commits (Day 2)

```
feat: add SQLAlchemy database architecture
feat: add repository model and migration
feat: add repository CRUD API
feat: add repository management UI
test: add repository API tests
docs: update RepoPilot setup documentation
```

