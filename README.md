# RepoPilot AI

An AI-powered software engineering assistant that connects to public GitHub repositories, indexes source code, and helps developers understand unfamiliar codebases.

This is an incremental learning project — each day adds a new layer of full-stack software architecture.

---

## Project Status

**Day 6 — Vector Embedding Storage Pipeline (PostgreSQL + pgvector)**

The architecture transforms stored code chunks into 384-dimensional vector embeddings stored in PostgreSQL using `pgvector`:

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
       ▼ SentenceTransformers (all-MiniLM-L6-v2, 384-dim) + SHA-256 Hashing
PostgreSQL / Supabase (chunk_embeddings table + pgvector)
       │
       ▼ REST API
Next.js 16 UI (Vector Embedding Manager & Status Card)
```

---

## What Are Vector Embeddings & Why Does RepoPilot Need Them?

### 1. What is an Embedding?
An embedding converts raw code or documentation text (e.g. `"def authenticate_user(username, password): ..."`) into a dense list of floating-point numbers called a **vector** (e.g., `[0.012, -0.184, 0.721, ...]` across 384 dimensions).

### 2. What is Semantic Search?
Traditional keyword search looks for exact string matches (`"login"` won't match `"authenticate"`). **Semantic search** compares vectors mathematically (e.g., using cosine similarity) so that queries find relevant code chunks based on **meaning and intent**, even when exact keywords differ.

### 3. What is pgvector?
`pgvector` is an open-source vector similarity search extension for PostgreSQL. Storing embeddings directly in PostgreSQL eliminates the need for external vector databases (like Pinecone or Chroma), keeping the database architecture unified, reliable, and transactionally safe inside Supabase/PostgreSQL.

> [!NOTE]
> **Important Disclaimer**: Day 6 implements **local embedding generation and vector persistence**. It does **NOT** call Gemini LLM APIs, does **NOT** run RAG context assembly, and does **NOT** require paid API keys.

---

## Embedding Model & Specifications

- **Selected Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Vector Dimension**: `384`
- **License**: Apache 2.0 (100% free & local, no external API calls)
- **Model Size**: ~80 MB (runs efficiently on standard CPU)

---

## Database Architecture (Day 6)

### Schema Hierarchy

```
repositories
      │
      ▼ (one-to-many)
repository_files
      │
      ▼ (one-to-many)
code_chunks
      │
      ▼ (one-to-one)
chunk_embeddings (pgvector)
```

### `ChunkEmbedding` Model Fields

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key (`gen_random_uuid()`) |
| `code_chunk_id` | UUID | Foreign Key -> `code_chunks.id` (`ON DELETE CASCADE`, Unique) |
| `embedding` | Vector(384) | pgvector 384-dimensional vector column |
| `model_name` | String(100) | Name of model used (`"all-MiniLM-L6-v2"`) |
| `embedding_dimension` | Integer | Vector dimension (`384`) |
| `content_hash` | String(64) | SHA-256 hex hash of `CodeChunk.content` for idempotency |
| `created_at` | DateTime | Timestamp with timezone |
| `updated_at` | DateTime | Timestamp with timezone |

---

## Idempotency & Change Detection Strategy

Re-running embedding generation uses **SHA-256 content hashing**:
1. For each `CodeChunk`, compute `current_hash = sha256(chunk.content)`.
2. Check existing `ChunkEmbedding` record:
   - **Matching hash & model**: Skip regeneration (`embeddings_skipped`).
   - **Different hash (content updated)**: Regenerate vector and update row (`embeddings_updated`).
   - **No embedding record**: Generate vector and insert row (`embeddings_created`).

---

## Current Endpoints & Features

- `GET  /api/health` — Backend process and PostgreSQL database health check
- `POST /api/repositories/import` — Import a public GitHub repository by URL
- `POST /api/repositories/{id}/ingest` — Ingest repository files and persist in PostgreSQL
- `GET  /api/repositories/{repository_id}/files` — List stored files for a repository
- `GET  /api/repositories/{repository_id}/files/{file_id}` — Retrieve a single stored file
- `POST /api/repositories/{repository_id}/chunks/generate` — Generate code chunks for stored files
- `GET  /api/repositories/{repository_id}/chunks` — List chunk metadata for a repository
- `POST /api/repositories/{repository_id}/embeddings/generate` — Generate 384-dim vector embeddings for chunks
- `GET  /api/repositories/{repository_id}/embeddings/status` — Get embedding status (total chunks, embedded count, model, dimension)
- `POST /api/repositories` — Add a repository manually
- `GET  /api/repositories` — List all saved repositories
- `DELETE /api/repositories/{id}` — Delete a repository (cascade deletes files, chunks, and embeddings)

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

Run the complete 56-test suite:

```bash
# From backend directory with venv active:
venv\Scripts\python -m pytest
```
