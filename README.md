# RepoPilot AI

An AI-powered software engineering assistant that connects to public GitHub repositories, indexes source code, and helps developers understand unfamiliar codebases.

This is an incremental learning project — each day adds a new layer of full-stack software architecture.

---

## Project Status

**Day 4 — Persistent Repository File Storage and Ingestion**

The architecture persists discovered GitHub repository files directly into PostgreSQL:

```
GitHub Public Repository
       │
       ▼ GitHub REST API
FastAPI Ingestion Service
       │
       ▼ SQL Alchemy ORM & Idempotent Upsert
PostgreSQL / Supabase (repository_files table)
       │
       ▼ REST API
Next.js 16 UI (File Explorer & Code Viewer)
```

Users can import public GitHub repositories, ingest their source files into PostgreSQL with database-level uniqueness constraints, browse stored repository file trees in an interactive UI, and view source code/documentation contents directly in the web app.

> [!NOTE]
> **Important Disclaimer**: Day 4 does **NOT** implement RAG, vector embeddings, `pgvector`, code chunking, or Gemini AI endpoints. Those are planned for future phases.

---

## Database Architecture (Day 4)

### `Repository` → `RepositoryFile` One-to-Many Relationship

A single `Repository` record can own many `RepositoryFile` records.

```
repositories
---------------------------------
id (UUID)
name
full_name
github_url
default_branch

repository_files
---------------------------------
id (UUID)
repository_id (UUID, Foreign Key -> repositories.id, ON DELETE CASCADE)
path (e.g., "src/components/Login.jsx")
name (e.g., "Login.jsx")
extension (e.g., ".jsx")
size (bytes)
file_type ("source", "documentation", "configuration")
content (Text)
created_at (Timestamp)
updated_at (Timestamp)
```

### Database Uniqueness Constraint

To enforce database integrity, a unique constraint on `(repository_id, path)` prevents duplicate file records for the same repository. Re-running repository ingestion executes an idempotent upsert strategy (inserting new files, updating modified files, and deleting stale files transactionally).

---

## Current Endpoints & Features

- `GET  /api/health` — Backend process and PostgreSQL database health check
- `POST /api/repositories/import` — Import a public GitHub repository by URL
- `POST /api/repositories/{id}/ingest` — Ingest repository files and persist in PostgreSQL
- `GET  /api/repositories/{repository_id}/files` — List stored files for a repository (excluding large content body)
- `GET  /api/repositories/{repository_id}/files/{file_id}` — Retrieve a single stored file with full text content (with cross-repository access protection)
- `POST /api/repositories` — Add a repository manually
- `GET  /api/repositories` — List all saved repositories
- `GET  /api/repositories/{id}` — Get a repository by ID
- `DELETE /api/repositories/{id}` — Delete a repository (cascade deletes all stored files)

---

## File Ingestion & Safety Thresholds

### Supported Extensions
- Source: `.py`, `.js`, `.jsx`, `.ts`, `.tsx`, `.java`, `.c`, `.cpp`, `.h`, `.hpp`, `.html`, `.css`, `.sh`, `.sql`
- Documentation: `.md`, `.txt`, `.rst`
- Configuration: `.json`, `.yaml`, `.yml`, `.xml`, `.toml`

### Ignored Directories
- `.git`, `node_modules`, `dist`, `build`, `__pycache__`, `.next`, `coverage`, `vendor`, `.venv`, `.idea`, `.vscode`

### Ignored Extensions & Safety Limits
- Media & Binaries: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.mp4`, `.mp3`, `.pdf`, `.zip`, `.exe`, `.ico`, `.woff`, `.ttf`, `.tar`
- Max File Size: `500 KB` per file limit (oversized files are safely skipped without failing the ingestion run)
- Repository Cap: `200` file limit per repository ingestion run

---

## Future Features (Planned for Later Days)

The following features are **not yet implemented**:
- Code chunking & sliding window parsing
- Embeddings and vector search (`pgvector`)
- RAG (Retrieval-Augmented Generation) context assembly
- Gemini API integration for Q&A
- GitHub OAuth login & user management
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

Run the complete 39-test suite:

```bash
# From project root with venv active:
backend\venv\Scripts\pytest backend\tests\ -v
```
