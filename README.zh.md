# HomomicsLab

一个面向计算生物学的通用智能体平台，弥合** rigid 生物信息学流程管线**与**非结构化笔记本集合**之间的鸿沟。HomomicsLab 将自然语言研究问题转化为可复现、可审计、自我进化的分析工作流——结合 AI 智能体的自适应能力与生产级数据工程的严谨性。

> **v0.4.0** — 端到端分析自动化，支持动态智能体角色、多智能体集群、自我进化的技能知识图谱、动态重规划、智能体自我进化、CBKB 自动策展、多层稳定性保障，以及完整的可复现性捕获。

---

## 问题所在

计算生物学处在一个痛苦的交叉点：

| 方案 | 优势 | 致命弱点 |
|---|---|---|
| ** turnkey 流程管线** (Galaxy, nf-core) | 可复现、经过验证 | 僵化——参数稍有偏差流程就中断；用户必须会说"工作流语言" |
| **笔记本集合** (Scanpy 教程, Seurat vignettes) | 灵活、有教育意义 | 碎片化、手动操作、无法规模化复现 |
| **通用 LLM 智能体** (ChatGPT, Claude Code) | 对话式、通用 | 没有生物信息学领域知识；会幻觉化包名、忽略批次效应、产生不可复现的一次性结果 |
| **工作流引擎** (Snakemake, Nextflow DSL) | 可扩展、声明式 | 需要专家编排；对数据状态没有语义理解 |

**HomomicsLab 是第四种选择**：一个**领域原生智能体平台**，既懂生物学*也*懂工程——从自然语言规划分析策略，以沙盒精度执行，以领域感知的异常检测解读结果，并捕获每一个决策以实现可复现性。

---

## HomomicsLab 的独特之处

HomomicsLab 并非凭空构建。它综合了**通用 AI 智能体**、**生物信息学工作流系统**、**交互式笔记本**、**MLOps 工具**和**代码生成助手**中的最佳思想——然后添加了它们单独都无法提供的缺失部分。

### 学术渊源

HomomicsLab 属于科学领域**特定领域智能体系统**这一快速涌现的类别。我们直接承认我们所站立的巨人肩膀：

| 系统 | 我们采纳了什么 | 缺失了什么（HomomicsLab 补充的） |
|---|---|---|
| **Biomni** (Stanford/Genentech) | CodeAct 风格的代码生成；统一的生物医学工具空间；检索增强规划 | 单智能体架构，无稳定性保障；无版本锁定；无数据血缘；可复现性是事后考虑 |
| **DeerFlow 2** (ByteDance) | 子智能体编排；沙盒执行；渐进式技能加载；持久化记忆 | 通用研究框架，无生物信息学领域策略；无模式验证；无回归测试；循环检测会误杀合法的生物信息学工作流 |
| **Hermes** (NousResearch) | `SKILL.md` 技能规范格式；模块化技能库 | 无执行时模式验证；无技能关系进化；无工作空间溯源 |
| **OmicVerse** | 单细胞/ bulk RNA-seq 分析方法；可视化最佳实践 | 一个 Python 库，不是智能体——需要手动编排；无自然语言接口；无可复现性捕获 |
| **CowAgent** (zhayujie) | 子智能体编排；沙盒执行；渐进式技能加载；持久化记忆；Markdown 维基 PKB | 通用 IM 助手，无生物信息学领域策略；无模式验证；无回归测试；PKB 是黑盒维基，无实验溯源或参数知识 |
| **AutoGPT / BabyAGI** | 自主规划循环；任务分解；记忆层 | 无生物学领域知识；无稳定性保障；无可复现性框架 |
| **LangChain / LlamaIndex** | 工具注册抽象；上下文压缩；检索模式 | 对工具 I/O 无严格模式验证；无版本锁定；无回归测试 |
| **Galaxy / nf-core** | 社区验证的工作流；可复现环境 | 僵化参数模式；用户必须会说"工作流语言"；无基于数据状态的自适应规划 |
| **Snakemake / Nextflow** | 声明式执行；HPC 可扩展性 | 需要专家编排；对数据状态无语义理解 |
| **Aider / Cursor / Devin** | 代码生成作为一等公民；智能体驱动的编辑 | 无领域策略模板；无代码生成*原因*的解释；无跨运行学习 |
| **W&B / MLflow** | 实验追踪；环境日志 | 追踪模型训练，而非端到端生物信息学分析；遗漏 HITL 决策和智能体推理 |
| **DVC** | 数据版本控制；流程管线血缘概念 | 需要手动 DAG 定义；无来自智能体执行的自动溯源 |

