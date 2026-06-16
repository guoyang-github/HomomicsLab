---
name: scientific-ideation
description: "Research ideation and strategic problem selection. Combines creative brainstorming for hypothesis generation with systematic project evaluation, risk assessment, and decision-tree frameworks for choosing high-impact scientific problems."
allowed-tools: [Read, Write, Edit, Bash]
---

# Scientific Ideation

## Overview

**Note: This skill contains no automation scripts. It is a pure knowledge/reference skill to guide LLM reasoning and structured thinking.**

Scientific ideation is the complete process from generating novel research ideas to strategically selecting the right problem to pursue. This skill combines two essential capabilities:

1. **Creative Brainstorming** — Generating novel ideas, exploring interdisciplinary connections, and identifying research gaps through collaborative, open-ended ideation.
2. **Strategic Problem Selection** — Evaluating ideas systematically using risk assessment, impact analysis, and decision-tree frameworks to choose problems with maximum scientific payoff.

Apply this skill when you need help with research problem selection, project ideation, troubleshooting stuck projects, or strategic scientific decisions. Typical requests include "I have an idea for a project", "I'm stuck on my research", "help me evaluate this project", "what should I work on", or "I need strategic advice about my research".

## When to Use This Skill

This skill should be used when:
- Generating novel research ideas or directions
- Choosing what scientific problem to work on
- Evaluating project ideas for feasibility and impact
- Exploring interdisciplinary connections and analogies
- Troubleshooting stuck projects or navigating decision trees
- Developing new methodological approaches
- Identifying research gaps or opportunities
- Planning research strategy and risk management

## Getting Started

Present users with three entry points:

**1) Pitch an idea for a new project** — to brainstorm and evaluate it together

**2) Share a problem in a current project** — to troubleshoot together

**3) Ask a strategic question** — to navigate the decision tree together

This conversational entry meets scientists where they are and establishes a collaborative tone.

---

# Part 1: Creative Brainstorming

## Brainstorming Workflow

### Phase 1: Understanding the Context

Begin by deeply understanding what the scientist is working on. This phase establishes the foundation for productive ideation.

**Approach:**
- Ask open-ended questions about their current research, interests, or challenge
- Understand their field, methodology, and constraints
- Identify what they're trying to achieve and what obstacles they face
- Listen for implicit assumptions or unexplored angles

**Example questions:**
- "What aspect of your research are you most excited about right now?"
- "What problem keeps you up at night?"
- "What assumptions are you making that might be worth questioning?"
- "Are there any unexpected findings that don't fit your current model?"

**Transition:** Once the context is clear, acknowledge understanding and suggest moving into active ideation.

### Phase 2: Divergent Exploration

Help the scientist generate a wide range of ideas without judgment. The goal is quantity and diversity, not immediate feasibility.

**Select a structured method based on the creative challenge:**

```
What is the brainstorming challenge?
├── Stuck / no new ideas coming
│   ├── Need a completely fresh perspective → Provocation Technique
│   └── Need external stimulus → Random Input
├── Improving an existing method or system
│   ├── Incremental improvements → SCAMPER
│   └── Hit a technical contradiction → TRIZ
├── Exploring a design space systematically
│   ├── Known dimensions, many options → Morphological Analysis
│   └── Unknown dimensions, need inspiration → Biomimicry
├── Need multiple perspectives on a decision
│   └── → Six Thinking Hats
├── Questioning fundamental assumptions
│   └── → Reverse Assumptions
└── Planning long-term research direction
    └── → Future Backwards
```

| Method | When to Use | Cognitive Category | Scientific Example |
|--------|-------------|-------------------|-------------------|
| **SCAMPER** | Improving or extending an existing method | Divergent | Substitute fluorescence for radioactive labeling; combine two biomarker panels into multiplex |
| **Six Thinking Hats** | Need multiple perspectives on a research question | Convergent | Evaluate a clinical trial: White examines data, Black identifies risks, Green suggests novel endpoints |
| **Morphological Analysis** | Exploring all combinations within a design space | Connecting | Drug delivery: carrier × targeting × release mechanism = systematic design space |
| **TRIZ** | Resolving technical contradictions | Convergent | Increasing drug potency increases toxicity → apply separation principle for tissue-specific targeting |
| **Biomimicry** | Seeking nature-inspired solutions | Connecting | "How does nature filter particles?" → kidney nephron principles for microfluidic filters |
| **Provocation (Po)** | Breaking out of fixed thinking patterns | Divergent | "Po: cells never divide" → extract principles leading to intrinsically disordered protein research |
| **Random Input** | Need fresh connections when stuck | Divergent | Random word "bridge" + enzyme kinetics → bridging molecules connecting substrate to active site |
| **Reverse Assumptions** | Questioning fundamental assumptions | Connecting | Reverse "higher purity improves results" → study beneficial contaminants |
| **Future Backwards** | Envisioning long-term research directions | Divergent | "Cancer is cured in 2050" → work backwards to identify today's enabling research |

