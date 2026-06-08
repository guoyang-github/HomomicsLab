# HomomicsLab MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the "Agent Brain" core of HomomicsLab — task decomposition, multi-agent orchestration, TODO tracking, human-in-the-loop, and a basic dual-pane UI, with local execution capability.

**Architecture:** Layered hybrid architecture. Core Agent engine as a modular monolith (Python/FastAPI). Basic React dual-pane frontend. Skills runtime with sandboxed local execution. SQLite for MVP data persistence. Nextflow integration deferred to Phase 2.

**Tech Stack:** Python 3.10+, FastAPI, React 18 + TypeScript, Zustand, SQLite, Pydantic, pytest, pytest-asyncio

---

## Scope

This MVP plan implements the "Agent Brain First" strategy from the design spec. It covers:

1. **Project scaffolding** — Python backend, React frontend, shared types
2. **Agent Core Engine** — Intent analysis, task decomposition, orchestrator, state machine
3. **Multi-Agent collaboration** — Agent registry, message passing, simple agent types
4. **TODO tracking** — Task tree, status management, progress reporting
5. **Human-in-the-loop** — Checkpoint triggers, user request/response flow
6. **Context compression** — Working memory, relevance filtering, basic summarization
7. **Skills runtime** — Skill definition, sandboxed execution, builtin skills
8. **Basic dual-pane UI** — Chat panel, simple workspace canvas, real-time sync
9. **Project management** — Data upload, session management, simple reports
10. **Local deployment** — pip-installable, SQLite, local skill execution

**Deferred to Phase 2:**
- HPC/SLURM integration (Nextflow)
- Skills self-generation (Skills Forge)
- Skills self-evolution (Evolution Engine)
- Skills marketplace
- Vector database / semantic search
- Advanced visualizations (UMAP, heatmap components)
- Team collaboration / sharing
- Cloud deployment
- Kubernetes

---

## File Structure

```
homics-lab/
├── pyproject.toml                    # Python package config
├── README.md                         # Setup instructions
├── Makefile                          # Common dev commands
│
├── backend/                          # Python FastAPI backend
│   ├── homomics_lab/                 # Main package
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app entry
│   │   ├── config.py                 # Configuration (env vars, defaults)
│   │   │
│   │   ├── agent/                    # Agent core engine
│   │   │   ├── __init__.py
│   │   │   ├── intent_analyzer.py    # Intent analysis
│   │   │   ├── task_decomposer.py    # Task decomposition (PlannerAgent)
│   │   │   ├── orchestrator.py       # Task orchestration & state machine
│   │   │   ├── agent_registry.py     # Agent registration & discovery
│   │   │   ├── base_agent.py         # Base agent class
│   │   │   ├── bioinfo_agent.py      # Bioinformatics agent
│   │   │   ├── viz_agent.py          # Visualization agent
│   │   │   ├── experiment_agent.py   # Experiment design agent
│   │   │   └── message_bus.py        # Inter-agent messaging
│   │   │
│   │   ├── tasks/                    # Task & TODO management
│   │   │   ├── __init__.py
│   │   │   ├── models.py             # TaskNode, TaskStatus, Checkpoint
│   │   │   ├── task_tree.py          # Task tree construction & DAG
│   │   │   └── state_machine.py      # Task state transitions
│   │   │
│   │   ├── context/                  # Context & memory management
│   │   │   ├── __init__.py
│   │   │   ├── working_memory.py     # Working memory (current session)
│   │   │   ├── short_term_memory.py  # Short-term memory (session history)
│   │   │   ├── relevance_filter.py   # Relevance filtering
│   │   │   ├── summarizer.py         # Context summarization
│   │   │   └── prompter.py           # LLM prompt assembly
│   │   │
│   │   ├── skills/                   # Skills system
│   │   │   ├── __init__.py
│   │   │   ├── models.py             # Skill, SkillDefinition
│   │   │   ├── registry.py           # Skill registry & discovery
│   │   │   ├── runtime.py            # Skill execution runtime
│   │   │   ├── sandbox.py            # Sandboxed execution
│   │   │   └── builtin/              # Built-in skills
│   │   │       ├── __init__.py
│   │   │       ├── scanpy_qc.py
│   │   │       ├── scanpy_cluster.py
│   │   │       └── data_loader.py
│   │   │
│   │   ├── projects/                 # Project management
│   │   │   ├── __init__.py
│   │   │   ├── models.py             # Project, Session, Report
│   │   │   ├── manager.py            # Project CRUD
│   │   │   └── storage.py            # File storage abstraction
│   │   │
│   │   ├── api/                      # API routes
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # Main router
│   │   │   ├── chat.py               # Chat/WebSocket endpoints
│   │   │   ├── tasks.py              # Task management endpoints
│   │   │   ├── projects.py           # Project endpoints
│   │   │   ├── skills.py             # Skill endpoints
│   │   │   └── files.py              # File upload/download
│   │   │
│   │   ├── models/                   # Shared Pydantic models
│   │   │   ├── __init__.py
│   │   │   └── common.py             # Common types, enums
│   │   │
│   │   └── database/                 # Database layer
│   │       ├── __init__.py
│   │       ├── connection.py         # SQLite connection
│   │       ├── migrations/           # Alembic migrations
│   │       └── repositories/         # Data access layer
│   │
│   └── tests/                        # Backend tests
│       ├── __init__.py
│       ├── conftest.py               # pytest fixtures
│       ├── test_agent/
│       │   ├── test_intent_analyzer.py
│       │   ├── test_task_decomposer.py
│       │   ├── test_orchestrator.py
│       │   └── test_state_machine.py
│       ├── test_tasks/
│       │   └── test_task_tree.py
│       ├── test_context/
│       │   └── test_working_memory.py
│       ├── test_skills/
│       │   ├── test_runtime.py
│       │   └── test_sandbox.py
│       └── test_api/
│           └── test_chat.py
│
├── frontend/                         # React TypeScript frontend
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   │
│   ├── src/
│   │   ├── main.tsx                  # Entry point
│   │   ├── App.tsx                   # Root component
│   │   ├── config.ts                 # Frontend config
│   │   │
│   │   ├── components/               # UI components
│   │   │   ├── layout/
│   │   │   │   ├── Header.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── DualPane.tsx
│   │   │   ├── chat/
│   │   │   │   ├── ChatPanel.tsx
│   │   │   │   ├── MessageList.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── ChatInput.tsx
│   │   │   │   ├── TodoList.tsx
│   │   │   │   ├── HITLRequest.tsx
│   │   │   │   └── ToolCallCard.tsx
│   │   │   ├── workspace/
│   │   │   │   ├── Workspace.tsx
│   │   │   │   ├── FlowCanvas.tsx
│   │   │   │   ├── WorkflowNode.tsx
│   │   │   │   └── DetailPanel.tsx
│   │   │   └── shared/
│   │   │       ├── DataUploader.tsx
│   │   │       ├── ParameterForm.tsx
│   │   │       └── StatusBadge.tsx
│   │   │
│   │   ├── stores/                   # Zustand stores
│   │   │   ├── chatStore.ts
│   │   │   ├── workspaceStore.ts
│   │   │   ├── taskStore.ts
│   │   │   └── projectStore.ts
│   │   │
│   │   ├── hooks/                    # Custom hooks
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useTaskTree.ts
│   │   │   └── useFileUpload.ts
│   │   │
│   │   ├── types/                    # TypeScript types
│   │   │   ├── api.ts
│   │   │   ├── chat.ts
│   │   │   ├── tasks.ts
│   │   │   └── workspace.ts
│   │   │
│   │   ├── services/                 # API clients
│   │   │   ├── api.ts
│   │   │   ├── chatService.ts
│   │   │   ├── taskService.ts
│   │   │   └── projectService.ts
│   │   │
│   │   └── utils/                    # Utilities
│   │       ├── websocket.ts
│   │       └── formatters.ts
│   │
│   └── tests/                        # Frontend tests
│       ├── setup.ts
│       └── components/
│           └── ChatPanel.test.tsx
│
├── shared/                           # Shared types/contracts
│   └── types/
│       ├── index.ts
│       ├── agent.ts
│       ├── tasks.ts
│       ├── skills.ts
│       └── chat.ts
│
└── docs/                             # Documentation
    ├── setup.md
    └── architecture.md
```

---

## Milestones

| Milestone | Description | Estimated Tasks |
|-----------|-------------|-----------------|
| **M1: Foundation** | Project scaffolding, shared types, database layer | 1-8 |
| **M2: Agent Core** | Intent analysis, task decomposition, orchestrator | 9-18 |
| **M3: Task System** | Task tree, state machine, TODO tracking | 19-26 |
| **M4: Context & Memory** | Working memory, relevance filter, summarizer | 27-32 |
| **M5: Skills Runtime** | Skill registry, sandboxed execution, builtin skills | 33-40 |
| **M6: HITL** | Checkpoint triggers, user interaction flow | 41-46 |
| **M7: API Layer** | REST + WebSocket endpoints | 47-52 |
| **M8: Frontend Core** | React app, chat panel, state management | 53-62 |
| **M9: Workspace** | Workflow canvas, node visualization | 63-68 |
| **M10: Integration** | End-to-end flow, project management, local deployment | 69-76 |

---


## Tasks

### Task 1: Initialize Python Package

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `backend/homics_lab/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "homics-lab"
version = "0.1.0"
description = "A general-purpose agent for bioinformatics analysis"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    "aiosqlite>=0.19.0",
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.26.0",
    "python-multipart>=0.0.6",
    "aiofiles>=23.2.0",
]

[project.optional-dependencies]
dev = ["black", "ruff", "mypy"]

[project.scripts]
homics-lab = "homics_lab.cli:main"
```

- [ ] **Step 2: Create package init file**

```bash
mkdir -p backend/homics_lab
touch backend/homics_lab/__init__.py
echo '__version__ = "0.1.0"' > backend/homics_lab/__init__.py
```

- [ ] **Step 3: Create README with basic setup**

```markdown
# HomomicsLab

A general-purpose agent tool for bioinformatics.

## Development Setup

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Frontend
cd frontend
npm install
npm run dev
```
```

- [ ] **Step 4: Verify install**

Run: `cd backend && pip install -e "." && python -c "import homics_lab; print(homics_lab.__version__)"`
Expected: `0.1.0`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md backend/homics_lab/__init__.py
git commit -m "chore: initialize HomicsLab Python package"
```

---

### Task 2: Setup Configuration Module

**Files:**
- Create: `backend/homics_lab/config.py`
- Create: `backend/tests/__init__.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_config.py`:

```python
import os
from homics_lab.config import Settings

def test_default_port():
    settings = Settings()
    assert settings.port == 8080

def test_env_override():
    os.environ["HOMICS_PORT"] = "9000"
    settings = Settings()
    assert settings.port == 9000
    del os.environ["HOMICS_PORT"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: `ModuleNotFoundError: No module named 'homics_lab.config'`

- [ ] **Step 3: Implement config module**

Create `backend/homics_lab/config.py`:

```python
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "HomicsLab"
    port: int = 8080
    host: str = "0.0.0.0"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./homics_lab.db"
    data_dir: Path = Path("./data")
    skills_dir: Path = Path("./skills")
    
    class Config:
        env_prefix = "HOMICS_"


settings = Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: 2 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/config.py backend/tests/test_config.py backend/tests/__init__.py
git commit -m "feat: add configuration module with pydantic-settings"
```

---

### Task 3: Define Shared Pydantic Models

**Files:**
- Create: `backend/homics_lab/models/__init__.py`
- Create: `backend/homics_lab/models/common.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_models.py`:

```python
from homics_lab.models.common import (
    TaskStatus, MessageType, AgentType, HITLTrigger
)

def test_task_status_values():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.COMPLETED.value == "completed"

def test_hitl_triggers():
    assert HITLTrigger.LOW_CONFIDENCE.value == "low_confidence"
    assert HITLTrigger.HIGH_COST.value == "high_cost"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_models.py -v`
Expected: ImportError

- [ ] **Step 3: Implement shared models**

Create `backend/homics_lab/models/__init__.py`:
```python
from .common import *
```

Create `backend/homics_lab/models/common.py`:

```python
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_HUMAN = "awaiting_human"
    ABORTED = "aborted"


class MessageType(str, Enum):
    TEXT = "text"
    TODO_LIST = "todo_list"
    HITL_REQUEST = "hitl_request"
    TOOL_CALL = "tool_call"
    RESULT_PREVIEW = "result_preview"
    PARAMETER_FORM = "parameter_form"
    FILE_REFERENCE = "file_reference"
    ERROR = "error"
    SYSTEM = "system"


class AgentType(str, Enum):
    PLANNER = "planner"
    BIOINFO = "bioinfo"
    VIZ = "viz"
    EXPERIMENT = "experiment"
    QA = "qa"
    REPORT = "report"


class HITLTrigger(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    HIGH_COST = "high_cost"
    HIGH_RISK = "high_risk"
    POLICY = "policy"
    ANOMALY = "anomaly"


class Option(BaseModel):
    id: str
    label: str
    description: Optional[str] = None


class HITLCheckpoint(BaseModel):
    id: str
    trigger_reason: HITLTrigger
    context_summary: str
    options: list[Option]
    default_option: Optional[Option] = None
    timeout_minutes: int = 60 * 24


class ChatMessage(BaseModel):
    id: str
    type: MessageType = MessageType.TEXT
    content: Any
    sender: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    task_id: Optional[str] = None
    skill_id: Optional[str] = None
    related_files: list[str] = Field(default_factory=list)


class AgentMessage(BaseModel):
    from_agent: str
    to_agent: Optional[str] = None
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_models.py -v`
Expected: 2 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/models/ backend/tests/test_models.py
git commit -m "feat: add shared Pydantic models for tasks, messages, agents"
```

---

### Task 4: Setup SQLite Database Layer

**Files:**
- Create: `backend/homics_lab/database/__init__.py`
- Create: `backend/homics_lab/database/connection.py`
- Test: `backend/tests/test_database.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_database.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from homics_lab.database.connection import async_engine, get_async_session


@pytest.mark.asyncio
async def test_database_connection():
    async with async_engine.connect() as conn:
        result = await conn.exec_driver_sql("SELECT 1")
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_get_session():
    async for session in get_async_session():
        assert isinstance(session, AsyncSession)
        break
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_database.py -v`
Expected: ImportError

- [ ] **Step 3: Implement database connection**

Create `backend/homics_lab/database/__init__.py`:
```python
from .connection import async_engine, get_async_session
```

Create `backend/homics_lab/database/connection.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from homics_lab.config import settings


async_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_async_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_database.py -v`
Expected: 2 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/database/ backend/tests/test_database.py
git commit -m "feat: add async SQLite database connection"
```

---

### Task 5: Create FastAPI Application Entry

**Files:**
- Create: `backend/homics_lab/main.py`
- Test: `backend/tests/test_main.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_main.py`:

```python
from fastapi.testclient import TestClient
from homics_lab.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_app_info():
    response = client.get("/")
    assert response.status_code == 200
    assert "HomicsLab" in response.json()["name"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_main.py -v`
Expected: ImportError

- [ ] **Step 3: Implement FastAPI app**

Create `backend/homics_lab/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from homics_lab.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.skills_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"name": settings.app_name, "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_main.py -v`
Expected: 2 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/main.py backend/tests/test_main.py
git commit -m "feat: add FastAPI application entry with health endpoint"
```

---

### Task 6: Setup Frontend React Project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "homics-lab-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "zustand": "^4.5.0",
    "@tanstack/react-query": "^5.18.0",
    "axios": "^1.6.0",
    "socket.io-client": "^4.7.0",
    "reactflow": "^11.10.0",
    "tailwindcss": "^3.4.0",
    "clsx": "^2.1.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vitest": "^1.2.0"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Also create `frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 3: Create vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true,
      },
    },
  },
})
```

- [ ] **Step 4: Create index.html and React entry**

`frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>HomicsLab</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/src/main.tsx`:
```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

`frontend/src/App.tsx`:
```tsx
function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-blue-600 p-4 text-white">
        <h1 className="text-xl font-bold">HomicsLab</h1>
      </header>
      <main className="p-4">
        <p>Welcome to HomicsLab</p>
      </main>
    </div>
  )
}

export default App
```

- [ ] **Step 5: Install dependencies and verify**

Run:
```bash
cd frontend
npm install
npm run build
```
Expected: Build succeeds with no errors

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "chore: initialize React + TypeScript + Vite frontend"
```

---

### Task 7: Setup Tailwind CSS

**Files:**
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/index.css`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Create Tailwind config files**

`frontend/tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#2563eb',
        success: '#16a34a',
        warning: '#eab308',
        error: '#dc2626',
      },
    },
  },
  plugins: [],
}
```

`frontend/postcss.config.js`:
```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

`frontend/src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  font-family: 'Inter', system-ui, sans-serif;
}

code, pre {
  font-family: 'JetBrains Mono', monospace;
}
```

- [ ] **Step 2: Import index.css in main.tsx**

Modify `frontend/src/main.tsx`:
```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

- [ ] **Step 3: Update App.tsx to use Tailwind classes**

Modify `frontend/src/App.tsx`:
```tsx
function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-primary p-4 text-white">
        <h1 className="text-xl font-bold">HomicsLab</h1>
      </header>
      <main className="p-4">
        <div className="rounded-lg bg-white p-6 shadow">
          <h2 className="text-lg font-semibold text-slate-800">Welcome to HomicsLab</h2>
          <p className="mt-2 text-slate-600">Your bioinformatics AI assistant</p>
        </div>
      </main>
    </div>
  )
}

export default App
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "chore: setup Tailwind CSS with custom theme"
```

---

### Task 8: Create Makefile for Common Commands

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create Makefile**

```makefile
.PHONY: install dev test lint format clean

install:
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

dev-backend:
	cd backend && uvicorn homics_lab.main:app --reload --port 8080

dev-frontend:
	cd frontend && npm run dev

test-backend:
	cd backend && pytest -v

test-frontend:
	cd frontend && npm test -- --run

lint-backend:
	cd backend && ruff check .
	cd backend && mypy homics_lab

format:
	cd backend && black .
	cd backend && ruff check . --fix

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "node_modules" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	rm -f backend/homics_lab.db
```

- [ ] **Step 2: Verify Makefile commands work**

Run: `make test-backend`
Expected: All current backend tests pass

Run: `make test-frontend`
Expected: No tests yet, command succeeds

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: add Makefile for common development commands"
```

---

## Milestone 1 Complete ✅

At this point you have:
- Python package with FastAPI, config, shared models, database connection
- React frontend with Vite, TypeScript, Tailwind CSS
- Makefile for common dev tasks
- Health endpoint tested

Next: Build the Agent Core engine.


## Milestone 2: Agent Core Engine

### Task 9: Create Base Agent Class

**Files:**
- Create: `backend/homics_lab/agent/__init__.py`
- Create: `backend/homics_lab/agent/base_agent.py`
- Test: `backend/tests/test_agent/test_base_agent.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_agent/test_base_agent.py`:

```python
import pytest
from homics_lab.agent.base_agent import BaseAgent
from homics_lab.models.common import AgentMessage