**以上系统单独都无法提供的**：一个具备动态角色、自我进化技能关系、三层稳定性保障、完整可复现性包、自动数据血缘的**生物信息学原生智能体平台**——运行在带有 human-in-the-loop 检查点的沙盒化工作空间中。

### 1. 端到端分析闭环

从一句话如 *"分析我的 PBMC 数据集并找出每个 cluster 的 marker 基因"* 到一份**自包含的 HTML 报告，包含 UMAP、DE 表格和方法章节**——一次对话完成。

HomomicsLab 处理完整的生命周期：
- **意图分析** — 将自然语言研究目标解析为结构化的 `UserIntent` 对象（分析目标、数据约束、质量阈值）。不限于预定义类别——任何生物信息学工作流都可以表达。
- **自适应规划** — 从可扩展的领域策略模板库中选择并生成随实时数据状态自适应的计划。检测到批次效应 → 注入整合步骤；质量低 → 收紧 QC；技能失败 → 通过 SkillDAG 自动切换替代技能。
- **执行** — 带有模式验证和资源监控的沙盒化技能运行时
- **解读** — 阶段级结果分析："QC 过滤了 12% 的细胞——在正常范围内。下一步：归一化。"
- **报告** — 自动生成可发表的 HTML/Markdown 报告，含图表和溯源信息
- **可复现性** — 每次分析导出一个 `ReproducibilityBundle`：精确代码、计划、HITL 决策、环境锁定

### 2. 领域原生智能

HomomicsLab 不是 GPT-4 的薄包装。它在架构层面嵌入了**生物信息学工作流知识**：

- **策略模板**：PlanEngine 携带内置的领域策略（`single_cell_standard`、`spatial_transcriptomics`、`qc_only`），编码了*正确的操作顺序*——不是作为硬编码脚本，而是作为响应数据特征的可适应模板。
- **数据状态自适应**：计划根据数据告诉我们什么而变化。检测到批次效应？计划自动注入整合。细胞质量低？QC 阈值收紧。已有 clusters？跳过冗余步骤。
- **SkillDAG**：一个自我进化的知识图谱，追踪技能在实践中如何关联——`scanpy_qc` → `scanpy_pca` → `scanpy_cluster`——从执行历史中学习，而非手工编码。

### 3. 自我进化的技能生态系统

HomomicsLab 中的技能不是手动安装后就忘记的工具。它们是**一个活跃系统中的一等公民**：

- **自我进化的关系**：SkillDAG 自动从执行历史中发现 `followed_by`、`conflicts_with` 和 `alternative_to` 关系。边在重复成功执行后从 `CANDIDATE` → `CONFIRMED` 升级。
- **语义发现**：双引擎技能搜索——TF-IDF 用于精确匹配 + sentence-transformers 用于概念相似度。查询"降低维度"可以找到 PCA、UMAP 和 t-SNE，即使它们的标题中都没有提到"降低"。
- **自动生成**：通过模板化脚手架从自然语言需求生成新技能。
- **统一格式**：内置技能和外部技能使用完全相同的 `SKILL.md + scripts/` 格式。外部技能不是"二等公民"。

### 4. 多层稳定性保障

生物信息学分析太重要了，不能静默失败。HomomicsLab 部署**纵深防御**：

| 层级 | 防御机制 | 防止的问题 |
|---|---|---|
| **L1 — 模式验证** | 每个技能输入/输出对照声明的 JSON Schema 进行验证 | 类型不匹配、缺少必填字段、静默数据损坏 |
| **L2 — 版本锁定** | 项目级锁定：技能版本、脚本 SHA-256、pip freeze、Python 版本 | "昨天还能跑"的漂移、依赖地狱 |
| **L2 — 回归测试** | 从已知良好执行中记录基线；检测输出签名漂移 | 静默改变结果的技能更新 |
| *(计划) L3* | 跨阶段语义一致性检查 | 分析步骤之间的逻辑矛盾 |

