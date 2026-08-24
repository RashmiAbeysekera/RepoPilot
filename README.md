# RepoPilot AI

An AI-powered software engineering assistant that will eventually connect to
GitHub repositories, index source code, and help developers understand and
work with unfamiliar codebases.

## Project Status

**Day 1 — Foundation Setup**

Today's goal was to prove a working full-stack chain — frontend, backend,
and database — with no AI functionality yet.

## Current Architecture

```text
Next.js
   ↓
FastAPI
   ↓
PostgreSQL
```

The Next.js frontend calls the FastAPI backend over HTTP. The backend, in
turn, checks connectivity to a Supabase-hosted PostgreSQL database and
reports the combined status back to the frontend.

## Current Features

- Next.js (App Router) + React + TypeScript frontend
- FastAPI backend with automatic OpenAPI docs
- `GET /api/health` REST endpoint
- Frontend ↔ backend communication over `fetch()`
- PostgreSQL/Supabase connectivity check
- Environment variable configuration (`.env` / `.env.example`)
- Restricted CORS policy (no wildcard origins)
- Basic error handling on both frontend and backend

## Future Features

The following are **planned only** — none of them exist yet:

- GitHub OAuth and API integration
- Repository indexing and ingestion
- Retrieval-Augmented Generation (RAG) over source code
- Gemini-powered question answering with source-code references
- AI agents for multi-step codebase investigation
- Automated test case generation
- Pull request analysis and bug/risk identification
- Commit analysis and architecture summaries
- GitHub webhook–driven automated workflows
- Docker, CI/CD, and cloud deployment (Vercel / Cloud Run)

## Running Locally

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs at [http://localhost:3000](http://localhost:3000).

### Backend

```bash
cd backend
python -m venv venv
```

Activate the virtual environment:

```bash
# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

Install dependencies and run the server:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Runs at [http://localhost:8000](http://localhost:8000), with interactive
API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

## Environment Variables

Neither `.env` file is committed to Git. Copy the example files and fill
in real values locally.

**`backend/.env`** (copy from `backend/.env.example`)

| Variable          | Description                                   |
| ----------------- | ---------------------------------------------- |
| `DATABASE_URL`    | Supabase PostgreSQL connection string           |
| `FRONTEND_ORIGIN` | Frontend origin allowed by CORS (dev default: `http://localhost:3000`) |

**`frontend/.env.local`** (copy from `frontend/.env.local.example`)

| Variable              | Description                        |
| ---------------------- | ----------------------------------- |
| `NEXT_PUBLIC_API_URL`  | Base URL of the FastAPI backend    |

## Day 2 Preview

Day 2 will focus on GitHub connectivity: 