class TestAgent(BaseAgent):
    agent_type = "test"
    
    async def run(self, task, context):
        return {"result": f"processed {task.name}"}


@pytest.mark.asyncio
async def test_base_agent_run():
    agent = TestAgent()
    task = type("Task", (), {"name": "test_task"})()
    result = await agent.run(task, {})
    assert result["result"] == "processed test_task"

def test_agent_can_handle():
    agent = TestAgent()
    assert agent.can_handle("test") is True
    assert agent.can_handle("other") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent/test_base_agent.py -v`
Expected: ImportError

- [ ] **Step 3: Implement base agent class**

Create `backend/homics_lab/agent/base_agent.py`:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from homics_lab.models.common import AgentMessage, AgentType


class BaseAgent(ABC):
    agent_type: AgentType = None
    capabilities: List[str] = []
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.agent_type
    
    def can_handle(self, task_type: str) -> bool:
        return task_type in self.capabilities
    
    @abstractmethod
    async def run(self, task: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's core logic for a given task."""
        pass
    
    async def review(self, task: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        """Optional review step. Override for QA agents."""
        return {"approved": True, "feedback": None}
    
    def send_message(self, to_agent: str, content: str) -> AgentMessage:
        return AgentMessage(
            from_agent=self.name,
            to_agent=to_agent,
            content=content,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent/test_base_agent.py -v`
Expected: 2 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/agent/ backend/tests/test_agent/
git commit -m "feat: add BaseAgent abstract class with messaging support"
```

---

### Task 10: Create Agent Registry

**Files:**
- Create: `backend/homics_lab/agent/agent_registry.py`
- Test: `backend/tests/test_agent/test_agent_registry.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_agent/test_agent_registry.py`:

```python
import pytest
from homics_lab.agent.agent_registry import AgentRegistry
from homics_lab.agent.base_agent import BaseAgent
from homics_lab.models.common import AgentType


class FakeBioinfoAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = ["qc", "clustering"]


class FakeVizAgent(BaseAgent):
    agent_type = AgentType.VIZ
    capabilities = ["plot"]


@pytest.fixture
def registry():
    reg = AgentRegistry()
    reg.register(FakeBioinfoAgent())
    reg.register(FakeVizAgent())
    return reg


def test_register_agent(registry):
    assert len(registry.list_agents()) == 2

def test_get_agent_by_type(registry):
    agent = registry.get_agent(AgentType.BIOINFO)
    assert agent.agent_type == AgentType.BIOINFO

def test_find_agent_for_task(registry):
    agent = registry.find_agent_for_task("qc")
    assert agent.agent_type == AgentType.BIOINFO
    
    agent = registry.find_agent_for_task("plot")
    assert agent.agent_type == AgentType.VIZ
    
    agent = registry.find_agent_for_task("unknown")
    assert agent is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent/test_agent_registry.py -v`
Expected: ImportError

- [ ] **Step 3: Implement agent registry**

Create `backend/homics_lab/agent/agent_registry.py`:

```python
from typing import Dict, List, Optional, Type
from homics_lab.agent.base_agent import BaseAgent
from homics_lab.models.common import AgentType


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[AgentType, BaseAgent] = {}
    
    def register(self, agent: BaseAgent) -> None:
        if agent.agent_type is None:
            raise ValueError("Agent must have an agent_type")
        self._agents[agent.agent_type] = agent
    
    def get_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        return self._agents.get(agent_type)
    
    def list_agents(self) -> List[BaseAgent]:
        return list(self._agents.values())
    
    def find_agent_for_task(self, task_type: str) -> Optional[BaseAgent]:
        for agent in self._agents.values():
            if agent.can_handle(task_type):
                return agent
        return None
    
    def reset(self) -> None:
        self._agents.clear()


_registry = AgentRegistry()

def get_default_registry() -> AgentRegistry:
    return _registry
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent/test_agent_registry.py -v`
Expected: 3 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/agent/agent_registry.py backend/tests/test_agent/test_agent_registry.py
git commit -m "feat: add agent registry for task-to-agent routing"
```

---

### Task 11: Implement Intent Analyzer

**Files:**
- Create: `backend/homics_lab/agent/intent_analyzer.py`
- Test: `backend/tests/test_agent/test_intent_analyzer.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_agent/test_intent_analyzer.py`:

```python
import pytest
from homics_lab.agent.intent_analyzer import IntentAnalyzer, UserIntent


@pytest.fixture
def analyzer():
    return IntentAnalyzer()


@pytest.mark.asyncio
async def test_detect_single_cell_analysis(analyzer):
    intent = await analyzer.analyze("帮我分析这组单细胞数据")
    assert intent.analysis_type == "single_cell_analysis"
    assert intent.complexity == "complex"


@pytest.mark.asyncio
async def test_detect_simple_task(analyzer):
    intent = await analyzer.analyze("把文件转换成 h5ad 格式")
    assert intent.analysis_type == "file_conversion"
    assert intent.complexity == "single_step"


@pytest.mark.asyncio
async def test_detect_qa(analyzer):
    intent = await analyzer.analyze("什么是 UMAP？")
    assert intent.analysis_type == "qa"
    assert intent.complexity == "direct_response"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent/test_intent_analyzer.py -v`
Expected: ImportError

- [ ] **Step 3: Implement intent analyzer**

Create `backend/homics_lab/agent/intent_analyzer.py`:

```python
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class UserIntent:
    analysis_type: str
    complexity: str  # direct_response, single_step, complex
    data_scale: Optional[str] = None
    urgency: str = "normal"
    domain_knowledge: list[str] = None
    
    def __post_init__(self):
        if self.domain_knowledge is None:
            self.domain_knowledge = []


class IntentAnalyzer:
    """Rule-based intent analyzer (LLM-enhanced in Phase 2)."""
    
    SINGLE_CELL_KEYWORDS = [
        "单细胞", "single cell", "scRNA", "10x", "scanpy", "seurat",
        "PBMC", "细胞", "cell"
    ]
    
    SPATIAL_KEYWORDS = [
        "空间", "spatial", "visium", "xenium", "merfish"
    ]
    
    CONVERSION_KEYWORDS = [
        "转换", "convert", "格式", "format", "变成", "转成"
    ]
    
    QA_KEYWORDS = [
        "什么是", "什么是", "how to", "怎么", "如何", "explain"
    ]
    
    COMPLEX_KEYWORDS = [
        "分析", "analysis", "流程", "pipeline", "全流程", "完整"
    ]
    
    async def analyze(self, message: str) -> UserIntent:
        text = message.lower()
        
        # Determine analysis type
        if any(kw in text for kw in self.SINGLE_CELL_KEYWORDS):
            analysis_type = "single_cell_analysis"
        elif any(kw in text for kw in self.SPATIAL_KEYWORDS):
            analysis_type = "spatial_analysis"
        elif any(kw in text for kw in self.CONVERSION_KEYWORDS):
            analysis_type = "file_conversion"
        elif any(kw in text for kw in self.QA_KEYWORDS):
            analysis_type = "qa"
        else:
            analysis_type = "general"
        
        # Determine complexity
        if analysis_type == "qa":
            complexity = "direct_response"
        elif analysis_type == "file_conversion":
            complexity = "single_step"
        elif any(kw in text for kw in self.COMPLEX_KEYWORDS):
            complexity = "complex"
        else:
            complexity = "single_step"
        
        # Extract data scale hint
        data_scale = self._extract_data_scale(text)
        
        return UserIntent(
            analysis_type=analysis_type,
            complexity=complexity,
            data_scale=data_scale,
        )
    
    def _extract_data_scale(self, text: str) -> Optional[str]:
        patterns = [
            r'(\d+)\s*个细胞',
            r'(\d+)\s*cells',
            r'(\d+)k\s*cells',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent/test_intent_analyzer.py -v`
Expected: 3 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/agent/intent_analyzer.py backend/tests/test_agent/test_intent_analyzer.py
git commit -m "feat: add rule-based intent analyzer for bioinformatics queries"
```

---

### Task 12: Implement Task Decomposer

**Files:**
- Create: `backend/homics_lab/agent/task_decomposer.py`
- Test: `backend/tests/test_agent/test_task_decomposer.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_agent/test_task_decomposer.py`:

```python
import pytest
from homics_lab.agent.task_decomposer import TaskDecomposer
from homics_lab.agent.intent_analyzer import UserIntent


@pytest.fixture
def decomposer():
    return TaskDecomposer()


@pytest.mark.asyncio
async def test_decompose_single_cell_pipeline(decomposer):
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
    )
    
    tree = await decomposer.decompose(intent, context={"sample_count": 1})
    
    task_names = [t.name for t in tree.tasks]
    assert "quality_control" in task_names
    assert "dimensionality_reduction" in task_names
    assert "clustering" in task_names
    assert "cell_annotation" in task_names


@pytest.mark.asyncio
async def test_decompose_file_conversion(decomposer):
    intent = UserIntent(
        analysis_type="file_conversion",
        complexity="single_step",
    )
    
    tree = await decomposer.decompose(intent, context={})
    
    assert len(tree.tasks) == 1
    assert tree.tasks[0].name == "convert_file"


@pytest.mark.asyncio
async def test_task_dependencies(decomposer):
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
    )
    
    tree = await decomposer.decompose(intent, context={})
    
    # Clustering should depend on dimensionality_reduction
    cluster_task = next(t for t in tree.tasks if t.name == "clustering")
    dr_task = next(t for t in tree.tasks if t.name == "dimensionality_reduction")
    assert dr_task.id in cluster_task.dependencies
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent/test_task_decomposer.py -v`
Expected: ImportError

- [ ] **Step 3: Implement task decomposer**

Create `backend/homics_lab/agent/task_decomposer.py`:

```python
import uuid
from typing import Any, Dict, List
from homics_lab.agent.intent_analyzer import UserIntent
from homics_lab.models.common import AgentType
from homics_lab.tasks.models import TaskNode


class TaskTree:
    def __init__(self, tasks: List[TaskNode] = None):
        self.tasks = tasks or []
    
    def get_task(self, task_id: str) -> TaskNode:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"Task {task_id} not found")
    
    def topological_sort(self) -> List[TaskNode]:
        """Return tasks in dependency order."""
        completed = set()
        result = []
        
        def can_schedule(task: TaskNode) -> bool:
            return all(dep in completed for dep in task.dependencies)
        
        pending = list(self.tasks)
        while pending:
            progress = False
            for task in pending[:]:
                if can_schedule(task):
                    result.append(task)
                    completed.add(task.id)
                    pending.remove(task)
                    progress = True
            
            if not progress and pending:
                raise ValueError("Cyclic dependency detected in task tree")
        
        return result


class TaskDecomposer:
    """Decomposes user intent into executable task trees."""
    
    SINGLE_CELL_PIPELINE = [
        {
            "name": "quality_control",
            "description": "Filter low-quality cells and genes",
            "phase": "preprocessing",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_qc"],
        },
        {
            "name": "dimensionality_reduction",
            "description": "Compute PCA on normalized data",
            "phase": "analysis",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_pca"],
            "dependencies": ["quality_control"],
        },
        {
            "name": "clustering",
            "description": "Compute neighbors and UMAP embedding",
            "phase": "analysis",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_cluster"],
            "dependencies": ["dimensionality_reduction"],
            "hitl": ["n_neighbors", "resolution"],
        },
        {
            "name": "cell_annotation",
            "description": "Annotate cell clusters with marker genes",
            "phase": "analysis",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_annotation"],
            "dependencies": ["clustering"],
        },
        {
            "name": "differential_expression",
            "description": "Find marker genes for each cluster",
            "phase": "analysis",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_de"],
            "dependencies": ["cell_annotation"],
        },
        {
            "name": "visualization",
            "description": "Generate UMAP plots and heatmaps",
            "phase": "reporting",
            "agent": AgentType.VIZ,
            "skills": ["plot_umap", "plot_heatmap"],
            "dependencies": ["clustering", "cell_annotation"],
        },
    ]
    
    async def decompose(self, intent: UserIntent, context: Dict[str, Any]) -> TaskTree:
        if intent.analysis_type == "single_cell_analysis" and intent.complexity == "complex":
            return self._build_single_cell_pipeline(context)
        elif intent.analysis_type == "file_conversion":
            return self._build_single_step("convert_file", "Convert file format", ["data_loader"])
        elif intent.analysis_type == "qa":
            return self._build_single_step("answer_question", "Answer user question", [])
        else:
            return self._build_single_step(
                "general_analysis",
                f"General {intent.analysis_type} analysis",
                ["data_loader"],
            )
    
    def _build_single_cell_pipeline(self, context: Dict[str, Any]) -> TaskTree:
        tasks = []
        id_map = {}
        
        for step in self.SINGLE_CELL_PIPELINE:
            task_id = str(uuid.uuid4())[:8]
            id_map[step["name"]] = task_id
            
            dependencies = [
                id_map[dep] for dep in step.get("dependencies", [])
                if dep in id_map
            ]
            
            task = TaskNode(
                id=task_id,
                name=step["name"],
                description=step["description"],
                phase=step["phase"],
                agent_assignment=step["agent"],
                skills_required=step["skills"],
                dependencies=dependencies,
            )
            tasks.append(task)
        
        return TaskTree(tasks)
    
    def _build_single_step(self, name: str, description: str, skills: List[str]) -> TaskTree:
        task = TaskNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            phase="execution",
            skills_required=skills,
        )
        return TaskTree([task])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent/test_task_decomposer.py -v`
Expected: 3 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/agent/task_decomposer.py backend/tests/test_agent/test_task_decomposer.py
git commit -m "feat: add task decomposer for single-cell pipeline and simple tasks"
```

---

### Task 13: Define Task Data Models

**Files:**
- Create: `backend/homics_lab/tasks/__init__.py`
- Create: `backend/homics_lab/tasks/models.py`
- Test: `backend/tests/test_tasks/test_task_models.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_tasks/test_task_models.py`:

```python
from homics_lab.tasks.models import TaskNode, TaskStatus, RetryPolicy
from homics_lab.models.common import HITLTrigger


def test_task_node_defaults():
    task = TaskNode(id="t1", name="test", description="test task")
    assert task.status == TaskStatus.PENDING
    assert task.dependencies == []
    assert task.skills_required == []


def test_retry_policy_defaults():
    policy = RetryPolicy()
    assert policy.max_attempts == 3
    assert policy.backoff_seconds == 2.0


def test_task_with_hitl():
    task = TaskNode(
        id="t2",
        name="clustering",
        description="cluster cells",
        hitl_checkpoints=[{
            "trigger_reason": HITLTrigger.POLICY,
            "context_summary": "Please confirm clustering parameters",
            "options": [{"id": "default", "label": "Use defaults"}],
        }],
    )
    assert len(task.hitl_checkpoints) == 1
    assert task.hitl_checkpoints[0].trigger_reason == HITLTrigger.POLICY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_tasks/test_task_models.py -v`
Expected: ImportError

- [ ] **Step 3: Implement task models**

Create `backend/homics_lab/tasks/__init__.py`:
```python
from .models import TaskNode, TaskStatus, RetryPolicy
from .task_tree import TaskTree
```

Create `backend/homics_lab/tasks/models.py`:

```python
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from homics_lab.models.common import HITLCheckpoint, TaskStatus


class RetryPolicy(BaseModel):
    max_attempts: int = 3
    backoff_seconds: float = 2.0
    retry_on: List[str] = Field(default_factory=lambda: ["timeout", "transient_error"])


class TaskNode(BaseModel):
    id: str
    name: str
    description: str
    phase: str = "execution"
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = Field(default_factory=list)
    agent_assignment: Optional[str] = None
    skills_required: List[str] = Field(default_factory=list)
    hitl_checkpoints: List[HITLCheckpoint] = Field(default_factory=list)
    estimated_duration_minutes: int = 10
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempt_count: int = 0


class TaskTreeSnapshot(BaseModel):
    """Serializable snapshot of a task tree for persistence."""
    project_id: str
    session_id: str
    tasks: List[TaskNode]
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_tasks/test_task_models.py -v`
Expected: 3 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/tasks/ backend/tests/test_tasks/
git commit -m "feat: add TaskNode and RetryPolicy models"
```

---

### Task 14: Implement Task State Machine

**Files:**
- Create: `backend/homics_lab/tasks/state_machine.py`
- Test: `backend/tests/test_tasks/test_state_machine.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_tasks/test_state_machine.py`:

```python
import pytest
from homics_lab.tasks.models import TaskNode, TaskStatus
from homics_lab.tasks.state_machine import TaskStateMachine, TransitionError


@pytest.fixture
def sm():
    return TaskStateMachine()


