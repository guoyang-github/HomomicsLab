<!-- Reference Metadata Type: Workflow Template Guide Last Verified: 2026-05-20 Version: 1.0.0 Note: Pre-defined multi-skill workflow sequences for the scientific orchestrator -->

# Workflow Templates

Pre-defined multi-skill sequences for common research scenarios. Each workflow specifies stages, decision gates, estimated effort, and exit criteria.

## Workflow 1: Paper Pipeline

**ID:** `paper_pipeline`
**Description:** Complete journey from research idea to published paper with conference presentation
**Use when:** Starting a new research project with the goal of journal publication
**Estimated duration:** 6-18 months (heavily dependent on experimental execution time)

### Stage Sequence

```
[1] ideation
    |
    v (gate: research question defined)
[2] literature-review
    |
    v (gate: knowledge gaps identified)
[3] research-design
    |
    v (gate: protocol finalized)
[4] execution  <-- EXTERNAL: data collection, experiments, simulations
    |
    v (gate: data collected and cleaned)
[5] visualization
    |
    v (gate: publication-ready figures)
[6] illustration
    |
    v (gate: key schematics complete)
[7] manuscript
    |
    v (gate: full draft complete)
[8] peer-review (self-critique before submission)
    |
    v (gate: manuscript submitted)
[9] peer-review (external response revision)
    |
    v (gate: manuscript accepted)
[10] communication
```

### Decision Gates

| Gate | Question | If YES | If NO |
|------|----------|--------|-------|
| After ideation | Is the research question specific and testable? | Proceed to literature | Refine with ideation skill |
| After literature | Are the knowledge gaps genuine and addressable? | Proceed to design | Return to ideation |
| After design | Is the protocol feasible with available resources? | Proceed to execution | Revise design or scope |
| After execution | Are the results sufficient to support a story? | Proceed to visualization | Consider additional experiments |
| After visualization | Do figures meet target journal standards? | Proceed to manuscript | Revise with visualization skill |
| After manuscript | Is the draft ready for co-author review? | Proceed to self-peer-review | Continue writing |
| After peer-review | Are there major methodological concerns? | Revise manuscript | Submit to journal |

### Effort Estimates by Stage

| Stage | Skill | Estimated Effort | Agent-Assistable? |
|-------|-------|-----------------|-------------------|
| Ideation | scientific-ideation | 1-2 weeks | Yes |
| Literature | scientific-literature-review | 2-4 weeks | Yes (search + synthesis) |
| Design | scientific-research-design | 1-2 weeks | Yes |
| Execution | (external) | 3-12 months | No |
| Visualization | scientific-visualization | 1-2 weeks | Yes |
| Illustration | scientific-illustration | 3-5 days | Yes |
| Manuscript | scientific-manuscript | 2-6 weeks | Yes (writing + revision) |
| Peer Review | scientific-peer-review | 1-2 weeks | Yes |
| Communication | scientific-communication | 3-7 days | Yes |

### Exit Points

User can exit the workflow at any stage and resume later. Common exit points:
- After design: pause until experimental data is ready
- After manuscript: submit and wait for reviews
- After peer-review (pre-submission): circulate to co-authors

---

## Workflow 2: Data to Paper

**ID:** `data_to_paper`
**Description:** Transform existing data into a published manuscript
**Use when:** Data collection is complete; need to write and publish
**Estimated duration:** 2-6 months

### Stage Sequence

```
[1] visualization
    |
    v (gate: figures ready)
[2] illustration (optional: if conceptual schematics needed)
    |
    v (gate: schematics ready or skipped)
[3] manuscript
    |
    v (gate: draft complete)
[4] peer-review
    |
    v (gate: submitted)
[5] communication (post-acceptance)
```

### Decision Gates

| Gate | Question | If YES | If NO |
|------|----------|--------|-------|
| Entry | Is data analysis complete? | Begin visualization | Complete analysis first |
| After visualization | Are figures formatted for target journal? | Proceed to manuscript | Revise figures |
| After manuscript | Does the story hold together? | Proceed to peer-review | Restructure or add analysis |

### Key Difference from Paper Pipeline
- Skips ideation, literature, and design (assumed complete)
- Execution stage is already done
- Faster time-to-submission

---

## Workflow 3: Paper to Presentation

**ID:** `paper_to_presentation`
**Description:** Convert an existing or accepted paper into conference materials
**Use when:** Manuscript is complete/accepted and a presentation is needed
**Estimated duration:** 1-2 weeks

