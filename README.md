# RepoPilot AI — Intelligent Repository Intelligence & Codebase Search

[![Live Demo](https://img.shields.io/badge/Live_Demo-repopilot--green.vercel.app-0070f3?style=for-the-badge&logo=vercel)](https://repopilot-green.vercel.app/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16.3-black?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/Supabase-pgvector-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

> 🌐 **Live Production Application**: [https://repopilot-green.vercel.app/](https://repopilot-green.vercel.app/)  
> 💻 **GitHub Repository**: [https://github.com/RashmiAbeysekera/RepoPilot](https://github.com/RashmiAbeysekera/RepoPilot)

---

## 1. Why RepoPilot?

Navigating unfamiliar open-source codebases or large enterprise repositories is one of the biggest bottlenecks in software engineering:
- **High Onboarding Overhead**: Developers spend days tracing function calls, imports, and configuration flows just to find where core features live.
- **Context Window & Cost Limits**: Naively feeding an entire repository into commercial LLMs exceeds token windows, creates massive API bills, and causes hallucinations.
- **Security & Privacy Risks**: Dumping untrusted code without sanitization exposes applications to prompt injection attacks.

**RepoPilot AI solves this.** It ingests public GitHub repositories, computes semantic code embeddings locally (zero API fees for embedding), stores dense vectors in Supabase PostgreSQL with `pgvector`, and provides two complementary exploration interfaces powered by Google Gemini:
1. **Grounded RAG Question Answering**: Synthesizes natural-language answers strictly backed by cited, line-numbered source chunks.
2. **Autonomous Agentic Investigation**: Executes multi-step read-only codebase searches across file trees, file names, and regex snippets to answer deep architectural queries.

---

## 2. System Architecture

```
                                  USER BROWSER
                                        │
                                        ▼ HTTPS
                       ┌─────────────────────────────────┐
                       │      Next.js 16 (React 19)      │
                       │     Hosted on Vercel (Edge)     │
                       └────────────────┬────────────────┘
                                        │
                         REST API Calls │ (CORS Protected)
                                        ▼
                       ┌─────────────────────────────────┐
                       │     FastAPI Backend Service     │
                       │  Hosted on Render / Dockerized  │
                       └──────┬──────────┬─────────┬─────┘
                              │          │         │
           GitHub REST / Push │          │         │ Prompt & Context
                              ▼          │         ▼
         ┌─────────────────────────┐     │   ┌───────────────────────────┐
         │       GitHub API        │     │   │      Google Gemini API    │
         │ (Ingestion & Webhooks)  │     │   │ (gemini-3.5-flash / 2.5)  │
         └────────────┬────────────┘     │   └───────────────────────────┘
                      │                  │
        Event Trigger │                  ▼
                      ▼        ┌───────────────────┐
               ┌─────────────┐ │ Local Embedding   │ (all-MiniLM-L6-v2)
               │ n8n Engine  │ │ 384-dim Vectors   │ (In-Memory Batching)
               │ (Auto Sync) │ └─────────┬─────────┘
               └─────────────┘           │
                                         ▼ SQL / pgvector
                               ┌───────────────────┐
                               │     Supabase      │
                               │ PostgreSQL Engine │
                               │ (Vectors & Chunks)│
                               └───────────────────┘
```

### Ingestion & Search Data Flow
1. **Repository Ingestion**: User enters a GitHub URL -> Backend fetches files via GitHub REST API -> Filters binary files (`.png`, `.zip`, `.exe`) and enforces a 500 KB size limit.
2. **Sliding-Window Chunking**: Source files are chunked into 100-line segments with 20-line overlap, preserving file paths, line ranges, and SHA-256 content hashes.
3. **Local Vector Embeddings**: Chunks are embedded using `SentenceTransformers (all-MiniLM-L6-v2)` into 384-dimensional dense vectors with **zero external API calls**.
4. **pgvector Storage**: Vectors are persisted into PostgreSQL using the `pgvector` extension with cosine distance indexing (`<=>`).
5. **Grounded RAG / Agent**: User asks questions -> Question is embedded with the same model -> Top-K chunks retrieved (cosine similarity cutoff `≥ 0.20`) -> Passed into Gemini with prompt injection defense delimiters.

---

## 3. Key Features

- **⚡ Instant Repository Import**: Connects to public repositories via GitHub REST API without requiring git clones on disk.
- **🔍 Zero-Cost Semantic Code Search**: Uses local `SentenceTransformers` for embedding generation—no OpenAI/Gemini embedding API costs.
- **🛡️ Prompt Injection Defense**: Untrusted code chunks and system instructions are isolated with strict markdown boundaries (`=== REPOSITORY CONTEXT ===` and `=== USER QUESTION ===`).
- **📍 Source Traceability & Grounding**: Every AI response includes exact citations: file paths, line ranges, similarity scores, and source previews.
- **🤖 Autonomous Read-Only Agent**: An investigation agent with bounded iterations (max 5) that inspects directory trees, searches patterns, and reads specific lines.
- **🔄 Event-Driven Synchronization**: Automated re-indexing on git push via GitHub Webhooks (HMAC-SHA256 verified) and pre-built **n8n** workflow support.
- **🔒 Enterprise Security Guardrails**: Process-level secret scrubbing filter on logs, path traversal protection (`os.path.commonpath`), tenant repository isolation, and sliding-window rate limiting.
- **🐳 Docker Ready**: Multi-layer production Dockerfile with unprivileged non-root user (`repopilot`), layered dependency caching, and dynamic `$PORT` handling.

---

## 4. Technology Stack

| Layer | Technologies | Details / Purpose |
| :--- | :--- | :--- |
| **Frontend** | **Next.js 16**, **React 19**, **TypeScript**, **Tailwind CSS 4** | App Router, Turbopack, Lucide icons, dynamic status badges, responsive drawer layouts. |
| **Backend** | **Python 3.12**, **FastAPI**, **Uvicorn**, **Pydantic v2** | High-performance asynchronous REST API, structured error envelopes, request-ID tracing. |
| **Database & ORM** | **PostgreSQL (Supabase)**, **pgvector**, **SQLAlchemy 2.0**, **Alembic** | Relational data persistence with native vector similarity search (`<=>` cosine operator). |
| **Machine Learning** | **SentenceTransformers**, **PyTorch**, **Hugging Face** | Local `all-MiniLM-L6-v2` dense vector model (384 dimensions, zero embedding API fees). |
| **LLM & AI** | **Google Gemini API** (`google-genai` SDK), **gemini-3.5-flash** | Grounded code synthesis, prompt injection boundaries, and multi-turn agent tool loops. |
| **DevOps & Hosting** | **Vercel** (Frontend), **Render** (Backend), **Docker** | Edge CDN hosting for Next.js, cloud web service for FastAPI, multi-stage Linux container. |
| **Automation** | **GitHub Webhooks**, **n8n** | Event-driven continuous re-indexing upon default branch push events. |
| **Testing** | **Pytest**, **httpx TestClient**, **ESLint** | 140 automated backend tests (100% pass rate) covering chunking, RAG, agent tools, security, and health. |

---

## 5. Engineering Challenges & Solutions

### 1. Eliminating AI Hallucination in Codebases
- **Problem**: General-purpose LLMs hallucinate file names, outdated functions, and non-existent libraries when asked about unfamiliar code.
- **Solution**: Implemented strict grounding rules:
  - Enforced an empirical cosine similarity threshold (`RAG_SIMILARITY_THRESHOLD = 0.20`).
  - Gemini is explicitly instructed to respond with *"I couldn't find enough relevant information in the indexed repository"* when evidence is insufficient.
  - Every answer must reference specific line ranges from retrieved chunks.

### 2. High Cost & Latency of Embedding APIs
- **Problem**: Repositories contain tens of thousands of lines of code. Using commercial embedding APIs creates recurring costs and external network bottlenecks.
- **Solution**: Bundled local `all-MiniLM-L6-v2` SentenceTransformers into the backend. Generated embeddings run in-process using mini-batches with SHA-256 content hashes, skipping unchanged code chunks during re-syncs.

### 3. Agent Tool Safety & Directory Traversal
- **Problem**: An autonomous LLM agent with file inspection capabilities could attempt directory traversal (`../../etc/passwd`) or read private server files.
- **Solution**: Implemented strict read-only tool guardrails:
  - Bounded agent iterations (`MAX_AGENT_ITERATIONS = 5`).
  - Sanitized paths using `os.path.commonpath` to guarantee access never leaves the target repository boundary.
  - Zero write/execute tools exposed to the agent.

### 4. Zero Credential Leakage in Observability Logs
- **Problem**: Debug logs or stack traces can inadvertently output database connection strings or AI keys to standard output.
- **Solution**: Implemented a centralized `SecretScrubbingFilter` across the root logger that automatically redacts Supabase URLs, Google AI keys (`AIza...`), GitHub tokens (`ghp_...`), and Authorization headers before they reach stdout/stderr.

---

## 6. Project Structure

```
RepoPilot/
├── backend/                        # FastAPI Python Backend
│   ├── app/
│   │   ├── api/                    # REST endpoints (repositories, webhooks, health)
│   │   ├── core/                   # Config, database, security, logging, error envelopes
│   │   ├── models/                 # SQLAlchemy ORM models (repositories, files, chunks, embeddings)
│   │   ├── schemas/                # Pydantic request/response validation schemas
│   │   ├── services/               # Business logic (GitHub, chunking, embeddings, RAG, agent)
│   │   └── resources/              # Pre-built n8n workflow template
│   ├── tests/                      # 140 automated pytest tests
│   ├── Dockerfile                  # Production-grade multi-layer Dockerfile (non-root user)
│   ├── .dockerignore               # Security & build context filter
│   ├── requirements.txt            # Pinned dependencies
│   └── Procfile                    # Render production web process
├── frontend/                       # Next.js 16 TypeScript Frontend
│   ├── app/                        # Next.js App Router (layout, pages, styles)
│   ├── components/                 # UI components (RAG chat, Agent view, Repository explorer)
│   ├── lib/                        # API client, types, utility helpers
│   ├── package.json                # Dependencies & build scripts
│   └── vercel.json                 # Vercel deployment configuration
├── render.yaml                     # Render Infrastructure-as-Code blueprint
└── README.md                       # Project documentation
```

---

## 7. Getting Started (Local Development)

### Prerequisites
- Python 3.12+
- Node.js 20+ & npm
- PostgreSQL with `pgvector` extension (or a free [Supabase](https://supabase.com) project)
- [Google AI Studio](https://aistudio.google.com/) Gemini API Key

---

### Backend Setup

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file in the `backend/` directory based on `.env.example`:
   ```ini
   DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   FRONTEND_ORIGIN=http://localhost:3000
   PORT=8000
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-3.5-flash
   GITHUB_WEBHOOK_SECRET=your_optional_webhook_secret
   ```

5. **Start the development server**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   Interactive API documentation will be available at: `http://localhost:8000/docs`.

---

### Frontend Setup

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Configure local environment**:
   Create a `.env.local` file in `frontend/`:
   ```ini
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

4. **Start the development server**:
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 8. Docker Containerization

The backend includes a production-ready, security-hardened `Dockerfile` running Python 3.12 on Debian Bookworm slim.

### Build the Backend Image
```bash
docker build -t repopilot-backend:latest ./backend
```

### Run the Container
```bash
docker run -d \
  --name repopilot-backend-app \
  -p 8000:8000 \
  --env-file ./backend/.env \
  repopilot-backend:latest
```

### Verify Container Health
```bash
curl http://localhost:8000/api/health
```

### Stop & Remove
```bash
docker stop repopilot-backend-app && docker rm repopilot-backend-app
```

---

## 9. Automated Testing & Verification

RepoPilot enforces strict test-driven quality assurance:

```bash
# Run backend test suite (from repo root)
pytest backend/ -v
```

```
============================== test session starts ==============================
collected 140 items

backend/tests/test_health.py .........................                   [ 17%]
backend/tests/test_github_service.py .................                   [ 29%]
backend/tests/test_chunking.py .......................                   [ 45%]
backend/tests/test_embeddings.py .....................                   [ 60%]
backend/tests/test_rag.py ............................                   [ 80%]
backend/tests/test_agent.py ..........................                   [ 95%]
backend/tests/test_webhooks.py .......                                   [100%]

======================== 140 passed in 269.81s =========================
```

- **Frontend Lint & Build**:
  ```bash
  cd frontend
  npm run lint    # 0 errors, 0 warnings
  npm run build   # Static pages generated successfully via Turbopack
  ```

---

## 10. Live Deployment Architecture

- **Frontend**: Deployed on **Vercel Edge Network** with continuous delivery from GitHub `main`.
- **Backend API**: Deployed on **Render** (Python 3.12 web service with `/api/health` monitoring).
- **Database**: Managed **Supabase PostgreSQL** instance with `pgvector` indexing.
- **Continuous Ingestion**: GitHub Webhooks linked to an **n8n** webhook engine for push-triggered vector sync.

---

## 11. Author

**Rashmi Abeysekera**  
- **GitHub**: [@RashmiAbeysekera](https://github.com/RashmiAbeysekera)  
- **Live Demo**: [https://repopilot-green.vercel.app/](https://repopilot-green.vercel.app/)
