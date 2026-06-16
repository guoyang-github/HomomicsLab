# HomomicsLab

一个面向计算生物学的通用智能体平台，弥合**僵化的生物信息学流程管线**与**非结构化笔记本集合**之间的鸿沟。HomomicsLab 将自然语言研究问题转化为可复现、可审计、可扩展的分析工作流——结合 AI 智能体的自适应能力与生产级数据工程的严谨性。

> **v0.4.1** — 端到端分析自动化，支持单文件领域声明、CLI 脚手架、LLM 辅助领域生成、运行时热加载、动态智能体角色、多智能体集群、自我进化技能知识图谱、动态重规划、CBKB 自动策展、多层稳定性保障、完整可复现性捕获、大数据结果卸载、技能结果缓存、**CodeAct 代码缓存**、**跨进程工具调用沙盒**以及**领域模板市场**。

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

## 当前状态与成熟度

HomomicsLab 最好被理解为一套**生产就绪的智能体框架**，内置能力库正在不断扩展。核心架构、执行引擎、稳定性保障和可扩展机制均已实现并经过测试。然而，与任何通用智能体平台一样，其实际能力随安装的技能/领域数量和质量而增长。

| 能力 | 状态 | 说明 |
|---|---|---|
| 智能体编排（意图→计划→执行） | ✅ 已实现 | `TurnRunner`、`PlanEngine`、`Orchestrator`、`AgentCore` |
| 动态智能体角色 | ✅ 已实现 | YAML 可配置的 `RoleDefinition` + `DynamicAgent` |
| 多智能体集群与共识 | ✅ 已实现 | `AgentSwarm` 信号量控制并行 |
| 技能运行时与沙盒 | ✅ 已实现 | 本地 / bubblewrap / 容器 后端 |
| 模式验证（L1） | ✅ 已实现 | 每个技能的 JSON Schema 输入/输出验证 |
| 版本锁定（L2） | ✅ 已实现 | 项目级技能/环境/版本锁定 |
| 回归基线（L2） | ✅ 已实现 | CodeAct 成功执行后自动记录基线 |
| 可复现包 | ✅ 已实现 | 每个任务捕获代码、计划、HITL、环境锁 |
| DataStore 卸载 | ✅ 已实现 | Parquet/H5AD/pickle 大对象卸载 |
| 技能结果缓存 | ✅ 已实现 | SHA-256 键值记忆化 |
| CodeAct 代码缓存 | ✅ 已实现 | 基于任务描述 embedding 的相似缓存 |
| 跨进程工具调用沙盒 | ✅ 已实现 | 隔离的 `shell_exec`/`file_*` 工具调用 |
| 领域模板市场 | ✅ 已实现 | 通过 UI/API 导入/导出领域模板 |
| CBKB 与自动策展 | 🟡 框架就绪 | 接口已实现；自进化循环需要足够执行历史 |
| SkillDAG 自进化 | 🟡 框架就绪 | 图存在并记录执行；边升级需要重复成功运行 |
| 稠密语义搜索 | 🟡 可选 | 需配置 `HOMOMICS_SEMANTIC_SEARCH_MODEL` |
| 智能体自进化 | 🟡 框架就绪 | 对个人用户默认关闭定时任务 |

> **对个人用户**：HomomicsLab 设计为可自托管、隐私优先、本地可运行。除非你显式配置外部 LLM API 或云存储，否则数据不会离开你的机器。

---

## v0.4.1 新特性

### 跨进程工具调用沙盒
- `backend/homomics_lab/tools/invoke_tool.py` 提供跨进程边界调用原子工具的统一协议。
- 支持 `local`、`bubblewrap`、`container` 后端，使高风险工具调用在隔离沙盒中运行。

### CodeAct 代码缓存
- `backend/homomics_lab/execution/code_cache.py` 基于任务描述 embedding 缓存 CodeAct 生成的代码。
- 相似任务命中缓存，无需再次调用 LLM，降低成本和延迟。

### 自动记录回归基线
- CodeAct 成功执行后，系统自动记录回归基线。
- 后续相同技能/代码的运行可与基线对比，检测静默漂移。

