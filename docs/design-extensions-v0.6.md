# HomomicsLab v0.6 扩展能力设计方案

> 面向作图、个人知识库/KG、湿实验辅助、科研写作/文献情报、临床数据分析、Skill 评估进化六大方向的有机集成方案。  
> 原则：**宁缺毋滥**，不另起炉灶，优先复用现有 Skill/Domains、CBKB、SemanticMemory、Provenance、HITL、Evaluation Harness 与 RO-Crate 体系。

---

## 1. 设计目标与原则

### 1.1 目标
在 v0.5 已完成「架构基础设施（记忆、HITL、规划、执行、可复现）」的基础上，把 HomomicsLab 从"能跑通生信 pipeline"扩展为覆盖**数据→分析→图表→知识→写作→临床→进化**的科研生产力平台。

### 1.2 核心原则

| 原则 | 说明 |
|------|------|
| **Skill-First** | 每个新能力优先以 `SKILL.md + scripts/` 形式落地，通过 `SkillStore.import_skill()` 进入系统，而非写死代码。 |
| **Domain-Driven** | 使用 `domain.yaml` 定义作图、临床、科研写作等垂直领域，复用 `StrategyLibrary` / `SkillDAG` / `TurnRunner`。 |
| **记忆即资产** | 个人上传的 PDF、数据集、实验记录全部进入 `CBKB` + `SemanticMemory`，形成可检索、可演化的知识资产。 |
| **可复现闭环** | 所有图表、写作产物、临床报告都走 `ProvenanceRecorder` → `ReproducibilityEngine` → `RO-Crate` 导出。 |
| **人在回路** | 涉及临床决策、论文投稿、实验方案时强制 HITL checkpoint，保留审计日志。 |
| **验证驱动进化** | Skill 评估不是静态 lint，而是基于 test-prompts 的结构+效果双重评分，并采用 ratchet（只升不降）机制。 |

---

## 2. 与现有架构的关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         新增 / 扩展的能力层（v0.6）                            │
│  作图域    科研写作域    临床域    湿实验域    知识库域    Skill 进化域        │
│   (Domain)  (Domain)    (Domain)  (Domain)   (Domain+CBKB)  (Evolution Engine)│
└──────────────────┬──────────────────────────────────────────────────────────┘
                   │ 复用 SkillRuntimeExecutor / AgentSkillExecutor / CodeAct
                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    v0.5 已有核心层                                            │
│  SkillRegistry · SkillStore · SkillDAG · StrategyLibrary · DomainLoader       │
│  TurnRunner · Orchestrator · HITL · SemanticMemory · CBKB · Provenance       │
│  EvaluationHarness · RO-Crate · WorkspaceManager · DataStore                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

新增能力**不破坏**现有接口，主要扩展点：
- `backend/homomics_lab/domains/{viz,clinical,paperwriting,experimental_design,knowledge}/`
- `backend/homomics_lab/skills/imported/`（通过 `SkillStore` 引入外部 skill 集合）
- `backend/homomics_lab/knowledge/{assets.py,graph.py}`（知识资产与 KG）
- `backend/homomics_lab/evaluation/skill_evolution.py`（Skill 评估与进化）
- `backend/homomics_lab/api/{knowledge.py,figures.py,clinical.py,writing.py}`（可选 API 薄层）
- `frontend/src/components/{Figures,Knowledge,Writing,Clinical}/`

---

## 3. 六大能力域设计方案

### 3.1 作图能力（GraphPad-Prism 替代）

#### 3.1.1 能力边界（宁缺毋滥）
- **做**：通用生物医学统计 + 发表级图表生成、多图排版、自然语言/圈选修图、可复现 Notebook 导出。
- **不做**：不构建一个完整的拖拽式 GUI 绘图工具；不替代复杂交互式可视化（如 Shiny/Plotly Dash）。

#### 3.1.2 落地方式
直接引入并适配本地已有的 `Stat-Viz-Skills`：

```text
data/skill_store/imported/local/
  bio-statistics-visualization/      # 来自 Stat-Viz-Skills
    SKILL.md
    scripts/python/
      importer.py        # DataImportSkill
      stat_tests.py      # StatTestSkill
      renderer.py        # FigureRenderer
      export.py          # ExportEngine
      layout.py          # MultiPanelComposer
      vision_edit.py     # VisionEditSkill（可选）
```

