---
name: scientific-orchestrator
description: "Coordinate multi-skill research workflows across the 9 scientific writing skills. Detect project state, route to appropriate skills, track progress, and manage handoffs between ideation, literature review, research design, visualization, illustration, manuscript writing, peer review, grant writing, and scientific communication."
allowed-tools: [Read, Write, Edit, Bash]
---

# Scientific Orchestrator

## Overview

The scientific orchestrator is the coordination hub for the research workflow. It does not replace any individual skill; instead, it determines which skill to invoke, when, and in what order based on the user's current project state and goals.

**Three core capabilities:**

1. **State Detection** — Infer which stage of the research lifecycle a project is in by scanning existing files and artifacts
2. **Skill Routing** — Route the user to the most appropriate next skill based on project state and stated intent
3. **Workflow Management** — Track progress through pre-defined multi-skill workflows (e.g., "from idea to publication")

**Note:** This skill contains lightweight coordination scripts. It delegates all substantive work to the 9 domain-specific skills.

## When to Use This Skill

This skill should be used when:
- Starting a new research project and unsure where to begin
- Resuming a project after a break and need to re-establish context
- The user's request spans multiple skills (e.g., "help me go from data to a conference presentation")
- A project feels "stuck" and the next step is unclear
- Need to track overall project progress across multiple skill boundaries
- Switching between goals (e.g., from writing a paper to applying for a grant)
- Onboarding a new project into the skill system

## When NOT to Use This Skill

- Do not use when the user explicitly names a specific skill (e.g., "use scientific-manuscript to write my Methods section")
- Do not use for the actual content work — always delegate to domain skills
- Do not use if the user's request is narrow and self-contained within one skill

## Quick Start

### For Users: Starting a New Project

```
"我想发表一篇关于 [主题] 的论文，目前处于 [阶段/ nothing]，目标是 [目标期刊/会议]。"
```

The orchestrator will:
1. Detect or initialize project state
2. Recommend the appropriate workflow template
3. Identify the current stage and next skill to invoke
4. Present a roadmap with estimated effort

### For Agents: Routing Decision Flow

```
User makes a request
        |
        v
Is a specific skill explicitly named?
    YES → Invoke that skill directly, do not use orchestrator
    NO  → Continue below
        |
        v
Does a project state file (.scientific-project.json) exist?
    YES → Load state, detect current stage, suggest next skill
    NO  → Treat as new project, ask for goal, recommend workflow
        |
        v
Does the request span multiple skills?
    YES → Load/create workflow template, decompose into stages
    NO  → Route to single appropriate skill, update state after completion
```

## Project State Model

Each tracked project has a state file (`.scientific-project.json` in the working directory).

### State Schema

```json
{
  "project_id": "auto-generated-uuid",
  "created_at": "2026-05-20T10:00:00Z",
  "updated_at": "2026-05-20T10:00:00Z",
  "current_stage": "ideation",
  "completed_stages": [],
  "active_workflow": "paper_pipeline",
  "workflows": {
    "paper_pipeline": {
      "status": "in_progress",
      "current_step": 1,
      "total_steps": 8
    }
  },
  "artifacts": {
    "ideation": ["research_question.md"],
    "literature": [],
    "design": [],
    "analysis": [],
    "visualization": [],
    "illustration": [],
    "manuscript": [],
    "review": [],
    "communication": [],
    "grant": []
  },
  "metadata": {
    "title": "",
    "target_journal": "",
    "target_conference": "",
    "funding_agency": "",
    "deadline": "",
    "research_field": "",
    "notes": ""
  }
}
```

### Stage Definitions

