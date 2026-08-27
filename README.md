# RepoPilot AI

An AI-powered software engineering assistant that connects to public GitHub repositories, indexes source code, and helps developers understand unfamiliar codebases.

This is an incremental learning project — each day adds a new layer of full-stack software architecture.

---

## Project Status

**Day 5 — Code Chunking & Derived Text Data Persistence**

The architecture divides stored source and documentation files into line-based chunks stored in PostgreSQL:

```
GitHub Public Repository
       │
       ▼ GitHub REST API
FastAPI Ingestion Service
       │
       ▼ SQL Alchemy ORM (repository_files table)
PostgreSQL / Supabase
       │
       ▼ Local Chunking Service (CHUNK_SIZE=100, CHUNK_OVERLAP=10)
PostgreSQL / Supabase (code_chunks table)
       │
       ▼ REST API
Next.js 16 UI (Chunk Explorer & Code Chunk Inspector)
```

### What is Code Chunking and Why RepoPilot Needs It?
Large source code and documentation files cannot fit into AI prompt contexts as single monolithic blocks without diluting relevance or exceeding token limits. Code chunking splits files into smaller, contiguous text segments with line number metadata (`start_line` and `end_line`), laying the groundwork for precise vector retrieval and RAG citations.

> [!NOTE]
> **Important Disclaimer**: Day 5 implements **purely local, line-based text chunking**. It does **NOT** call GitHub again during chunk generation, and does **NOT** implement vector embeddings, `pgvector`, RAG, Gemini LLM calls, or agent orchestration today.

---

## Database Architecture (Day 5)

### Database Schema Hierarchy

```
repositories
      │
      ▼ (one-to-many)
repository_files
      │
      ▼ (one-to-many)
code_chunks
```

### `CodeChunk` Model Fields

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key (`gen_random_uuid()`) |
| `repository_file_id` | UUID | Foreign Key -> `repository_files.id` (`ON DELETE CASCADE`) |
| `chunk_index` | Integer | 0-based position of the chunk in the file |
| `content` | Text | Actual text content of the chunk |
| `start_line` | Integer | 1-based start line in original file |
| `end_line` | Integer | 1-based end line in original file |
| `created_at` | DateTime | Timestamp with timezone |
| `updated_at` | DateTime | Timestamp with timezone |

---

## Chunking Strategy & Algorithm

- **Deterministic Line-Based Strategy**:
  - `CHUNK_SIZE_LINES = 100`
  - `CHUNK_OVERLAP_LINES = 10`
- **Rules**:
  - Empty files (`0` lines or whitespace-only) create `0` chunks.
  - Small files (`<= 100` lines) create `1` chunk spanning lines `1` to `N`.
  - Large files (`> 100` lines) create multiple overlapping chunks incrementing by `step = CHUNK_SIZE_LINES - CHUNK_OVERLAP_LINES = 90` lines.
- **Idempotent Regeneration**:
  Re-running chunk generation for a file or repository transactionally deletes existing chunks for those files before inserting new chunks, guaranteeing zero duplicate records.

---

## Current Endpoints & Features

- `GET  /api/health` — Backend process and PostgreSQL database health check
- `POST /api/repositories/import` — Import a public GitHub repository by URL
- `POST /api/repositories/{id}/ingest` — Ingest repository files and persist in PostgreSQL
- `GET  /api/repositories/{repository_id}/files` — List stored files for a repository
- `GET  /api/repositories/{repository_id}/files/{file_id}` — Retrieve a single stored file
- `POST /api/repositories/{repository_id}/chunks/generate` — Generate code chunks for all stored files in a repository
- `POST /api/repositories/{repository_id}/files/{file_id}/chunks/generate` — Generate code chunks for a single file
- `GET  /api/repositories/{repository_id}/chunks` — List chunk metadata for a repository
- `GET  /api/repositories/{repository_id}/chunks/{chunk_id}` — Retrieve full content for a single code chunk
- `POST /api/repositories` — Add a repository manually
- `GET  /api/repositories` — List all saved repositories
- `GET  /api/repositories/{id}` — Get a repository by ID
- `DELETE /api/repositories/{id}` — Delete a repository (cascade deletes files and chunks)

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

Run the complete 50-test suite:

```bash
# From backend directory with venv active:
venv\Scripts\python -m pytest
```