同时新增一个 `viz_biomedical` domain：

```yaml
# backend/homomics_lab/domains/viz_biomedical/domain.yaml
domain: viz_biomedical
version: 1.0.0
phases:
  - id: data_import
    required: true
    default_skill: bio-statistics-visualization
  - id: stat_test
    required: false
    skills: [bio-statistics-visualization]
  - id: figure_render
    required: true
    default_skill: bio-statistics-visualization
  - id: layout_export
    required: false
    default_skill: bio-statistics-visualization
intents:
  - analysis_type: biomedical_plotting
    keywords: ["作图", "Prism", "ANOVA", "t-test", "生存曲线", "箱线图", "小提琴图"]
    examples: ["帮我画一张 Nature 风格的小鼠肿瘤体积箱线图"]
roles:
  - role_id: viz_specialist
    allowed_skills: ["bio-statistics-visualization"]
    permissions: ["execute_script", "read_file", "write_file"]
sops:
  - id: figure_export_sop
    title: 发表级图表导出 SOP
    steps: ["确认期刊主题", "检查字体/字号/DPI", "导出 SVG+TIFF", "生成可复现 Notebook"]
```

#### 3.1.3 关键集成
- **数据流**：用户上传 CSV/Excel → `DataStore` 保存为 Parquet → `FigureSpec` 生成 → `FigureRenderer` 输出 SVG/PNG/Plotly → `WorkspaceManager` 注册到 `figures/` 目录。
- **API 复用**：结果通过现有 `/api/viz/plot` 返回，新增 `/api/viz/figures/{project_id}` 列出图表资产。
- **自然语言修图**：在 `bio-statistics-visualization` 中增加 `VisionEditSkill` 子能力，调用多模态 LLM 解析"把 Group A 改成红色"或基于用户圈选坐标微调，输出新的 `FigureSpec` 并记录 diff。
- **可复现性**：每次图表生成同时写入 `notebooks/figure_<id>.ipynb` 与 `provenance.db`，支持 RO-Crate 导出。

---

### 3.2 个人知识库 / 数据集 / 知识图谱

#### 3.2.1 能力边界
- **做**：把用户上传的 PDF/书籍/论文/数据集/实验记录转化为可检索、可推理、可与分析流程联动的知识资产；构建项目级知识图谱。
- **不做**：不做一个通用网盘；不替代 Zotero/EndNote 的完整文献管理功能，但支持导入/导出。

#### 3.2.2 新增数据模型

```python
# backend/homomics_lab/knowledge/assets.py
class KnowledgeAsset(BaseModel):
    id: str
    project_id: str
    asset_type: Literal["pdf", "book", "dataset", "paper", "protocol", "note"]
    title: str
    source_path: Path
    extracted_text_path: Optional[Path]
    metadata: dict
    embedding_id: Optional[str]   # 指向 SemanticMemory
    kg_node_id: Optional[str]     # 指向 KnowledgeGraph

class DatasetAsset(KnowledgeAsset):
    format: Literal["csv", "xlsx", "h5ad", "fastq", "mzml", "image"]
    schema: dict                  # 列名/类型
    sample_size: Optional[int]
    preview_rows: list[dict]
```

#### 3.2.3 落地方式
1. **文档→Skill/Knowledge**：参考 `book-to-skill` 思路，新增一个内部 skill `knowledge_ingest`：
   - 输入：PDF/EPUB/DOCX/TXT/Markdown 路径。
   - 处理：`docling` / `pdftotext` 提取 → LLM 生成章节摘要/术语表/模式清单 → 输出为：
     - 一条 `KnowledgeAsset` 记录；
     - 多个 `SemanticMemory` memory（类型 `NOTE`/`CONCEPT`）；
     - 可选：打包为临时 skill（`~/.homomics/skills/books/<slug>/`）供后续对话引用。