| Stage | Skill | Key Artifacts | Entry Condition | Exit Condition |
|-------|-------|---------------|-----------------|----------------|
| **ideation** | scientific-ideation | `research_question.md`, `risk_assessment.md` | No project state exists | Research question defined |
| **literature** | scientific-literature-review | `literature_review.md`, `knowledge_gaps.md` | Research question exists | Gap analysis complete |
| **design** | scientific-research-design | `experimental_design.md`, `hypothesis_framework.md` | Gaps identified | Protocol finalized |
| **analysis** | (external tools) | Raw data, processed datasets | Data collected | Analysis complete |
| **visualization** | scientific-visualization | `figures/`, `*.pdf`, `*.tiff` | Analysis results ready | Publication-ready figures |
| **illustration** | scientific-illustration | `schematics/`, `diagrams/` | Conceptual explanation needed | Key schematics complete |
| **manuscript** | scientific-manuscript | `manuscript.md`, `*.bib` | Figures + outline ready | Full draft complete |
| **review** | scientific-peer-review | `review_report.md`, revision notes | Draft exists | Revisions addressed |
| **communication** | scientific-communication | `slides.pptx`, `poster.pdf`, `website/` | Paper accepted or ready | Presentation delivered |
| **grant** | scientific-grant-writing | `proposal.pdf`, `budget.xlsx`, `timeline.gantt` | Funding opportunity identified | Proposal submitted |

## Workflow Templates

Workflows are ordered sequences of stages with decision gates. See `references/workflow_templates.md` for full definitions.

### 1. Paper Pipeline (Most Common)

```
ideation → literature-review → research-design → [execution] → visualization → illustration → manuscript → peer-review → communication
```

**Use when:** Starting from scratch with the goal of publishing a research paper.
**Estimated duration:** 6-18 months (execution phase dominates)
**Note:** The execution stage (data collection, experiments) happens outside the skill system.

### 2. Data to Paper

```
visualization → illustration → manuscript → peer-review → communication
```

**Use when:** Data already collected, need to publish.
**Estimated duration:** 2-6 months

### 3. Paper to Presentation

```
illustration → communication
```

**Use when:** Manuscript is complete or accepted, need slides/poster for a conference.
**Estimated duration:** 1-2 weeks

### 4. Grant Pipeline

```
ideation → literature-review → research-design → grant-writing
```

**Use when:** Goal is securing research funding.
**Estimated duration:** 1-3 months

### 5. Quick Poster

```
ideation → illustration → communication (poster only)
```

**Use when:** Preliminary results for a poster session, no full paper planned yet.
**Estimated duration:** 2-4 weeks

### 6. Review and Revise

```
peer-review → manuscript → communication
```

**Use when:** Manuscript received reviews, need structured revision and resubmission.
**Estimated duration:** 2-4 weeks

## Routing Logic by User Intent

### "I want to publish a paper on [topic]"
→ **Workflow:** paper_pipeline
→ **Start stage:** ideation
→ **First skill:** scientific-ideation

### "I have data and need to write it up"
→ **Workflow:** data_to_paper
→ **Start stage:** visualization
→ **First skill:** scientific-visualization (format figures) OR scientific-manuscript (if figures are ready)

### "My paper was accepted, I need slides for a conference"
→ **Workflow:** paper_to_presentation
→ **Start stage:** illustration
→ **First skill:** scientific-illustration (schematics) then scientific-communication

### "I need to write a grant proposal"
→ **Workflow:** grant_pipeline
→ **Start stage:** ideation
→ **First skill:** scientific-ideation

### "Help me continue my project"
→ **Action:** Run `scripts/detect_state.py` to infer stage
→ **Next:** Suggest next skill based on detected stage

### "I got reviewer comments back"
→ **Workflow:** review_and_revise
→ **Start stage:** peer-review
→ **First skill:** scientific-peer-review

## Agent Execution Protocol

When acting as the orchestrator, follow this protocol:

### Step 1: Detect or Initialize State

```bash
# Check if project state exists
python skills/scientific-orchestrator/scripts/detect_state.py
```

- If state file found: load it, report current stage
- If no state found: ask user for project goal, initialize state with chosen workflow

### Step 2: Identify Current Position

Compare artifacts in the working directory against the stage definitions. The highest completed stage is the current position.

### Step 3: Recommend Next Action

Based on the workflow template and current position:
1. State what stage the project is in
2. Identify the next skill to invoke
3. Explain what that skill will produce
4. Note any prerequisites or decision gates

### Step 4: Update State After Skill Completion

After a skill finishes its work, update the state file:

```bash
python skills/scientific-orchestrator/scripts/state_manager.py \
  --complete-stage manuscript \
  --add-artifact manuscript/manuscript.md
```