**Method categories for session design:**
- **Divergent methods** expand the idea space: SCAMPER, Provocation, Random Input, Future Backwards. Use when you need more options or feel stuck.
- **Connecting methods** find relationships: Morphological Analysis, Biomimicry, Reverse Assumptions. Use when you have elements that might relate but haven't identified how.
- **Convergent methods** evaluate and select: Six Thinking Hats, TRIZ. Use when you have many ideas and need to identify the most promising.

A complete brainstorming session should use at least one method from each category, typically in order: divergent → connecting → convergent.

**Recommended method combinations:**
- **SCAMPER + Six Hats**: Generate modifications, then evaluate from six perspectives (protocol refinement)
- **Morphological Analysis + TRIZ**: Map the design space, then resolve contradictions in promising combinations
- **Biomimicry + Provocation**: Find natural solutions, then push beyond biological constraints
- **Three-method sequence** (recommended): Start with divergent (SCAMPER/Provocation, 15 min), then connecting (Morphological Analysis/Biomimicry, 15 min), then convergent (Six Hats/TRIZ, 15 min)

**Core techniques to employ (method-agnostic):**

1. **Cross-Domain Analogies**
   - Draw parallels from other scientific fields
   - "How might concepts from [field X] apply to your problem?"

2. **Assumption Reversal**
   - Identify core assumptions and flip them
   - "What if the opposite were true?"

3. **Scale Shifting**
   - Explore the problem at different scales (molecular to ecosystem)
   - Consider temporal scales (milliseconds to millennia)

4. **Constraint Removal/Addition**
   - Remove apparent constraints: "What if you could measure anything?"
   - Add new constraints: "What if you had to solve this with 1800s technology?"

5. **Interdisciplinary Fusion**
   - Suggest combining methodologies from different fields
   - Propose collaborations that bridge disciplines

6. **Technology Speculation**
   - Imagine emerging technologies applied to the problem
   - "What becomes possible with CRISPR/AI/quantum computing/etc.?"

**Interaction style:**
- Rapid-fire idea generation with the scientist
- Build on their suggestions with "Yes, and..."
- Encourage wild ideas explicitly: "What's the most radical approach imaginable?"
- Consult `references/brainstorming_methods.md` for detailed operator descriptions of each method

### Phase 3: Connection Making

Help identify patterns, themes, and unexpected connections among the generated ideas.

**Approach:**
- Look for common threads across different ideas
- Identify which ideas complement or enhance each other
- Find surprising connections between seemingly unrelated concepts
- Map relationships between ideas visually (if helpful)

**Prompts:**
- "I notice several ideas involve [theme]—what if we combined them?"
- "These three approaches share [commonality]—is there something deeper there?"
- "What's the most unexpected connection you're seeing?"

### Phase 4: Critical Evaluation

Shift to constructively evaluating the most promising ideas while maintaining creative momentum.

**Balance:**
- Be critical but not dismissive
- Identify both strengths and challenges
- Consider feasibility while preserving innovative elements
- Suggest modifications to make wild ideas more tractable

**Questions to explore:**
- "What would it take to actually test this?"
- "What's the first small experiment to run?"
- "What existing data or tools could be leveraged?"
- "Who else would need to be involved?"
- "What's the biggest obstacle, and how might it be overcome?"

### Phase 5: Synthesis and Next Steps

Help crystallize insights and create concrete paths forward.

**Deliverables:**
- Summarize the most promising directions identified
- Highlight novel connections or perspectives discovered
- Suggest immediate next steps (literature search, pilot experiments, collaborations)
- Capture key questions that emerged for future exploration
- Identify resources or expertise that would be valuable

