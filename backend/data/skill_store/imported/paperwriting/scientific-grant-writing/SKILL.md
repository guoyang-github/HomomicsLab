---
name: scientific-grant-writing
description: "Write competitive research proposals for U.S. (NSF, NIH, DOE, DARPA) and Chinese (NSFC, NKRD, Postdoc, Provincial) funding agencies. Agency-specific formatting, review criteria, budget preparation, broader impacts, significance statements, innovation narratives, and compliance with submission requirements."
allowed-tools: [Read, Write, Edit, Bash]
---

# Research Grant Writing

## Overview

Research grant writing is the process of developing competitive funding proposals for federal agencies, foundations, and national research councils. Master agency-specific requirements, review criteria, narrative structure, budget preparation, and compliance for U.S. agencies (NSF, NIH, DOE, DARPA) and Chinese agencies (NSFC, NKRD, Postdoc, Provincial) submissions.

**Critical Principle: Grants are persuasive documents that must simultaneously demonstrate scientific rigor, innovation, feasibility, and broader impact.** Each agency has distinct priorities, review criteria, formatting requirements, and strategic goals that must be addressed.

## When to Use This Skill

This skill should be used when:
- Writing research proposals for U.S. agencies (NSF, NIH, DOE, DARPA) or Chinese agencies (NSFC, NKRD, Postdoc, Provincial)
- Preparing project descriptions, specific aims, technical narratives, or 立项依据
- Developing broader impacts (NSF), significance statements (NIH), or 创新点 (NSFC)
- Creating research timelines and milestone plans (including NSFC年度研究计划)
- Preparing budget justifications, personnel allocation plans, or NSFC经费申请说明
- Responding to program solicitations, funding announcements, or 项目指南
- Addressing reviewer comments in resubmissions (NIH A1, NSFC修改)
- Planning multi-institutional collaborative proposals (including 国家重点研发计划课题任务书)
- Writing preliminary data or feasibility sections (including NSFC研究基础)
- Preparing biosketches, CVs, facilities descriptions, or 人才计划申请材料
- Applying for Chinese talent programs (Chang Jiang Scholars, Ten Thousand Talents, etc.)

## Visual Enhancement with Scientific Schematics

**Recommended visual elements:** Grant proposals are significantly more competitive with clear visual elements. Before finalizing any document:
1. Generate at minimum ONE schematic or diagram (e.g., project timeline, methodology flowchart, or conceptual framework)
2. Prefer 2-3 figures for comprehensive proposals (research workflow, Gantt chart, preliminary data visualization)

**How to generate figures:**
- Use the **scientific-illustration** skill to generate AI-powered publication-quality diagrams
- Simply describe your desired diagram in natural language
- The scientific-illustration skill auto-detects the best available backend to generate diagrams

**How to generate schematics:**
```bash
python skills/scientific-illustration/scripts/generate_schematic.py "your diagram description" -o figures/output.png
```

The script will automatically:
- Detect the best available backend (External API, Local Graphviz, or Spec fallback)
- Generate publication-quality images with proper formatting
- Ensure accessibility (colorblind-friendly, high contrast)
- Save outputs in the figures/ directory

**When to add schematics:**
- Research methodology and workflow diagrams
- Project timeline Gantt charts
- Conceptual framework illustrations
- System architecture diagrams (for technical proposals)
- Experimental design flowcharts
- Broader impacts activity diagrams
- Collaboration network diagrams
- Any complex concept that benefits from visualization

For detailed guidance on creating schematics, refer to the scientific-illustration skill documentation.

---

## Agency-Specific Overview

### NSF (National Science Foundation)
**Mission**: Promote the progress of science and advance national health, prosperity, and welfare

**Key Features**:
- Intellectual Merit + Broader Impacts (equally weighted)
- 15-page project description limit (most programs)
- Emphasis on education, diversity, and societal benefit
- Collaborative research encouraged
- Open data and open science emphasis
- Merit review process with panel + ad hoc reviewers

### NIH (National Institutes of Health)
**Mission**: Enhance health, lengthen life, and reduce illness and disability

**Key Features**:
- Specific Aims (1 page) + Research Strategy (12 pages for R01)
- Significance, Innovation, Approach as core review criteria
- Preliminary data typically required for R01s
- Emphasis on rigor, reproducibility, and clinical relevance
- Modular budgets ($250K increments) for most R01s
- Multiple resubmission opportunities

### DOE (Department of Energy)
**Mission**: Ensure America's security and prosperity through energy, environmental, and nuclear challenges

**Key Features**:
- Focus on energy, climate, computational science, basic energy sciences
- Often requires cost sharing or industry partnerships
- Emphasis on national laboratory collaboration
- Strong computational and experimental integration
- Energy innovation and commercialization pathways
- Varies by office (ARPA-E, Office of Science, EERE, etc.)

### DARPA (Defense Advanced Research Projects Agency)
**Mission**: Make pivotal investments in breakthrough technologies for national security

**Key Features**:
- High-risk, high-reward transformative research
- Focus on "DARPA-hard" problems (what if true, who cares)
- Emphasis on prototypes, demonstrations, and transition paths
- Often requires multiple phases (feasibility, development, demonstration)
- Strong project management and milestone tracking
- Teaming and collaboration often required
- Varies dramatically by program manager and BAA (Broad Agency Announcement)

### NSFC (National Natural Science Foundation of China)
**Mission**: 支持基础研究，坚持自由探索，发挥导向作用，发现和培养科技人才

**Key Features**:
- **面上项目 (General Program)**: ~50万元/4年，自主选题基础研究
- **青年科学基金 (Youth Program)**: ~30万元/3年，男性<35岁，女性<40岁，培养独立科研能力
- **重点项目 (Key Program)**: ~200-300万元/5年，深入系统的创新性研究
- **优青/杰青 (Distinguished/Excellent Young Scholars)**: 人才项目，强调学术贡献和潜力
- **评审标准**: 创新性(30%) + 科学价值(30%) + 研究方案(25%) + 研究基础(15%)
- **申请结构**: 立项依据 → 研究内容/目标/关键问题 → 研究方案/可行性 → 创新点 → 年度计划/预期成果 → 研究基础/工作条件
- **摘要限制**: 400字（严格），需同时提供中英文
- **预算模式**: 定额补助（包干制），无需详细预算论证