### 前端"保存为 Skill"
- Skill Manager UI 新增 **保存为 Skill** 按钮，可将成功的 CodeAct 运行提升为可复用的 `SKILL.md + scripts/` 包。

### 领域模板市场
- 新增 `frontend/src/components/domains/DomainMarketplace.tsx` UI 标签页，用于浏览、导入、导出领域模板。
- 后端端点：`GET /api/domains/`、`POST /api/domains/import`、`POST /api/domains/{id}/export`、`POST /api/domains/import-zip`。

### 现代化前端 UI/UX 重构
- 新增 `frontend/src/components/ui/` 组件库（Button、Input、Card、Modal、Tabs、Toast、CommandPalette 等）。
- 亮/暗主题系统，支持跟随系统、自动切换，并持久化用户偏好。
- 侧边栏 + 顶部导航布局，支持键盘快捷键和命令面板（`Ctrl+K` / `Cmd+K`）。
- Settings 面板：LLM 提供商/模型、执行后端、搜索、预算与通用偏好设置。
- Chat：Markdown + LaTeX + 语法高亮代码渲染、拖拽文件上传、会话切换、HITL 内联表单。
- 工作流画布：实时执行日志面板、节点状态徽标、自适应缩放、详情侧边栏。
- 统一的空状态、骨架屏加载和 Toast 通知。

### 任务编排与资源调度
- 新增 `backend/homomics_lab/hpc/` 模块，支持可插拔执行后端：`LocalScheduler`、`SlurmScheduler`、`NextflowRunner`。
- Nextflow DSL2 模板注册表将分析意图（如 `rnaseq_analysis`、`single_cell_analysis`）映射到精选工作流模板。
- nf-core 集成（`backend/homomics_lab/nfcore_integration.py`）：支持流程发现、下载、JSON 参数模式加载、profile 检测与执行。
- SLURM 支持：通过 `sbatch`/`squeue`/`sacct` 将长时分析提交到 HPC 集群。
- 每次请求可选择执行后端，同一份智能体计划可在本地、集群或 Nextflow 上运行。

---

## HomomicsLab 的独特之处

### 1. 端到端分析闭环

从一句话如 *"分析我的 PBMC 数据集并找出每个 cluster 的 marker 基因"* 到一份**自包含的 HTML 报告，包含 UMAP、DE 表格和方法章节**——一次对话完成。

HomomicsLab 处理完整生命周期：
- **意图分析** — 从 `domain.yaml` 加载自然语言研究目标并解析为结构化 `UserIntent`。
- **自适应规划** — 从可扩展领域策略模板中选择并生成随实时数据状态自适应的计划。
- **执行** — 带模式验证和资源监控的沙盒化技能运行时，技能来源无关。
- **解读** — 阶段级结果分析与异常检测。
- **报告** — 自动生成含图表和溯源的 HTML/Markdown 报告。
- **可复现性** — 每次分析导出 `ReproducibilityBundle`：精确代码、计划、HITL 决策、环境锁。

### 2. 领域原生智能

- **策略模板**：PlanEngine 内置领域策略（`single_cell_standard`、`spatial_transcriptomics`、`qc_only`），以可适应模板编码*正确操作顺序*。
- **数据状态自适应**：计划根据数据特征变化——检测到批次效应 → 注入整合；质量低 → 收紧 QC。
- **SkillDAG**：自我进化的知识图谱，从执行历史和 `domain.yaml` 种子中学习技能间关系。

### 3. 自我进化的技能生态系统

- **自我进化关系**：SkillDAG 发现 `followed_by`、`conflicts_with`、`alternative_to` 关系，边在重复成功后从 `CANDIDATE` → `CONFIRMED` 升级。
- **语义发现**：双引擎技能搜索——TF-IDF 回退 + 可选 sentence-transformers 稠密嵌入。
- **自动生成**：从自然语言需求生成新技能。
- **统一格式**：内置与外部技能使用完全相同的 `SKILL.md + scripts/` 格式。
- **从 CodeAct 提升**：成功的 CodeAct 运行可通过 UI 或 API 提升为可复用技能。

### 4. 多层稳定性保障