### 5. 完整的可复现性，不只是版本控制

Git commit 对计算生物学来说不够。HomomicsLab 的 `ReproducibilityEngine` 捕获：

- **精确代码** — 智能体生成的调用技能的 Python 代码，不只是技能名称
- **计划** — 带有数据状态自适应的完整执行策略
- **每个 HITL 决策** — 当人类选择 resolution=0.8 而非默认值时
- **环境锁定** — `pip freeze`、`conda env export`、Python 版本
- **技能版本锁定** — 每个使用技能的精确版本和脚本校验和

结果是一个**JSON 可序列化的 Bundle**，可以被重新加载、检查和重放。

### 6. 可解释，不是黑盒

在每个主要阶段（QC、聚类、注释、DE、可视化）之后，**InterpretationEngine** 产出：

- **人类可读的摘要**：*"QC 过滤了 12% 的细胞（剩余 2,531），在正常范围内。"*
- **异常标记**：当过滤率超过 50% 时，*"高细胞过滤率：80% — 请检查数据质量"*
- **可操作的建议**：*"下一步：使用 PCA 降维"* — 按置信度排序，基于工作流规则 + SkillDAG + 当前数据状态

用户始终知道发生了什么、为什么发生、以及下一步应该做什么。

### 7. 计算生物学知识库 (CBKB)

与通用个人知识库（如 CowAgent 的 Markdown 维基）不同，HomomicsLab 的 CBKB 是**围绕生物信息学分析的本体论构建的结构化知识库**：

| 层级 | 存储内容 | 价值 |
|---|---|---|
| **实验图谱** | 每个 `ReproducibilityBundle` 作为一个节点；带类型的边（`shares_skill`、`shares_parameter`、`derived_from`） | "哪些过往分析使用了相同的 QC 策略？" |
| **参数知识** | 从执行历史中提取的"技能参数 → 结果质量"映射 | "对于 PBMC 数据集，`resolution=0.6` 历史上产生最佳的 cluster 分离" |
| **异常档案** | InterpretationEngine 检测到的每个阶段级异常 | "上次批次效应超过 30% 时，Harmony 优于 scVI" |
| **实验室 SOP** | 从重复成功分析中自动提炼的最佳实践模板 | 按实验室分类、可版本控制、可锁定的标准操作程序 |
| **技能进化日志** | SkillDAG 边状态转换的历史（`CANDIDATE` → `CONFIRMED`） | "我们的实验室数据已独立确认 QC→PCA→Cluster 工作流 47 次" |

CBKB **不是黑盒向量数据库**。每个条目都可追溯到 `ReproducibilityBundle`、`Workspace` 工件或 `SkillDAG` 边。它是**实验室的集体记忆**，不只是助手的记忆。

### 8. 数据溯源作为一等公民

HomomicsLab 中的每个工件都携带其历史：

```
workspaces/{project_id}/
├── data/               # 原始数据 — 只读保护 (chmod 444)
├── intermediate/       # 带 SHA-256 校验和的步骤工件
├── outputs/            # 最终交付物
├── logs/               # 执行日志
└── .metadata/          # 工件注册表、血缘图谱、快照、version.lock
```

- **血缘图谱**：从原始数据 → QC → 聚类 → DE → 图表的有向溯源
- **快照**：工作空间的时间点状态捕获
- **校验和完整性**：每个工件注册时附带 SHA-256；篡改可检测

### 9. 动态智能体角色 — 能力即配置

HomomicsLab 不硬编码 `BioinfoAgent`、`VizAgent` 和 `ExperimentAgent` 类，而是使用**YAML 可配置的角色**，决定智能体拥有哪些技能、工具和权限：

```yaml
role_id: visualization
name: Visualization Specialist
allowed_skills: [plot_umap, plot_heatmap, plot_violin]
allowed_tools: [file_read, file_write]
permissions:
  can_execute: true
  can_spawn_specialist: false
  max_concurrent_tasks: 2
```

- 一个常驻的 **Analyst** 协调；**Specialists** 按需生成
- **通配符匹配**：`scanpy_*` 自动路由所有 Scanpy 技能
- **被阻止的技能**：显式拒绝列表，用于安全敏感环境
- **工具级访问控制**：每个角色只能看到其被允许的原子工具

