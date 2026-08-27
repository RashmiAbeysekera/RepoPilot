# RepoPilot AI

An AI-powered software engineering assistant that connects to public GitHub repositories, indexes source code, and helps developers understand unfamiliar codebases.

This is an incremental learning project — each day adds a new layer of full-stack software architecture.

---

## Project Status

**Day 7 — Repository Semantic Search (Retrieval Engine)**

The architecture now allows natural language developer questions to be converted into 384-dimensional query vectors and searched against stored code chunk embeddings using `pgvector` distance queries in PostgreSQL:

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
       ▼ Local Embedding Model (all-MiniLM-L6-v2) + SHA-256 Hashing
PostgreSQL / Supabase (chunk_embeddings table + pgvector)
       ▲
       │
 User Question (e.g. "Where is authentication handled?")
       │
       ▼ Local Query Vector (all-MiniLM-L6-v2, 384-dim)
       │
       ▼ PostgreSQL + pgvector Cosine Distance Query (<=>)
 Top-K Relevant CodeChunks + Relevance Scores
       │
       ▼ REST API (POST /api/repositories/{id}/search)
Next.js 15 UI (🔍 Semantic Search Explorer)
```

> [!IMPORTANT]
> **Scope Disclaimer**: Day 7 is specifically about **RETRIEVAL**. It does **NOT** call Gemini LLM APIs, does **NOT** generate AI natural language answers, does **NOT** handle GitHub webhooks, and does **NOT** execute RAG agent orchestration yet. RAG/Gemini answer generation will be added in subsequent phases.

---

## What is Semantic Search & Why Does RepoPilot Need It?

### 1. Semantic Search vs. Keyword Search
- **Keyword Search**: Performs exact string matching. A query like `"verify user credentials"` will fail to find code containing `def check_login(user, pass):` because the exact words differ.
- **Semantic Search**: Translates both the developer's question and the repository code chunks into high-dimensional vector spaces. Vectors close to each other represent similar concepts. Thus, `"Where is authentication implemented?"` naturally retrieves `login.py` or `jwt.py` based on semantic meaning.

### 2. How Query Embeddings Are Generated
When a user submits a query:
1. The input string is normalized and validated.
2. The query is passed to the exact same local model (`SentenceTransformers("all-MiniLM-L6-v2")`) used to embed the repository chunks.
3. A 384-element float vector is produced representing the query's semantic meaning.

### 3. How pgvector Retrieves Similar Chunks & Cosine Distance
Vector similarity search is executed **100% inside PostgreSQL** using `pgvector`:
- **Distance Operator**: pgvector's `<=>` cosine distance operator measures the angle between vectors.
- **Distance to Similarity Formula**:
  $$\text{Cosine Similarity } S = 1.0 - d$$
  where $d$ is the cosine distance ($d \in [0, 2]$). Since `all-MiniLM-L6-v2` produces L2-normalized vectors (length = 1.0), Cosine Distance $d = 1.0 - \langle u, v \rangle$.
- The API converts distance to a bounded similarity score $S \in [0.0, 1.0]$ rounded to 4 decimals. A smaller distance $d$ yields a higher similarity score $S$.

### 4. What is Top-K?
`top_k` specifies the maximum number of most relevant chunks to return (default: `5`, range: `1` to `20`). This prevents overloading the client and ensures fast database response times.

### 5. Strict Repository Scoping
Every search query is explicitly scoped to a single `repository_id`:
```sql
SELECT code_chunks.*, chunk_embeddings.embedding <=> query_vector AS distance
FROM chunk_embeddings
JOIN code_chunks ON chunk_embeddings.code_chunk_id = code_chunks.id
JOIN repository_files ON code_chunks.repository_file_id = repository_files.id
WHERE repository_files.repository_id = :requested_repository_id
ORDER BY distance
LIMIT :top_k;
```
Searches in Repository A will **NEVER** return code chunks belonging to Repository B.

---

## Embedding Model & Specifications

- **Selected Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Vector Dimension**: `384`
- **License**: Apache 2.0 (100% free & local CPU execution)
- **Model Size**: ~80 MB

---

## Example API Request & Response

### Endpoint
`POST /api/repositories/{repository_id}/search`

### Request Body
```json
{
  "query": "Where is user authentication implemented?",
  "top_k": 5
}
```

### Response Body
```json
{
  "repository_id": "4e353f65-3db5-48fe-8f10-1ac8b14dc83d",
  "query": "Where is user authentication implemented?",
  "top_k": 5,
  "total_results": 1,
  "results": [
    {
      "chunk_id": "8f3b2c1a-5d4e-4f3a-9b1c-2d3e4f5a6b7c",
      "repository_file_id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
      "file_path": "backend/models/User.js",
      "chunk_index": 0,
      "start_line": 1,
      "end_line": 10,
      "content": "const mongoose = require('mongoose');\nconst userSchema = new mongoose.Schema({...});",
      "score": 0.8641
    }
  ]
}
```

---

## Endpoints & Features

- `GET  /api/health` — Backend process and PostgreSQL database health check
- `POST /api/repositories/import` — Import a public GitHub repository by URL
- `POST /api/repositories/{id}/ingest` — Ingest repository files and persist in PostgreSQL
- `GET  /api/repositories/{repository_id}/files` — List stored files for a repository
- `GET  /api/repositories/{repository_id}/files/{file_id}` — Retrieve a single stored file
- `POST /api/repositories/{repository_id}/chunks/generate` — Generate code chunks for stored files
- `GET  /api/repositories/{repository_id}/chunks` — List chunk metadata for a repository
- `POST /api/repositories/{repository_id}/embeddings/generate` — Generate 384-dim vector embeddings for chunks
- `GET  /api/repositories/{repository_id}/embeddings/status` — Get embedding coverage status
- `POST /api/repositories/{repository_id}/search` — **[NEW]** Vector similarity search over code chunks
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
Runs at [http://localhost:8000](http://localhost:8000). Interactive API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### 4. Start Frontend Server

```bash
cd frontend
npm run dev
```
Runs at [http://localhost:3000](http://localhost:3000).

---

## Running Tests

Run the full 66-test suite:

```bash
# From backend directory with venv active:
venv\Scripts\python -m pytest
```