| 层级 | 防御机制 | 防止的问题 |
|---|---|---|
| **L1 — 模式验证** | 每个技能输入/输出对照声明的 JSON Schema 验证 | 类型不匹配、缺少必填字段、静默数据损坏 |
| **L2 — 版本锁定** | 项目级锁定：技能版本、脚本 SHA-256、pip freeze、Python 版本 | "昨天还能跑"的漂移、依赖地狱 |
| **L2 — 回归测试** | 从已知良好执行记录基线；检测输出签名漂移 | 静默改变结果的技能更新 |
| **L2 — 代码安全** | 执行前对 LLM 生成 CodeAct 代码做静态审计 | 危险导入、路径遍历、shell 注入 |

### 5. 完整可复现性

`ReproducibilityEngine` 捕获：
- 智能体生成的精确代码
- 带数据状态自适应的完整执行计划
- 每一次 HITL 决策
- 环境锁定（`pip freeze`、Python 版本）
- 技能版本锁定（精确版本和脚本校验和）

### 6. 可解释，不是黑盒

每个主要阶段后，**InterpretationEngine** 产出：
- 人类可读摘要
- 超出阈值时标记异常
- 按置信度排序的可操作建议

### 7. 数据溯源作为一等公民

```
workspaces/{project_id}/
├── data/               # 原始数据 — 只读保护
├── intermediate/       # 带 SHA-256 校验和的步骤工件
├── outputs/            # 最终交付物
├── logs/               # 执行日志
└── .metadata/          # 工件注册表、血缘图谱、快照、version.lock
```

### 8. 动态智能体角色

HomomicsLab 不硬编码智能体类，而是使用 YAML 可配置角色：

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

### 9. 大数据与技能记忆化

- **DataStore** 自动将 pandas `DataFrame` → Parquet、`AnnData` → H5AD、大对象卸载到文件，返回小型 `ResultReference`。
- **SkillCache** 以 `skill_id + inputs + fingerprint` 的 SHA-256 键值记忆化确定性技能执行。
- **CodeActCache** 基于任务描述 embedding 相似度缓存生成代码。

### 10. 安全与信任模型

- 导入技能默认标记为 `trusted=false`。
- `POST /api/skills/{id}/trust` 切换信任状态。
- 高风险工具（`shell_exec`、`file_write`、`file_edit`）携带 `risk_level=high`。
- `HOMOMICS_INTERACTIVE_MODE=true` 要求高风险工具调用前显式批准。
- `HOMOMICS_FORCE_SANDBOX=true` 使 shell/代码执行走 bubblewrap/容器沙盒。

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
# 后端（从仓库根目录运行，以便找到 uv.lock / pyproject.toml）
pip install -e ".[dev,test]"
cd backend
uvicorn homomics_lab.main:app --reload --port 8080