2. **数据集注册**：新增 `/api/projects/{id}/datasets` 上传与 `/api/knowledge/datasets/{id}/preview` 预览，元数据写入 `KnowledgeAsset`。
3. **知识图谱构建**：
   - 节点类型：`Paper`、`Dataset`、`Experiment`、`Skill`、`Concept`、`Protocol`、`ClinicalCohort`。
   - 边类型：`cites`、`uses_skill`、`produces`、`derived_from`、`mentions_concept`、`similar_to`。
   - 构建来源：CBKB 已有 `experiment_nodes/edges` + 新提取的实体关系 + SkillDAG。
   - 存储：复用 SQLite（`knowledge_graph.db`），可选 Neo4j 后端作为未来扩展点。
4. **检索接口**：新增 `KnowledgeGraphRetriever`（类似 `CBKBRetriever`），支持：
   - "我的项目里有哪些单细胞数据用了 scanpy 做 QC？"
   - "找与这篇 protocol 相关的实验节点。"

#### 3.2.4 关键集成
- 上传入口：`frontend/src/components/Knowledge/AssetUploader.tsx`。
- 图谱展示：复用 `ReactFlow` 已有能力，新增 `KnowledgeGraphCanvas`。
- 与分析联动：`ContextEngine.build()` 中加入 `KnowledgeGraphRetriever` 作为新的 `ContextSource`。

---

### 3.3 辅助生物实验设计及实验数据处理

#### 3.3.1 能力边界
- **做**：帮助用户设计湿实验（假设生成、样本量、随机化、盲法、对照、偏差评估）、管理 protocol/SOP、处理常见仪器输出（板读仪、流式、显微镜图像、质谱 raw）。
- **不做**：不替代完整 ELN（Labii/Benchling）；不做 GxP 合规认证；不直接控制实验设备。

#### 3.3.2 落地方式
新增 `experimental_design` domain 并引入 `paperwriting-Skills/scientific-research-design` 作为基础：

```yaml
# backend/homomics_lab/domains/experimental_design/domain.yaml
domain: experimental_design
phases:
  - id: hypothesis_generation
    default_skill: scientific-research-design
  - id: design_evaluation
    default_skill: scientific-research-design
  - id: sample_size_power
    default_skill: wetlab_sample_size
  - id: randomization_blinding
    default_skill: wetlab_randomization
  - id: protocol_design
    default_skill: wetlab_protocol_writer
  - id: instrument_data_import
    default_skill: wetlab_data_import
```

新增/复用 skills：
- `wetlab_sample_size`：基于 `statsmodels` 计算样本量 / power。
- `wetlab_randomization`：生成随机分组表、盲法标签。
- `wetlab_protocol_writer`：输出结构化 protocol，并写入 CBKB `lab_sop`。
- `wetlab_data_import`：读取常见仪器格式（FlowJo CSV、酶标仪 Excel、质谱 mzML），做基础 QC 并转入 `DataStore`。

#### 3.3.3 关键集成
- `scientific-research-design` 是纯知识 skill，使用 `AgentSkillExecutor` 执行。
- 计算类 skill 使用 Python sandbox，结果写入 `DataStore`。
- 每个 protocol 生成后触发 HITL checkpoint："请实验负责人确认该方案"，确认后锁定版本并写入审计日志。

---

### 3.4 科研方案、文献情报、文献写作全流程

#### 3.4.1 能力边界
- **做**：从 idea → 文献调研 → 研究方案 → 论文/基金写作 → 审稿回复的全流程辅助。
- **不做**：不保证发表；不自动投稿；不代替作者对学术事实的最终审核。

#### 3.4.2 落地方式
引入 `paperwriting-Skills` 作为核心 skill 集群：

```text
data/skill_store/imported/local/
  scientific-research-design/
  scientific-literature-review/
  scientific-manuscript/
  scientific-grant-writing/
  scientific-peer-review/
  scientific-illustration/
  scientific-visualization/
  scientific-ideation/
  scientific-communication/
  scientific-orchestrator/      # 新增：串联上述 skill 的 orchestrator
```

新增 `scientific_writing` domain：

```yaml
# backend/homomics_lab/domains/scientific_writing/domain.yaml
domain: scientific_writing
phases:
  - id: ideation
    default_skill: scientific-ideation
  - id: literature_review
    default_skill: scientific-literature-review
  - id: research_design
    default_skill: scientific-research-design
  - id: proposal_or_manuscript
    default_skill: scientific-orchestrator
  - id: figure_table_prep
    default_skill: scientific-visualization
  - id: peer_review_simulation
    default_skill: scientific-peer-review
```

