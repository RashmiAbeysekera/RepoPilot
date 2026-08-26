# RepoPilot AI

An AI-powered software engineering assistant that connects to public GitHub repositories, indexes source code, and helps developers understand unfamiliar codebases.

This is an incremental learning project — each day adds a new layer of full-stack software architecture.

---

## Project Status

**Day 3 — GitHub Integration & Ingestion Foundation**

The architecture communicates directly with the public **GitHub REST API**:

```
Next.js 16 UI
    ↓  HTTP / REST
FastAPI Backend
    ├──► GitHub REST API (httpx client — metadata & file discovery)
    ↓  SQLAlchemy ORM
PostgreSQL / Supabase
```

Users can import public GitHub repositories by URL, fetch live repository metadata, inspect repository file trees, and analyze source code structure.

---

## Technology Explained

### Why GitHub REST API Integration?
RepoPilot needs real GitHub repository metadata (owner, repository name, description, default branch) and file tree contents so it can inspect and digest source code. Working directly with GitHub's REST API allows public repositories to be imported seamlessly without needing manual input.

### PostgreSQL & Supabase
PostgreSQL stores structured repository metadata. Supabase hosts the PostgreSQL database in the cloud.

### SQLAlchemy & Alembic
SQLAlchemy maps Python objects to PostgreSQL tables cleanly. Alembic manages database schema versions and migrations.

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
    services/
      github_service.py               Communicates with GitHub REST API
      repository_service.py           CRUD operations & GitHub import
      repository_ingestion_service.py File discovery, filtering & metrics
    api/           FastAPI route handlers
  alembic/         Database migration scripts
  tests/           33 pytest unit tests
    ↓
Supabase PostgreSQL
```

---

## Current Endpoints & Features

- `GET  /api/health` — Backend process and PostgreSQL database health check
- `POST /api/repositories/import` — Import a public GitHub repository by URL
- `POST /api/repositories/{id}/ingest` — Inspect file tree & count source vs ignored files
- `POST /api/repositories` — Add a repository manually
- `GET  /api/repositories` — List all saved repositories
- `GET  /api/repositories/{id}` — Get a repository by ID
- `DELETE /api/repositories/{id}` — Delete a repository

---

## File Ingestion Rules (Day 3)

### Supported Source Extensions
- Python (`.py`), JavaScript/TypeScript (`.js`, `.jsx`, `.ts`, `.tsx`)
- Systems & Web: `.java`, `.c`, `.cpp`, `.h`, `.hpp`, `.html`, `.css`
- Config & Data: `.json`, `.yaml`, `.yml`, `.md`, `.sql`, `.xml`, `.sh`

### Ignored Directories
- `.git`, `node_modules`, `dist`, `build`, `__pycache__`, `.next`, `coverage`, `vendor`, `.venv`

### Ignored Extensions
- Images/Media: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.mp4`, `.mp3`
- Documents/Archives: `.pdf`, `.zip`, `.exe`, `.ico`, `.woff`, `.ttf`, `.tar`

---

## Future Features (Planned for Later Days)

The following features are **not yet implemented**:
- GitHub OAuth login & user accounts
- Embeddings and vector search (`pgvector`)
- Chunking & RAG over source code
- Gemini API for AI-powered codebase Q&A
- Docker / Production deployment

---

## Running Locally

### 1. Backend Setup

```bash
cd backend

# Activate virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Database Migrations

```bash
alembic -c alembic.ini upgrade head
```

### 3. Start Backend Server

```bash
uvicorn app.main:app --reload
```
Runs at [http://localhost:8000](http://localhost:8000). Interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### 4. Start Frontend Server

```bash
cd frontend
npm run dev
```
Runs at [http://localhost:3000](http://localhost:3000).

---

## Running Tests

Run the complete 33-test suite:

```bash
# From project root with venv active:
backend\venv\Scripts\pytest backend\tests\ -v
```