# 前端（新终端）
cd frontend
npm install
npm run dev
# 打开 http://localhost:5173
```

### 无外部 LLM Key 运行

如需使用本地/嵌入式模型，配置兼容的本地推理端点并设置：

```env
HOMOMICS_LLM_PROVIDER=openai-compatible
HOMOMICS_LLM_BASE_URL=http://localhost:11434/v1
HOMOMICS_LLM_MODEL=qwen2.5:14b
```

> 注意：本地模型最适合意图分析和简单技能选择，复杂 CodeAct 生成仍受益于前沿模型。

---

## 任务编排与资源调度

HomomicsLab 不局限于单进程技能执行。同一份智能体计划可以根据数据规模、运行环境与可复现性要求，分发到多种执行后端。

| 后端 | 适用场景 | 工作原理 |
|---|---|---|
| **Local** | 快速迭代、小数据、笔记本/WSL | Python/R/Bash 技能在 API 进程或本地子进程沙盒中运行 |
| **SLURM** | HPC 集群、长时任务、多核并行 | `SlurmScheduler` 将技能代码转为 `sbatch` 脚本，通过 `squeue`/`sacct` 监控并回流结果 |
| **Nextflow** | 可复现流程、nf-core 工作流、云/HPC | `NextflowRunner` 渲染 DSL2 模板或调用 nf-core 流程，基于参数模式与 profile 执行 |

### Nextflow 与 nf-core 集成

- **模板注册表**（`hpc/template_registry.py`）：将 `rnaseq_analysis`、`single_cell_analysis` 等高层意图映射到精选 Nextflow DSL2 模板。
- **NFCoreManager**（`nfcore_integration.py`）：发现可用 nf-core 流程、本地缓存、加载 JSON 参数模式、检测执行器 profile（`docker`、`singularity`、`conda`、`slurm`）并执行。
- **API 端点**（`api/nfcore.py`）：`GET /api/nfcore/pipelines`、`POST /api/nfcore/run` 及执行状态端点直接向前端暴露 nf-core 能力。
- **参数安全**：nf-core 流程参数在提交前按已发布模式校验，降低“参数稍有偏差流程就中断”的风险。

### 为什么重要

- **一个智能体，多种执行器**：自然语言请求可变为本地沙盒测试、SLURM 批处理作业或容器化 Nextflow 流程，无需重写计划。
- **生产级规模**：长时生物信息学负载（比对、定量、变异检测）可卸载到集群或云执行器，智能体继续监控、解读并生成报告。
- **默认可复现**：Nextflow 与 nf-core 提供容器化、版本锁定的执行；HomomicsLab 在此基础上叠加自身的可复现包。

---

## 项目结构

```
HomomicsLab/
├── backend/
│   ├── homomics_lab/
│   │   ├── agent/              # 智能体编排层
│   │   │   ├── core/           # AgentCore, DynamicAgent, RoleRegistry, roles/*.yaml
│   │   │   ├── plan/           # PlanEngine — 自适应策略生成
│   │   │   ├── replanning.py   # DynamicReplanningEngine
│   │   │   ├── interpretation.py
│   │   │   ├── swarm.py        # AgentSwarm — 并行多智能体执行 + 共识
│   │   │   ├── orchestrator.py # 带重试和 HITL 的任务调度器
│   │   │   ├── evolution.py    # AgentEvolutionEngine
│   │   │   └── turn_runner.py  # 统一对话轮次循环
│   │   ├── domain/             # 领域声明系统 (v0.4.1)
│   │   │   ├── models.py
│   │   │   ├── loader.py       # DomainLoader — 读取 domain.yaml
│   │   │   ├── registry.py     # DomainRegistry
│   │   │   ├── hot_reload.py   # 运行时热加载
│   │   │   ├── marketplace.py  # 领域模板市场
│   │   │   └── domains/        # 内置领域声明
│   │   │       ├── single_cell/domain.yaml
│   │   │       ├── spatial/domain.yaml
│   │   │       └── metagenomics/domain.yaml
│   │   ├── cli/                # 命令行工具
│   │   │   └── commands/       # init, validate, install, generate, list, trace
│   │   ├── execution/          # CodeAct 执行基座层
│   │   │   ├── code_act.py     # CodeAct 执行引擎
│   │   │   ├── code_cache.py   # CodeAct 相似缓存
│   │   │   └── code_safety.py  # 生成代码静态安全审计
│   │   ├── hpc/                # 任务编排与资源调度
│   │   │   ├── scheduler.py    # Local / SLURM / Nextflow 执行器
│   │   │   └── template_registry.py  # 意图 → Nextflow DSL2 模板
│   │   ├── nfcore_integration.py  # nf-core 流程发现与执行
│   │   ├── skills/             # 技能生态系统
│   │   │   ├── skill_dag.py    # 自我进化的类型化知识图谱
│   │   │   ├── loader.py       # 统一的 SKILL.md + scripts/ 加载器
│   │   │   ├── runtime.py      # 带模式验证的沙盒执行
│   │   │   ├── registry.py     # 技能发现与注册
│   │   │   ├── promotion.py    # 将 CodeAct 运行提升为技能
│   │   │   └── models.py       # Pydantic 技能定义
│   │   ├── stability/          # 质量保证
│   │   │   ├── schema_validator.py
│   │   │   ├── version_locker.py
│   │   │   └── regression_tester.py
│   │   ├── tools/              # 原子工具注册表 + 跨进程调用
│   │   │   ├── registry.py
│   │   │   ├── approval.py
│   │   │   └── invoke_tool.py
│   │   ├── workspace/          # 数据溯源与持久化
│   │   ├── reproducibility/    # 审计追踪
│   │   ├── context/            # 工作记忆、语义记忆、压缩
│   │   ├── knowledge/          # CBKB: 五层领域特定知识库
│   │   ├── jobs/               # 后台任务队列 + Worker
│   │   └── api/                # FastAPI REST + WebSocket 端点
│   └── tests/                  # 901 个测试
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── ui/             # 可复用 UI 组件库 + 主题系统
│       │   ├── layout/         # 侧边栏、顶部栏、应用外壳
│       │   ├── settings/       # 设置面板（LLM、执行、搜索、预算）
│       │   ├── chat/           # 聊天面板、HITL 表单、图表渲染、会话
│       │   ├── workspace/      # 工作流画布、执行日志面板、详情侧边栏
│       │   ├── reports/        # 报告列表 + 查看器
│       │   ├── skills/         # 技能搜索 + 管理 + 生成器
│       │   └── domains/        # 领域市场
│       ├── hooks/              # 主题、键盘快捷键、命令面板
│       └── stores/             # Zustand 状态管理
├── Dockerfile
├── docker-compose.yml
└── docs/
    ├── architecture.md
    ├── design.md
    ├── operations.md
    ├── domain-extension-guide.md
    ├── roadmap-v0.5.md
    └── homomics-lab-improvement-plan-v1.0.md