#### 3.4.3 文献情报子系统（PaperFlow + STORM 思路）
新增一个后台服务 `LiteratureIntelligenceService`（可视为一个定时 job）：
- **Profile**：从用户自然语言描述、Google Scholar 主页、已发表论文构建研究画像。
- **Daily Push**：从 arXiv/bioRxiv/PubMed/OpenReview 拉取当日论文，按画像排序。
- **Reading Report**：对选中论文调用 LLM 生成摘要、方法、与项目的关联。
- **Local Wiki**：把论文、报告、用户反馈写入 `KnowledgeGraph`。
- **Cited Q&A**：基于本地知识图谱回答"我最近读过的关于 GNN 的论文有哪些结论？"。

与 HomomicsLab 集成：
- 作为 `paperflow` skill 集合提供，用户可配置源与 API key；无 key 时回退到 mock/本地模式。
- 文献情报结果作为 `ContextSource` 进入 `ContextEngine`，影响写作与研究方案。

#### 3.4.4 STORM 式综述生成
新增 skill `storm_literature_review`：
- 输入：主题 + 可选本地/网络检索源。
- 过程：多视角问题生成 → 检索/对话模拟 → 大纲生成 → 分段写作 → 引用校验 → 润色。
- 输出：带引用标记的 Markdown 综述，存入 `reports/`。

#### 3.4.5 关键集成
- 写作产物复用 `/api/reports` 与 `/api/projects/{id}/export/rocrate`。
- `scientific-orchestrator` skill 使用 `AgentSkillExecutor` 调用子 skill，由 `TurnRunner` 统一调度。
- 引用校验使用 `ToolRegistry.web_search` + 本地 `KnowledgeGraph`。

---

### 3.5 临床医学数据分析（面向临床医生）

#### 3.5.1 能力边界
- **做**：提供临床医生常用的"套路/模板/工具/方法"：基线特征表、倾向性评分匹配、生存分析、回归模型、亚组分析、诊断试验、临床报告与 STROBE/CONSORT 检查清单。
- **不做**：不做临床决策支持系统（CDSS）认证；不处理可识别患者信息，默认强制本地脱敏。

#### 3.5.2 落地方式
新增 `clinical_research` domain：

```yaml
# backend/homomics_lab/domains/clinical_research/domain.yaml
domain: clinical_research
phases:
  - id: data_import_deidentify
    default_skill: clinical_data_import
  - id: table1_baseline
    default_skill: clinical_table1
  - id: survival_analysis
    default_skill: clinical_survival
  - id: regression_model
    default_skill: clinical_regression
  - id: propensity_matching
    default_skill: clinical_psm
  - id: subgroup_forest
    default_skill: clinical_subgroup
  - id: diagnostic_test
    default_skill: clinical_diagnostic
  - id: report_checklist
    default_skill: clinical_reporting
```

新增 skills（内部实现尽量调用 `bio-statistics-visualization` 与 `scientific-manuscript`）：
- `clinical_data_import`：CSV/RedCap/Excel 导入，自动检测 PHI 列并提示脱敏。
- `clinical_table1`：生成 Table 1（均值±SD、中位数、计数%、组间比较 p 值）。
- `clinical_survival`：Kaplan-Meier + log-rank + Cox（单/多因素）。
- `clinical_regression`：logistic / linear / Poisson 回归，输出 OR/β、95% CI、p 值。
- `clinical_psm`：倾向性评分匹配（1:1 / 1:N）。
- `clinical_subgroup`：亚组分析 + 森林图。
- `clinical_diagnostic`：ROC、AUC、灵敏度、特异度、NPV/PPV。
- `clinical_reporting`：按 STROBE/CONSORT/TRIPOD/STARD 生成检查清单与结果段落。

#### 3.5.3 关键集成
- 临床数据默认标记 `sensitivity=high`，触发 `ToolApprovalRequired` / HITL。
- 所有分析结果写入 `provenance.db`，附带脱敏声明；RO-Crate 导出时保留审计链。
- 前端提供 "Clinical Wizard" 组件，医生按步骤选择分析类型、上传数据、查看结果。

---

### 3.6 Skill 评估及进化能力

