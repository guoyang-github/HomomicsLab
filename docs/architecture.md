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