```

---

## API 端点

### 聊天与执行
| 端点 | 描述 |
|---|---|
| `POST /api/chat/send` | 向智能体发送消息 |
| `POST /api/chat/hitl/respond` | 响应 HITL 检查点 |
| `POST /api/chat/debate/respond` | 响应 debate 选择 |
| `WS /api/chat/ws/{session_id}` | 实时聊天 WebSocket |
| `POST /api/chat/sla` | 执行前评估置信度/执行模式 |

### 技能
| 端点 | 描述 |
|---|---|
| `GET /api/skills/` | 列出所有技能 |
| `GET /api/skills/search?q=` | 关键词搜索技能 |
| `GET /api/skills/{id}` | 获取技能详情 |
| `POST /api/skills/import` | 从路径/git/zip 导入技能 |
| `POST /api/skills/{id}/update` | 重新导入/更新技能 |
| `DELETE /api/skills/{id}` | 移除技能 |
| `POST /api/skills/{id}/enable` | 启用技能 |
| `POST /api/skills/{id}/disable` | 禁用技能 |
| `POST /api/skills/{id}/validate` | 验证技能目录结构 |
| `POST /api/skills/{id}/test` | 运行技能内置测试 |
| `POST /api/skills/{id}/trust` | 标记技能信任/不信任 |
| `POST /api/skills/promote` | 将 CodeAct 运行提升为可复用技能 |
| `POST /api/skills/lock` | 创建项目版本锁定 |
| `GET /api/skills/tools/pending` | 列出待审批的高风险工具调用 |
| `POST /api/skills/approve-tool/{call_id}` | 批准高风险工具调用 |
| `POST /api/skills/reject-tool/{call_id}` | 拒绝高风险工具调用 |

### 计划与任务
| 端点 | 描述 |
|---|---|
| `GET /api/plan/{plan_id}` | 获取计划详情 |
| `POST /api/plan/{plan_id}/approve` | 批准计划 |
| `POST /api/plan/{plan_id}/reject` | 拒绝计划 |
| `POST /api/plan/{plan_id}/modify` | 修改并批准/拒绝计划 |
| `GET /api/execution/{job_id}/status` | 获取任务执行状态 |

### 领域与市场
| 端点 | 描述 |
|---|---|
| `GET /api/domains/` | 列出可用领域模板 |
| `POST /api/domains/import` | 从路径/git/zip 导入领域 |
| `POST /api/domains/import-zip` | 上传并导入领域 zip |
| `POST /api/domains/{id}/export` | 导出领域模板为 zip |
| `POST /api/domains/import-templates` | 向领域导入代码模板 |

### 项目、报告与可视化
| 端点 | 描述 |
|---|---|
| `GET /api/projects` | 列出项目 |
| `POST /api/projects` | 创建项目 |
| `GET /api/projects/{id}` | 获取项目详情 |
| `POST /api/projects/{id}/lock-versions` | 锁定环境版本 |
| `POST /api/viz/plot` | 生成图表 |
| `POST /api/reports/create` | 创建分析报告 |
| `GET /api/reports/{id}/html` | 导出自包含 HTML 报告 |

---

## CLI

```bash
# 初始化新领域
homomics init metagenomics --phases "qc,denoising,taxonomy,diversity"