**Close with encouragement:**
- Acknowledge the creative work done
- Reinforce the value of the ideas generated
- Offer to continue the brainstorming in future sessions

## Common Brainstorming Pitfalls

1. **Evaluating too early**: Critiquing ideas during the divergent phase kills creative momentum. Participants self-censor to avoid criticism.
   - *How to avoid*: Explicitly separate divergent (generation) and convergent (evaluation) phases. During divergent phases, the only permitted response is "Yes, and..."

2. **Staying in the comfort zone**: Defaulting to familiar methods and idea spaces produces incremental rather than transformative ideas.
   - *How to avoid*: Deliberately use at least one unfamiliar method per session. Include at least one cross-domain analogy in every session.

3. **Skipping the context phase**: Jumping directly into idea generation without understanding the problem space wastes time rediscovering known solutions.
   - *How to avoid*: Always begin with Phase 1 (Understand Context). Summarize current knowledge, key constraints, and what has already been tried.

4. **Forcing a method when it is not working**: Persisting with a method that is not generating results because of sunk-cost fallacy.
   - *How to avoid*: Set a 15-20 minute time limit per method. If ideas are not flowing, switch methods using the Decision Framework above.

5. **Focusing on quantity without connection-making**: A list of 50 unrelated ideas is less useful than 15 ideas organized into 3 coherent research directions.
   - *How to avoid*: After each divergent burst, spend time on connection-making (Phase 3). Use affinity mapping to group related ideas.

6. **No follow-through after the session**: Generating exciting ideas but never converting them into concrete research actions.
   - *How to avoid*: Always complete Phase 5 (Synthesis and Next Steps). Assign specific follow-up actions with deadlines. Revisit output within one week.

## Adaptive Brainstorming Techniques

### When the Scientist Is Stuck

- Switch from analytical methods (SCAMPER, Morphological Analysis) to provocative methods (Provocation, Random Input)
- The block is usually caused by analytical thinking inhibiting creative thinking
- A single absurd provocation often breaks the logjam
- Change the framing entirely ("Instead of asking X, what if we asked Y?")

### When Ideas Are Too Safe

- Explicitly encourage risk-taking: "What's an idea so bold it makes you nervous?"
- Use Reverse Assumptions to flip the most fundamental assumption
- Ask "what would a Nobel Prize-winning solution look like?" to raise aspiration level
- Apply TRIZ Ideal Final Result to envision the perfect outcome unconstrained by current limitations

### When Energy Lags

- Switch to a more interactive method. Random Input creates fresh starting points.
- Take a brief break and return with Biomimicry — exploring nature's solutions is inherently engaging
- Inject enthusiasm about interesting ideas
- Ask about something that excites them personally

---

# Part 2: Strategic Problem Selection

## The Central Insight

**Problem Choice >> Execution Quality**

Even brilliant execution of a mediocre problem yields incremental impact. Good execution of an important problem yields substantial impact.

### The Time Paradox

Scientists typically spend:
- **Days** choosing a problem
- **Years** solving it

This imbalance limits impact. These skills help invest more time choosing wisely.

### Evaluation Axes

**For Evaluating Ideas:**
- **X-axis:** Likelihood of success
- **Y-axis:** Impact if successful

Skills help move ideas rightward (more feasible) and upward (more impactful).

### The Risk Paradox

- Don't avoid risk—befriend it
- No risk = incremental work
- But: Multiple miracles = avoid or refine
- **Balance:** Understood, quantified, manageable risk

### The Parameter Paradox

- Too many fixed = brittleness
- Too few fixed = paralysis
- **Sweet spot:** Fix ONE meaningful constraint

### The Adversity Principle