#### 3.6.1 能力边界
- **做**：建立结构化 Skill 评估体系（结构 + 效果），基于 test-prompts 自动打分，识别低分维度并生成改进建议；支持人在回路的单维度优化与 ratchet 保留机制。
- **不做**：不保证所有 skill 都能自动进化到完美；不自动上线改进后的 skill，必须人工 approve。

#### 3.6.2 评估体系（参考 darwin-skill + SkillLens/SkillOpt）
新增 `SkillEvaluator`：

```python
# backend/homomics_lab/evaluation/skill_evaluator.py
class SkillEvaluator:
    async def evaluate(self, skill: SkillDefinition, test_cases: list[EvaluationCase]) -> SkillEvaluationReport
    async def structural_score(self, skill: SkillDefinition) -> dict[str, float]
```

评分维度（满分 100，权重可调）：

| 维度 | 来源 | 评估方式 |
|------|------|----------|
| 可执行具体性 | SkillLens | 静态检查 SKILL.md 是否含模糊词（"建议/视情况而定"） |
| 失败模式编码 | SkillLens | 是否显式列出已知失败路径与规避方法 |
| 高风险黑名单 | SkillLens | 是否明文禁止 rm/git reset --hard/force push 等 |
| 输入输出 schema | HomomicsLab | `SchemaValidator` 是否通过 |
| 用例覆盖 | HomomicsLab | `examples/` 与 `tests/` 数量与通过率 |
| 实际效果 | HomomicsLab | 跑 `test-prompts.json` 的 pass rate / F1 |
| 可复现性 | HomomicsLab | 是否声明依赖、环境、版本 |
| 安全性 | HomomicsLab | `code_safety` 静态审计结果 |
| 可维护性 | HomomicsLab | 代码复杂度、重复度 |

#### 3.6.3 进化流程（参考 darwin-skill）
新增 `SkillEvolutionEngine`：

```python
# backend/homomics_lab/evolution/skill_evolution.py
class SkillEvolutionEngine:
    async def run(self, skill_id: str) -> EvolutionResult
```

流程：
1. **基线评估**：自动评分 + 生成报告；HITL 确认是否优化。
2. **单维度优化**：每次只针对最低分维度，由独立 judge agent 提出 1 个具体编辑方案。
3. **编辑与测试**：修改 SKILL.md，运行 `test-prompts.json`，2 个独立评委重新评分。
4. **Ratchet**：新分 > 旧分 → 保留为新版本；否则 `git revert`。
5. **早停**：单轮涨幅 < 1 分或连续 3 轮无提升则停止。
6. **人工审批**：最终由用户在 `/skills/{id}/evolve` 页面确认发布新版本。

#### 3.6.4 关键集成
- 复用 `EvaluationHarness`、`SkillVersion`（v0.5 已引入 semver）、`SkillDAG` 记录进化边。
- 每个改进后的 skill 版本写入 `SkillVersionLock`，项目可显式选择是否升级。
- CLI：`homomics skill evaluate <skill_id>`、`homomics skill evolve <skill_id>`。
- API：`POST /api/skills/{id}/evaluate`、`POST /api/skills/{id}/evolve`。

---

## 4. 统一数据模型与 API 扩展

### 4.1 新增/扩展的数据模型

| 模型 | 位置 | 说明 |
|------|------|------|
| `KnowledgeAsset` / `DatasetAsset` | `knowledge/assets.py` | 个人知识库与数据集资产 |
| `KnowledgeGraphNode/Edge` | `knowledge/graph.py` | 项目级知识图谱 |
| `FigureAsset` | `workspace/figures.py` | 图表资产与版本 |
| `ClinicalReport` | `clinical/models.py` | 临床分析报告 |
| `WritingProject` | `writing/models.py` | 论文/基金项目结构 |
| `SkillEvaluationReport` | `evaluation/skill_evaluator.py` | Skill 评估报告 |
| `EvolutionResult` | `evolution/skill_evolution.py` | Skill 进化结果 |

### 4.2 新增 API 路由（薄层）