# 验证 domain.yaml
homomics validate domain.yaml

# 安装领域
homomics install ./metagenomics --domains-dir ./backend/homomics_lab/domains

# 从描述生成领域（需要 OPENAI_API_KEY）
homics generate "16S amplicon analysis with DADA2 and QIIME2"

# 列出已安装领域
homomics list --domains-dir ./backend/homomics_lab/domains
```

---

## 测试

```bash
cd backend
pytest tests/ -q
# 901 个测试通过
```

覆盖范围包括：
- **智能体层**：动态角色、自适应规划、解读、编排、任务状态机
- **技能层**：DAG 进化、统一加载器、沙盒执行、语义搜索、CodeAct 缓存
- **稳定性层**：模式验证、版本锁定、回归测试
- **工作空间层**：路径解析、工件注册表、血缘图谱、快照
- **可复现性层**：Bundle 捕获、JSON 往返、环境锁定
- **集成层**：AgentCore + Orchestrator、PlanEngine + AgentCore、Workspace + VersionLocker
- **领域层**：领域声明模型、加载器、注册表、验证、热加载
- **工具层**：跨进程调用、审批流、风险等级

---

## 配置

环境变量（前缀 `HOMOMICS_`）：

| 变量 | 默认值 | 描述 |
|---|---|---|
| `HOMOMICS_PORT` | `8080` | API 服务器端口 |
| `HOMOMICS_DATABASE_URL` | `sqlite+aiosqlite:///./homomics_lab.db` | 数据库 URL |
| `HOMOMICS_EXTERNAL_SKILLS_DIR` | — | 外部技能集合路径 |
| `HOMOMICS_SEMANTIC_SEARCH_MODEL` | — | 设置为 `all-MiniLM-L6-v2` 启用稠密嵌入 |
| `HOMOMICS_SKILL_SANDBOX_BACKEND` | `auto` | `local`、`bubblewrap`、`container` 或 `auto` |
| `HOMOMICS_FORCE_SANDBOX` | `true` | shell/代码执行走沙盒 |
| `HOMOMICS_INTERACTIVE_MODE` | `false` | 高风险工具调用需显式批准 |
| `HOMOMICS_CODEACT_CACHE_ENABLED` | `true` | 启用 CodeAct 代码缓存 |
| `HOMOMICS_SKILL_CACHE_ENABLED` | `true` | 启用技能结果记忆化 |
| `HOMOMICS_WORKER_MODE` | `true` | 在 API 进程内启动本地 worker |
| `HOMOMICS_CURATION_ENABLED` | `false` | 启用夜间 CBKB 策展 |
| `HOMOMICS_EVOLUTION_ENABLED` | `false` | 启用夜间智能体进化 |

---

## 技术栈

- **后端**: Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy, scikit-learn, sentence-transformers, sqlite-vec, pyarrow, weasyprint
- **前端**: React 18, TypeScript, Tailwind CSS, Zustand, TanStack Query, Plotly.js
- **工作流**: Nextflow (DSL2), SLURM (sbatch/sacct)
- **部署**: Docker, Docker Compose, nginx

---

## 路线图

详见 [`docs/roadmap-v0.5.md`](docs/roadmap-v0.5.md) 和 [`docs/homomics-lab-improvement-plan-v1.0.md`](docs/homomics-lab-improvement-plan-v1.0.md)。

下一步重点：
- 扩展单细胞、空间、基因组、宏基因组等领域的内置和社区技能覆盖。
- 随着执行历史积累，强化自进化闭环。
- 改善个人用户开箱体验（本地模型默认、示例数据集、引导式上手）。
- 加固个人设备上的长任务可靠性和资源监控。

---

## 许可

MIT