### Stage Sequence

```
[1] illustration (optional: if new schematics needed for audience)
    |
    v
[2] communication (slides, poster, or both)
```

### Decision Gates

| Gate | Question | If YES | If NO |
|------|----------|--------|-------|
| Entry | Is the paper content stable? | Begin | Finalize paper first |
| Before illustration | Does the audience need conceptual background? | Create schematics | Skip to communication |

### Output Options
- Conference slides (15-20 min presentation)
- Poster (A0 or custom size)
- Lightning talk (5 min)
- Seminar (45-60 min)

---

## Workflow 4: Grant Pipeline

**ID:** `grant_pipeline`
**Description:** Develop a competitive funding proposal from initial idea to submission
**Use when:** Goal is securing research funding
**Estimated duration:** 1-3 months

### Stage Sequence

```
[1] ideation
    |
    v (gate: innovative concept defined)
[2] literature-review
    |
    v (gate: gap and significance established)
[3] research-design
    |
    v (gate: feasible plan with milestones)
[4] grant-writing
    |
    v (gate: proposal submitted)
```

### Decision Gates

| Gate | Question | If YES | If NO |
|------|----------|--------|-------|
| After ideation | Is the concept innovative and significant? | Proceed to literature | Refine or pivot |
| After literature | Is the gap well-supported by current literature? | Proceed to design | Expand literature search |
| After design | Is the timeline realistic with available resources? | Proceed to grant-writing | Revise scope or budget |

### Agency-Specific Branches

At the grant-writing stage, the workflow branches by target agency:
- **NSF:** Broader impacts, intellectual merit narrative
- **NIH:** Specific aims, significance/innovation/approach structure
- **NSFC:** 立项依据, 研究内容, 研究基础
- **NKRD:** 国家重点研发计划 format

---

## Workflow 5: Quick Poster

**ID:** `quick_poster`
**Description:** Rapid poster creation for preliminary results or early-stage work
**Use when:** Need a poster for an upcoming session, no full paper planned yet
**Estimated duration:** 2-4 weeks

### Stage Sequence

```
[1] ideation (lightweight: frame the story)
    |
    v
[2] illustration (key schematic)
    |
    v
[3] communication (poster format)
```

### Decision Gates

| Gate | Question | If YES | If NO |
|------|----------|--------|-------|
| Entry | Is there at least one result or concept to present? | Begin | Not ready for poster |
| After ideation | Can the story be told in poster format (limited space)? | Proceed | Consider talk instead |

### Notes
- This is a condensed workflow; depth is sacrificed for speed
- Literature review is informal (not a separate stage)
- No manuscript stage

---

## Workflow 6: Review and Revise

**ID:** `review_and_revise`
**Description:** Structured response to peer review comments
**Use when:** Manuscript received external reviews and needs revision
**Estimated duration:** 2-4 weeks

### Stage Sequence

```
[1] peer-review (organize and categorize reviewer comments)
    |
    v (gate: response strategy defined)
[2] manuscript (implement revisions)
    |
    v (gate: revisions complete)
[3] communication (optional: revised figures or supplementary)
```

### Decision Gates

| Gate | Question | If YES | If NO |
|------|----------|--------|-------|
| Entry | Are all reviewer comments received? | Begin | Wait for all reviews |
| After peer-review | Are there major methodological revisions? | Extend manuscript stage | Minor revisions only |
| After manuscript | Are all points addressed in response letter? | Resubmit | Continue revisions |

### Output Artifacts
- Revised manuscript with tracked changes
- Point-by-point response letter
- Revised figures (if applicable)

---

## Custom Workflow Guidelines

Users and agents can define custom workflows by combining stages. Rules:

1. **Every workflow must start with a clear goal** (publish, fund, present)
2. **Stages must respect dependencies** — manuscript cannot precede visualization
3. **Optional stages must be explicitly marked** — use brackets: `[illustration]`
4. **Every workflow should have at least one exit point** defined
5. **Gate conditions should be binary** (pass/fail) for agent clarity

### Custom Workflow Example

```
Goal: Publish a methods paper about a new computational tool
Workflow: tool_paper

[1] ideation (what problem does the tool solve?)
[2] literature-review (existing tools and their limitations)
[3] illustration (tool architecture diagram)  [optional]
[4] visualization (benchmark results, comparison plots)
[5] manuscript (focus on Methods and Benchmarking)
[6] peer-review
[7] communication (software demo at conference)
```