```python
# backend/homomics_lab/api/knowledge.py
@router.post("/projects/{project_id}/knowledge/upload")
@router.get("/projects/{project_id}/knowledge")
@router.get("/projects/{project_id}/knowledge/{asset_id}/preview")
@router.post("/projects/{project_id}/knowledge/{asset_id}/ask")
@router.get("/projects/{project_id}/knowledge/graph")

# backend/homomics_lab/api/figures.py
@router.get("/projects/{project_id}/figures")
@router.post("/projects/{project_id}/figures/render")
@router.post("/projects/{project_id}/figures/{figure_id}/edit")

# backend/homomics_lab/api/clinical.py
@router.post("/projects/{project_id}/clinical/analyze")
@router.get("/projects/{project_id}/clinical/templates")
@router.post("/projects/{project_id}/clinical/deidentify")

# backend/homomics_lab/api/writing.py
@router.post("/projects/{project_id}/writing/outline")
@router.post("/projects/{project_id}/writing/section")
@router.post("/projects/{project_id}/writing/review")

# backend/homomics_lab/api/skills.py（扩展）
@router.post("/skills/{skill_id}/evaluate")
@router.post("/skills/{skill_id}/evolve")
@router.get("/skills/{skill_id}/evaluations")
```

### 4.3 与现有 ContextEngine 的集成
把新知识源加入 `ContextSource`：

```python
class ContextSource(str, Enum):
    SYSTEM_PROMPT = "system_prompt"
    PROJECT_STATE = "project_state"
    CBKB = "cbkb"
    SEMANTIC_MEMORY = "semantic_memory"
    EPISODIC_SUMMARY = "episodic_summary"
    WORKING_MEMORY = "working_memory"
    KNOWLEDGE_GRAPH = "knowledge_graph"      # 新增
    LITERATURE_INTEL = "literature_intel"    # 新增
    FIGURE_REGISTRY = "figure_registry"      # 新增
```

---

## 5. 前端集成方案

### 5.1 新增页面/组件

| 页面/组件 | 路径 | 功能 |
|-----------|------|------|
| 图表工作台 | `frontend/src/components/Figures/FigureWorkbench.tsx` | 上传数据、选择统计/图表类型、预览、自然语言修图 |
| 知识库浏览器 | `frontend/src/components/Knowledge/KnowledgeBrowser.tsx` | 上传资产、预览、搜索、图谱视图 |
| 知识图谱画布 | `frontend/src/components/Knowledge/KnowledgeGraphCanvas.tsx` | 复用 ReactFlow 展示实体关系 |
| 临床向导 | `frontend/src/components/Clinical/ClinicalWizard.tsx` | 选择临床分析模板、上传数据、查看报告 |
| 写作助手 | `frontend/src/components/Writing/WritingAssistant.tsx` | 大纲、分节写作、引用、审稿模拟 |
| 文献情报面板 | `frontend/src/components/Writing/LiteraturePanel.tsx` | 每日推送、阅读报告、本地 Wiki Q&A |
| Skill 进化面板 | `frontend/src/components/Skills/SkillEvolutionPanel.tsx` | 评估报告、维度得分、进化 diff、审批 |

### 5.2 与现有 UI 的融合
- 顶部导航增加 **Knowledge、Figures、Clinical、Writing** 入口；作为项目内标签页，不破坏现有 Chat/Workspace 主流程。
- Chat 中识别到作图/临床/写作意图时，自动弹出对应工作台的快捷入口。
- 所有新组件使用现有的 `components/ui`（Button、Card、Tabs、Toast、CommandPalette）。

---

## 6. 实施路线图

### Phase 1：作图 + 科研写作（2–3 周）
- [ ] 引入 `Stat-Viz-Skills` 与 `paperwriting-Skills` 到 `data/skill_store/imported/local/`。
- [ ] 新增 `viz_biomedical`、`scientific_writing` domain YAML。
- [ ] 扩展 `/api/viz` 与 `/api/reports` 支持图表资产与写作项目。
- [ ] 前端新增 FigureWorkbench、WritingAssistant 基础版。
- [ ] 测试：每个 domain 至少 1 个 end-to-end 测试。

### Phase 2：个人知识库与知识图谱（2–3 周）
- [ ] 实现 `KnowledgeAsset`、`DatasetAsset`、`KnowledgeGraph` 模型与存储。
- [ ] 新增 `knowledge_ingest` skill（book-to-skill 思路）。
- [ ] 扩展 `ContextEngine` 支持 `KNOWLEDGE_GRAPH` 源。
- [ ] 前端新增 KnowledgeBrowser、KnowledgeGraphCanvas。
- [ ] 测试：上传 → 检索 → 图谱查询链路测试。