### 国家重点研发计划 (National Key R&D Program / NKRD)
**Mission**: 面向国家重大战略需求，通过全链条设计解决制约经济社会发展的重大科技问题

**Key Features**:
- **指南导向**: 所有申报必须严格对应发布的指南方向
- **项目-课题两级管理**: 项目下设若干课题，各有负责人
- **青年科学家项目**: ~300-500万元/3年，负责人<40岁，弱化论文要求，强调目标完成
- **里程碑考核**: 明确的、量化的考核指标，强化过程管理
- **经费管理**: 按科目编制预算，需详细测算说明
- **评审特点**: 符合度(20%) + 方案先进性(25%) + 考核指标(20%) + 团队能力(20%) + 预算合理性(15%)
- **答辩要求**: 通常需要现场答辩

### 中国博士后科学基金 (China Postdoctoral Science Foundation)
**Key Features**:
- **面上资助**: 5-8万元/2年，进站18个月内申请
- **特别资助**: 15-18万元，分站前/站中/站后三类
- **评审重点**: 学术思想创新性(40%) + 研究方案(30%) + 研究基础(20%) + 条件(10%)

### 各省/市自然科学基金 (Provincial Funds)
**Key Features**:
- **资助强度**: 5-100万元（多数10-20万），执行期2-3年
- **区域特色**: 强调服务地方经济社会发展（如北京科技创新中心、上海五个中心、粤港澳大湾区）
- **申请策略**: 结合地方需求，可作为申请国家基金的"练兵场"

## Core Components of Research Proposals

### 1. Executive Summary / Project Summary / Abstract

Every proposal needs a concise overview that communicates the essential elements of the research to both technical reviewers and program officers.

**Purpose**: Provide a standalone summary that captures the research vision, significance, and approach

**Length**:
- NSF: 1 page (Project Summary with separate Overview, Intellectual Merit, Broader Impacts)
- NIH: 30 lines (Project Summary/Abstract)
- DOE: Varies (typically 1 page)
- DARPA: Varies (often 1-2 pages)
- **NSFC**: 400 Chinese characters (strict limit), bilingual Chinese + English required
- **NKRD**: 3000 characters for youth scientist project; varies for other programs

**Essential Elements**:
- Clear statement of the problem or research question
- Why this problem matters (significance, urgency, impact)
- Novel approach or innovation
- Expected outcomes and deliverables
- Qualifications of the team
- Broader impacts or translational pathway

**Writing Strategy**:
- Open with a compelling hook that establishes importance
- Use accessible language (avoid jargon in opening sentences)
- State specific, measurable objectives
- Convey enthusiasm and confidence
- Ensure every sentence adds value (no filler)
- End with transformative vision or impact statement

**Common Mistakes to Avoid**:
- Being too technical or detailed (save for project description)
- Failing to articulate "why now" or "why this team"
- Vague objectives or outcomes
- Neglecting broader impacts or significance
- Generic statements that could apply to any proposal

### 2. Project Description / Research Strategy

The core technical narrative that presents the research plan in detail.

**Structure Varies by Agency:**

**NSF Project Description** (typically 15 pages):
- Introduction and background
- Research objectives and questions
- Preliminary results (if applicable)
- Research plan and methodology
- Timeline and milestones
- Broader impacts (integrated throughout or separate section)
- Prior NSF support (if applicable)

