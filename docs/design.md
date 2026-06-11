# HomomicsLab Architecture Design (v0.4.1)

## System Overview

HomomicsLab is a **domain-native agent platform** for computational biology. It combines AI agent adaptability with production-grade data engineering rigor.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                  │
│         React + TypeScript + Zustand + WebSocket/REST                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API LAYER (FastAPI)                               │
│  /chat/send  /chat/hitl/respond  /skills  /viz/plot  /reports  /projects    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENT ORCHESTRATION LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ IntentAnalyzer│→│  PlanEngine   │→│DynamicReplan │→│   AgentCore   │   │
│  │              │  │  (strategies) │  │   Engine      │  │ (roles/yaml)  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────┬───────┘   │
│                                                                │            │
│  ┌─────────────────────────────────────────────────────────────┼───────┐   │
│  │                     AgentSwarm                               │       │   │
│  │  Parallel execution · Consensus voting · Broadcast           │       │   │
│  └─────────────────────────────────────────────────────────────┼───────┘   │
│                                                                ▼            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │Orchestrator  │  │ TurnRunner   │  │Interpretation│  │  AgentEvolution│  │
│  │ (state machine│  │ (unified loop)│  │   Engine      │  │    Engine     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SKILL ECOSYSTEM LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ SkillRegistry │  │ SkillLoader   │  │ SkillDAG      │  │ SkillRuntime  │   │
│  │ (discovery)   │  │ (SKILL.md)    │  │ (typed graph) │  │ (sandbox)     │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    ToolRegistry (atomic capabilities)                   │ │
│  │  file_read/write/list · shell_exec · web_search · memory_search       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          KNOWLEDGE & MEMORY LAYER                            │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         CBKB (5 Layers)                                │ │
│  │  ExperimentGraph · ParameterLore · AnomalyArchive · LabSOP · SkillEvolution│ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │CBKBCurator   │  │SemanticMemory│  │WorkingMemory │  │ContextCompress│   │
│  │(auto-curation)│  │ (sqlite-vec) │  │ (session)    │  │ (summarizer)  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STABILITY & REPRODUCIBILITY                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │SchemaValidator│  │VersionLocker │  │RegressionTester│  │Reproducibility│   │
│  │   (L1)       │  │   (L2)       │  │    (L2)       │  │    Engine     │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WORKSPACE & EXECUTION LAYER                           │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  WorkspaceManager (persistent project directories + artifact registry)  │ │
│  │  data/ (read-only) · intermediate/ · outputs/ · logs/ · .metadata/     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │  LineageGraph │  │  Snapshot    │  │  HPC Scheduler│                     │
│  │  (provenance) │  │  (checkpoint)│  │ (SLURM/local)│                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Module Contracts

### 1. PlanEngine + DynamicReplanningEngine

**PlanEngine** generates the initial plan from intent + data state.
**DynamicReplanningEngine** mutates the plan during execution based on triggers.

```python
# PlanEngine
async def plan(intent: UserIntent, data_state: DataState) -> PlanResult

# DynamicReplanningEngine
def replan(
    current_plan: PlanResult,
    triggers: List[ReplanningTrigger],
    data_state: DataState,
) -> PlanResult
```

**Key invariant**: Plan skeleton comes from domain strategy templates, NOT SkillDAG traversal. SkillDAG is only consulted for skill selection and conflict detection.

### 2. AgentCore + AgentSwarm

**AgentCore** manages the 1+N agent model (1 Analyst + N Specialists).
**AgentSwarm** executes tasks in parallel and resolves consensus.

```python
# AgentCore
def resolve_agent_for_task(task, executed_skills=None) -> Optional[DynamicAgent]
def spawn_specialist(role_id: str, name=None) -> DynamicAgent
def recommend_next_skills(last_skill_id: str) -> List[tuple]

# AgentSwarm
async def execute_parallel(task_group: ParallelTaskGroup) -> SwarmResult
async def consensus_vote(task, agents: List[DynamicAgent], context) -> SwarmResult
```

**Key invariant**: Roles are YAML-configurable; capabilities are determined at runtime by RoleDefinition, not hardcoded classes.

### 3. CBKB + CBKBCurator

**CBKB** is the structured domain knowledge base (5 layers).
**CBKBCurator** performs automatic nightly curation.

```python
# CBKB
def add_experiment_node(node: ExperimentNode)
def add_parameter_lore(entry: ParameterLoreEntry)
def archive_anomaly(record: AnomalyRecord)
def query_parameter_lore(skill_id, param_name, min_outcome) -> List[ParameterLoreEntry]
def suggest_parameters(skill_id) -> List[Dict]

# CBKBCurator
def run_full_curation(since=None) -> Dict
def distill_new_bundles(since=None) -> List[DistilledInsight]
def cluster_topics() -> List[TopicCluster]
def generate_narrative(period_days=30) -> NarrativeReport
```

**Key invariant**: Every CBKB entry is traceable to a ReproducibilityBundle, a Workspace artifact, or a SkillDAG edge.

### 4. ReproducibilityEngine + StabilityGuard

**ReproducibilityEngine** captures everything needed for replay.
**StabilityGuard** validates at L1 (schema) and L2 (version lock + regression).

```python
# ReproducibilityEngine
def start_analysis(project_id, random_seed=42)
def record_code(phase, code, language="python")
def record_hitl_decision(checkpoint_id, choice, parameters)
def finalize(cbkb=None) -> ReproducibilityBundle

# VersionLocker
def lock_project(project_id, skill_registry) -> VersionLock
def verify(skill_registry) -> LockVerificationResult

# RegressionTester
def record_baseline(skill, test_case_id, test_input, actual_output) -> TestBaseline
def test_against_baseline(skill_id, test_case_id, actual_output) -> RegressionResult
```

**Key invariant**: A ReproducibilityBundle is JSON-serializable and self-contained. No external references required for replay.

---

## Data Flow

### Normal Analysis Flow

```
User Message
    → IntentAnalyzer.analyze() → UserIntent
    → PlanEngine.plan(intent, data_state) → PlanResult
    → DynamicReplanningEngine.replan() [optional, if triggers]
    → AgentCore.resolve_agent_for_task() → DynamicAgent
    → SkillRuntimeExecutor.execute(skill_id, inputs)
        → SchemaValidator.validate_input() [L1]
        → Sandbox execution
        → SchemaValidator.validate_output() [L1]
    → InterpretationEngine.interpret_phase(phase, output, data_state)
        → CBKB.archive_anomaly() [if anomaly]
    → ReproducibilityEngine.record_code() / record_hitl_decision()
    → WorkspaceManager.register_artifact()
    → [Loop to next phase or return results]
    → ReproducibilityEngine.finalize(cbkb=cbkb)
        → CBKB.add_experiment_node() / add_parameter_lore()
    → Report generation
```

### Parallel Swarm Flow

```
TaskTree
    → SwarmOrchestrator identifies independent task groups
    → AgentSwarm.execute_parallel(group)
        → Semaphore-controlled asyncio.gather()
        → Each task: AgentCore.resolve_agent_for_task() → DynamicAgent.run()
    → [If consensus_required] consensus_vote()
    → Results merged back to task tree
    → Orchestrator continues with dependent tasks
```

### Evolution Flow (Background)

```
CBKB (accumulated history)
    → AgentEvolutionEngine.evolve_roles()
        → RoleRegistry updates (non-locked roles)
    → AgentEvolutionEngine.mine_plan_patterns()
        → Strategy template updates
    → AgentEvolutionEngine.auto_update_sops()
        → LabSOP create/version bump
    → CBKBCurator.run_full_curation()
        → DistilledInsight → TopicCluster → NarrativeReport
```

---

## State Machines

### Task State Machine

```
PENDING → RUNNING → COMPLETED
   │         │
   └────┬────┘
        ▼
   FAILED (→ retry → RUNNING)
   │
   └────> AWAITING_HUMAN (→ human response → RUNNING)
   │
   └────> ABORTED
```

### SkillDAG Edge State Machine

```
CANDIDATE ──(5 successful executions)──> CONFIRMED
     │
     └──(negative evidence)──> DEPRECATED
```

### HITL Checkpoint State

```
PENDING → TRIGGERED → AWAITING_HUMAN → RESPONDED → APPLIED
```

---

## Extension Points

### Adding a New Domain (Recommended: v0.4.1+)

The **single-file domain declaration** is the preferred way to extend HomomicsLab to a new bioinformatics sub-discipline.

1. **CLI Scaffold**: `homomics domain init {domain_name} --phases "..."`
2. **Edit `domain.yaml`**: Define phases, state_checks, intents, dag_seeds, roles, sops
3. **Add skills**: Create `skills/{skill_id}/SKILL.md + scripts/` in the domain directory
4. **Validate**: `homomics validate domain.yaml`
5. **Install**: `homomics install . --domains-dir {path}`
6. **Done**: DomainLoader auto-registers everything. No Python code changes. No restart.

The `DomainLoader` reads `domain.yaml` and automatically:
- Registers skills via `SkillLoader`
- Builds and registers `AnalysisStrategy` via `StrategyLibrary`
- Registers DAG seeds via `SkillDAG`
- Registers SOPs via `CBKB`
- Exposes intent config to `IntentAnalyzer` via `DomainRegistry`

### Adding a New Skill (Legacy)

1. Create directory: `skills/{skill_id}/`
2. Write `SKILL.md` with YAML frontmatter (input_schema, output_schema, runtime)
3. Add scripts to `skills/{skill_id}/scripts/python/` or `scripts/r/`
4. SkillLoader.auto-discovers on restart (or call `SkillRegistry.load_all()`)

**v0.4.1+**: Skills can also be hot-reloaded at runtime via `SkillHotReloader`.

### Adding a New Agent Role

1. Define role in `domain.yaml` under `roles:` (v0.4.1+)
2. Or create `agent/core/roles/{role_id}.yaml` (legacy)
3. AgentCore auto-discovers on restart

### Adding a New Tool

1. Implement handler function in `tools/`
2. Register via `ToolRegistry.register(ToolDefinition(...))`
3. Add tool name to relevant roles' `allowed_tools`

### Adding a New Plan Strategy

1. Define strategy in `domain.yaml` under `phases:` + `state_checks:` (v0.4.1+)
2. Or add strategy template to `agent/plan/strategies.py` (legacy)

---

## Design Principles

1. **SkillDAG is NOT the plan driver**: Plans come from domain strategy templates. SkillDAG only assists selection and validates sequences.
2. **GapFill removed**: AnalystAgent writes complete Python code that directly imports skill functions. No opaque LLM glue code.
3. **Built-in vs External unified**: Both use identical `SKILL.md + scripts/` format. Only `metadata["source"]` differs.
4. **Progressive disclosure**: L1 (name/desc) → L2 (schemas/runtime) → L3 (full scripts + DAG edges).
5. **Phase-level interpretation**: InterpretationEngine triggers at phase boundaries, not every step.
6. **Bundle-level reproducibility**: ReproducibilityBundle captures exact agent code, not just skill names.
7. **Domain-native knowledge base**: CBKB is structured around experiments, parameters, anomalies, SOPs—not generic chat logs.