### Phase 3：湿实验辅助 + 临床数据分析（3–4 周）
- [ ] 新增 `experimental_design`、`clinical_research` domain。
- [ ] 实现 `clinical_table1`、`clinical_survival`、`clinical_psm` 等 skills。
- [ ] 实现 `wetlab_sample_size`、`wetlab_randomization`、`wetlab_protocol_writer`。
- [ ] 前端新增 ClinicalWizard。
- [ ] 安全：临床数据 HITL + 脱敏 + 审计。
- [ ] 测试：临床分析模板 pass rate ≥ 90%。

### Phase 4：Skill 评估与进化（2–3 周）
- [ ] 实现 `SkillEvaluator` 9 维度评分。
- [ ] 实现 `SkillEvolutionEngine` ratchet 流程。
- [ ] 为 Phase 1–3 引入的每个 skill 编写 `test-prompts.json`。
- [ ] 前端新增 SkillEvolutionPanel。
- [ ] 测试：低分 skill 至少完成一次成功进化并保留。

---

## 7. 风险与"宁缺毋滥"取舍

| 风险 | 应对 |
|------|------|
| 外部 skill 质量参差不齐 | 引入时强制 `trusted=false`，必须通过 `SkillEvaluator` + 人工 trust 才能执行脚本。 |
| 临床数据隐私合规 | 默认本地执行；上传时强制脱敏检测；高敏感度操作必须 HITL；审计日志不可删。 |
| 知识图谱构建幻觉 | 实体关系由 LLM 提取后需人类确认；关键事实链接到原始 `KnowledgeAsset` 段落。 |
| Skill 进化导致退化 | 使用 ratchet + 独立评委 + 早停；改进版本不自动替换旧版，项目级锁定版本。 |
| 功能过度扩张 | 每个能力域先做 1–2 个核心 skill 闭环，后续按需扩展；不追求 GUI 完美。 |

**明确不做的事**：
- 不开发完整拖拽式 GraphPad GUI。
- 不替代 Zotero/EndNote 的完整文献管理。
- 不替代 Benchling/Labii 等完整 ELN。
- 不自动投稿或自动执行不可逆临床决策。

---

## 8. 附录：参考材料映射

| 参考材料 | 在本设计中的复用/借鉴 |
|----------|------------------------|
| PlotCase（微信文章） | 本地化科研绘图案例库思路 → 图表资产注册 + VisionEditSkill |
| Stat-Viz-Skills | 直接作为 `bio-statistics-visualization` skill 引入 |
| book-to-skill | 文档→Skill/Knowledge 的提取与结构化流程 |
| darwin-skill | 9 维度评估、ratchet、独立评委、HITL 三阶段进化 |
| STORM | 多视角文献调研 → `storm_literature_review` skill |
| PaperFlow | 每日论文推送、画像、阅读报告、本地 Wiki → `LiteratureIntelligenceService` |
| paperwriting-Skills | 直接作为 `scientific_writing` domain 的核心 skill 集群 |

---

## 9. 验收标准（建议）

- [ ] 作图：用户可通过自然语言完成"上传 CSV → 统计检验 → Nature 风格图表 → 导出 SVG"，端到端测试通过。
- [ ] 知识库：用户可上传 PDF，系统能回答基于该 PDF 的问题，并在知识图谱中展示相关节点。
- [ ] 湿实验：用户可生成并保存一个随机化分组表 + protocol SOP，审计日志可查。
- [ ] 临床：用户可上传脱敏临床数据，一键生成 Table 1 + KM 曲线 + Cox 表格，结果可导出 RO-Crate。
- [ ] 写作：用户可输入主题，系统生成带引用框架的综述/本子大纲，支持分节协作编辑。
- [ ] Skill 进化：低分 skill 经自动评估与人在回路优化后，评分提升 ≥ 5 分且测试通过。
- [ ] 全量测试：后端总测试数不下降；新增模块 ruff + mypy 通过；新增能力在 `docs/operations.md` 有文档。