- Crises are inevitable (don't be surprised)
- Crises are opportune (don't waste them)
- **Strategy:** Fix problem AND upgrade project simultaneously

## Entry Point 1: Pitch an Idea

### Initial Prompt

Ask: **"Tell me the short version of your idea (1-2 sentences)."**

### Response Approach

After the user shares their idea, return a quick summary (no more than one paragraph) demonstrating understanding. Note the general area of research and rephrase the idea in a way that highlights its kernel—showing alignment and readiness to dive into details.

### Follow-up Prompt

Then ask for more detail: "Now give me a bit more detail. You might include, however briefly or even say where you are unsure:
1. What exactly you want to do
2. How you currently plan to do it
3. If it works, why will it be a big deal
4. What you think are the major risks"

### Workflow

From there, guide the user through the early stages of problem selection and evaluation:
- **Skill 1: Intuition Pumps** - Refine and strengthen the idea
- **Skill 2: Risk Assessment** - Identify and manage project risks
- **Skill 3: Optimization Function** - Define success metrics
- **Skill 4: Parameter Strategy** - Determine what to fix vs. keep flexible

See `references/01-intuition-pumps.md`, `references/02-risk-assessment.md`, `references/03-optimization-function.md`, and `references/04-parameter-strategy.md` for detailed guidance.

## Entry Point 2: Troubleshoot a Problem

### Initial Prompt

Ask: **"Tell me a short version of your problem (1-2 sentences or whatever is easy)."**

### Response Approach

After the user shares their problem, return a quick summary (no more than one paragraph) demonstrating understanding. Note the context of the project where the problem occurred and rephrase the problem—highlighting its core essence—so the user knows the situation is understood. Also raise additional questions that seem important to discuss.

### Follow-up Prompt

Then ask: "Now give me a bit more detail. You might include, however briefly:
1. The overall goal of your project (if we have not talked about it before)
2. What exactly went wrong
3. Your current ideas for fixing it"

### Workflow

From there, guide the user through troubleshooting and decision tree navigation:
- **Skill 5: Decision Tree Navigation** - Plan decision points and navigate between execution and strategic thinking
- **Skill 4: Parameter Strategy** - Fix one parameter at a time, let others float
- **Skill 6: Adversity Response** - Frame problems as opportunities for growth
- **Skill 7: Problem Inversion** - Strategies for navigating around obstacles

Always include workarounds that might be useful whether or not the problem can be fixed easily.

See `references/05-decision-tree.md`, `references/06-adversity-planning.md`, `references/07-problem-inversion.md`, and `references/04-parameter-strategy.md` for detailed guidance.

## Entry Point 3: Ask a Strategic Question

### Initial Prompt

Ask: **"Tell me the short version of your question (1-2 sentences)."**

### Response Approach

After the user shares their question, return a quick summary (no more than one paragraph) demonstrating understanding. Note the broader context and rephrase the question—highlighting its crux—to confirm alignment with their thinking.

### Follow-up Prompt

Then ask: "Now give me a bit more detail. You might include, however briefly:
1. The setting (i.e., is this about a current or future project)
2. A bit more detail about what you're thinking"

### Workflow

From there, draw on the specific modules from the problem choice framework most appropriate to the question:
- **Skills 1-4** for future project planning (ideation, risk, impact, parameters)
- **Skills 5-7** for current project navigation (decision trees, adversity, inversion)
- **Skill 8** for communication and synthesis
- **Skill 9** for comprehensive workflow orchestration

See the complete reference materials in the `references/` folder.

## The 9 Skills Overview

| Skill | Purpose | Output | Time |
|-------|---------|--------|------|
| 1. Intuition Pumps | Generate high-quality research ideas | Problem Ideation Document | ~1 week |
| 2. Risk Assessment | Identify and manage project risks | Risk Assessment Matrix | 3-5 days |
| 3. Optimization Function | Define success metrics | Impact Assessment Document | 2-3 days |
| 4. Parameter Strategy | Decide what to fix vs. keep flexible | Parameter Strategy Document | 2-3 days |
| 5. Decision Tree Navigation | Plan decision points and altitude dance | Decision Tree Map | 2 days |
| 6. Adversity Response | Prepare for crises as opportunities | Adversity Playbook | 2 days |
| 7. Problem Inversion | Navigate around obstacles | Problem Inversion Analysis | 1 day |
| 8. Integration & Synthesis | Synthesize into coherent plan | Project Communication Package | 3-5 days |
| 9. Meta-Framework | Orchestrate complete workflow | Complete Project Package | 1-6 weeks |

## Complete Workflow

```
SKILL 1: Intuition Pumps
         | (generates idea)
         v
SKILL 2: Risk Assessment
         | (evaluates feasibility)
         v
SKILL 3: Optimization Function
         | (defines success metrics)
         v
SKILL 4: Parameter Strategy
         | (determines flexibility)
         v
SKILL 5: Decision Tree
         | (plans execution and evaluation)
         v
SKILL 6: Adversity Planning
         | (prepares for failure modes)
         v
SKILL 7: Problem Inversion
         | (provides pivot strategies)
         v
SKILL 8: Integration & Communication
         | (synthesizes into coherent plan)
         v
SKILL 9: Meta-Skill
         (orchestrates complete workflow)
```

## Key Design Principles

1. **Conversational Entry** - Meet users where they are with three clear starting points
2. **Thoughtful Interaction** - Ask clarifying questions; low confidence prompts additional input
3. **Literature Integration** - Use PubMed searches at strategic points for validation
4. **Concrete Outputs** - Every skill produces tangible 1-2 page documents
5. **Building Specificity** - Progressive detail emerges through targeted questions
6. **Flexibility** - Skills work independently, sequentially, or iteratively
7. **Scientific Rigor** - Claims about generality and feasibility should be evidence-based

## Who Should Use These Skills

### Graduate Students (Primary Audience)
- **When:** Choosing thesis projects, qualifying exams, committee meetings
- **Focus:** Skills 1-3 (ideation, risk, impact) + Skill 9 (complete workflow)
- **Timeline:** 2-4 weeks for comprehensive planning

### Postdocs
- **When:** Starting new position, planning independent projects, fellowship applications
- **Focus:** All skills, emphasizing independence and risk management
- **Timeline:** 1-2 weeks intensive planning

### Principal Investigators
- **When:** New lab, new direction, mentoring trainees, grant cycles
- **Focus:** Skills 1, 3, 4, 6 (ideation, impact, parameters, adversity)
- **Timeline:** Ongoing, integrate into lab culture

### Startup Founders
- **When:** Company inception, pivot decisions, investor pitches
- **Focus:** Skills 1-4 (ideation through parameters) + Skill 8 (communication)
- **Timeline:** 1-2 weeks for initial planning, revisit quarterly

## Reference Materials

Detailed skill documentation is available in the `references/` folder:

| File | Content | Search Patterns |
|------|---------|-----------------|
| `brainstorming_methods.md` | Structured brainstorming methodologies | SCAMPER, Six Thinking Hats, TRIZ |
| `01-intuition-pumps.md` | Generate research ideas | `Intuition Pump #`, `Trap #`, `Phase [0-9]` |
| `02-risk-assessment.md` | Risk identification | `Risk.*1-5`, `go/no-go`, `assumption` |
| `03-optimization-function.md` | Success metrics | `Generality.*Learning`, `optimization`, `impact` |
| `04-parameter-strategy.md` | Parameter fixation | `fixed.*float`, `constraint`, `parameter` |
| `05-decision-tree.md` | Decision tree navigation | `altitude`, `Level [0-9]`, `decision` |
| `06-adversity-planning.md` | Adversity response | `adversity`, `crisis`, `ensemble` |
| `07-problem-inversion.md` | Problem inversion strategies | `Strategy [0-9]`, `inversion`, `goal` |
| `08-integration-synthesis.md` | Integration and synthesis | `narrative`, `communication`, `story` |
| `09-meta-framework.md` | Complete workflow | `Phase`, `workflow`, `orchestrat` |

## Expected Outcomes

### Immediate (After Completing Workflow)
- Clear project vision
- Honest risk assessment
- Contingency plans
- Communication materials ready
- Confidence in problem choice

### 6-Month
- Faster decisions (have framework)
- Productive adversity handling
- No existential crises (risks mitigated)

### 2-Year
- Published results or strong progress
- Avoided dead-end projects
- Career aligned with goals
- **Time well-spent** (ultimate measure)

## Foundational Reference

**Fischbach, M.A., & Walsh, C.T. (2024).** "Problem choice and decision trees in science and engineering." *Cell*, 187, 1828-1833.

Based on course BIOE 395 taught at Stanford University.

---

## Integration with Other Skills

This skill connects to the broader research workflow:

- **scientific-literature-review** — Use before and during ideation to validate that your chosen problem is grounded in current knowledge and identifies genuine gaps
- **scientific-research-design** — The hypotheses and research questions generated here feed directly into experimental design and methodology planning
- **scientific-grant-writing** — A well-chosen problem with clear impact assessment is the foundation of any competitive funding proposal
- **scientific-manuscript** — The narrative and communication frameworks developed during ideation shape how the final paper is structured and positioned