### Step 5: Offer Continuation or Exit

After each skill completes, ask the user:
- "Continue to the next stage ([next_stage])?"
- "Switch to a different workflow?"
- "Pause and resume later?"

## Scripts

| Script | Purpose | Example |
|--------|---------|---------|
| `scripts/detect_state.py` | Scan directory and infer project stage | `python detect_state.py` |
| `scripts/state_manager.py` | Read, write, update project state | `python state_manager.py --init --workflow paper_pipeline` |
| `scripts/workflow_runner.py` | Validate workflow progress and report | `python workflow_runner.py --workflow paper_pipeline` |

## Skill Handoff Patterns

### ideation → literature-review
**Output:** `research_question.md`, `risk_assessment.md`
**Input:** Research questions, key terms for database searches
**Action:** Provide the research question and target keywords to the literature-review skill

### literature-review → research-design
**Output:** `literature_review.md`, `knowledge_gaps.md`
**Input:** Identified gaps, analogous methods from literature
**Action:** Use gap analysis to frame hypothesis and experimental design

### research-design → visualization
**Output:** `experimental_design.md`, statistical plan
**Input:** Analysis plan, expected figure types
**Action:** After data collection, use visualization skill to format results per target journal

### visualization + illustration → manuscript
**Output:** Publication-ready figures, schematics
**Input:** Figure captions, methods descriptions, results narrative
**Action:** Embed figures into manuscript sections; reference illustration schematics in Methods/Results

### manuscript → peer-review
**Output:** Complete draft manuscript
**Input:** Manuscript text, target journal criteria
**Action:** Use peer-review skill to self-critique before submission or to organize responses to external reviews

### peer-review → communication
**Output:** Revised manuscript, reviewer response letter
**Input:** Final paper content, key findings for presentation
**Action:** Extract key findings and transform into slides/poster for conference

## Cross-Skill Artifact Map

| Artifact | Produced By | Consumed By |
|----------|-------------|-------------|
| `research_question.md` | scientific-ideation | scientific-literature-review, scientific-research-design |
| `risk_assessment.md` | scientific-ideation | scientific-grant-writing |
| `literature_review.md` | scientific-literature-review | scientific-research-design, scientific-manuscript |
| `knowledge_gaps.md` | scientific-literature-review | scientific-ideation (refinement), scientific-research-design |
| `experimental_design.md` | scientific-research-design | scientific-manuscript (Methods), scientific-grant-writing |
| `figures/*.pdf` | scientific-visualization | scientific-manuscript, scientific-communication |
| `schematics/*.png` | scientific-illustration | scientific-manuscript, scientific-communication, scientific-grant-writing |
| `manuscript.md` | scientific-manuscript | scientific-peer-review, scientific-communication |
| `review_report.md` | scientific-peer-review | scientific-manuscript (revisions) |
| `slides.pptx` | scientific-communication | (final deliverable) |
| `poster.pdf` | scientific-communication | (final deliverable) |
| `proposal.pdf` | scientific-grant-writing | (final deliverable) |

## Reference Materials

| File | Content | Purpose |
|------|---------|---------|
| `references/workflow_templates.md` | Full workflow definitions with decision gates and estimated effort | Select and customize workflows |
| `references/state_model.md` | Detailed state schema, stage definitions, artifact catalog | Understand project state structure |

## Integration with Other Skills

- **scientific-ideation** — Entry point for new projects; generates research questions that seed all downstream workflows
- **scientific-literature-review** — Provides foundational knowledge base and gap analysis for design and manuscript stages
- **scientific-research-design** — Determines experimental structure that shapes Methods sections and grant proposals
- **scientific-visualization** — Produces data figures consumed by manuscript and communication stages
- **scientific-illustration** — Creates conceptual diagrams consumed by manuscript, communication, and grant stages
- **scientific-manuscript** — Central integration point; consumes outputs from ideation, literature, design, visualization, and illustration
- **scientific-peer-review** — Quality gate before submission; also used for revising after external reviews
- **scientific-grant-writing** — Uses ideation, literature, and design outputs to build funding proposals
- **scientific-communication** — Final dissemination stage; transforms manuscript content into presentations