**NIH Research Strategy** (12 pages for R01):
- Significance (why the problem matters)
- Innovation (what's novel and transformative)
- Approach (detailed research plan)
  - Preliminary data
  - Research design and methods
  - Expected outcomes
  - Potential problems and alternative approaches

**DOE Project Narrative** (varies):
- Background and significance
- Technical approach and innovation
- Qualifications and experience
- Facilities and resources
- Project management and timeline

**DARPA Technical Volume** (varies):
- Technical challenge and innovation
- Approach and methodology
- Schedule and milestones
- Deliverables and metrics
- Team qualifications
- Risk assessment and mitigation

**NSFC Project Description** (no strict page limit in ISIS system, typically 8000-15000 characters):
- 立项依据 (Research basis): Background, literature review, gaps
- 研究内容、研究目标及拟解决的关键科学问题 (Content, objectives, key questions)
- 拟采取的研究方案及可行性分析 (Research plan and feasibility)
- 本项目的特色与创新之处 (Innovation and uniqueness)
- 年度研究计划及预期研究成果 (Annual plan and expected outcomes)

**NKRD Project Narrative** (varies by program, typically 5000-10000 characters):
- 项目背景与问题提出 (Background and problem statement)
- 研究目标与内容 (Objectives and content)
- 研究方案与技术路线 (Research plan and technical route)
- 预期成果与考核指标 (Expected outcomes and assessment metrics)
- 研究基础与工作条件 (Research foundation and working conditions)
- 组织管理机制 (Organization and management)

For detailed agency-specific guidance, refer to:
- `references/nsf_guidelines.md`
- `references/nih_guidelines.md`
- `references/doe_guidelines.md`
- `references/darpa_guidelines.md`
- `references/nsfc_guidelines.md`
- `references/nkrdp_guidelines.md`

### 3. Specific Aims (NIH) / Research Contents (NSFC/NKRD)

Clear, testable goals that structure the research plan.

**NIH Specific Aims Page** (1 page):
- Opening paragraph: Gap in knowledge and significance
- Long-term goal and immediate objectives
- Central hypothesis or research question
- 2-4 specific aims with sub-aims
- Expected outcomes and impact
- Payoff paragraph: Why this matters

**Structure for Each Aim:**
- Aim statement (1-2 sentences, starts with action verb)
- Rationale (why this aim, preliminary data support)
- Working hypothesis (testable prediction)
- Approach summary (brief methods overview)
- Expected outcomes and interpretation

**NSFC 研究内容** (Research Contents):
- Typically 2-4 research content items (研究内容一, 二, 三, 四)
- Each item is a relatively independent research module
- Items should have logical connections (progressive, parallel, or complementary)
- Should account for 40-50% of the total proposal length
- Youth programs: 2-3 items recommended (avoid over-ambition)

**Structure for Each NSFC Research Content:**
- Content name (descriptive title)
- Detailed description of what to do
- How to do it (methods overview)
- Why this content is necessary
- Expected outcomes for this content

**NKRD 研究内容**:
- Typically 2-4 research content items aligned with guide direction
- Must clearly correspond to the assessment metrics (考核指标)
- Each item should have specific deliverables

**Writing Strategy**:
- Make aims independent but complementary
- Ensure each aim is achievable within timeline and budget
- Provide enough detail to judge feasibility
- Include contingency plans or alternative approaches
- Use parallel structure across aims
- Clearly state what will be learned from each aim
- **For NSFC**: Focus on 关键科学问题 (key scientific questions), distinguishing from technical/engineering problems

For detailed guidance, refer to `references/specific_aims_guide.md` and `references/nsfc_guidelines.md`.

### 4. Broader Impacts (NSF) / Significance (NIH)

Articulate the societal, educational, or translational value of the research.

**NSF Broader Impacts** (critical component, equal weight with Intellectual Merit):

NSF explicitly evaluates broader impacts. Address at least one of these areas:
1. **Advancing discovery and understanding while promoting teaching, training, and learning**
   - Integration of research and education
   - Training of students and postdocs
   - Curriculum development
   - Educational materials and resources

2. **Broadening participation of underrepresented groups**
   - Recruitment and retention strategies
   - Partnerships with minority-serving institutions
   - Outreach to underrepresented communities
   - Mentoring programs

3. **Enhancing infrastructure for research and education**
   - Shared facilities or instrumentation
   - Cyberinfrastructure and data resources
   - Community-wide tools or databases
   - Open-source software or methods

4. **Broad dissemination to enhance scientific and technological understanding**
   - Public outreach and science communication
   - K-12 educational programs
   - Museum exhibits or media engagement
   - Policy briefs or stakeholder engagement

5. **Benefits to society**
   - Economic impact or commercialization
   - Health, environment, or national security benefits
   - Informed decision-making
   - Workforce development

**Writing Strategy for NSF Broader Impacts**:
- Be specific with concrete activities, not vague statements
- Provide timeline and milestones for broader impacts activities
- Explain how impacts will be measured and assessed
- Connect to institutional resources and existing programs
- Show commitment through preliminary efforts or partnerships
- Integrate with research plan (not tacked on)

**NIH Significance**:
- Addresses important problem or critical barrier to progress
- Improves scientific knowledge, technical capability, or clinical practice
- Potential to lead to better outcomes, interventions, or understanding
- Rigor of prior research in the field
- Alignment with NIH mission and institute priorities

**NSFC 科学价值与社会价值**:
- **科学价值**: 阐明项目对学科发展的推动作用，预期成果的科学意义
- **应用前景**: 说明研究成果的潜在应用价值
- **对国家需求的响应**: 自然科学基金也关注对国家重大需求的贡献

**NKRD 应用前景与考核指标**:
- 预期成果必须具体、可量化、可考核
- 科学成果（论文、专著）+ 技术成果（专利、标准）+ 应用成果（示范应用、产品原型）
- 考核指标必须与指南方向紧密对应

**Provincial Funds 区域贡献**:
- 强调对地方经济社会发展的贡献
- 结合地方特色和产业需求

For detailed guidance, refer to `references/broader_impacts.md` and `references/nsfc_guidelines.md`.

### 5. Innovation and Transformative Potential

Articulate what is novel, creative, and paradigm-shifting about the research.

**Innovation Elements to Highlight**:
- **Conceptual Innovation**: New frameworks, models, or theories
- **Methodological Innovation**: Novel techniques, approaches, or technologies
- **Integrative Innovation**: Combining disciplines or approaches in new ways
- **Translational Innovation**: New pathways from discovery to application
- **Scale Innovation**: Unprecedented scope or resolution

**Writing Strategy**:
- Clearly state what is innovative (don't assume it's obvious)
- Explain why current approaches are insufficient
- Describe how your innovation overcomes limitations
- Provide evidence that innovation is feasible (preliminary data, proof-of-concept)
- Distinguish incremental from transformative advances
- Balance innovation with feasibility (not too risky)

**Common Mistakes**:
- Claiming novelty without demonstrating knowledge of prior work
- Confusing "new to me" with "new to the field"
- Over-promising without supporting evidence
- Being too incremental (minor variation on existing work)
- Being too speculative (no path to success)

### 6. Research Approach and Methods

Detailed description of how the research will be conducted.

**Essential Components**:
- Overall research design and framework
- Detailed methods for each aim/objective
- Sample sizes, statistical power, and analysis plans
- Timeline and sequence of activities
- Data collection, management, and analysis
- Quality control and validation approaches
- Potential problems and alternative strategies
- Rigor and reproducibility measures

**Writing Strategy**:
- Provide enough detail for reproducibility and feasibility assessment
- Use subheadings and figures to improve organization
- Justify choice of methods and approaches
- Address potential limitations proactively
- Include preliminary data demonstrating feasibility
- Show that you've thought through the research process
- Balance detail with readability (use supplementary materials for extensive details)

**For Experimental Research**:
- Describe experimental design (controls, replicates, blinding)
- Specify materials, reagents, and equipment
- Detail data collection protocols
- Explain statistical analysis plans
- Address rigor and reproducibility

**For Computational Research**:
- Describe algorithms, models, and software
- Specify datasets and validation approaches
- Explain computational resources required
- Address code availability and documentation
- Describe benchmarking and performance metrics

**For Clinical or Translational Research**:
- Describe study population and recruitment
- Detail intervention or treatment protocols
- Explain outcome measures and assessments
- Address regulatory approvals (IRB, IND, IDE)
- Describe clinical trial design and monitoring

For detailed methodology guidance by discipline, refer to `references/research_methods.md`.

### 7. Preliminary Data and Feasibility

Demonstrate that the research is achievable and the team is capable.

**Purpose**:
- Prove that the proposed approach can work
- Show that the team has necessary expertise
- Demonstrate access to required resources
- Reduce perceived risk for reviewers
- Provide foundation for proposed work

**What to Include**:
- Pilot studies or proof-of-concept results
- Method development or optimization
- Access to unique resources (samples, data, collaborators)
- Relevant publications from your team
- Preliminary models or simulations
- Feasibility assessments or power calculations

**NIH Requirements**:
- R01 applications typically require substantial preliminary data
- R21 applications may have less stringent requirements
- New investigators may have less preliminary data
- Preliminary data should directly support proposed aims

**NSF Approach**:
- Preliminary data less commonly required than NIH
- May be important for high-risk or novel approaches
- Can strengthen proposal for competitive programs

**NSFC 研究基础** (Critical section, standalone chapter):
- **直接相关的工作基础**: Preliminary results most directly related to this project
- **相关领域的工作积累**: Systematic research in related areas showing academic continuity
- **初步实验结果**: Key preliminary data presented with figures/charts
- **论文发表情况**: Representative publications listed
- **NSFC特色**: 研究基础占申请书较大比重，需充分展示团队能力和条件
- **青年项目**: 可相对薄弱，但需展示独立研究潜力和清晰思路

**NKRD 研究基础**:
- 强调已取得的自主创新研究成果
- 展示关键技术和核心数据
- 青年科学家项目需突出申请人的独立能力和发展潜力

**Writing Strategy**:
- Present most compelling data that supports your approach
- Clearly connect preliminary data to proposed aims
- Acknowledge limitations and how proposed work will address them
- Use figures and data visualizations effectively
- Avoid over-interpreting or overstating preliminary findings
- Show trajectory of your research program

### 8. Timeline, Milestones, and Management Plan

Demonstrate that the project is well-planned and achievable within the proposed timeframe.

**Essential Elements**:
- Phased timeline with clear milestones
- Logical sequence and dependencies
- Realistic timeframes for each activity
- Decision points and go/no-go criteria
- Risk mitigation strategies
- Resource allocation across time
- Coordination plan for multi-institutional teams

**Presentation Formats**:
- Gantt charts showing overlapping activities
- Year-by-year breakdown of activities
- Quarterly milestones and deliverables
- Table of aims/tasks with timeline and personnel

**Writing Strategy**:
- Be realistic about what can be accomplished
- Build in time for unexpected delays or setbacks
- Show that timeline aligns with budget and personnel
- Demonstrate understanding of regulatory timelines (IRB, IACUC)
- Include time for dissemination and broader impacts
- Address how progress will be monitored and assessed

**DARPA Emphasis**:
- Particularly important for DARPA proposals
- Clear technical milestones with measurable metrics
- Quarterly deliverables and reporting
- Phase-based structure with exit criteria
- Demonstration and transition planning

**NSFC 年度研究计划** (Mandatory, year-by-year breakdown):
- Each year must have specific tasks and expected progress
- Must show logical progression of research
- Should align with budget and personnel allocation
- Typically 4 years for General/Key programs, 3 years for Youth program

**NKRD 进度安排**:
- Must align with assessment metrics timeline
- Clear phase deliverables
- Risk analysis and mitigation measures

For detailed guidance, refer to `references/timeline_planning.md` and `references/nsfc_guidelines.md`.

### 9. Team Qualifications and Collaboration

Demonstrate that the team has the expertise, experience, and resources to succeed.

**Essential Elements**:
- PI qualifications and relevant expertise
- Co-I and collaborator roles and contributions
- Track record in the research area
- Complementary expertise across team
- Institutional support and resources
- Prior collaboration history (if applicable)
- Mentoring and training plan (for students/postdocs)

**Writing Strategy**:
- Highlight most relevant publications and accomplishments
- Clearly define roles and responsibilities
- Show that team composition is necessary (not just convenient)
- Demonstrate successful prior collaborations
- Address how team will be managed and coordinated
- Explain institutional commitment and support

**Biosketches / CVs**:
- Follow agency-specific formats (NSF, NIH, DOE, DARPA differ)
- Highlight most relevant publications and accomplishments
- Include synergistic activities and collaborations
- Show trajectory and productivity
- Address any career gaps or interruptions

**Letters of Collaboration**:
- Specific commitments and contributions
- Demonstrates genuine partnership
- Includes resource sharing or access agreements
- Signed and on letterhead

For detailed guidance, refer to `references/team_building.md`.

### 10. Budget and Budget Justification

Develop realistic budgets that align with the proposed work and agency guidelines.

**Budget Categories** (typical):
- **Personnel**: Salary and fringe for PI, co-Is, postdocs, students, staff
- **Equipment**: Items >$5,000 (varies by agency)
- **Travel**: Conferences, collaborations, fieldwork
- **Materials and Supplies**: Consumables, reagents, software
- **Other Direct Costs**: Publication costs, participant incentives, consulting
- **Indirect Costs (F&A)**: Institutional overhead (rates vary)
- **Subawards**: Costs for collaborating institutions

**Agency-Specific Considerations**:

**NSF**:
- Full budget justification required
- Cost sharing generally not required (but may strengthen proposal)
- Up to 2 months summer salary for faculty
- Graduate student support encouraged

**NIH**:
- Modular budgets for ≤$250K direct costs per year (R01)
- Detailed budgets for >$250K or complex awards
- Salary cap applies (~$221,900 for 2024)
- Limited to 1 month (8.33% FTE) for most PIs

**DOE**:
- Often requires cost sharing (especially ARPA-E)
- Detailed budget with quarterly breakdown
- Requires institutional commitment letters
- National laboratory collaboration budgets separate

**DARPA**:
- Detailed budgets by phase and task
- Requires supporting cost data for large procurements
- Often requires cost-plus or firm-fixed-price structures
- Travel budget for program meetings

**NSFC (定额补助 / Fixed Amount)**:
- **No detailed budget required**: Applicants fill in "经费申请说明" (budget description) only
- **Typical amounts**: General Program ~50万, Youth Program ~30万, Key Program ~200-300万
- **Categories**: Equipment, operational costs, labor, indirect costs
- **Key requirement**: Budget should match research scope; no over- or under-budgeting
- **包干制**: Recipients have flexibility in using funds within categories

**NKRD (Detailed Budget)**:
- **Itemized budget required**: Must justify each category with detailed calculations
- **Categories**: Equipment, materials, testing, travel, labor, consulting
- **Quarterly breakdown** often required
- **Alignment with milestones**: Budget should align with project phases

**Provincial Funds**:
- Varies by province, typically follow NSFC or NKRD model
- Generally lower amounts (5-100万)

**Budget Justification Writing**:
- Justify each line item in terms of the research plan
- Explain effort percentages for personnel
- Describe specific equipment and why necessary
- Justify travel (conferences, collaborations)
- Explain consultant roles and rates
- Show how budget aligns with timeline

For detailed budget guidance, refer to `references/budget_preparation.md`.

## Review Criteria by Agency

Understanding how proposals are evaluated is critical for writing competitive applications.

### NSF Review Criteria

**Intellectual Merit** (primary):
- What is the potential for the proposed activity to advance knowledge?
- How well-conceived and organized is the proposed activity?
- Is there sufficient access to resources?
- How well-qualified is the individual, team, or institution to conduct proposed activities?

**Broader Impacts** (equally important):
- What is the potential for the proposed activity to benefit society?
- To what extent does the proposal address broader impacts in meaningful ways?

**Additional Considerations**:
- Integration of research and education
- Diversity and inclusion
- Results from prior NSF support (if applicable)

### NIH Review Criteria

**Scored Criteria** (1-9 scale, 1 = exceptional, 9 = poor):

1. **Significance**
   - Addresses important problem or critical barrier
   - Improves scientific knowledge, technical capability, or clinical practice
   - Aligns with NIH mission

2. **Investigator(s)**
   - Well-suited to the project
   - Track record of accomplishments
   - Adequate training and expertise

3. **Innovation**
   - Novel concepts, approaches, methodologies, or interventions
   - Challenges existing paradigms
   - Addresses important problem in creative ways

4. **Approach**
   - Well-reasoned and appropriate
   - Rigorous and reproducible
   - Adequately accounts for potential problems
   - Feasible within timeline

5. **Environment**
   - Institutional support and resources
   - Scientific environment contributes to probability of success

**Additional Review Considerations** (not scored but discussed):
- Protections for human subjects
- Inclusion of women, minorities, and children
- Vertebrate animal welfare
- Biohazards
- Resubmission response (if applicable)
- Budget and timeline appropriateness

### DOE Review Criteria

Varies by program office, but generally includes:
- Scientific and/or technical merit
- Appropriateness of proposed method or approach
- Competency of personnel and adequacy of facilities
- Reasonableness and appropriateness of budget
- Relevance to DOE mission and program goals

### DARPA Review Criteria

**DARPA-specific considerations**:
- Overall scientific and technical merit
- Potential contribution to DARPA mission
- Relevance to stated program goals
- Plans and capability to accomplish technology transition
- Qualifications and experience of proposed team
- Realism of proposed costs and availability of funds

**Key Questions DARPA Asks**:
- **What if you succeed?** (Impact if the research works)
- **What if you're right?** (Implications of your hypothesis)
- **Who cares?** (Why it matters for national security)

### NSFC Review Criteria

**面上项目/青年项目评审标准**:

1. **科学价值** (约30%):
   - 研究问题的科学意义
   - 预期成果对学科发展的推动作用
   - 对国家需求或社会发展的贡献

2. **创新性** (约30%):
   - 研究思路的新颖程度
   - 理论或方法的原创性
   - 对现有认知的突破潜力

3. **研究方案** (约25%):
   - 技术路线的合理性和可行性
   - 研究方法的先进性和适用性
   - 研究计划的周密性和可操作性

4. **研究基础** (约15%):
   - 申请人及团队的研究能力
   - 前期工作积累与项目的相关性
   - 工作条件的保障程度

**优青/杰青额外考察**:
   - 已取得成果的学术影响力
   - 独立开展研究的能力
   - 培养团队和学生的潜力
   - 未来研究方向的开拓性

### NKRD Review Criteria

**重点专项项目评审标准**:

1. **目标与指南的符合度** (约20%):
   - 是否紧密对应指南方向
   - 是否解决指南提出的关键问题
   - 是否体现全链条设计

2. **研究方案的先进性与可行性** (约25%):
   - 技术路线是否先进、合理
   - 研究方法是否科学、可行
   - 研究计划是否周密、可操作

3. **预期成果的明确性与考核指标** (约20%):
   - 预期成果是否明确、具体
   - 考核指标是否可量化、可考核
   - 成果对专项总体目标的贡献

4. **团队能力与组织管理** (约20%):
   - 团队结构是否合理、互补
   - 牵头单位是否有足够的能力和平台
   - 组织管理机制是否健全
   - 课题间的协同机制是否清晰

5. **经费预算的合理性** (约15%):
   - 预算与研究任务的匹配度
   - 预算测算的依据是否充分
   - 预算结构是否合理

**青年科学家项目额外特点**:
   - 更关注申请人本身的科研能力和创新潜力
   - 弱化论文和头衔要求
   - 强调独立承担科研任务的能力
   - 对原创性、探索性研究给予更大包容

For detailed review criteria by agency, refer to `references/review_criteria.md` and `references/nsfc_guidelines.md`.

## Writing Principles for Competitive Proposals

### Clarity and Accessibility

**Write for Multiple Audiences**:
- Technical reviewers in your field (will scrutinize methods)
- Reviewers in related but not identical fields (need context)
- Program officers (look for alignment with agency goals)
- Panel members reading 15+ proposals (need clear organization)

**Strategies**:
- Use clear section headings and subheadings
- Start sections with overview paragraphs
- Define technical terms and abbreviations
- Use figures, diagrams, and tables to clarify complex ideas
- Avoid jargon when possible; explain when necessary
- Use topic sentences to guide readers

### Persuasive Argumentation

**Build a Compelling Narrative**:
- Establish the problem and its importance
- Show gaps in current knowledge or approaches
- Present your solution as innovative and feasible
- Demonstrate that you're the right team
- Show that success will have significant impact

**Structure of Persuasion**:
1. **Hook**: Capture attention with significance
2. **Problem**: Establish what's not known or not working
3. **Solution**: Present your innovative approach
4. **Evidence**: Support with preliminary data
5. **Impact**: Show transformative potential
6. **Team**: Demonstrate capability to deliver

**Language Choices**:
- Use active voice for clarity and confidence
- Choose strong verbs (investigate, elucidate, discover vs. look at, study)
- Be confident but not arrogant (avoid "obviously," "clearly")
- Acknowledge uncertainty appropriately
- Use precise language (avoid vague terms like "several," "various")

### Visual Communication

**Effective Use of Figures**:
- Conceptual diagrams showing research framework
- Preliminary data demonstrating feasibility
- Timelines and Gantt charts
- Workflow diagrams showing methodology
- Expected results or predictions

**Design Principles**:
- Make figures self-explanatory with complete captions
- Use consistent color schemes and fonts
- Ensure readability (large enough fonts, clear labels)
- Integrate figures with text (refer to specific figures)
- Follow agency-specific formatting requirements

### Addressing Risk and Feasibility

**Balance Innovation and Risk**:
- Acknowledge potential challenges
- Provide alternative approaches
- Show preliminary data reducing risk
- Demonstrate expertise to handle challenges
- Include contingency plans

**Common Concerns**:
- Too ambitious for timeline/budget
- Technically infeasible
- Team lacks necessary expertise
- Preliminary data insufficient
- Methods not adequately described
- Lack of innovation or significance

### Integration and Coherence

**Ensure All Parts Align**:
- Budget supports activities in project description
- Timeline matches aims and milestones
- Team composition matches required expertise
- Broader impacts connect to research plan
- Letters of support confirm stated collaborations

**Avoid Contradictions**:
- Preliminary data vs. stated gaps
- Claimed expertise vs. publication record
- Stated aims vs. actual methods
- Budget vs. stated activities

## Common Proposal Types

### NSF Proposal Types

- **Standard Research Proposals**: Most common, up to $500K and 5 years
- **CAREER Awards**: Early career faculty, integrated research/education, $400-500K over 5 years
- **Collaborative Research**: Multiple institutions, separately submitted, shared research plan
- **RAPID**: Urgent research opportunities, up to $200K, no preliminary data required
- **EAGER**: High-risk, high-reward exploratory research, up to $300K
- **EArly-concept Grants for Exploratory Research (EAGER)**: Early-stage exploratory work

### NIH Award Mechanisms

- **R01**: Research Project Grant, $250K+ per year, 3-5 years, most common
- **R21**: Exploratory/Developmental Research, up to $275K over 2 years, no preliminary data
- **R03**: Small Grant Program, up to $100K over 2 years
- **R15**: Academic Research Enhancement Awards (AREA), for primarily undergraduate institutions
- **R35**: MIRA (Maximizing Investigators' Research Award), program-specific
- **P01**: Program Project Grant, multi-project integrated research
- **U01**: Research Project Cooperative Agreement, NIH involvement in conduct

**Fellowship Mechanisms**:
- **F30**: Predoctoral MD/PhD Fellowship
- **F31**: Predoctoral Fellowship
- **F32**: Postdoctoral Fellowship
- **K99/R00**: Pathway to Independence Award
- **K08**: Mentored Clinical Scientist Research Career Development Award

### DOE Programs

- **Office of Science**: Basic research in physical sciences, biological sciences, computing
- **ARPA-E**: Transformative energy technologies, requires cost sharing
- **EERE**: Applied research in renewable energy and energy efficiency
- **National Laboratories**: Collaborative research with DOE labs

### DARPA Programs

- **Varies by Office**: BTO, DSO, I2O, MTO, STO, TTO
- **Program-Specific BAAs**: Broad Agency Announcements for specific thrusts
- **Young Faculty Award (YFA)**: Early career researchers, up to $500K
- **Director's Fellowship**: High-risk, paradigm-shifting research

### NSFC Program Types

- **面上项目 (General Program)**: ~50万元/4年，支持自主选题基础研究，最普遍的基金类型
- **青年科学基金 (Youth Program)**: ~30万元/3年，<35岁（男）/<40岁（女），培养独立科研能力
- **地区科学基金 (Regional Program)**: ~30-40万元/4年，支持特定地区科研人员
- **重点项目 (Key Program)**: ~200-300万元/5年，深入系统的创新性研究
- **优秀青年科学基金 (优青)**: ~200万元/3年，<38岁（男）/<40岁（女），培养学术骨干
- **国家杰出青年科学基金 (杰青)**: ~400万元/5年，<45岁（男）/<48岁（女），培养学术带头人
- **联合基金 (Joint Funds)**: NSFC与企业/地方政府联合资助，聚焦特定领域

### 国家重点研发计划 (NKRD) Program Types

- **重点专项 (Key Special Projects)**: 面向国家重大需求，多领域覆盖，指南导向
- **青年科学家项目 (Young Scientists Project)**: ~300-500万元/3年，<40岁，弱化论文，强调目标完成
- **课题/任务 (Tasks under Projects)**: 重点专项下设课题，需明确分工和协同
- **揭榜挂帅**: 发布榜单，优势团队揭榜攻关
- **部省联动**: 中央和地方共同出资、协同实施

### 中国博士后科学基金

- **面上资助 (General Funding)**: 5-8万元/2年，进站18个月内申请
- **特别资助（站前/站中/站后）**: 15-18万元，分阶段支持优秀博士后
- **优秀学术专著出版资助**: ~8万元/部

### 省级自然科学基金 (代表性)

- **北京市自然科学基金**: 面上~20万，青年~10万，杰青~100万
- **上海市自然科学基金**: 面上~20万，青年~10万，探索类~10万
- **广东省自然科学基金**: 面上~10万，杰青~100万，团队~200万
- **江苏省自然科学基金**: 青年~20万，面上~10万，杰青~100万
- **浙江省自然科学基金**: 一般~10万，青年~5-10万，杰青~80万

### 人才计划

- **长江学者 (Chang Jiang Scholars)**: 特聘教授/青年学者，教育部
- **万人计划 (Ten Thousand Talents)**: 杰出人才/领军人才/青年拔尖，中组部
- **海外优青/杰青**: 吸引海外人才回国，NSFC

For detailed program guidance, refer to `references/funding_mechanisms.md`, `references/nsfc_guidelines.md`, and `references/nkrdp_guidelines.md`.

## Resubmission Strategies

### NIH Resubmission (A1)

**Introduction to Resubmission** (1 page):
- Summarize major criticisms from previous review
- Describe specific changes made in response
- Use bullet points for clarity
- Be respectful of reviewers' comments
- Highlight substantial improvements

**Strategies**:
- Address every major criticism
- Make changes visible (but don't use track changes in final)
- Strengthen weak areas (preliminary data, methods, significance)
- Consider changing aims if fundamentally flawed
- Get external feedback before resubmitting
- Use full 37-month window if needed for new data

**When Not to Resubmit**:
- Fundamental conceptual flaws
- Lack of innovation or significance
- Missing key expertise or resources
- Extensive revisions needed (consider new submission)

### NSF Resubmission

**NSF allows resubmission after revision**:
- Address reviewer concerns in revised proposal
- No formal "introduction to resubmission" section
- May be reviewed by same or different panel
- Consider program officer feedback
- May need to wait for next submission cycle

### NSFC Resubmission (修改后重报)

**NSFC allows resubmission after revision**:
- 仔细阅读评审意见，逐条分析问题和不足
- 针对性地修改申请书中的薄弱环节
- 创新点不足 → 深化研究思路，突出原创性
- 研究基础薄弱 → 补充新的初步实验数据或论文
- 研究方案不合理 → 优化技术路线，增加可行性论证
- 无正式的"修改说明"要求，但修改应显而易见
- 可能被同一批或不同专家再次评审
- 考虑更换申请代码或调整研究方向（如果原方向确实不合适）

**When Not to Resubmit**:
- 创新点被专家认为不成立
- 研究基础存在根本性缺陷
- 研究方向与申请代码不匹配
- 评审分数过低且无实质性改进可能

**Key Differences from NIH/NSF**:
- NSFC无A1/A2机制，修改后可按新项目重新申报
- 需注意限项规定，确保不影响其他在研项目
- 青年项目修改后可继续申报，直至超龄

For detailed resubmission guidance, refer to `references/resubmission_strategies.md` and `references/nsfc_guidelines.md`.

## Common Mistakes to Avoid

### Conceptual Mistakes

1. **Failing to Address Review Criteria**: Not explicitly discussing significance, innovation, approach, etc.
2. **Mismatch with Agency Mission**: Proposing research that doesn't align with agency goals
3. **Unclear Significance**: Failing to articulate why the research matters
4. **Insufficient Innovation**: Incremental work presented as transformative
5. **Vague Objectives**: Goals that are not specific or measurable

### Writing Mistakes

1. **Poor Organization**: Lack of clear structure and flow
2. **Excessive Jargon**: Inaccessible to broader review panel
3. **Verbosity**: Unnecessarily complex or wordy writing
4. **Missing Context**: Assuming reviewers know your field deeply
5. **Inconsistent Terminology**: Using different terms for same concept

### Technical Mistakes

1. **Inadequate Methods**: Insufficient detail to judge feasibility
2. **Overly Ambitious**: Too much proposed for timeline/budget
3. **No Preliminary Data**: For mechanisms requiring demonstrated feasibility
4. **Poor Timeline**: Unrealistic or poorly justified schedule
5. **Misaligned Budget**: Budget doesn't support proposed activities

### Formatting Mistakes

1. **Exceeding Page Limits**: Automatic rejection
2. **Wrong Font or Margins**: Non-compliant formatting
3. **Missing Required Sections**: Incomplete application
4. **Poor Figure Quality**: Illegible or unprofessional figures
5. **Inconsistent Citations**: Formatting errors in references

### Strategic Mistakes

1. **Wrong Program or Mechanism**: Proposing to inappropriate opportunity
2. **Weak Team**: Insufficient expertise or missing key collaborators
3. **No Broader Impacts**: For NSF, failing to adequately address
4. **Ignoring Program Priorities**: Not aligning with current emphasis areas
5. **Late Submission**: Technical issues or rushed preparation

### NSFC-Specific Mistakes

1. **忽视申请代码选择**: 申请代码决定送审方向，选择不当导致专家不匹配 → 仔细研究申请代码，选择最贴切的
2. **摘要超字数**: NSFC摘要严格400字限制，超出会影响形式审查 → 反复打磨，精确控制在400字以内
3. **立项依据文献堆砌**: 只罗列文献不做评述 → 批判性分析文献，明确指出现有研究的gap
4. **研究内容过多**: 面上项目3-4项为宜，青年项目2-3项 → 聚焦核心问题，不贪多
5. **创新点空泛**: 没有具体支撑的创新声明 → 每个创新点需有论据，谨慎使用"首次""国际领先"
6. **关键科学问题与技术问题混淆**: 关键科学问题应是本质的科学问题，不是技术实现问题 → 以"机制""规律""关系"等形式表述
7. **年度计划不具体**: 泛泛而谈，缺乏可操作性 → 每年应有明确的任务和预期进展
8. **研究基础与申请脱节**: 前期工作与申请内容关联性不强 → 选择最直接相关的成果展示
9. **忽视中英文摘要一致性**: 中英文摘要内容不一致 → 确保中英文摘要信息对应
10. **NKRD偏离指南方向**: 申报内容与指南要求不符 → 严格对照指南，逐条回应要求

## Workflow for Grant Development

### Phase 1: Planning and Preparation (2-6 months before deadline)

**Activities**:
- Identify appropriate funding opportunities
- Review program announcements and requirements
- Consult with program officers (if appropriate)
- Assemble team and confirm collaborations
- Develop preliminary data (if needed)
- Outline research plan and specific aims
- Review successful proposals (if available)

**Outputs**:
- Selected funding opportunity
- Assembled team with defined roles
- Preliminary outline of specific aims
- Gap analysis of needed preliminary data

### Phase 2: Drafting (2-3 months before deadline)

**Activities**:
- Write specific aims or objectives (start here!)
- Develop project description/research strategy
- Create figures and data visualizations
- Draft timeline and milestones
- Prepare preliminary budget
- Write broader impacts or significance sections
- Request letters of support/collaboration

**Outputs**:
- Complete first draft of narrative sections
- Preliminary budget with justification
- Timeline and management plan
- Requested letters from collaborators

### Phase 3: Internal Review (1-2 months before deadline)

**Activities**:
- Circulate draft to co-investigators
- Seek feedback from colleagues and mentors
- Request institutional review (if required)
- Mock review session (if possible)
- Revise based on feedback
- Refine budget and budget justification

**Outputs**:
- Revised draft incorporating feedback
- Refined budget aligned with revised plan
- Identified weaknesses and mitigation strategies

### Phase 4: Finalization (2-4 weeks before deadline)

**Activities**:
- Final revisions to narrative
- Prepare all required forms and documents
- Finalize budget and budget justification
- Compile biosketches, CVs, and current & pending
- Collect letters of support
- Prepare data management plan (if required)
- Write project summary/abstract
- Proofread all materials

**Outputs**:
- Complete, polished proposal
- All required supplementary documents
- Formatted according to agency requirements

### Phase 5: Submission (1 week before deadline)

**Activities**:
- Institutional review and approval
- Upload to submission portal
- Verify all documents and formatting
- Submit 24-48 hours before deadline
- Confirm successful submission
- Receive confirmation and proposal number

**Outputs**:
- Submitted proposal
- Submission confirmation
- Archived copy of all materials

**Critical Tip**: Never wait until the deadline. Portals crash, files corrupt, and emergencies happen. Aim for 48 hours early.

### Domestic Fund Workflow Differences

**NSFC-Specific Workflow**:
- **Annual deadline**: Typically March (for most programs)
- **System**: 科学基金网络信息系统 (ISISN)
- **No page limit in system**: But concise writing is still preferred
- **Abstract**: 400 Chinese characters (strict), plus English version
- **No detailed budget**: Only "经费申请说明" required
- **No biosketch format**: CV uploaded as attachment
- **Institutional approval**: Required before submission
- **Result announcement**: Usually August

**NKRD-Specific Workflow**:
- **Guide release**: Varies by special project, typically Q4 or Q1
- **Pre-registration**: May require pre-registration in system
- **Project proposal + Task proposals**: For project-level applications
- **PPT preparation**: For答辩环节
- **Institutional coordination**: Multi-institution collaboration requires agreements

**Provincial Funds Workflow**:
- **Shorter preparation time**: Usually 1-2 months after guide release
- **Less complex**: Simpler application forms and requirements
- **Annual or bi-annual**: Varies by province

## Integration with Other Skills

This skill works effectively with:
- **Scientific Writing**: For clear, compelling prose
- **Literature Review**: For comprehensive background sections
- **Peer Review**: For self-assessment before submission
- **Research Lookup**: For finding relevant citations and prior work
- **Data Visualization**: For creating effective figures

## Resources

This skill includes comprehensive reference files covering specific aspects of grant writing:

- `references/nsf_guidelines.md`: NSF-specific requirements, formatting, and strategies
- `references/nih_guidelines.md`: NIH mechanisms, review criteria, and submission requirements
- `references/doe_guidelines.md`: DOE programs, emphasis areas, and application procedures
- `references/darpa_guidelines.md`: DARPA BAAs, program offices, and proposal strategies
- `references/broader_impacts.md`: Strategies for compelling broader impacts statements
- `references/specific_aims_guide.md`: Writing effective specific aims pages
- `references/budget_preparation.md`: Budget development and justification
- `references/review_criteria.md`: Detailed review criteria by agency
- `references/timeline_planning.md`: Creating realistic timelines and milestones
- `references/team_building.md`: Assembling and presenting effective teams
- `references/resubmission_strategies.md`: Responding to reviews and revising proposals

### Domestic (Chinese) Agency Resources

- `references/nsfc_guidelines.md`: NSFC program types, application structure, review criteria, and writing strategies
- `references/nkrdp_guidelines.md`: National Key R&D Program guide-direction requirements, project-task structure, and assessment metrics
- `references/postdoc_guidelines.md`: China Postdoctoral Science Foundation application guidance
- `references/provincial_fund_guidelines.md`: Provincial natural science fund strategies for Beijing, Shanghai, Guangdong, Jiangsu, Zhejiang, etc.
- `references/talent_program_guidelines.md`: Chang Jiang Scholars, Ten Thousand Talents, and other talent program applications

Load these references as needed when working on specific aspects of grant writing.

## Templates and Assets

### U.S. Agency Templates

- `assets/nsf_project_summary_template.md`: NSF project summary structure
- `assets/nih_specific_aims_template.md`: NIH specific aims page template
- `assets/timeline_gantt_template.md`: Timeline and Gantt chart examples
- `assets/budget_justification_template.md`: Budget justification structure
- `assets/biosketch_templates/`: Agency-specific biosketch formats

### Chinese Agency Templates

- `assets/nsfc_general_program_template.md`: NSFC 面上项目 (General Program) full application template
- `assets/nsfc_youth_program_template.md`: NSFC 青年科学基金 (Youth Program) application template
- `assets/nsfc_key_program_template.md`: NSFC 重点项目 (Key Program) application template
- `assets/nkrdp_youth_scientist_template.md`: 国家重点研发计划青年科学家项目 template
- `assets/nkrdp_task_template.md`: 国家重点研发计划课题任务书 template

## Scripts and Tools

- `scripts/compliance_checker.py`: Verify U.S. agency formatting requirements
- `scripts/budget_calculator.py`: Calculate budgets with inflation and fringe
- `scripts/deadline_tracker.py`: Track submission deadlines and milestones
- `scripts/nsfc_compliance_checker.py`: Verify NSFC proposal compliance (title length, abstract length, section completeness, reference count, figure requirements, program-specific checks)

---

**Final Note**: Grant writing is both an art and a science. Success requires not only excellent research ideas but also clear communication, strategic positioning, and meticulous attention to detail. Start early, seek feedback, and remember that even the best researchers face rejection—persistence and revision are key to funding success.