### 10. 长程动态重规划

计划不是刻在石头上的。**DynamicReplanningEngine** 监控执行并在现实偏离预期时实时重规划：

- **QC 中检测到关键异常** → 自动插入带有收紧阈值的 re-QC 阶段
- **聚类后发现批次效应** → 动态在差异表达前插入整合步骤
- **技能失败** → 通过 SkillDAG 切换到替代技能并恢复
- **用户干预改变参数** → 将变更向下传播到所有依赖阶段

与静态工作流引擎（Snakemake、Galaxy）不同，HomomicsLab 在执行过程中基于数据状态和中间结果自适应调整计划。

### 11. 多智能体集群 — 并行执行 + 共识

HomomicsLab 不限于每个任务一个智能体。**AgentSwarm** 编排多个 Specialist 并行工作：

- **并行任务组**：独立任务扇出到子智能体，通过信号量控制并发
- **共识投票**：同一任务可分配给多个智能体；不同意见以置信度分数呈现
- **广播消息**：首席 Analyst 可向所有匹配的 Specialist 广播上下文
- **SwarmOrchestrator**：自动识别任务树中的独立任务组并并行执行

这不只是"多智能体"表演——是有冲突检测的受控并行。

### 12. 智能体自我进化

智能体随着每次分析变得更聪明。**AgentEvolutionEngine** 持续从 CBKB 历史中学习：

- **角色进化**：如果 `resolution=0.6` 在 10+ 项目中始终产生更好的 clusters，系统提议更新角色的默认提示词或元数据
- **计划模式挖掘**：重复成功的阶段序列被提取为可复用的计划模式，附带成功率统计
- **参数偏好学习**：每个项目和每个实验室的参数偏好自动从 ParameterLore 中提炼
- **SOP 自动进化**：当成功分析模式重复 >3 次时，系统提议新的 Lab SOP 或现有 SOP 的版本升级

角色和计划是**活的配置**，不是静态 YAML 文件。

### 13. CBKB 自动策展 — 自我策展的知识库

计算生物学知识库不等待手动维护。**CBKBCurator** 运行自动策展流程：

- **夜间提炼**：扫描新实验包中的技能序列、参数组合和项目相似度
- **主题聚类**：实验通过 Jaccard 相似度在技能+参数上分组；每个组获得主题名称和中心摘要
- **叙事报告**："本月您的实验室分析了 12 个单细胞数据集。最常见的异常是批次效应（6 次）。最可靠的参数是 `resolution=0.6`。"
- **自动链接**：相似实验在实验图谱中自动获得类型化的边（`shares_skill`、`shares_parameter`）
- **SOP 偏离检测**：当现有 SOP 不再匹配实验室的实际最佳实践时，系统标记它们以供审查

---

## 快速开始

### Docker（推荐）

```bash
docker-compose up --build
# 后端: http://localhost:8080
# 前端: http://localhost:3000
```

### 本地开发

```bash
# 后端
cd backend
pip install -e ".[dev]"
uvicorn homomics_lab.main:app --reload --port 8080

# 前端（新终端）
cd frontend
npm install
npm run dev
# 打开 http://localhost:5173
```

---

## 项目结构