def test_pending_to_running(sm):
    task = TaskNode(id="t1", name="test", description="test")
    sm.transition(task, TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING

def test_running_to_completed(sm):
    task = TaskNode(id="t1", name="test", description="test")
    task.status = TaskStatus.RUNNING
    sm.transition(task, TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED

def test_invalid_transition_raises(sm):
    task = TaskNode(id="t1", name="test", description="test")
    task.status = TaskStatus.COMPLETED
    with pytest.raises(TransitionError):
        sm.transition(task, TaskStatus.RUNNING)

def test_awaiting_human_transition(sm):
    task = TaskNode(id="t1", name="test", description="test")
    task.status = TaskStatus.RUNNING
    sm.transition(task, TaskStatus.AWAITING_HUMAN)
    assert task.status == TaskStatus.AWAITING_HUMAN
    
    sm.transition(task, TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_tasks/test_state_machine.py -v`
Expected: ImportError

- [ ] **Step 3: Implement state machine**

Create `backend/homics_lab/tasks/state_machine.py`:

```python
from datetime import datetime
from typing import Set
from homics_lab.tasks.models import TaskNode, TaskStatus


class TransitionError(ValueError):
    pass


class TaskStateMachine:
    """Manages valid transitions between task statuses."""
    
    VALID_TRANSITIONS: dict[TaskStatus, Set[TaskStatus]] = {
        TaskStatus.PENDING: {
            TaskStatus.RUNNING,
            TaskStatus.AWAITING_HUMAN,
            TaskStatus.ABORTED,
        },
        TaskStatus.RUNNING: {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.AWAITING_HUMAN,
            TaskStatus.ABORTED,
        },
        TaskStatus.AWAITING_HUMAN: {
            TaskStatus.RUNNING,
            TaskStatus.ABORTED,
        },
        TaskStatus.FAILED: {
            TaskStatus.RUNNING,
            TaskStatus.ABORTED,
        },
        TaskStatus.COMPLETED: set(),
        TaskStatus.ABORTED: set(),
    }
    
    def can_transition(self, task: TaskNode, new_status: TaskStatus) -> bool:
        return new_status in self.VALID_TRANSITIONS.get(task.status, set())
    
    def transition(self, task: TaskNode, new_status: TaskStatus) -> None:
        if not self.can_transition(task, new_status):
            raise TransitionError(
                f"Invalid transition from {task.status.value} to {new_status.value}"
            )
        
        task.status = new_status
        
        if new_status == TaskStatus.RUNNING and task.started_at is None:
            task.started_at = datetime.utcnow()
        
        if new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.ABORTED):
            task.completed_at = datetime.utcnow()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_tasks/test_state_machine.py -v`
Expected: 4 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/tasks/state_machine.py backend/tests/test_tasks/test_state_machine.py
git commit -m "feat: add task state machine with validation and timestamps"
```

---

### Task 15: Implement Orchestrator

**Files:**
- Create: `backend/homics_lab/agent/orchestrator.py`
- Test: `backend/tests/test_agent/test_orchestrator.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_agent/test_orchestrator.py`:

```python
import pytest
from homics_lab.agent.orchestrator import Orchestrator
from homics_lab.agent.agent_registry import AgentRegistry
from homics_lab.agent.base_agent import BaseAgent
from homics_lab.agent.task_decomposer import TaskTree
from homics_lab.models.common import AgentType, TaskStatus
from homics_lab.tasks.models import TaskNode


class FakeBioinfoAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = ["scanpy_qc"]
    
    async def run(self, task, context):
        return {"output_file": "qc_result.h5ad"}


@pytest.fixture
def orchestrator():
    registry = AgentRegistry()
    registry.register(FakeBioinfoAgent())
    return Orchestrator(registry=registry)


@pytest.mark.asyncio
async def test_orchestrator_can_run_task(orchestrator):
    tree = TaskTree([
        TaskNode(id="t1", name="quality_control", description="QC", skills_required=["scanpy_qc"]),
    ])
    
    result = await orchestrator.run_tree(tree)
    
    assert result["t1"]["output_file"] == "qc_result.h5ad"
    task = tree.get_task("t1")
    assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_orchestrator_respects_dependencies(orchestrator):
    tree = TaskTree([
        TaskNode(id="t1", name="step1", description="step 1", skills_required=["scanpy_qc"]),
        TaskNode(id="t2", name="step2", description="step 2", skills_required=["scanpy_qc"], dependencies=["t1"]),
    ])
    
    result = await orchestrator.run_tree(tree)
    
    assert "t1" in result
    assert "t2" in result
    assert tree.get_task("t1").status == TaskStatus.COMPLETED
    assert tree.get_task("t2").status == TaskStatus.COMPLETED


def test_orchestrator_progress(orchestrator):
    tree = TaskTree([
        TaskNode(id="t1", name="step1", description="step 1"),
        TaskNode(id="t2", name="step2", description="step 2", dependencies=["t1"]),
    ])
    
    progress = orchestrator.get_progress(tree)
    assert progress["total"] == 2
    assert progress["pending"] == 2
    assert progress["completed"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent/test_orchestrator.py -v`
Expected: ImportError

- [ ] **Step 3: Implement orchestrator**

Create `backend/homics_lab/agent/orchestrator.py`:

```python
from typing import Any, Dict
from homics_lab.agent.agent_registry import AgentRegistry, get_default_registry
from homics_lab.agent.task_decomposer import TaskTree
from homics_lab.models.common import TaskStatus
from homics_lab.tasks.models import TaskNode
from homics_lab.tasks.state_machine import TaskStateMachine


class Orchestrator:
    """Central task scheduler and executor."""
    
    def __init__(self, registry: AgentRegistry = None):
        self.registry = registry or get_default_registry()
        self.state_machine = TaskStateMachine()
    
    async def run_tree(self, tree: TaskTree, context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        results = {}
        completed = set()
        
        for task in tree.topological_sort():
            # Check dependencies are satisfied
            if not all(dep in completed for dep in task.dependencies):
                raise ValueError(f"Dependencies not satisfied for task {task.id}")
            
            # Transition to running
            self.state_machine.transition(task, TaskStatus.RUNNING)
            
            try:
                # Find agent for this task
                agent = self._resolve_agent(task)
                
                if agent is None:
                    raise RuntimeError(f"No agent found for task {task.name}")
                
                # Execute task
                result = await agent.run(task, context)
                results[task.id] = result
                task.result = result
                
                # Transition to completed
                self.state_machine.transition(task, TaskStatus.COMPLETED)
                completed.add(task.id)
                
            except Exception as e:
                task.error_message = str(e)
                task.attempt_count += 1
                
                if task.attempt_count < task.retry_policy.max_attempts:
                    self.state_machine.transition(task, TaskStatus.FAILED)
                    # In a real system, retry with backoff
                    raise  # For MVP, just raise
                else:
                    self.state_machine.transition(task, TaskStatus.FAILED)
                    raise
        
        return results
    
    def _resolve_agent(self, task: TaskNode):
        """Find the best agent for a task."""
        # First try by explicit assignment
        if task.agent_assignment:
            agent = self.registry.get_agent(task.agent_assignment)
            if agent:
                return agent
        
        # Then try by required skills
        for skill in task.skills_required:
            agent = self.registry.find_agent_for_task(skill)
            if agent:
                return agent
        
        return None
    
    def get_progress(self, tree: TaskTree) -> Dict[str, int]:
        total = len(tree.tasks)
        by_status = {
            "total": total,
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "awaiting_human": 0,
        }
        
        for task in tree.tasks:
            if task.status == TaskStatus.PENDING:
                by_status["pending"] += 1
            elif task.status == TaskStatus.RUNNING:
                by_status["running"] += 1
            elif task.status == TaskStatus.COMPLETED:
                by_status["completed"] += 1
            elif task.status == TaskStatus.FAILED:
                by_status["failed"] += 1
            elif task.status == TaskStatus.AWAITING_HUMAN:
                by_status["awaiting_human"] += 1
        
        by_status["percent"] = int((by_status["completed"] / total) * 100) if total > 0 else 0
        return by_status
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent/test_orchestrator.py -v`
Expected: 3 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/agent/orchestrator.py backend/tests/test_agent/test_orchestrator.py
git commit -m "feat: add task orchestrator with dependency resolution and progress tracking"
```

---

### Task 16: Implement Simple Bioinfo and Viz Agents

**Files:**
- Create: `backend/homics_lab/agent/bioinfo_agent.py`
- Create: `backend/homics_lab/agent/viz_agent.py`
- Create: `backend/homics_lab/agent/experiment_agent.py`
- Test: `backend/tests/test_agent/test_specialized_agents.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_agent/test_specialized_agents.py`:

```python
import pytest
from homics_lab.agent.bioinfo_agent import BioinfoAgent
from homics_lab.agent.viz_agent import VizAgent
from homics_lab.agent.experiment_agent import ExperimentAgent
from homics_lab.models.common import AgentType


@pytest.mark.asyncio
async def test_bioinfo_agent():
    agent = BioinfoAgent()
    task = type("Task", (), {"name": "qc", "skills_required": ["scanpy_qc"], "parameters": {}})()
    result = await agent.run(task, {})
    assert result["agent_type"] == AgentType.BIOINFO
    assert "executed" in result["message"]


@pytest.mark.asyncio
async def test_viz_agent():
    agent = VizAgent()
    task = type("Task", (), {"name": "umap", "skills_required": ["plot_umap"], "parameters": {}})()
    result = await agent.run(task, {})
    assert result["agent_type"] == AgentType.VIZ


@pytest.mark.asyncio
async def test_experiment_agent():
    agent = ExperimentAgent()
    task = type("Task", (), {"name": "protocol", "skills_required": ["protocol_design"], "parameters": {}})()
    result = await agent.run(task, {})
    assert result["agent_type"] == AgentType.EXPERIMENT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent/test_specialized_agents.py -v`
Expected: ImportError

- [ ] **Step 3: Implement specialized agents**

Create `backend/homics_lab/agent/bioinfo_agent.py`:

```python
from typing import Any, Dict
from homics_lab.agent.base_agent import BaseAgent
from homics_lab.models.common import AgentType


class BioinfoAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = [
        "scanpy_qc",
        "scanpy_pca",
        "scanpy_cluster",
        "scanpy_annotation",
        "scanpy_de",
        "data_loader",
    ]
    
    async def run(self, task: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "task": task.name,
            "skills": task.skills_required,
            "message": f"BioinfoAgent executed {task.name}",
            "output": context.get("input_data"),
        }
```

Create `backend/homics_lab/agent/viz_agent.py`:

```python
from typing import Any, Dict
from homics_lab.agent.base_agent import BaseAgent
from homics_lab.models.common import AgentType


class VizAgent(BaseAgent):
    agent_type = AgentType.VIZ
    capabilities = ["plot_umap", "plot_heatmap", "plot_violin"]
    
    async def run(self, task: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "task": task.name,
            "plot_type": task.skills_required[0] if task.skills_required else "unknown",
            "message": f"VizAgent generated visualization for {task.name}",
        }
```

Create `backend/homics_lab/agent/experiment_agent.py`:

```python
from typing import Any, Dict
from homics_lab.agent.base_agent import BaseAgent
from homics_lab.models.common import AgentType


class ExperimentAgent(BaseAgent):
    agent_type = AgentType.EXPERIMENT
    capabilities = ["protocol_design", "primer_design"]
    
    async def run(self, task: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "task": task.name,
            "message": f"ExperimentAgent designed experiment for {task.name}",
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent/test_specialized_agents.py -v`
Expected: 3 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/agent/bioinfo_agent.py backend/homics_lab/agent/viz_agent.py backend/homics_lab/agent/experiment_agent.py backend/tests/test_agent/test_specialized_agents.py
git commit -m "feat: add specialized bioinfo, viz, and experiment agents"
```

---

### Task 17: Implement Agent Message Bus

**Files:**
- Create: `backend/homics_lab/agent/message_bus.py`
- Test: `backend/tests/test_agent/test_message_bus.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_agent/test_message_bus.py`:

```python
import pytest
from homics_lab.agent.message_bus import MessageBus
from homics_lab.models.common import AgentMessage


@pytest.fixture
def bus():
    return MessageBus()


@pytest.mark.asyncio
async def test_send_and_receive(bus):
    await bus.send(AgentMessage(from_agent="a", to_agent="b", content="hello"))
    messages = await bus.get_messages_for("b")
    assert len(messages) == 1
    assert messages[0].content == "hello"


@pytest.mark.asyncio
async def test_broadcast(bus):
    await bus.broadcast(AgentMessage(from_agent="a", to_agent=None, content="all"))
    messages = await bus.get_all_messages()
    assert len(messages) == 1
    assert messages[0].content == "all"


@pytest.mark.asyncio
async def test_clear_messages(bus):
    await bus.send(AgentMessage(from_agent="a", to_agent="b", content="hello"))
    await bus.clear("b")
    messages = await bus.get_messages_for("b")
    assert len(messages) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent/test_message_bus.py -v`
Expected: ImportError

- [ ] **Step 3: Implement message bus**

Create `backend/homics_lab/agent/message_bus.py`:

```python
from collections import defaultdict
from typing import Dict, List
from homics_lab.models.common import AgentMessage


class MessageBus:
    """In-memory message bus for inter-agent communication."""
    
    def __init__(self):
        self._inboxes: Dict[str, List[AgentMessage]] = defaultdict(list)
        self._broadcasts: List[AgentMessage] = []
    
    async def send(self, message: AgentMessage) -> None:
        if message.to_agent:
            self._inboxes[message.to_agent].append(message)
        else:
            self._broadcasts.append(message)
    
    async def broadcast(self, message: AgentMessage) -> None:
        self._broadcasts.append(message)
    
    async def get_messages_for(self, agent_name: str) -> List[AgentMessage]:
        return list(self._inboxes[agent_name])
    
    async def get_all_messages(self) -> List[AgentMessage]:
        all_msgs = []
        for msgs in self._inboxes.values():
            all_msgs.extend(msgs)
        all_msgs.extend(self._broadcasts)
        return all_msgs
    
    async def clear(self, agent_name: str = None) -> None:
        if agent_name:
            self._inboxes[agent_name].clear()
        else:
            self._inboxes.clear()
            self._broadcasts.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent/test_message_bus.py -v`
Expected: 3 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/agent/message_bus.py backend/tests/test_agent/test_message_bus.py
git commit -m "feat: add in-memory message bus for agent communication"
```

---

### Task 18: Wire Up Agent System Initialization

**Files:**
- Create: `backend/homics_lab/agent/factory.py`
- Modify: `backend/homics_lab/main.py`
- Test: `backend/tests/test_agent/test_factory.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_agent/test_factory.py`:

```python
from homics_lab.agent.factory import create_default_agents
from homics_lab.agent.agent_registry import get_default_registry
from homics_lab.models.common import AgentType


def test_create_default_agents():
    create_default_agents()
    registry = get_default_registry()
    
    assert registry.get_agent(AgentType.BIOINFO) is not None
    assert registry.get_agent(AgentType.VIZ) is not None
    assert registry.get_agent(AgentType.EXPERIMENT) is not None
    
    # Reset for isolation
    registry.reset()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent/test_factory.py -v`
Expected: ImportError

- [ ] **Step 3: Implement agent factory and wire into app**

Create `backend/homics_lab/agent/factory.py`:

```python
from homics_lab.agent.agent_registry import get_default_registry
from homics_lab.agent.bioinfo_agent import BioinfoAgent
from homics_lab.agent.viz_agent import VizAgent
from homics_lab.agent.experiment_agent import ExperimentAgent


def create_default_agents():
    """Register all default agents."""
    registry = get_default_registry()
    
    registry.register(BioinfoAgent())
    registry.register(VizAgent())
    registry.register(ExperimentAgent())
```

Modify `backend/homics_lab/main.py` to initialize agents on startup:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from homics_lab.config import settings
from homics_lab.agent.factory import create_default_agents


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.skills_dir.mkdir(parents=True, exist_ok=True)
    create_default_agents()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)
# ... rest unchanged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent/test_factory.py tests/test_main.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/agent/factory.py backend/homics_lab/main.py backend/tests/test_agent/test_factory.py
git commit -m "feat: wire up default agent registration on app startup"
```

---

## Milestone 2 Complete ✅

At this point you have:
- Base agent class and registry
- Rule-based intent analyzer
- Task decomposer with single-cell pipeline template
- Task state machine with valid transitions
- Orchestrator that resolves agents and tracks progress
- Specialized agents (bioinfo, viz, experiment)
- In-memory message bus for agent communication
- Agent system initialized on app startup

Next: Context compression and memory management.


## Milestone 3: Task System (Supplement)

### Task 19: Extract TaskTree to Dedicated Module

**Files:**
- Create: `backend/homics_lab/tasks/task_tree.py`
- Modify: `backend/homics_lab/agent/task_decomposer.py` to use TaskTree from tasks module
- Test: `backend/tests/test_tasks/test_task_tree.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_tasks/test_task_tree.py`:

```python
import pytest
from homics_lab.tasks.task_tree import TaskTree
from homics_lab.tasks.models import TaskNode


def test_topological_sort_simple():
    tree = TaskTree([
        TaskNode(id="t1", name="a", description="first"),
        TaskNode(id="t2", name="b", description="second", dependencies=["t1"]),
    ])
    sorted_tasks = tree.topological_sort()
    assert sorted_tasks[0].id == "t1"
    assert sorted_tasks[1].id == "t2"


def test_topological_sort_detects_cycle():
    tree = TaskTree([
        TaskNode(id="t1", name="a", description="first", dependencies=["t2"]),
        TaskNode(id="t2", name="b", description="second", dependencies=["t1"]),
    ])
    with pytest.raises(ValueError):
        tree.topological_sort()


def test_ready_tasks():
    tree = TaskTree([
        TaskNode(id="t1", name="a", description="first"),
        TaskNode(id="t2", name="b", description="second", dependencies=["t1"]),
    ])
    ready = tree.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].id == "t1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_tasks/test_task_tree.py -v`
Expected: ImportError

- [ ] **Step 3: Implement TaskTree module**

Create `backend/homics_lab/tasks/task_tree.py`:

```python
from typing import List, Set
from homics_lab.tasks.models import TaskNode, TaskStatus


class TaskTree:
    def __init__(self, tasks: List[TaskNode] = None):
        self.tasks = tasks or []
    
    def get_task(self, task_id: str) -> TaskNode:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"Task {task_id} not found")
    
    def topological_sort(self) -> List[TaskNode]:
        completed: Set[str] = set()
        result: List[TaskNode] = []
        pending = list(self.tasks)
        
        while pending:
            progress = False
            for task in pending[:]:
                if all(dep in completed for dep in task.dependencies):
                    result.append(task)
                    completed.add(task.id)
                    pending.remove(task)
                    progress = True
            
            if not progress and pending:
                raise ValueError("Cyclic dependency detected in task tree")
        
        return result
    
    def get_ready_tasks(self) -> List[TaskNode]:
        completed = {
            t.id for t in self.tasks
            if t.status == TaskStatus.COMPLETED
        }
        return [
            t for t in self.tasks
            if t.status == TaskStatus.PENDING
            and all(dep in completed for dep in t.dependencies)
        ]
    
    def add_task(self, task: TaskNode) -> None:
        self.tasks.append(task)
```

- [ ] **Step 4: Update task_decomposer to import TaskTree from tasks module**

Modify `backend/homics_lab/agent/task_decomposer.py`:
```python
from homics_lab.tasks.task_tree import TaskTree
# Remove local TaskTree class definition
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_tasks/test_task_tree.py tests/test_agent/test_task_decomposer.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/homics_lab/tasks/task_tree.py backend/tests/test_tasks/test_task_tree.py
git commit -m "refactor: extract TaskTree to dedicated module with ready-task detection"
```

---

## Milestone 4: Context & Memory Management

### Task 20: Implement Working Memory

**Files:**
- Create: `backend/homics_lab/context/__init__.py`
- Create: `backend/homics_lab/context/working_memory.py`
- Test: `backend/tests/test_context/test_working_memory.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_context/test_working_memory.py`:

```python
import pytest
from homics_lab.context.working_memory import WorkingMemory
from homics_lab.models.common import ChatMessage, MessageType


def test_add_and_retrieve_messages():
    wm = WorkingMemory(max_messages=10)
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content="hello", sender="user"))
    wm.add_message(ChatMessage(id="m2", type=MessageType.TEXT, content="hi", sender="agent"))
    
    messages = wm.get_recent_messages()
    assert len(messages) == 2
    assert messages[0].sender == "user"


def test_message_limit():
    wm = WorkingMemory(max_messages=3)
    for i in range(5):
        wm.add_message(ChatMessage(id=f"m{i}", type=MessageType.TEXT, content=str(i), sender="user"))
    
    messages = wm.get_recent_messages()
    assert len(messages) == 3
    assert messages[0].content == "2"


def test_set_current_task():
    wm = WorkingMemory()
    wm.set_current_task("task_123")
    assert wm.current_task_id == "task_123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_context/test_working_memory.py -v`
Expected: ImportError

- [ ] **Step 3: Implement working memory**

Create `backend/homics_lab/context/__init__.py`:
```python
from .working_memory import WorkingMemory
```

Create `backend/homics_lab/context/working_memory.py`:

```python
from collections import deque
from typing import List, Optional
from homics_lab.models.common import ChatMessage


class WorkingMemory:
    """Short-lived session memory for current conversation and task."""
    
    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self.messages: deque[ChatMessage] = deque(maxlen=max_messages)
        self.current_task_id: Optional[str] = None
        self.pinned_items: List[str] = []
    
    def add_message(self, message: ChatMessage) -> None:
        self.messages.append(message)
    
    def get_recent_messages(self, n: int = None) -> List[ChatMessage]:
        if n is None:
            n = self.max_messages
        return list(self.messages)[-n:]
    
    def set_current_task(self, task_id: str) -> None:
        self.current_task_id = task_id
    
    def pin_item(self, item_id: str) -> None:
        if item_id not in self.pinned_items:
            self.pinned_items.append(item_id)
    
    def clear(self) -> None:
        self.messages.clear()
        self.current_task_id = None
        self.pinned_items.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_context/test_working_memory.py -v`
Expected: 3 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/context/ backend/tests/test_context/
git commit -m "feat: add working memory for session state"
```

---

### Task 21: Implement Relevance Filter

**Files:**
- Create: `backend/homics_lab/context/relevance_filter.py`
- Test: `backend/tests/test_context/test_relevance_filter.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_context/test_relevance_filter.py`:

```python
import pytest
from homics_lab.context.relevance_filter import RelevanceFilter, ContextItem


@pytest.fixture
def filter():
    return RelevanceFilter()


def test_high_similarity_retained(filter):
    items = [
        ContextItem(content="单细胞质控结果", type="result"),
        ContextItem(content="今天的天气很好", type="chat"),
    ]
    goal = "分析单细胞数据"
    
    scored = filter.score_all(items, goal)
    assert scored[0][1] > scored[1][1]


def test_pinned_items_get_bonus(filter):
    item = ContextItem(content="无关内容", type="chat", is_pinned=True)
    score = filter.score(item, "分析数据")
    assert score >= 0.5  # Pinned items get minimum boost


def test_filter_by_budget(filter):
    items = [
        ContextItem(content=f"message {i}", type="chat")
        for i in range(10)
    ]
    # Mark first item as upstream result
    items[0].is_upstream_result = True
    
    filtered = filter.filter(items, budget=3, current_goal="test")
    assert len(filtered) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_context/test_relevance_filter.py -v`
Expected: ImportError

- [ ] **Step 3: Implement relevance filter**

Create `backend/homics_lab/context/relevance_filter.py`:

```python
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import math


@dataclass
class ContextItem:
    content: str
    type: str  # chat, result, parameter, error
    is_pinned: bool = False
    is_upstream_result: bool = False
    agent_importance: float = 0.5  # 0-1
    hours_since_created: float = 0.0
    
    # Optional precomputed embedding
    embedding: Optional[List[float]] = field(default=None, repr=False)


class RelevanceFilter:
    """Filter context items based on relevance to current goal."""
    
    def score(self, item: ContextItem, current_goal: str) -> float:
        scores = {
            'semantic_similarity': self._semantic_similarity(item, current_goal),
            'temporal_proximity': self._temporal_decay(item.hours_since_created),
            'user_pin': 1.0 if item.is_pinned else 0.0,
            'result_dependency': 1.0 if item.is_upstream_result else 0.3,
            'agent_importance': item.agent_importance,
        }
        
        weights = {
            'semantic_similarity': 0.35,
            'temporal_proximity': 0.20,
            'user_pin': 0.20,
            'result_dependency': 0.15,
            'agent_importance': 0.10,
        }
        
        return sum(scores[k] * weights[k] for k in scores)
    
    def score_all(self, items: List[ContextItem], current_goal: str) -> List[Tuple[ContextItem, float]]:
        return [(item, self.score(item, current_goal)) for item in items]
    
    def filter(self, items: List[ContextItem], budget: int, current_goal: str) -> List[ContextItem]:
        """Return top-k items within budget, keeping pinned items."""
        pinned = [item for item in items if item.is_pinned]
        unpinned = [item for item in items if not item.is_pinned]
        
        scored = self.score_all(unpinned, current_goal)
        scored.sort(key=lambda x: x[1], reverse=True)
        
        budget_for_unpinned = max(0, budget - len(pinned))
        selected_unpinned = [item for item, _ in scored[:budget_for_unpinned]]
        
        return pinned + selected_unpinned
    
    def _semantic_similarity(self, item: ContextItem, goal: str) -> float:
        """Simple keyword overlap similarity (replace with embedding in Phase 2)."""
        if not item.content or not goal:
            return 0.0
        
        content_words = set(item.content.lower().split())
        goal_words = set(goal.lower().split())
        
        if not content_words or not goal_words:
            return 0.0
        
        overlap = len(content_words & goal_words)
        return overlap / max(len(goal_words), 1)
    
    def _temporal_decay(self, hours: float) -> float:
        return math.exp(-hours / 24.0)  # Decay over 24 hours
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_context/test_relevance_filter.py -v`
Expected: 3 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/context/relevance_filter.py backend/tests/test_context/test_relevance_filter.py
git commit -m "feat: add context relevance filter with multi-dimensional scoring"
```

---

### Task 22: Implement Context Summarizer

**Files:**
- Create: `backend/homics_lab/context/summarizer.py`
- Test: `backend/tests/test_context/test_summarizer.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_context/test_summarizer.py`:

```python
import pytest
from homics_lab.context.summarizer import ContextSummarizer, ContextSummary


@pytest.fixture
def summarizer():
    return ContextSummarizer(max_length=500)


def test_summarize_results(summarizer):
    text = """
    Performed QC on PBMC 3k dataset. Started with 2700 cells.
    Filtered cells with fewer than 200 genes and genes expressed in fewer than 3 cells.
    Removed cells with mitochondrial content above 5%.
    Final dataset contains 2531 cells and 13714 genes.
    """
    
    summary = summarizer.summarize(text, summary_type="result")
    assert "2531 cells" in summary.key_conclusions[0] or "13714 genes" in summary.key_conclusions[0]


def test_preserves_parameters(summarizer):
    text = "QC parameters: min_genes=200, min_cells=3, mt_threshold=0.05"
    summary = summarizer.summarize(text, summary_type="method")
    assert summary.key_parameters.get("min_genes") == "200"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_context/test_summarizer.py -v`
Expected: ImportError

- [ ] **Step 3: Implement summarizer**

Create `backend/homics_lab/context/summarizer.py`:

```python
import re
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ContextSummary:
    key_conclusions: List[str] = field(default_factory=list)
    key_parameters: Dict[str, str] = field(default_factory=dict)
    key_results: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    full_text_hash: str = ""
    storage_location: str = ""


class ContextSummarizer:
    """Extract structured summaries from long context items."""
    
    def __init__(self, max_length: int = 1000):
        self.max_length = max_length
    
    def summarize(self, text: str, summary_type: str = "result") -> ContextSummary:
        summary = ContextSummary()
        
        # Extract key conclusions (first sentence + result sentences)
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        if sentences:
            summary.key_conclusions.append(sentences[0][:200])
        
        for sentence in sentences:
            if any(kw in sentence.lower() for kw in ["final", "result", "output", "contains", "identified"]):
                if sentence not in summary.key_conclusions:
                    summary.key_conclusions.append(sentence[:200])
        
        summary.key_conclusions = summary.key_conclusions[:5]
        
        # Extract parameters
        summary.key_parameters = self._extract_parameters(text)
        
        # Extract warnings
        summary.warnings = self._extract_warnings(text)
        
        return summary
    
    def _extract_parameters(self, text: str) -> Dict[str, str]:
        params = {}
        # Match patterns like "key=value" or "key: value"
        patterns = [
            r'(\w+)[=:](\d+(?:\.\d+)?)',
            r'(\w+)[=:](\w+)',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                key, value = match.groups()
                params[key] = value
        return params
    
    def _extract_warnings(self, text: str) -> List[str]:
        warnings = []
        for sentence in text.split("."):
            if any(kw in sentence.lower() for kw in ["warning", "caution", "note", "attention", "error"]):
                warnings.append(sentence.strip())
        return warnings[:3]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_context/test_summarizer.py -v`
Expected: 2 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/context/summarizer.py backend/tests/test_context/test_summarizer.py
git commit -m "feat: add context summarizer with parameter and warning extraction"
```

---

### Task 23: Implement Prompter

**Files:**
- Create: `backend/homics_lab/context/prompter.py`
- Test: `backend/tests/test_context/test_prompter.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_context/test_prompter.py`:

```python
import pytest
from homics_lab.context.prompter import Prompter
from homics_lab.context.working_memory import WorkingMemory
from homics_lab.models.common import ChatMessage, MessageType


@pytest.fixture
def prompter():
    return Prompter(token_budget=200)


def test_build_prompt_with_messages(prompter):
    wm = WorkingMemory()
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content="hello", sender="user"))
    
    prompt = prompter.build_prompt(
        user_message="analyze this",
        working_memory=wm,
        task=None,
    )
    
    assert "analyze this" in prompt
    assert "hello" in prompt


def test_prompt_respects_token_budget(prompter):
    wm = WorkingMemory()
    long_message = "word " * 100
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content=long_message, sender="user"))
    
    prompt = prompter.build_prompt(
        user_message="short",
        working_memory=wm,
        task=None,
    )
    
    # Budget should trigger truncation
    assert len(prompt.split()) <= 250  # Allow some overhead
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_context/test_prompter.py -v`
Expected: ImportError

- [ ] **Step 3: Implement prompter**

Create `backend/homics_lab/context/prompter.py`:

```python
from typing import Any, Dict, Optional
from homics_lab.context.working_memory import WorkingMemory