```
HomomicsLab/
├── backend/
│   ├── homomics_lab/
│   │   ├── agent/              # 智能体编排层
│   │   │   ├── core/           # AgentCore, DynamicAgent, RoleRegistry, roles/*.yaml
│   │   │   ├── plan/           # PlanEngine — 自适应策略生成
│   │   │   ├── replanning.py     # DynamicReplanningEngine — 执行时计划自适应
│   │   │   ├── interpretation.py   # InterpretationEngine
│   │   │   ├── swarm.py            # AgentSwarm — 并行多智能体执行 + 共识
│   │   │   ├── orchestrator.py     # 带重试和 HITL 的任务调度器
│   │   │   ├── evolution.py        # AgentEvolutionEngine — 角色/计划/SOP 自我进化
│   │   │   └── turn_runner.py    # 统一的对话轮次循环
│   │   ├── skills/             # 技能生态系统
│   │   │   ├── skill_dag.py    # 自我进化的类型化知识图谱
│   │   │   ├── loader.py       # 统一的 SKILL.md + scripts/ 加载器
│   │   │   ├── runtime.py      # 带模式验证的沙盒执行
│   │   │   ├── registry.py     # 技能发现与注册
│   │   │   └── models.py       # Pydantic 技能定义
│   │   ├── stability/          # 质量保证
│   │   │   ├── schema_validator.py   # L1: JSON Schema 验证
│   │   │   ├── version_locker.py     # L2: 版本锁定
│   │   │   └── regression_tester.py  # L2: 回归基线
│   │   ├── workspace/          # 数据溯源与持久化
│   │   │   ├── manager.py      # 持久化工作空间 + 工件注册表
│   │   │   └── lineage.py      # 数据溯源图谱
│   │   ├── reproducibility/    # 审计追踪
│   │   │   └── engine.py       # Bundle 捕获（代码、计划、HITL、环境）
│   │   ├── tools/              # 带角色过滤的原子工具注册表
│   │   ├── context/            # 工作记忆、语义记忆、压缩
│   │   ├── knowledge/          # CBKB: 5 层领域特定知识库
│   │   │   ├── cbkb.py             # ExperimentGraph, ParameterLore, AnomalyArchive, LabSOP, SkillEvolutionLog
│   │   │   └── curator.py        # CBKBCurator — 自动提炼、聚类、叙事报告
│   │   ├── hpc/                # SLURM, Nextflow, 本地调度器
│   │   ├── viz/                # Plotly 可视化引擎
│   │   ├── reports/            # HTML/Markdown 报告生成
│   │   └── api/                # FastAPI REST + WebSocket 端点
│   └── tests/                  # 504 个测试
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── chat/           # 聊天面板、HITL 表单、图表渲染
│       │   ├── workspace/      # 工作流画布、标签页
│       │   ├── reports/        # 报告列表 + 查看器
│       │   └── skills/         # 技能搜索 + 生成器
│       └── stores/             # Zustand 状态管理
├── Dockerfile
├── docker-compose.yml
└── docs/
    ├── architecture.md         # v0.4.0 架构原则
    └── setup.md
```

---

## API 端点

| 端点 | 描述 |
|---|---|
| `POST /api/chat/send` | 向智能体发送消息 |
| `POST /api/chat/hitl/respond` | 响应 HITL 检查点 |
| `GET /api/skills/` | 列出所有技能 |
| `GET /api/skills/search?q=` | 语义 + 图谱增强的技能搜索 |
| `POST /api/viz/plot` | 生成图表 |
| `POST /api/reports/create` | 创建分析报告 |
| `GET /api/reports/{id}/html` | 导出自包含 HTML 报告 |
| `POST /api/skill-generator/generate` | 从需求自动生成技能 |

---

## 测试

```bash
cd backend
pytest tests/ -q
# 504 个测试通过
```

覆盖范围包括：
- **智能体层**：动态角色、自适应规划、解读、编排、任务状态机
- **技能层**：DAG 进化、统一加载器、沙盒执行、语义搜索
- **稳定性层**：模式验证、版本锁定、回归测试
- **工作空间层**：路径解析、工件注册表、血缘图谱、快照
- **可复现性层**：Bundle 捕获、JSON 往返、环境锁定
- **集成层**：AgentCore + Orchestrator、PlanEngine + AgentCore、Workspace + VersionLocker

---

## 配置

环境变量（前缀 `HOMOMICS_`）：

| 变量 | 默认值 | 描述 |
|---|---|---|
| `HOMOMICS_PORT` | `8080` | API 服务器端口 |
| `HOMOMICS_EXTERNAL_SKILLS_DIR` | — | 外部技能集合路径 |
| `HOMOMICS_SEMANTIC_SEARCH_MODEL` | — | 设置为 `all-MiniLM-L6-v2` 以启用稠密嵌入 |

---

## 技术栈

- **后端**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy, scikit-learn, sentence-transformers, sqlite-vec
- **前端**: React 18, TypeScript, Tailwind CSS, Zustand, TanStack Query, Plotly.js
- **工作流**: Nextflow (DSL2), SLURM (sbatch/sacct)
- **部署**: Docker, Docker Compose, nginx

---

## 许可

MIT