class Prompter:
    """Assembles LLM prompts from layered memory."""
    
    def __init__(self, token_budget: int = 4000):
        self.token_budget = token_budget
        self.words_per_token = 0.75  # Rough estimate
    
    def build_prompt(
        self,
        user_message: str,
        working_memory: WorkingMemory,
        task: Any = None,
        project_context: str = "",
        user_profile: str = "",
    ) -> str:
        parts = []
        
        # System prompt
        parts.append(self._system_prompt())
        
        # User profile
        if user_profile:
            parts.append(f"User Profile:\n{user_profile}")
        
        # Project context
        if project_context:
            parts.append(f"Project Context:\n{project_context}")
        
        # Recent messages
        recent_msgs = working_memory.get_recent_messages(10)
        if recent_msgs:
            history = "\n".join(
                f"{msg.sender}: {msg.content}"
                for msg in recent_msgs
            )
            parts.append(f"Recent Conversation:\n{history}")
        
        # Current task
        if task:
            parts.append(f"Current Task: {task.name} - {task.description}")
            if task.parameters:
                params = "\n".join(f"  {k}: {v}" for k, v in task.parameters.items())
                parts.append(f"Task Parameters:\n{params}")
        
        # User current message
        parts.append(f"User: {user_message}")
        parts.append("Assistant:")
        
        prompt = "\n\n".join(parts)
        return self._truncate_if_needed(prompt)
    
    def _system_prompt(self) -> str:
        return """You are HomicsLab, an AI assistant specialized in bioinformatics analysis.
You help researchers design experiments, analyze omics data, and interpret results.
Be concise, accurate, and ask for clarification when needed."""
    
    def _truncate_if_needed(self, prompt: str) -> str:
        words = prompt.split()
        max_words = int(self.token_budget * self.words_per_token)
        
        if len(words) <= max_words:
            return prompt
        
        # Simple truncation from the middle (keep system + user message)
        # A more sophisticated approach would use the relevance filter
        system_end = words.index("Assistant:") if "Assistant:" in words else 0
        user_idx = prompt.rfind("User:")
        user_part = prompt[user_idx:] if user_idx > 0 else ""
        
        head_words = words[:max_words - len(user_part.split()) - 10]
        return " ".join(head_words) + "\n\n... [context truncated] ...\n\n" + user_part
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_context/test_prompter.py -v`
Expected: 2 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/context/prompter.py backend/tests/test_context/test_prompter.py
git commit -m "feat: add prompter that assembles context from layered memory"
```

---

## Milestone 4 Complete ✅

At this point you have:
- Working memory for session state
- Relevance filter with multi-dimensional scoring
- Context summarizer
- Prompter that assembles LLM prompts

Next: Skills runtime.


## Milestone 5: Skills Runtime

### Task 24: Define Skill Models

**Files:**
- Create: `backend/homics_lab/skills/__init__.py`
- Create: `backend/homics_lab/skills/models.py`
- Test: `backend/tests/test_skills/test_models.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_skills/test_models.py`:

```python
from homics_lab.skills.models import SkillDefinition, SkillInputSchema, SkillRuntime


def test_skill_definition_validation():
    skill = SkillDefinition(
        id="scanpy_qc",
        name="Single Cell QC",
        version="1.0.0",
        category="single_cell_analysis",
        runtime=SkillRuntime(type="python", python_version="3.10"),
        input_schema=SkillInputSchema(
            type="object",
            properties={"adata_path": {"type": "string"}},
            required=["adata_path"],
        ),
    )
    assert skill.id == "scanpy_qc"
    assert skill.runtime.type == "python"


def test_input_validation():
    skill = SkillDefinition(
        id="test",
        name="Test",
        version="1.0.0",
        category="test",
        input_schema=SkillInputSchema(
            type="object",
            properties={
                "count": {"type": "integer", "default": 10},
            },
            required=[],
        ),
    )
    
    validated = skill.validate_input({})
    assert validated["count"] == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_skills/test_models.py -v`
Expected: ImportError

- [ ] **Step 3: Implement skill models**

Create `backend/homics_lab/skills/__init__.py`:
```python
from .models import SkillDefinition, SkillRuntime, SkillInputSchema
```

Create `backend/homics_lab/skills/models.py`:

```python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SkillInputSchema(BaseModel):
    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)


class SkillOutputSchema(BaseModel):
    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)


class SkillResources(BaseModel):
    memory: str = "4G"
    cpu: int = 2
    time: str = "30m"


class SkillRuntime(BaseModel):
    type: str = "python"
    python_version: str = "3.10"
    dependencies: List[str] = Field(default_factory=list)
    executor: str = "auto"  # auto/local/slurm/cloud
    resources: SkillResources = Field(default_factory=SkillResources)


class SkillTestCase(BaseModel):
    name: str
    input: Dict[str, Any]
    expected_output: Dict[str, Any]


class SkillQuality(BaseModel):
    test_cases: List[SkillTestCase] = Field(default_factory=list)
    validation_rules: List[str] = Field(default_factory=list)


class SkillDefinition(BaseModel):
    id: str
    name: str
    version: str
    category: str
    author: str = "builtin"
    description: str = ""
    input_schema: SkillInputSchema = Field(default_factory=SkillInputSchema)
    output_schema: SkillOutputSchema = Field(default_factory=SkillOutputSchema)
    runtime: SkillRuntime = Field(default_factory=SkillRuntime)
    quality: SkillQuality = Field(default_factory=SkillQuality)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fill defaults for skill input."""
        validated = {}
        
        for key, prop in self.input_schema.properties.items():
            if key in data:
                validated[key] = data[key]
            elif "default" in prop:
                validated[key] = prop["default"]
            elif key in self.input_schema.required:
                raise ValueError(f"Missing required parameter: {key}")
        
        return validated
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_skills/test_models.py -v`
Expected: 2 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/skills/ backend/tests/test_skills/
git commit -m "feat: add SkillDefinition model with input validation"
```

---

### Task 25: Implement Skill Registry

**Files:**
- Create: `backend/homics_lab/skills/registry.py`
- Test: `backend/tests/test_skills/test_registry.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_skills/test_registry.py`:

```python
import pytest
from homics_lab.skills.registry import SkillRegistry
from homics_lab.skills.models import SkillDefinition, SkillRuntime


@pytest.fixture
def registry():
    return SkillRegistry()


def test_register_skill(registry):
    skill = SkillDefinition(id="s1", name="Skill 1", version="1.0.0", category="test")
    registry.register(skill)
    assert registry.get("s1") == skill


def test_get_unknown_skill(registry):
    assert registry.get("unknown") is None


def test_list_by_category(registry):
    registry.register(SkillDefinition(id="s1", name="A", version="1.0.0", category="cat1"))
    registry.register(SkillDefinition(id="s2", name="B", version="1.0.0", category="cat1"))
    registry.register(SkillDefinition(id="s3", name="C", version="1.0.0", category="cat2"))
    
    cat1 = registry.list_by_category("cat1")
    assert len(cat1) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_skills/test_registry.py -v`
Expected: ImportError

- [ ] **Step 3: Implement skill registry**

Create `backend/homics_lab/skills/registry.py`:

```python
from typing import Dict, List, Optional
from homics_lab.skills.models import SkillDefinition


class SkillRegistry:
    """Registry for skill definitions."""
    
    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}
    
    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.id] = skill
    
    def get(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._skills.get(skill_id)
    
    def list_all(self) -> List[SkillDefinition]:
        return list(self._skills.values())
    
    def list_by_category(self, category: str) -> List[SkillDefinition]:
        return [s for s in self._skills.values() if s.category == category]
    
    def search(self, query: str) -> List[SkillDefinition]:
        """Simple keyword search."""
        query = query.lower()
        results = []
        for skill in self._skills.values():
            if (query in skill.name.lower() or
                query in skill.description.lower() or
                query in skill.category.lower() or
                any(query in tag.lower() for tag in skill.metadata.get("tags", []))):
                results.append(skill)
        return results
    
    def reset(self) -> None:
        self._skills.clear()


_default_registry = SkillRegistry()

def get_default_registry() -> SkillRegistry:
    return _default_registry
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_skills/test_registry.py -v`
Expected: 3 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/skills/registry.py backend/tests/test_skills/test_registry.py
git commit -m "feat: add skill registry with search and category filtering"
```

---

### Task 26: Implement Sandboxed Skill Execution

**Files:**
- Create: `backend/homics_lab/skills/sandbox.py`
- Test: `backend/tests/test_skills/test_sandbox.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_skills/test_sandbox.py`:

```python
import pytest
from homics_lab.skills.sandbox import LocalSandbox


@pytest.fixture
def sandbox(tmp_path):
    return LocalSandbox(working_dir=tmp_path)


@pytest.mark.asyncio
async def test_run_python_script(sandbox):
    code = """
result = {"sum": 1 + 2, "message": "hello"}
"""
    result = await sandbox.run_python(code, {"x": 10})
    assert result["sum"] == 3
    assert result["message"] == "hello"


@pytest.mark.asyncio
async def test_run_with_timeout(sandbox):
    code = """
import time
time.sleep(10)
"""
    with pytest.raises(TimeoutError):
        await sandbox.run_python(code, {}, timeout_seconds=0.1)


@pytest.mark.asyncio
async def test_run_captures_errors(sandbox):
    code = """
raise ValueError("test error")
"""
    with pytest.raises(RuntimeError) as exc_info:
        await sandbox.run_python(code, {})
    assert "test error" in str(exc_info.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_skills/test_sandbox.py -v`
Expected: ImportError

- [ ] **Step 3: Implement local sandbox**

Create `backend/homics_lab/skills/sandbox.py`:

```python
import asyncio
import tempfile
from pathlib import Path
from typing import Any, Dict


class LocalSandbox:
    """Execute Python code in a subprocess with resource limits."""
    
    def __init__(self, working_dir: Path = None):
        self.working_dir = working_dir or Path(tempfile.mkdtemp())
        self.working_dir.mkdir(parents=True, exist_ok=True)
    
    async def run_python(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 60.0,
    ) -> Dict[str, Any]:
        """Execute Python code and return the 'result' variable."""
        script = self._build_script(code, inputs)
        
        script_path = self.working_dir / "__skill_script__.py"
        script_path.write_text(script)
        
        result_path = self.working_dir / "__skill_result__.json"
        
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "python", str(script_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=timeout_seconds,
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                raise RuntimeError(f"Skill execution failed: {stderr.decode()}")
            
            if not result_path.exists():
                return {"raw_output": stdout.decode()}
            
            import json
            return json.loads(result_path.read_text())
            
        except asyncio.TimeoutError:
            raise TimeoutError(f"Skill execution timed out after {timeout_seconds}s")
    
    def _build_script(self, code: str, inputs: Dict[str, Any]) -> str:
        import json
        inputs_json = json.dumps(inputs)
        
        return f"""import json
import sys

# Inject inputs
__inputs__ = json.loads({repr(inputs_json)})
locals().update(__inputs__)

# Run skill code
{code}

# Serialize result
if 'result' not in locals():
    result = {{}}

with open('__skill_result__.json', 'w') as f:
    json.dump(result, f)
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_skills/test_sandbox.py -v`
Expected: 3 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/skills/sandbox.py backend/tests/test_skills/test_sandbox.py
git commit -m "feat: add local subprocess sandbox for skill execution"
```

---

### Task 27: Implement Skills Runtime

**Files:**
- Create: `backend/homics_lab/skills/runtime.py`
- Test: `backend/tests/test_skills/test_runtime.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_skills/test_runtime.py`:

```python
import pytest
from homics_lab.skills.runtime import SkillRuntimeExecutor
from homics_lab.skills.models import SkillDefinition
from homics_lab.skills.registry import SkillRegistry


@pytest.fixture
def executor(tmp_path):
    registry = SkillRegistry()
    return SkillRuntimeExecutor(registry=registry, working_dir=tmp_path)


@pytest.mark.asyncio
async def test_execute_builtin_skill(executor, tmp_path):
    skill = SkillDefinition(
        id="add_numbers",
        name="Add Numbers",
        version="1.0.0",
        category="math",
        runtime={"type": "python", "python_version": "3.10"},
    )
    executor.registry.register(skill)
    
    # Register the skill code
    code = """
result = {"sum": a + b}
"""
    executor._register_builtin_code("add_numbers", code)
    
    result = await executor.execute("add_numbers", {"a": 2, "b": 3})
    assert result["sum"] == 5


@pytest.mark.asyncio
async def test_execute_unknown_skill(executor):
    with pytest.raises(ValueError) as exc_info:
        await executor.execute("unknown", {})
    assert "not found" in str(exc_info.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_skills/test_runtime.py -v`
Expected: ImportError

- [ ] **Step 3: Implement skill runtime executor**

Create `backend/homics_lab/skills/runtime.py`:

```python
from pathlib import Path
from typing import Any, Dict
from homics_lab.skills.models import SkillDefinition
from homics_lab.skills.registry import SkillRegistry, get_default_registry
from homics_lab.skills.sandbox import LocalSandbox


class SkillRuntimeExecutor:
    """Executes skills in a sandboxed environment."""
    
    def __init__(self, registry: SkillRegistry = None, working_dir: Path = None):
        self.registry = registry or get_default_registry()
        self.sandbox = LocalSandbox(working_dir=working_dir)
        self._builtin_code: Dict[str, str] = {}
    
    def register_builtin(self, skill: SkillDefinition, code: str) -> None:
        """Register a builtin skill with its Python code."""
        self.registry.register(skill)
        self._builtin_code[skill.id] = code
    
    def _register_builtin_code(self, skill_id: str, code: str) -> None:
        """Internal method for testing."""
        self._builtin_code[skill_id] = code
    
    async def execute(self, skill_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        skill = self.registry.get(skill_id)
        if skill is None:
            raise ValueError(f"Skill '{skill_id}' not found")
        
        # Validate inputs
        validated = skill.validate_input(inputs)
        
        # Get skill code
        if skill.id not in self._builtin_code:
            raise RuntimeError(f"No code registered for skill '{skill_id}'")
        
        code = self._builtin_code[skill.id]
        
        # Execute in sandbox
        timeout = self._parse_timeout(skill.runtime.resources.time)
        result = await self.sandbox.run_python(code, validated, timeout_seconds=timeout)
        
        return result
    
    def _parse_timeout(self, time_str: str) -> float:
        """Parse time string like '30m' or '1h' into seconds."""
        if time_str.endswith("m"):
            return float(time_str[:-1]) * 60
        elif time_str.endswith("h"):
            return float(time_str[:-1]) * 3600
        elif time_str.endswith("s"):
            return float(time_str[:-1])
        return float(time_str)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_skills/test_runtime.py -v`
Expected: 2 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/skills/runtime.py backend/tests/test_skills/test_runtime.py
git commit -m "feat: add skill runtime executor with validation and sandboxing"
```

---

### Task 28: Create Builtin Skills

**Files:**
- Create: `backend/homics_lab/skills/builtin/__init__.py`
- Create: `backend/homics_lab/skills/builtin/data_loader.py`
- Create: `backend/homics_lab/skills/builtin/scanpy_qc.py`
- Create: `backend/homics_lab/skills/builtin/scanpy_cluster.py`
- Modify: `backend/homics_lab/main.py` to register builtin skills
- Test: `backend/tests/test_skills/test_builtin.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_skills/test_builtin.py`:

```python
import pytest
from homics_lab.skills.runtime import SkillRuntimeExecutor
from homics_lab.skills.registry import SkillRegistry
from homics_lab.skills.builtin import register_builtin_skills


@pytest.fixture
def executor(tmp_path):
    registry = SkillRegistry()
    exec = SkillRuntimeExecutor(registry=registry, working_dir=tmp_path)
    register_builtin_skills(exec)
    return exec


@pytest.mark.asyncio
async def test_data_loader_skill(executor):
    result = await executor.execute("data_loader", {"format": "10x", "path": "/fake/path"})
    assert result["format"] == "10x"
    assert "loaded" in result["status"]


@pytest.mark.asyncio
async def test_scanpy_qc_defaults(executor):
    result = await executor.execute("scanpy_qc", {"adata_path": "/fake/data.h5ad"})
    assert result["min_genes"] == 200
    assert result["min_cells"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_skills/test_builtin.py -v`
Expected: ImportError

- [ ] **Step 3: Implement builtin skills**

Create `backend/homics_lab/skills/builtin/__init__.py`:

```python
from homics_lab.skills.runtime import SkillRuntimeExecutor
from .data_loader import DATA_LOADER_SKILL, DATA_LOADER_CODE
from .scanpy_qc import SCANPY_QC_SKILL, SCANPY_QC_CODE
from .scanpy_cluster import SCANPY_CLUSTER_SKILL, SCANPY_CLUSTER_CODE


def register_builtin_skills(executor: SkillRuntimeExecutor) -> None:
    executor.register_builtin(DATA_LOADER_SKILL, DATA_LOADER_CODE)
    executor.register_builtin(SCANPY_QC_SKILL, SCANPY_QC_CODE)
    executor.register_builtin(SCANPY_CLUSTER_SKILL, SCANPY_CLUSTER_CODE)
```

Create `backend/homics_lab/skills/builtin/data_loader.py`:

```python
from homics_lab.skills.models import SkillDefinition, SkillInputSchema


DATA_LOADER_SKILL = SkillDefinition(
    id="data_loader",
    name="Load Omics Data",
    version="1.0.0",
    category="data_io",
    description="Load omics data from various formats",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "format": {"type": "string", "default": "auto"},
            "path": {"type": "string"},
        },
        required=["path"],
    ),
)


DATA_LOADER_CODE = '''
# Mock data loader for MVP
import os

result = {
    "format": format,
    "path": adata_path if "adata_path" in locals() else path,
    "status": "loaded (mock)",
    "shape": [1000, 2000] if format == "10x" else [500, 1000],
}
'''
```

Create `backend/homics_lab/skills/builtin/scanpy_qc.py`:

```python
from homics_lab.skills.models import SkillDefinition, SkillInputSchema


SCANPY_QC_SKILL = SkillDefinition(
    id="scanpy_qc",
    name="Scanpy Quality Control",
    version="1.0.0",
    category="single_cell_analysis",
    description="Perform QC filtering on single-cell data",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "adata_path": {"type": "string"},
            "min_genes": {"type": "integer", "default": 200},
            "min_cells": {"type": "integer", "default": 3},
            "mt_threshold": {"type": "number", "default": 0.05},
        },
        required=["adata_path"],
    ),
)


SCANPY_QC_CODE = '''
# Mock QC for MVP
result = {
    "input_cells": 2700,
    "output_cells": 2531,
    "input_genes": 32738,
    "output_genes": 13714,
    "min_genes": min_genes,
    "min_cells": min_cells,
    "mt_threshold": mt_threshold,
    "output_path": adata_path.replace(".h5ad", "_qc.h5ad"),
}
'''
```

Create `backend/homics_lab/skills/builtin/scanpy_cluster.py`:

```python
from homics_lab.skills.models import SkillDefinition, SkillInputSchema


SCANPY_CLUSTER_SKILL = SkillDefinition(
    id="scanpy_cluster",
    name="Scanpy Clustering",
    version="1.0.0",
    category="single_cell_analysis",
    description="Cluster single-cell data with UMAP",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "adata_path": {"type": "string"},
            "n_neighbors": {"type": "integer", "default": 15},
            "resolution": {"type": "number", "default": 0.8},
            "n_pcs": {"type": "integer", "default": 30},
        },
        required=["adata_path"],
    ),
)


SCANPY_CLUSTER_CODE = '''
# Mock clustering for MVP
result = {
    "n_clusters": 8,
    "n_neighbors": n_neighbors,
    "resolution": resolution,
    "n_pcs": n_pcs,
    "output_path": adata_path.replace(".h5ad", "_clustered.h5ad"),
}
'''
```

- [ ] **Step 4: Update main.py to register builtin skills**

Modify `backend/homics_lab/main.py`:
```python
from homics_lab.agent.factory import create_default_agents
from homics_lab.skills.runtime import SkillRuntimeExecutor
from homics_lab.skills.builtin import register_builtin_skills


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.skills_dir.mkdir(parents=True, exist_ok=True)
    create_default_agents()
    
    # Initialize skills runtime
    app.state.skill_executor = SkillRuntimeExecutor()
    register_builtin_skills(app.state.skill_executor)
    
    yield
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_skills/test_builtin.py -v`
Expected: 2 passing tests

- [ ] **Step 6: Commit**

```bash
git add backend/homics_lab/skills/builtin/ backend/homics_lab/main.py backend/tests/test_skills/test_builtin.py
git commit -m "feat: add builtin skills for data loading, QC, and clustering"
```

---

### Task 29: Integrate Skills with Orchestrator

**Files:**
- Modify: `backend/homics_lab/agent/orchestrator.py`
- Modify: `backend/homics_lab/agent/base_agent.py` to accept skill executor
- Modify: `backend/homics_lab/agent/bioinfo_agent.py`
- Test: `backend/tests/test_agent/test_skill_integration.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_agent/test_skill_integration.py`:

```python
import pytest
from homics_lab.agent.orchestrator import Orchestrator
from homics_lab.agent.agent_registry import AgentRegistry
from homics_lab.agent.bioinfo_agent import BioinfoAgent
from homics_lab.agent.task_decomposer import TaskTree
from homics_lab.skills.runtime import SkillRuntimeExecutor
from homics_lab.skills.registry import SkillRegistry
from homics_lab.skills.builtin import register_builtin_skills
from homics_lab.tasks.models import TaskNode
from homics_lab.models.common import TaskStatus


@pytest.fixture
async def skill_orchestrator(tmp_path):
    registry = AgentRegistry()
    
    skill_registry = SkillRegistry()
    executor = SkillRuntimeExecutor(registry=skill_registry, working_dir=tmp_path)
    register_builtin_skills(executor)
    
    agent = BioinfoAgent(skill_executor=executor)
    registry.register(agent)
    
    return Orchestrator(registry=registry)


@pytest.mark.asyncio
async def test_orchestrator_executes_skill(tmp_path):
    skill_registry = SkillRegistry()
    executor = SkillRuntimeExecutor(registry=skill_registry, working_dir=tmp_path)
    register_builtin_skills(executor)
    
    registry = AgentRegistry()
    registry.register(BioinfoAgent(skill_executor=executor))
    
    orchestrator = Orchestrator(registry=registry)
    tree = TaskTree([
        TaskNode(id="t1", name="quality_control", description="QC", skills_required=["scanpy_qc"]),
    ])
    
    results = await orchestrator.run_tree(tree)
    
    assert "t1" in results
    assert results["t1"]["output_cells"] == 2531
    assert tree.get_task("t1").status == TaskStatus.COMPLETED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent/test_skill_integration.py -v`
Expected: Test fails (agent not using skill executor yet)

- [ ] **Step 3: Update base agent and bioinfo agent to support skill execution**

Modify `backend/homics_lab/agent/base_agent.py`:
```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from homics_lab.models.common import AgentMessage, AgentType


class BaseAgent(ABC):
    agent_type: AgentType = None
    capabilities: List[str] = []
    
    def __init__(self, name: Optional[str] = None, skill_executor=None):
        self.name = name or self.agent_type
        self.skill_executor = skill_executor
```

Modify `backend/homics_lab/agent/bioinfo_agent.py`:
```python
from typing import Any, Dict
from homics_lab.agent.base_agent import BaseAgent
from homics_lab.models.common import AgentType


class BioinfoAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = [
        "scanpy_qc", "scanpy_pca", "scanpy_cluster",
        "scanpy_annotation", "scanpy_de", "data_loader",
    ]
    
    async def run(self, task: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        if task.skills_required and self.skill_executor:
            skill_id = task.skills_required[0]
            result = await self.skill_executor.execute(skill_id, task.parameters)
            return {
                "agent_type": self.agent_type,
                "task": task.name,
                "skill": skill_id,
                "result": result,
            }
        
        return {
            "agent_type": self.agent_type,
            "task": task.name,
            "message": f"BioinfoAgent executed {task.name}",
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent/test_skill_integration.py -v`
Expected: Test passes

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/agent/ backend/tests/test_agent/test_skill_integration.py
git commit -m "feat: integrate skills runtime with agent orchestrator"
```

---

## Milestone 5 Complete ✅

At this point you have:
- Skill definition models with input validation
- Skill registry with search
- Local subprocess sandbox
- Skills runtime executor
- Builtin skills (data_loader, scanpy_qc, scanpy_cluster)
- Agents can execute skills through the runtime

Next: Human-in-the-loop mechanism.


## Milestone 6: Human-in-the-Loop

### Task 30: Implement HITL Checkpoint Detection

**Files:**
- Create: `backend/homics_lab/hitl/__init__.py`
- Create: `backend/homics_lab/hitl/detector.py`
- Test: `backend/tests/test_hitl/test_detector.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_hitl/test_detector.py`:

```python
import pytest
from homics_lab.hitl.detector import HITLDetector
from homics_lab.tasks.models import TaskNode
from homics_lab.models.common import HITLTrigger


@pytest.fixture
def detector():
    return HITLDetector()


def test_detects_policy_checkpoint(detector):
    task = TaskNode(
        id="t1",
        name="clustering",
        description="cluster cells",
        hitl_checkpoints=[{
            "trigger_reason": HITLTrigger.POLICY,
            "context_summary": "Confirm parameters",
            "options": [{"id": "default", "label": "Default"}],
        }],
    )
    
    checkpoint = detector.check(task, context={})
    assert checkpoint is not None
    assert checkpoint.trigger_reason == HITLTrigger.POLICY


def test_detects_high_cost(detector):
    task = TaskNode(
        id="t1",
        name="big_analysis",
        description="run big analysis",
        estimated_duration_minutes=200,
    )
    
    checkpoint = detector.check(
        task,
        context={"cost_threshold_minutes": 180},
    )
    assert checkpoint is not None
    assert checkpoint.trigger_reason == HITLTrigger.HIGH_COST


def test_no_checkpoint_for_simple_task(detector):
    task = TaskNode(id="t1", name="load", description="load data")
    checkpoint = detector.check(task, context={})
    assert checkpoint is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_hitl/test_detector.py -v`
Expected: ImportError

- [ ] **Step 3: Implement HITL detector**

Create `backend/homics_lab/hitl/__init__.py`:
```python
from .detector import HITLDetector
```

Create `backend/homics_lab/hitl/detector.py`:

```python
from typing import Any, Dict, Optional
from homics_lab.models.common import HITLCheckpoint, HITLTrigger, Option
from homics_lab.tasks.models import TaskNode


class HITLDetector:
    """Detects when human input is required before task execution."""
    
    DEFAULT_COST_THRESHOLD_MINUTES = 120
    DEFAULT_CONFIDENCE_THRESHOLD = 0.7
    
    def check(self, task: TaskNode, context: Dict[str, Any]) -> Optional[HITLCheckpoint]:
        # Check explicit checkpoints
        if task.hitl_checkpoints:
            return task.hitl_checkpoints[0]
        
        # Check cost threshold
        cost_threshold = context.get("cost_threshold_minutes", self.DEFAULT_COST_THRESHOLD_MINUTES)
        if task.estimated_duration_minutes > cost_threshold:
            return self._create_cost_checkpoint(task)
        
        # Check confidence threshold (mock for MVP)
        confidence = context.get("confidence", 1.0)
        if confidence < self.DEFAULT_CONFIDENCE_THRESHOLD:
            return self._create_confidence_checkpoint(task, confidence)
        
        return None
    
    def _create_cost_checkpoint(self, task: TaskNode) -> HITLCheckpoint:
        return HITLCheckpoint(
            id=f"hitl_cost_{task.id}",
            trigger_reason=HITLTrigger.HIGH_COST,
            context_summary=(
                f"Task '{task.name}' is estimated to take "
                f"{task.estimated_duration_minutes} minutes. "
                "Please confirm before proceeding."
            ),
            options=[
                Option(id="proceed", label="Proceed", description="Run the task"),
                Option(id="cancel", label="Cancel", description="Skip this task"),
            ],
        )
    
    def _create_confidence_checkpoint(self, task: TaskNode, confidence: float) -> HITLCheckpoint:
        return HITLCheckpoint(
            id=f"hitl_conf_{task.id}",
            trigger_reason=HITLTrigger.LOW_CONFIDENCE,
            context_summary=(
                f"Low confidence ({confidence:.2f}) for task '{task.name}'. "
                "Please review parameters."
            ),
            options=[
                Option(id="accept", label="Accept and continue"),
                Option(id="modify", label="Modify parameters"),
            ],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_hitl/test_detector.py -v`
Expected: 3 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/hitl/ backend/tests/test_hitl/
git commit -m "feat: add HITL checkpoint detector"
```

---

### Task 31: Integrate HITL with Orchestrator

**Files:**
- Modify: `backend/homics_lab/agent/orchestrator.py`
- Create: `backend/homics_lab/hitl/manager.py`
- Test: `backend/tests/test_hitl/test_orchestrator_hitl.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_hitl/test_orchestrator_hitl.py`:

```python
import pytest
from homics_lab.agent.orchestrator import Orchestrator
from homics_lab.agent.agent_registry import AgentRegistry
from homics_lab.agent.base_agent import BaseAgent
from homics_lab.agent.task_decomposer import TaskTree
from homics_lab.models.common import AgentType, TaskStatus, HITLTrigger
from homics_lab.tasks.models import TaskNode


class FakeBioinfoAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = ["scanpy_qc"]
    
    async def run(self, task, context):
        return {"done": True}


@pytest.mark.asyncio
async def test_orchestrator_pauses_for_hitl():
    registry = AgentRegistry()
    registry.register(FakeBioinfoAgent())
    orchestrator = Orchestrator(registry=registry)
    
    tree = TaskTree([
        TaskNode(
            id="t1",
            name="clustering",
            description="cluster",
            skills_required=["scanpy_qc"],
            hitl_checkpoints=[{
                "trigger_reason": HITLTrigger.POLICY,
                "context_summary": "Confirm",
                "options": [{"id": "ok", "label": "OK"}],
            }],
        ),
    ])
    
    result = await orchestrator.run_tree(tree)
    
    # With HITL, task should be awaiting human
    task = tree.get_task("t1")
    assert task.status == TaskStatus.AWAITING_HUMAN
    assert "hitl" in result


@pytest.mark.asyncio
async def test_orchestrator_resumes_after_hitl():
    registry = AgentRegistry()
    registry.register(FakeBioinfoAgent())
    orchestrator = Orchestrator(registry=registry)
    
    tree = TaskTree([
        TaskNode(
            id="t1",
            name="clustering",
            description="cluster",
            skills_required=["scanpy_qc"],
            hitl_checkpoints=[{
                "trigger_reason": HITLTrigger.POLICY,
                "context_summary": "Confirm",
                "options": [{"id": "ok", "label": "OK"}],
            }],
        ),
    ])
    
    # First run pauses
    await orchestrator.run_tree(tree)
    assert tree.get_task("t1").status == TaskStatus.AWAITING_HUMAN
    
    # Resume
    await orchestrator.resume_task(tree, "t1", {"choice": "ok"})
    assert tree.get_task("t1").status == TaskStatus.COMPLETED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_hitl/test_orchestrator_hitl.py -v`
Expected: Test fails (orchestrator doesn't support HITL yet)

- [ ] **Step 3: Update orchestrator with HITL support**

Modify `backend/homics_lab/agent/orchestrator.py`:

```python
from typing import Any, Dict, Optional
from homics_lab.agent.agent_registry import AgentRegistry, get_default_registry
from homics_lab.agent.task_decomposer import TaskTree
from homics_lab.hitl.detector import HITLDetector
from homics_lab.models.common import TaskStatus
from homics_lab.tasks.models import TaskNode
from homics_lab.tasks.state_machine import TaskStateMachine


class Orchestrator:
    """Central task scheduler and executor."""
    
    def __init__(self, registry: AgentRegistry = None):
        self.registry = registry or get_default_registry()
        self.state_machine = TaskStateMachine()
        self.hitl_detector = HITLDetector()
    
    async def run_tree(self, tree: TaskTree, context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        results = {}
        completed = set()
        
        for task in tree.topological_sort():
            if task.status in (TaskStatus.COMPLETED, TaskStatus.ABORTED):
                completed.add(task.id)
                continue
            
            # Check dependencies
            if not all(dep in completed for dep in task.dependencies):
                raise ValueError(f"Dependencies not satisfied for task {task.id}")
            
            # Check HITL
            checkpoint = self.hitl_detector.check(task, context)
            if checkpoint:
                self.state_machine.transition(task, TaskStatus.AWAITING_HUMAN)
                results[task.id] = {"hitl": checkpoint.model_dump()}
                continue
            
            await self._execute_task(task, context, results)
            completed.add(task.id)
        
        return results
    
    async def resume_task(
        self,
        tree: TaskTree,
        task_id: str,
        human_response: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        task = tree.get_task(task_id)
        if task.status != TaskStatus.AWAITING_HUMAN:
            raise ValueError(f"Task {task_id} is not awaiting human input")
        
        # Apply human response to parameters
        if "parameters" in human_response:
            task.parameters.update(human_response["parameters"])
        
        context = context or {}
        results = {}
        await self._execute_task(task, context, results)
        
        # Continue with remaining tasks
        remaining_results = await self.run_tree(tree, context)
        results.update(remaining_results)
        
        return results
    
    async def _execute_task(self, task: TaskNode, context: Dict[str, Any], results: Dict[str, Any]) -> None:
        self.state_machine.transition(task, TaskStatus.RUNNING)
        
        try:
            agent = self._resolve_agent(task)
            if agent is None:
                raise RuntimeError(f"No agent found for task {task.name}")
            
            result = await agent.run(task, context)
            results[task.id] = result
            task.result = result
            self.state_machine.transition(task, TaskStatus.COMPLETED)
            
        except Exception as e:
            task.error_message = str(e)
            task.attempt_count += 1
            self.state_machine.transition(task, TaskStatus.FAILED)
            raise
    
    def _resolve_agent(self, task: TaskNode):
        if task.agent_assignment:
            agent = self.registry.get_agent(task.agent_assignment)
            if agent:
                return agent
        
        for skill in task.skills_required:
            agent = self.registry.find_agent_for_task(skill)
            if agent:
                return agent
        
        return None
    
    def get_progress(self, tree: TaskTree) -> Dict[str, int]:
        total = len(tree.tasks)
        by_status = {
            "total": total,
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "awaiting_human": 0,
        }
        
        for task in tree.tasks:
            if task.status == TaskStatus.PENDING:
                by_status["pending"] += 1
            elif task.status == TaskStatus.RUNNING:
                by_status["running"] += 1
            elif task.status == TaskStatus.COMPLETED:
                by_status["completed"] += 1
            elif task.status == TaskStatus.FAILED:
                by_status["failed"] += 1
            elif task.status == TaskStatus.AWAITING_HUMAN:
                by_status["awaiting_human"] += 1
        
        by_status["percent"] = int((by_status["completed"] / total) * 100) if total > 0 else 0
        return by_status
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_hitl/test_orchestrator_hitl.py -v`
Expected: 2 passing tests

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/agent/orchestrator.py backend/homics_lab/hitl/detector.py backend/tests/test_hitl/test_orchestrator_hitl.py
git commit -m "feat: integrate HITL checkpoints with orchestrator pause/resume"
```

---

## Milestone 6 Complete ✅

At this point you have:
- HITL checkpoint detector with multiple trigger types
- Orchestrator pauses tasks awaiting human input
- Resume flow with human response

Next: API Layer.


## Milestone 7: API Layer

### Task 32: Create Chat API and WebSocket Endpoint

**Files:**
- Create: `backend/homics_lab/api/__init__.py`
- Create: `backend/homics_lab/api/router.py`
- Create: `backend/homics_lab/api/chat.py`
- Modify: `backend/homics_lab/main.py` to include router
- Test: `backend/tests/test_api/test_chat.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_api/test_chat.py`:

```python
import pytest
from fastapi.testclient import TestClient
from homics_lab.main import app

client = TestClient(app)


def test_send_message():
    response = client.post("/api/chat/send", json={
        "project_id": "proj_1",
        "session_id": "sess_1",
        "message": "帮我分析单细胞数据",
    })
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "task_tree" in data


def test_get_messages():
    response = client.get("/api/chat/messages?session_id=sess_1")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_api/test_chat.py -v`
Expected: 404 (routes don't exist yet)

- [ ] **Step 3: Implement chat API**

Create `backend/homics_lab/api/__init__.py`:
```python
from .router import api_router
```

Create `backend/homics_lab/api/router.py`:
```python
from fastapi import APIRouter
from . import chat

api_router = APIRouter(prefix="/api")
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
```

Create `backend/homics_lab/api/chat.py`:

```python
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from homics_lab.agent.agent_registry import get_default_registry
from homics_lab.agent.intent_analyzer import IntentAnalyzer
from homics_lab.agent.orchestrator import Orchestrator
from homics_lab.agent.task_decomposer import TaskDecomposer
from homics_lab.context.prompter import Prompter
from homics_lab.context.working_memory import WorkingMemory
from homics_lab.models.common import ChatMessage, MessageType
from homics_lab.tasks.task_tree import TaskTree

router = APIRouter()

# In-memory session store for MVP
_sessions: dict[str, WorkingMemory] = {}


class SendMessageRequest(BaseModel):
    project_id: str
    session_id: str
    message: str


class SendMessageResponse(BaseModel):
    response: str
    task_tree: dict
    messages: List[dict]


@router.post("/send", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    # Get or create session memory
    wm = _sessions.get(request.session_id, WorkingMemory())
    _sessions[request.session_id] = wm
    
    # Add user message
    user_msg = ChatMessage(
        id=f"msg_{len(wm.messages)}",
        type=MessageType.TEXT,
        content=request.message,
        sender="user",
    )
    wm.add_message(user_msg)
    
    # Analyze intent
    analyzer = IntentAnalyzer()
    intent = await analyzer.analyze(request.message)
    
    # Decompose into task tree
    decomposer = TaskDecomposer()
    tree = await decomposer.decompose(intent, context={"project_id": request.project_id})
    
    # Run orchestrator
    orchestrator = Orchestrator(registry=get_default_registry())
    results = await orchestrator.run_tree(tree)
    
    # Build response
    response_text = f"已为您规划 {len(tree.tasks)} 个分析步骤。"
    if any("hitl" in r for r in results.values()):
        response_text += " 部分步骤需要您确认参数。"
    
    # Add agent message
    agent_msg = ChatMessage(
        id=f"msg_{len(wm.messages)}",
        type=MessageType.TODO_LIST,
        content={
            "text": response_text,
            "tasks": [t.model_dump() for t in tree.tasks],
            "progress": orchestrator.get_progress(tree),
        },
        sender="agent",
    )
    wm.add_message(agent_msg)
    
    return SendMessageResponse(
        response=response_text,
        task_tree={"tasks": [t.model_dump() for t in tree.tasks]},
        messages=[m.model_dump() for m in wm.get_recent_messages()],
    )


@router.get("/messages")
async def get_messages(session_id: str) -> List[dict]:
    wm = _sessions.get(session_id)
    if not wm:
        return []
    return [m.model_dump() for m in wm.get_recent_messages()]


@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # Echo back with type
            await websocket.send_json({
                "type": "ack",
                "session_id": session_id,
                "received": data,
            })
    except WebSocketDisconnect:
        pass
```

- [ ] **Step 4: Wire router into main app**

Modify `backend/homics_lab/main.py`:
```python
from homics_lab.api.router import api_router
# ... after app creation
app.include_router(api_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_api/test_chat.py -v`
Expected: 2 passing tests

- [ ] **Step 6: Commit**

```bash
git add backend/homics_lab/api/ backend/tests/test_api/test_chat.py backend/homics_lab/main.py
git commit -m "feat: add chat REST API and WebSocket endpoint"
```

---

### Task 33: Add HITL Response API

**Files:**
- Modify: `backend/homics_lab/api/chat.py`
- Test: `backend/tests/test_api/test_hitl_api.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_api/test_hitl_api.py`:

```python
from fastapi.testclient import TestClient
from homics_lab.main import app

client = TestClient(app)


def test_hitl_response():
    # First send a message that triggers HITL
    response = client.post("/api/chat/send", json={
        "project_id": "proj_1",
        "session_id": "sess_hitl",
        "message": "帮我做聚类分析",
    })
    assert response.status_code == 200
    
    # Respond to HITL
    response = client.post("/api/chat/hitl/respond", json={
        "session_id": "sess_hitl",
        "task_id": response.json()["task_tree"]["tasks"][0]["id"],
        "choice": "ok",
        "parameters": {"n_neighbors": 20},
    })
    assert response.status_code == 200
    data = response.json()
    assert "result" in data or "message" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_api/test_hitl_api.py -v`
Expected: 404

- [ ] **Step 3: Implement HITL response endpoint**

Add to `backend/homics_lab/api/chat.py`:

```python
from pydantic import BaseModel
from typing import Dict, Any

# Add after SendMessageResponse

class HITLResponseRequest(BaseModel):
    session_id: str
    task_id: str
    choice: str
    parameters: Dict[str, Any] = {}


class HITLResponseResponse(BaseModel):
    message: str
    result: Dict[str, Any]


# Add endpoint

# In-memory task tree storage for MVP (replace with DB in production)
_task_trees: dict[str, TaskTree] = {}


# Modify send_message to store tree
@router.post("/send", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    # ... existing logic ...
    _task_trees[request.session_id] = tree
    # ... rest unchanged ...


@router.post("/hitl/respond", response_model=HITLResponseResponse)
async def respond_to_hitl(request: HITLResponseRequest):
    tree = _task_trees.get(request.session_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Session not found")
    
    orchestrator = Orchestrator(registry=get_default_registry())
    result = await orchestrator.resume_task(
        tree,
        request.task_id,
        {"choice": request.choice, "parameters": request.parameters},
    )
    
    return HITLResponseResponse(
        message="Task resumed successfully",
        result=result,
    )
```

Also add `from fastapi import HTTPException` to imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_api/test_hitl_api.py -v`
Expected: Test passes

- [ ] **Step 5: Commit**

```bash
git add backend/homics_lab/api/chat.py backend/tests/test_api/test_hitl_api.py
git commit -m "feat: add HITL response API endpoint"
```

---

### Task 34: Add Project and File Upload APIs

**Files:**
- Create: `backend/homics_lab/api/projects.py`
- Create: `backend/homics_lab/api/files.py`
- Modify: `backend/homics_lab/api/router.py`
- Test: `backend/tests/test_api/test_projects.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_api/test_projects.py`:

```python
from fastapi.testclient import TestClient
from homics_lab.main import app

client = TestClient(app)


def test_create_project():
    response = client.post("/api/projects", json={
        "name": "PBMC Analysis",
        "description": "Single cell analysis of PBMC 3k",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "PBMC Analysis"
    assert "id" in data


def test_list_projects():
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_api/test_projects.py -v`
Expected: 404

- [ ] **Step 3: Implement project API**

Create `backend/homics_lab/api/projects.py`:

```python
from typing import List
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel, Field
import uuid

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


# In-memory store for MVP
_projects: List[ProjectResponse] = []


@router.post("", response_model=ProjectResponse)
async def create_project(project: ProjectCreate):
    now = datetime.utcnow()
    p = ProjectResponse(
        id=f"proj_{uuid.uuid4().hex[:8]}",
        name=project.name,
        description=project.description,
        created_at=now,
        updated_at=now,
    )
    _projects.append(p)
    return p


@router.get("", response_model=List[ProjectResponse])
async def list_projects():
    return _projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    for p in _projects:
        if p.id == project_id:
            return p
    raise HTTPException(status_code=404, detail="Project not found")
```

- [ ] **Step 4: Implement file upload API**

Create `backend/homics_lab/api/files.py`:

```python
from pathlib import Path
from fastapi import APIRouter, UploadFile, File
from homics_lab.config import settings

router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), project_id: str = "default"):
    project_dir = settings.data_dir / "raw" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = project_dir / file.filename
    content = await file.read()
    file_path.write_bytes(content)
    
    return {
        "filename": file.filename,
        "path": str(file_path),
        "size": len(content),
    }
```

- [ ] **Step 5: Update router**

Modify `backend/homics_lab/api/router.py`:
```python
from fastapi import APIRouter
from . import chat, projects, files

api_router = APIRouter(prefix="/api")
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/test_api/test_projects.py -v`
Expected: 2 passing tests

- [ ] **Step 7: Commit**

```bash
git add backend/homics_lab/api/projects.py backend/homics_lab/api/files.py backend/homics_lab/api/router.py backend/tests/test_api/test_projects.py
git commit -m "feat: add project management and file upload APIs"
```

---

## Milestone 7 Complete ✅

At this point you have:
- REST API for chat, projects, file uploads
- WebSocket endpoint for real-time updates
- HITL response API
- In-memory stores for MVP (replace with DB in Phase 2)

Next: Frontend core.


## Milestone 8: Frontend Core

### Task 35: Setup API Client and Types

**Files:**
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/types/chat.ts`
- Create: `frontend/src/types/tasks.ts`
- Create: `frontend/src/services/api.ts`

- [ ] **Step 1: Create shared TypeScript types**

`frontend/src/types/api.ts`:
```typescript
export interface Project {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
}

export interface SendMessageRequest {
  project_id: string
  session_id: string
  message: string
}

export interface SendMessageResponse {
  response: string
  task_tree: { tasks: TaskNode[] }
  messages: ChatMessage[]
}

export interface FileUploadResponse {
  filename: string
  path: string
  size: number
}
```

`frontend/src/types/chat.ts`:
```typescript
export type MessageType =
  | 'text'
  | 'todo_list'
  | 'hitl_request'
  | 'tool_call'
  | 'result_preview'
  | 'parameter_form'
  | 'file_reference'
  | 'error'
  | 'system'

export interface ChatMessage {
  id: string
  type: MessageType
  content: string | Record<string, unknown>
  sender: 'user' | 'agent' | 'system'
  timestamp: string
  task_id?: string
  skill_id?: string
  related_files?: string[]
}
```

`frontend/src/types/tasks.ts`:
```typescript
export type TaskStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'awaiting_human'
  | 'aborted'

export interface TaskNode {
  id: string
  name: string
  description: string
  phase: string
  status: TaskStatus
  dependencies: string[]
  agent_assignment?: string
  skills_required: string[]
  estimated_duration_minutes: number
  parameters: Record<string, unknown>
  result?: Record<string, unknown>
  error_message?: string
}

export interface TaskProgress {
  total: number
  pending: number
  running: number
  completed: number
  failed: number
  awaiting_human: number
  percent: number
}
```

- [ ] **Step 2: Create API client**

`frontend/src/services/api.ts`:
```typescript
import axios from 'axios'
import type { SendMessageRequest, SendMessageResponse, Project, FileUploadResponse } from '@/types/api'

const API_BASE = '/api'

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const chatApi = {
  sendMessage: (data: SendMessageRequest) =>
    api.post<SendMessageResponse>('/chat/send', data),
  
  getMessages: (sessionId: string) =>
    api.get<ChatMessage[]>(`/chat/messages?session_id=${sessionId}`),
  
  respondToHITL: (data: { session_id: string; task_id: string; choice: string; parameters?: Record<string, unknown> }) =>
    api.post('/chat/hitl/respond', data),
}

export const projectApi = {
  createProject: (data: { name: string; description?: string }) =>
    api.post<Project>('/projects', data),
  
  listProjects: () =>
    api.get<Project[]>('/projects'),
}

export const fileApi = {
  uploadFile: (file: File, projectId: string) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<FileUploadResponse>(`/files/upload?project_id=${projectId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export default api
```

Add missing import at top:
```typescript
import type { ChatMessage } from '@/types/chat'
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/ frontend/src/services/api.ts
git commit -m "chore: add frontend API types and client"
```

---

### Task 36: Create Zustand Chat Store

**Files:**
- Create: `frontend/src/stores/chatStore.ts`
- Test: `frontend/src/stores/chatStore.test.ts`

- [ ] **Step 1: Write test**

Create `frontend/src/stores/chatStore.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { useChatStore } from './chatStore'

describe('chatStore', () => {
  it('should add a message', () => {
    const store = useChatStore.getState()
    store.addMessage({
      id: '1',
      type: 'text',
      content: 'hello',
      sender: 'user',
      timestamp: new Date().toISOString(),
    })
    
    expect(useChatStore.getState().messages).toHaveLength(1)
    expect(useChatStore.getState().messages[0].content).toBe('hello')
  })

  it('should set typing state', () => {
    useChatStore.getState().setIsTyping(true)
    expect(useChatStore.getState().isTyping).toBe(true)
  })
})
```

- [ ] **Step 2: Create chat store**

Create `frontend/src/stores/chatStore.ts`:

```typescript
import { create } from 'zustand'
import type { ChatMessage } from '@/types/chat'

interface ChatState {
  messages: ChatMessage[]
  isTyping: boolean
  currentSessionId: string
  currentProjectId: string
  
  addMessage: (message: ChatMessage) => void
  setMessages: (messages: ChatMessage[]) => void
  setIsTyping: (typing: boolean) => void
  setSessionId: (id: string) => void
  setProjectId: (id: string) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isTyping: false,
  currentSessionId: `sess_${Date.now()}`,
  currentProjectId: 'default',
  
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  
  setMessages: (messages) => set({ messages }),
  setIsTyping: (isTyping) => set({ isTyping }),
  setSessionId: (currentSessionId) => set({ currentSessionId }),
  setProjectId: (currentProjectId) => set({ currentProjectId }),
  clearMessages: () => set({ messages: [] }),
}))
```

- [ ] **Step 3: Install vitest and run tests**

Run:
```bash
cd frontend
npm install -D vitest @testing-library/react jsdom
```

Update `frontend/package.json` scripts:
```json
"test": "vitest --run"
```

Update `frontend/vite.config.ts` to add test config:
```typescript
export default defineConfig({
  // ... existing config
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
```

Run: `cd frontend && npm test`
Expected: Tests pass

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/ frontend/package.json frontend/vite.config.ts
git commit -m "feat: add Zustand chat store with tests"
```

---

### Task 37: Create Task Store

**Files:**
- Create: `frontend/src/stores/taskStore.ts`
- Test: `frontend/src/stores/taskStore.test.ts`

- [ ] **Step 1: Write test**

Create `frontend/src/stores/taskStore.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { useTaskStore } from './taskStore'
import type { TaskNode } from '@/types/tasks'

describe('taskStore', () => {
  it('should update task tree', () => {
    const tree: TaskNode[] = [
      { id: '1', name: 'qc', description: 'QC', phase: 'pre', status: 'pending', dependencies: [], skills_required: [], estimated_duration_minutes: 10, parameters: {} },
    ]
    
    useTaskStore.getState().setTaskTree(tree)
    expect(useTaskStore.getState().tasks).toHaveLength(1)
    expect(useTaskStore.getState().tasks[0].name).toBe('qc')
  })

  it('should update task status', () => {
    const tree: TaskNode[] = [
      { id: '1', name: 'qc', description: 'QC', phase: 'pre', status: 'pending', dependencies: [], skills_required: [], estimated_duration_minutes: 10, parameters: {} },
    ]
    
    useTaskStore.getState().setTaskTree(tree)
    useTaskStore.getState().updateTaskStatus('1', 'running')
    
    expect(useTaskStore.getState().tasks[0].status).toBe('running')
  })
})
```

- [ ] **Step 2: Create task store**

Create `frontend/src/stores/taskStore.ts`:

```typescript
import { create } from 'zustand'
import type { TaskNode, TaskProgress, TaskStatus } from '@/types/tasks'

interface TaskState {
  tasks: TaskNode[]
  progress: TaskProgress
  selectedTaskId: string | null
  
  setTaskTree: (tasks: TaskNode[]) => void
  updateTaskStatus: (taskId: string, status: TaskStatus) => void
  updateTaskResult: (taskId: string, result: Record<string, unknown>) => void
  setProgress: (progress: TaskProgress) => void
  selectTask: (taskId: string | null) => void
}

const emptyProgress: TaskProgress = {
  total: 0,
  pending: 0,
  running: 0,
  completed: 0,
  failed: 0,
  awaiting_human: 0,
  percent: 0,
}

export const useTaskStore = create<TaskState>((set) => ({
  tasks: [],
  progress: emptyProgress,
  selectedTaskId: null,
  
  setTaskTree: (tasks) => set({ tasks }),
  
  updateTaskStatus: (taskId, status) =>
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === taskId ? { ...t, status } : t
      ),
    })),
  
  updateTaskResult: (taskId, result) =>
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === taskId ? { ...t, result } : t
      ),
    })),
  
  setProgress: (progress) => set({ progress }),
  selectTask: (selectedTaskId) => set({ selectedTaskId }),
}))
```

- [ ] **Step 3: Run tests**

Run: `cd frontend && npm test`
Expected: Tests pass

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/taskStore.ts frontend/src/stores/taskStore.test.ts
git commit -m "feat: add Zustand task store"
```

---

### Task 38: Build Chat Panel UI

**Files:**
- Create: `frontend/src/components/chat/ChatPanel.tsx`
- Create: `frontend/src/components/chat/MessageList.tsx`
- Create: `frontend/src/components/chat/MessageBubble.tsx`
- Create: `frontend/src/components/chat/ChatInput.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create MessageBubble component**

Create `frontend/src/components/chat/MessageBubble.tsx`:

```tsx
import type { ChatMessage } from '@/types/chat'

interface Props {
  message: ChatMessage
}

export function MessageBubble({ message }: Props) {
  const isUser = message.sender === 'user'
  
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 ${
          isUser
            ? 'bg-primary text-white'
            : 'bg-white border border-slate-200 text-slate-800'
        }`}
      >
        <div className="text-xs opacity-75 mb-1">
          {isUser ? 'You' : 'Agent'} • {new Date(message.timestamp).toLocaleTimeString()}
        </div>
        <div className="text-sm">
          {typeof message.content === 'string'
            ? message.content
            : JSON.stringify(message.content, null, 2)}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create MessageList component**

Create `frontend/src/components/chat/MessageList.tsx`:

```tsx
import { useEffect, useRef } from 'react'
import { useChatStore } from '@/stores/chatStore'
import { MessageBubble } from './MessageBubble'

export function MessageList() {
  const messages = useChatStore((state) => state.messages)
  const bottomRef = useRef<HTMLDivElement>(null)
  
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-2">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
```

- [ ] **Step 3: Create ChatInput component**

Create `frontend/src/components/chat/ChatInput.tsx`:

```tsx
import { useState } from 'react'
import { useChatStore } from '@/stores/chatStore'
import { chatApi } from '@/services/api'
import type { ChatMessage } from '@/types/chat'

export function ChatInput() {
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const { addMessage, currentSessionId, currentProjectId, setIsTyping } = useChatStore()
  
  const handleSend = async () => {
    if (!input.trim() || isLoading) return
    
    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      type: 'text',
      content: input,
      sender: 'user',
      timestamp: new Date().toISOString(),
    }
    addMessage(userMessage)
    setInput('')
    setIsLoading(true)
    setIsTyping(true)
    
    try {
      const response = await chatApi.sendMessage({
        project_id: currentProjectId,
        session_id: currentSessionId,
        message: input,
      })
      
      const agentMessage: ChatMessage = {
        id: `msg_${Date.now()}_agent`,
        type: 'todo_list',
        content: {
          text: response.data.response,
          tasks: response.data.task_tree.tasks,
        },
        sender: 'agent',
        timestamp: new Date().toISOString(),
      }
      addMessage(agentMessage)
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: `msg_${Date.now()}_error`,
        type: 'error',
        content: 'Failed to send message. Please try again.',
        sender: 'system',
        timestamp: new Date().toISOString(),
      }
      addMessage(errorMessage)
    } finally {
      setIsLoading(false)
      setIsTyping(false)
    }
  }
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }
  
  return (
    <div className="border-t border-slate-200 p-4 bg-white">
      <div className="flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="描述您的分析需求..."
          rows={2}
          className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
          className="rounded-lg bg-primary px-4 py-2 text-white text-sm font-medium disabled:opacity-50 hover:bg-blue-700"
        >
          {isLoading ? '发送中...' : '发送'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Create ChatPanel component**

Create `frontend/src/components/chat/ChatPanel.tsx`:

```tsx
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'

export function ChatPanel() {
  return (
    <div className="flex h-full flex-col border-r border-slate-200 bg-slate-50">
      <div className="border-b border-slate-200 bg-white px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-800">对话</h2>
      </div>
      <MessageList />
      <ChatInput />
    </div>
  )
}
```

- [ ] **Step 5: Update App.tsx to show chat panel**

Modify `frontend/src/App.tsx`:

```tsx
import { ChatPanel } from '@/components/chat/ChatPanel'

function App() {
  return (
    <div className="flex h-screen flex-col bg-slate-50">
      <header className="bg-primary px-4 py-3 text-white">
        <h1 className="text-lg font-bold">HomicsLab</h1>
      </header>
      <main className="flex flex-1 overflow-hidden">
        <div className="w-2/5 min-w-[360px] max-w-[480px]">
          <ChatPanel />
        </div>
        <div className="flex-1 bg-white p-4">
          <div className="flex h-full items-center justify-center rounded-lg border-2 border-dashed border-slate-200">
            <p className="text-slate-400">工作空间将在后续任务中实现</p>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
```

- [ ] **Step 6: Verify dev server shows chat panel**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/chat/ frontend/src/App.tsx
git commit -m "feat: add chat panel UI with message list and input"
```

---

### Task 39: Render TODO Lists in Chat

**Files:**
- Create: `frontend/src/components/chat/TodoList.tsx`
- Modify: `frontend/src/components/chat/MessageBubble.tsx`

- [ ] **Step 1: Create TodoList component**

Create `frontend/src/components/chat/TodoList.tsx`:

```tsx
import { useTaskStore } from '@/stores/taskStore'
import type { TaskNode, TaskProgress } from '@/types/tasks'

interface Props {
  content: {
    text: string
    tasks: TaskNode[]
    progress?: TaskProgress
  }
}

const statusIcons: Record<TaskNode['status'], string> = {
  pending: '⬜',
  running: '▶️',
  completed: '✅',
  failed: '❌',
  awaiting_human: '⏸️',
  aborted: '🚫',
}

export function TodoList({ content }: Props) {
  const selectTask = useTaskStore((state) => state.selectTask)
  
  return (
    <div className="space-y-3">
      <p className="text-sm">{content.text}</p>
      
      {content.progress && (
        <div className="mb-3">
          <div className="mb-1 flex justify-between text-xs text-slate-600">
            <span>进度</span>
            <span>{content.progress.completed}/{content.progress.total}</span>
          </div>
          <div className="h-2 w-full rounded-full bg-slate-200">
            <div
              className="h-2 rounded-full bg-success transition-all"
              style={{ width: `${content.progress.percent}%` }}
            />
          </div>
        </div>
      )}
      
      <ul className="space-y-1">
        {content.tasks?.map((task) => (
          <li
            key={task.id}
            onClick={() => selectTask(task.id)}
            className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-slate-100"
          >
            <span>{statusIcons[task.status]}</span>
            <span className="flex-1">{task.description}</span>
            <span className="text-xs text-slate-500">{task.phase}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 2: Update MessageBubble to render typed content**

Modify `frontend/src/components/chat/MessageBubble.tsx`:

```tsx
import type { ChatMessage } from '@/types/chat'
import { TodoList } from './TodoList'

interface Props {
  message: ChatMessage
}

export function MessageBubble({ message }: Props) {
  const isUser = message.sender === 'user'
  
  const renderContent = () => {
    if (typeof message.content === 'string') {
      return <p className="text-sm">{message.content}</p>
    }
    
    switch (message.type) {
      case 'todo_list':
        return <TodoList content={message.content as { text: string; tasks: any[]; progress?: any }} />
      case 'error':
        return <p className="text-sm text-error">{message.content as string}</p>
      default:
        return <pre className="text-xs">{JSON.stringify(message.content, null, 2)}</pre>
    }
  }
  
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[90%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-primary text-white'
            : 'bg-white border border-slate-200 text-slate-800'
        }`}
      >
        <div className="text-xs opacity-75 mb-1">
          {isUser ? 'You' : 'Agent'} • {new Date(message.timestamp).toLocaleTimeString()}
        </div>
        {renderContent()}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/chat/TodoList.tsx frontend/src/components/chat/MessageBubble.tsx
git commit -m "feat: render TODO lists with progress in chat panel"
```

---

### Task 40: Build HITL Request Component

**Files:**
- Create: `frontend/src/components/chat/HITLRequest.tsx`
- Modify: `frontend/src/components/chat/MessageBubble.tsx`
- Modify: `frontend/src/components/chat/MessageList.tsx`

- [ ] **Step 1: Create HITLRequest component**

Create `frontend/src/components/chat/HITLRequest.tsx`:

```tsx
import { useState } from 'react'
import { chatApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'

interface Option {
  id: string
  label: string
  description?: string
}

interface Props {
  checkpoint: {
    id: string
    trigger_reason: string
    context_summary: string
    options: Option[]
    default_option?: Option
  }
  taskId: string
}

export function HITLRequest({ checkpoint, taskId }: Props) {
  const [selectedOption, setSelectedOption] = useState(checkpoint.default_option?.id || '')
  const [parameters, setParameters] = useState('{}')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { currentSessionId, addMessage } = useChatStore()
  
  const handleSubmit = async () => {
    if (!selectedOption) return
    
    setIsSubmitting(true)
    try {
      let parsedParams = {}
      try {
        parsedParams = JSON.parse(parameters)
      } catch {
        // Invalid JSON, ignore
      }
      
      await chatApi.respondToHITL({
        session_id: currentSessionId,
        task_id: taskId,
        choice: selectedOption,
        parameters: parsedParams,
      })
      
      addMessage({
        id: `msg_${Date.now()}`,
        type: 'system',
        content: `已确认：${checkpoint.options.find(o => o.id === selectedOption)?.label}`,
        sender: 'system',
        timestamp: new Date().toISOString(),
      })
    } finally {
      setIsSubmitting(false)
    }
  }
  
  return (
    <div className="rounded-lg border border-warning bg-yellow-50 p-3">
      <p className="mb-2 text-sm font-medium text-yellow-900">
        ⚠️ 需要您确认
      </p>
      <p className="mb-3 text-sm text-yellow-800">{checkpoint.context_summary}</p>
      
      <div className="mb-3 space-y-2">
        {checkpoint.options.map((option) => (
          <label
            key={option.id}
            className={`flex cursor-pointer items-start gap-2 rounded p-2 text-sm ${
              selectedOption === option.id ? 'bg-yellow-100' : 'hover:bg-yellow-100'
            }`}
          >
            <input
              type="radio"
              name={`hitl-${checkpoint.id}`}
              value={option.id}
              checked={selectedOption === option.id}
              onChange={() => setSelectedOption(option.id)}
              className="mt-1"
            />
            <div>
              <div className="font-medium">{option.label}</div>
              {option.description && (
                <div className="text-xs text-yellow-700">{option.description}</div>
              )}
            </div>
          </label>
        ))}
      </div>
      
      <div className="mb-3">
        <label className="mb-1 block text-xs font-medium text-yellow-800">
          参数 (JSON)
        </label>
        <textarea
          value={parameters}
          onChange={(e) => setParameters(e.target.value)}
          rows={2}
          className="w-full rounded border border-yellow-300 px-2 py-1 text-xs"
          placeholder='{"n_neighbors": 15}'
        />
      </div>
      
      <button
        onClick={handleSubmit}
        disabled={!selectedOption || isSubmitting}
        className="rounded bg-warning px-3 py-1.5 text-sm font-medium text-white hover:bg-yellow-600 disabled:opacity-50"
      >
        {isSubmitting ? '提交中...' : '确认'}
      </button>
    </div>
  )
}
```

- [ ] **Step 2: Update MessageBubble to render HITL requests**

Modify `frontend/src/components/chat/MessageBubble.tsx`:

```tsx
import type { ChatMessage } from '@/types/chat'
import { TodoList } from './TodoList'
import { HITLRequest } from './HITLRequest'

// ... inside renderContent switch case
      case 'hitl_request':
        const hitl = message.content as { checkpoint: any; task_id: string }
        return <HITLRequest checkpoint={hitl.checkpoint} taskId={hitl.task_id} />
```

- [ ] **Step 3: Update backend to send HITL messages**

Modify `backend/homics_lab/api/chat.py` send_message to detect HITL results and add a hitl_request message:

```python
# After running orchestrator
hitl_found = None
for task_id, result in results.items():
    if "hitl" in result:
        hitl_found = {"checkpoint": result["hitl"], "task_id": task_id}
        break

if hitl_found:
    agent_msg = ChatMessage(
        id=f"msg_{len(wm.messages)}",
        type=MessageType.HITL_REQUEST,
        content=hitl_found,
        sender="agent",
    )
else:
    agent_msg = ChatMessage(
        id=f"msg_{len(wm.messages)}",
        type=MessageType.TODO_LIST,
        content={
            "text": response_text,
            "tasks": [t.model_dump() for t in tree.tasks],
            "progress": orchestrator.get_progress(tree),
        },
        sender="agent",
    )
```

- [ ] **Step 4: Verify build and commit**

Run: `cd frontend && npm run build`
Expected: Build succeeds

Run backend tests: `cd backend && pytest`
Expected: Tests pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/HITLRequest.tsx backend/homics_lab/api/chat.py
git commit -m "feat: add HITL request UI and backend message formatting"
```

---

## Milestone 8 Complete ✅

At this point you have:
- API client with TypeScript types
- Zustand stores for chat and tasks
- Chat panel with message list, input, TODO lists
- HITL request UI
- Backend sends typed messages

Next: Workspace visualization.


## Milestone 9: Workspace Visualization

### Task 41: Build Simple Workflow Canvas

**Files:**
- Create: `frontend/src/components/workspace/Workspace.tsx`
- Create: `frontend/src/components/workspace/FlowCanvas.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Install ReactFlow**

Run: `cd frontend && npm install reactflow`

- [ ] **Step 2: Create FlowCanvas component**

Create `frontend/src/components/workspace/FlowCanvas.tsx`:

```tsx
import { useCallback, useEffect } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  NodeProps,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { useTaskStore } from '@/stores/taskStore'
import type { TaskNode } from '@/types/tasks'

const statusColors: Record<TaskNode['status'], string> = {
  pending: '#94a3b8',
  running: '#2563eb',
  completed: '#16a34a',
  failed: '#dc2626',
  awaiting_human: '#eab308',
  aborted: '#64748b',
}

function TaskNodeComponent({ data, selected }: NodeProps<TaskNode>) {
  const selectTask = useTaskStore((state) => state.selectTask)
  
  return (
    <div
      onClick={() => selectTask(data.id)}
      className={`rounded-lg border-2 bg-white p-3 shadow-sm cursor-pointer ${
        selected ? 'border-primary' : 'border-slate-200'
      }`}
      style={{ borderLeftColor: statusColors[data.status], borderLeftWidth: 4 }}
    >
      <Handle type="target" position={Position.Top} />
      <div className="text-sm font-semibold">{data.name}</div>
      <div className="text-xs text-slate-500">{data.description}</div>
      <div className="mt-1 text-xs font-medium" style={{ color: statusColors[data.status] }}>
        {data.status}
      </div>
      
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

const nodeTypes = {
  task: TaskNodeComponent,
}

export function FlowCanvas() {
  const tasks = useTaskStore((state) => state.tasks)
  const selectedTaskId = useTaskStore((state) => state.selectedTaskId)
  
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  
  useEffect(() => {
    const newNodes = tasks.map((task, index) => ({
      id: task.id,
      type: 'task',
      position: { x: 100 + (index % 3) * 250, y: 100 + Math.floor(index / 3) * 150 },
      data: task,
      selected: task.id === selectedTaskId,
    }))
    
    const newEdges = tasks.flatMap((task) =>
      task.dependencies.map((depId) => ({
        id: `e-${depId}-${task.id}`,
        source: depId,
        target: task.id,
        animated: task.status === 'running',
        style: { stroke: statusColors[task.status] },
      }))
    )
    
    setNodes(newNodes)
    setEdges(newEdges)
  }, [tasks, selectedTaskId])
  
  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap nodeStrokeWidth={3} />
      </ReactFlow>
    </div>
  )
}
```

- [ ] **Step 3: Create Workspace component**

Create `frontend/src/components/workspace/Workspace.tsx`:

```tsx
import { FlowCanvas } from './FlowCanvas'
import { DetailPanel } from './DetailPanel'

export function Workspace() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 bg-white px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-800">工作空间</h2>
      </div>
      
      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1">
          <FlowCanvas />
        </div>
        <DetailPanel />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Create DetailPanel component**

Create `frontend/src/components/workspace/DetailPanel.tsx`:

```tsx
import { useTaskStore } from '@/stores/taskStore'

export function DetailPanel() {
  const selectedTaskId = useTaskStore((state) => state.selectedTaskId)
  const tasks = useTaskStore((state) => state.tasks)
  
  const task = tasks.find((t) => t.id === selectedTaskId)
  
  if (!task) {
    return (
      <div className="w-72 border-l border-slate-200 bg-slate-50 p-4">
        <p className="text-sm text-slate-500">点击节点查看详情</p>
      </div>
    )
  }
  
  return (
    <div className="w-72 overflow-y-auto border-l border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-lg font-semibold">{task.name}</h3>
      <p className="mb-4 text-sm text-slate-600">{task.description}</p>
      
      <div className="mb-4 space-y-2 text-sm">
        <div>
          <span className="font-medium">状态: </span>
          <span className="rounded px-2 py-0.5 text-xs bg-slate-100">{task.status}</span>
        </div>
        <div>
          <span className="font-medium">阶段: </span>
          {task.phase}
        </div>
        <div>
          <span className="font-medium">预计耗时: </span>
          {task.estimated_duration_minutes} 分钟
        </div>
        {task.skills_required.length > 0 && (
          <div>
            <span className="font-medium">所需 Skills: </span>
            {task.skills_required.join(', ')}
          </div>
        )}
      </div>
      
      {task.parameters && Object.keys(task.parameters).length > 0 && (
        <div className="mb-4">
          <h4 className="mb-2 text-sm font-medium">参数</h4>
          <pre className="rounded bg-slate-50 p-2 text-xs">
            {JSON.stringify(task.parameters, null, 2)}
          </pre>
        </div>
      )}
      
      {task.result && (
        <div className="mb-4">
          <h4 className="mb-2 text-sm font-medium">结果</h4>
          <pre className="rounded bg-slate-50 p-2 text-xs">
            {JSON.stringify(task.result, null, 2)}
          </pre>
        </div>
      )}
      
      {task.error_message && (
        <div className="mb-4">
          <h4 className="mb-2 text-sm font-medium text-error">错误</h4>
          <p className="text-xs text-error">{task.error_message}</p>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Update App.tsx to use Workspace**

Modify `frontend/src/App.tsx`:

```tsx
import { ChatPanel } from '@/components/chat/ChatPanel'
import { Workspace } from '@/components/workspace/Workspace'

function App() {
  return (
    <div className="flex h-screen flex-col bg-slate-50">
      <header className="bg-primary px-4 py-3 text-white">
        <h1 className="text-lg font-bold">HomicsLab</h1>
      </header>
      <main className="flex flex-1 overflow-hidden">
        <div className="w-2/5 min-w-[360px] max-w-[480px]">
          <ChatPanel />
        </div>
        <div className="flex-1">
          <Workspace />
        </div>
      </main>
    </div>
  )
}

export default App
```

- [ ] **Step 6: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/workspace/ frontend/src/App.tsx
git commit -m "feat: add ReactFlow-based workspace with task node visualization"
```

---

### Task 42: Sync Task Tree Between Chat and Workspace

**Files:**
- Modify: `frontend/src/components/chat/ChatInput.tsx`
- Modify: `frontend/src/stores/taskStore.ts`

- [ ] **Step 1: Update ChatInput to populate task store**

Modify `frontend/src/components/chat/ChatInput.tsx`:

```tsx
import { useTaskStore } from '@/stores/taskStore'
// ... existing imports

export function ChatInput() {
  // ... existing state
  const { setTaskTree, setProgress } = useTaskStore()
  
  const handleSend = async () => {
    // ... existing user message logic
    
    try {
      const response = await chatApi.sendMessage({ ... })
      
      // Update task store
      const tasks = response.data.task_tree.tasks
      setTaskTree(tasks)
      if (response.data.messages[response.data.messages.length - 1]?.content?.progress) {
        setProgress(response.data.messages[response.data.messages.length - 1].content.progress)
      }
      
      // ... existing agent message logic
    } catch (error) {
      // ... existing error handling
    }
  }
  // ... rest unchanged
}
```

- [ ] **Step 2: Test by running dev server**

Run backend: `cd backend && uvicorn homics_lab.main:app --reload --port 8080`
Run frontend: `cd frontend && npm run dev`

Open browser to `http://localhost:5173`
Send message: "帮我分析单细胞数据"
Expected: Chat shows response, workspace shows task nodes

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/ChatInput.tsx frontend/src/stores/taskStore.ts
git commit -m "feat: sync task tree between chat and workspace"
```

---

### Task 43: Add File Upload UI

**Files:**
- Create: `frontend/src/components/shared/DataUploader.tsx`
- Modify: `frontend/src/App.tsx` to include uploader
- Test: Basic manual test

- [ ] **Step 1: Create DataUploader component**

Create `frontend/src/components/shared/DataUploader.tsx`:

```tsx
import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { fileApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'

export function DataUploader() {
  const { currentProjectId } = useChatStore()
  
  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    for (const file of acceptedFiles) {
      try {
        const response = await fileApi.uploadFile(file, currentProjectId)
        console.log('Uploaded:', response.data)
        alert(`上传成功: ${response.data.filename}`)
      } catch (error) {
        alert(`上传失败: ${file.name}`)
      }
    }
  }, [currentProjectId])
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/octet-stream': ['.h5ad', '.mtx', '.fastq.gz'],
    },
  })
  
  return (
    <div
      {...getRootProps()}
      className={`cursor-pointer rounded-lg border-2 border-dashed p-4 text-center transition-colors ${
        isDragActive
          ? 'border-primary bg-blue-50'
          : 'border-slate-300 hover:border-primary'
      }`}
    >
      <input {...getInputProps()} />
      <p className="text-sm text-slate-600">
        {isDragActive
          ? '释放文件以上传'
          : '拖拽文件到此处，或点击选择文件'}
      </p>
      <p className="mt-1 text-xs text-slate-400">支持 .h5ad, .mtx, .fastq.gz</p>
    </div>
  )
}
```

- [ ] **Step 2: Install react-dropzone**

Run: `cd frontend && npm install react-dropzone`

- [ ] **Step 3: Add uploader to workspace detail panel**

Modify `frontend/src/components/workspace/DetailPanel.tsx` to show DataUploader when no task is selected:

```tsx
import { DataUploader } from '@/components/shared/DataUploader'

// In the no-task-selected case:
<div className="w-72 border-l border-slate-200 bg-slate-50 p-4">
  <p className="mb-4 text-sm text-slate-500">点击节点查看详情，或上传数据开始分析</p>
  <DataUploader />
</div>
```

- [ ] **Step 4: Verify build and commit**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/shared/DataUploader.tsx frontend/src/components/workspace/DetailPanel.tsx
git commit -m "feat: add drag-and-drop file upload component"
```

---

## Milestone 9 Complete ✅

At this point you have:
- ReactFlow-based workspace canvas
- Task nodes with status colors
- Detail panel showing task info
- Bidirectional sync between chat and workspace
- File upload UI

Next: Integration and local deployment.


## Milestone 10: Integration and Local Deployment

### Task 44: Create CLI Entry Point

**Files:**
- Create: `backend/homics_lab/cli.py`
- Modify: `pyproject.toml` to register CLI
- Test: `homics-lab --help`

- [ ] **Step 1: Create CLI module**

Create `backend/homics_lab/cli.py`:

```python
import argparse
import sys
import uvicorn

from homics_lab.config import settings


def main():
    parser = argparse.ArgumentParser(description="HomicsLab - Bioinformatics Agent")
    parser.add_argument(
        "command",
        choices=["start", "version"],
        help="Command to run",
    )
    parser.add_argument("--host", default=settings.host, help="Host to bind")
    parser.add_argument("--port", type=int, default=settings.port, help="Port to bind")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    if args.command == "version":
        from homics_lab import __version__
        print(f"HomicsLab {__version__}")
        return
    
    if args.command == "start":
        print(f"Starting HomicsLab on http://{args.host}:{args.port}")
        uvicorn.run(
            "homics_lab.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify pyproject.toml has script entry**

Ensure `pyproject.toml` contains:
```toml
[project.scripts]
homics-lab = "homics_lab.cli:main"
```

- [ ] **Step 3: Reinstall and test CLI**

Run:
```bash
cd backend
pip install -e "."
homics-lab version
```
Expected: `HomicsLab 0.1.0`

Run: `homics-lab --help`
Expected: Help text displayed

- [ ] **Step 4: Commit**

```bash
git add backend/homics_lab/cli.py
git commit -m "feat: add CLI entry point with start and version commands"
```

---

### Task 45: Add Development Documentation

**Files:**
- Create: `docs/setup.md`
- Create: `docs/architecture.md`
- Modify: `README.md`

- [ ] **Step 1: Write setup documentation**

Create `docs/setup.md`:

```markdown
# HomicsLab Development Setup

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd homics-lab
make install

# 2. Start backend (terminal 1)
make dev-backend

# 3. Start frontend (terminal 2)
make dev-frontend

# 4. Open browser
# http://localhost:5173
```

## Production-like Local Setup

```bash
# SQLite is used by default
HOMICS_DATABASE_URL="sqlite+aiosqlite:///./homics_lab.db" homics-lab start
```

## Running Tests

```bash
make test-backend
make test-frontend
```
```

- [ ] **Step 2: Write architecture overview**

Create `docs/architecture.md`:

```markdown
# HomicsLab MVP Architecture

## Overview
HomicsLab uses a layered hybrid architecture:
- **Core**: Python/FastAPI modular monolith
- **Frontend**: React + TypeScript + Zustand + ReactFlow
- **Skills**: Local subprocess sandbox execution
- **Storage**: SQLite + filesystem

## Data Flow
1. User sends message via React frontend
2. FastAPI receives message, stores in working memory
3. Intent analyzer determines query type
4. Task decomposer creates task tree
5. Orchestrator dispatches tasks to agents
6. Agents execute skills in sandbox
7. Results are returned via WebSocket/REST
8. Frontend updates chat panel and workspace

## Key Components
- `agent/`: Agent engine (intent, decomposition, orchestration)
- `tasks/`: Task tree and state machine
- `context/`: Working memory and context compression
- `skills/`: Skill registry and runtime
- `hitl/`: Human-in-the-loop checkpoints
- `api/`: REST and WebSocket endpoints
- `frontend/src/`: React application
```

- [ ] **Step 3: Update README with setup instructions**

Modify `README.md` to reference `docs/setup.md` and include a quick demo section.

- [ ] **Step 4: Commit**

```bash
git add docs/ README.md
git commit -m "docs: add setup and architecture documentation"
```

---

### Task 46: Add End-to-End Health Check

**Files:**
- Create: `scripts/health_check.py`
- Test: Run full health check

- [ ] **Step 1: Create health check script**

Create `scripts/health_check.py`:

```python
#!/usr/bin/env python3
"""End-to-end health check for HomicsLab."""

import sys
import httpx


def check_backend() -> bool:
    try:
        response = httpx.get("http://localhost:8080/health", timeout=5.0)
        if response.status_code == 200:
            print("✅ Backend is running")
            return True
        else:
            print(f"❌ Backend returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        return False


def check_chat_api() -> bool:
    try:
        response = httpx.post(
            "http://localhost:8080/api/chat/send",
            json={
                "project_id": "health_check",
                "session_id": "health_session",
                "message": "hello",
            },
            timeout=10.0,
        )
        if response.status_code == 200:
            print("✅ Chat API is responding")
            return True
        else:
            print(f"❌ Chat API returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Chat API error: {e}")
        return False


def main():
    print("Running HomicsLab health check...")
    
    checks = [
        check_backend(),
        check_chat_api(),
    ]
    
    if all(checks):
        print("\n✅ All health checks passed")
        return 0
    else:
        print("\n❌ Some health checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run health check against running backend**

In one terminal: `cd backend && homics-lab start`
In another: `python scripts/health_check.py`
Expected: All checks pass

- [ ] **Step 3: Commit**

```bash
git add scripts/health_check.py
git commit -m "chore: add end-to-end health check script"
```

---

### Task 47: Final Integration Testing

**Files:**
- No new files
- Action: Run all tests and fix any remaining issues

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && pytest -v`
Expected: All tests pass (currently ~20-30 tests)

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 3: Run linting**

Run: `cd backend && ruff check .`
Expected: No lint errors (or fix them)

If there are lint errors, run:
```bash
cd backend && ruff check . --fix
cd backend && black .
```

- [ ] **Step 4: Manual end-to-end smoke test**

1. Start backend: `cd backend && homics-lab start`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:5173`
4. Type: "帮我分析单细胞数据"
5. Expected:
   - Chat shows agent response with TODO list
   - Workspace shows 5-6 task nodes
   - Click a node, detail panel shows task info

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve integration test issues"
```

---

### Task 48: Tag MVP Release

**Files:**
- No new files
- Action: Create git tag

- [ ] **Step 1: Update version**

Modify `backend/homics_lab/__init__.py`:
```python
__version__ = "0.1.0-mvp"
```

Modify `frontend/package.json`:
```json
"version": "0.1.0-mvp"
```

- [ ] **Step 2: Create git tag**

```bash
git add -A
git commit -m "chore: bump version to 0.1.0-mvp"
git tag -a v0.1.0-mvp -m "HomicsLab MVP: Agent Brain Core"
```

- [ ] **Step 3: Verify tag**

Run: `git tag -l`
Expected: `v0.1.0-mvp` listed

- [ ] **Step 4: Push tag**

```bash
git push origin v0.1.0-mvp
```

---

## Milestone 10 Complete ✅

At this point you have:
- CLI entry point (`homics-lab start`)
- Development documentation
- Health check script
- All tests passing
- Manual smoke test verified
- MVP release tagged

---

## Self-Review Checklist

### 1. Spec Coverage

| Spec Section | Implemented By Task |
|--------------|---------------------|
| Agent Core Engine (Ch 3) | Tasks 9-18 |
| State & Context Management (Ch 4) | Tasks 20-23 |
| Skills Ecosystem (Ch 5) | Tasks 24-29 |
| HITL (Ch 3.5 / 6) | Tasks 30-31, 40 |
| HPC Scheduling (Ch 6) | **Deferred to Phase 2** |
| Dual-pane Frontend (Ch 7) | Tasks 35-43 |
| Project Management (Ch 8) | Tasks 34, 45 |
| Data Flow & Error Handling (Ch 9) | Tasks 32-34, 46-47 |
| Deployment (Ch 10) | Tasks 44, 48 |

**Gaps identified:**
- HPC/SLURM integration explicitly deferred to Phase 2
- Vector database / semantic search explicitly deferred to Phase 2
- Advanced visualizations (UMAP, heatmap) deferred to Phase 2
- Skills self-generation/evolution deferred to Phase 2
- Team collaboration/sharing deferred to Phase 2
- Report generation deferred to Phase 2

These gaps are intentional per the MVP scope.

### 2. Placeholder Scan

- [x] No "TBD", "TODO", "implement later" found in task steps
- [x] Each task includes actual code snippets
- [x] Each task includes exact commands
- [x] Test code is complete, not just "write tests"

### 3. Type Consistency

- [x] `TaskNode` type consistent across backend (Pydantic) and frontend (TypeScript)
- [x] `ChatMessage` type consistent across both stacks
- [x] `TaskStatus` enum values match between Python and TypeScript
- [x] `AgentType` consistent across agent modules

### 4. Testability

- [x] Each backend module has corresponding tests
- [x] Frontend stores have unit tests
- [x] Integration test via health check script
- [x] Manual smoke test steps documented

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2025-06-08-homomics-lab-mvp.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for learning the codebase as we go and catching issues early.

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints. Faster but less structured.

**Which approach would you prefer?**

---

## Appendix: Phase 2+ Work (Out of Scope for This Plan)

### Phase 2: HPC Integration
- Nextflow executor adapter
- SLURM profile generation
- Job state tracker with polling + webhook
- Resource estimation model

### Phase 3: Advanced Skills
- Skills Forge (self-generation from sessions)
- Evolution Engine (A/B testing, parameter optimization)
- Skills marketplace with ratings

### Phase 4: Visualization
- UMAP/t-SNE scatter plot component
- Gene expression heatmap
- Volcano plot, pathway diagrams
- Interactive charts with Plotly

### Phase 5: Collaboration
- Static report generation (HTML/PDF)
- Share links with expiration
- Simple team permissions
- Data lineage tracking

### Phase 6: Scale
- PostgreSQL migration from SQLite
- Vector DB integration (Milvus)
- Redis for caching
- Cloud deployment (Docker Compose)
