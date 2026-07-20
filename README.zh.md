# HomomicsLab

一个**面向计算生物学的领域原生智能体平台**，弥合僵化的生物信息学流程管线与非结构化笔记本集合之间的鸿沟。HomomicsLab 将自然语言研究问题转化为可复现、可审计、可扩展的分析工作流——结合 AI 智能体的自适应能力与生产级数据工程的严谨性。

> **v0.5.0** — 意图驱动的分析自动化，支持单文件领域声明、CLI 脚手架、LLM 辅助领域生成、运行时热加载、动态智能体角色、假设驱动探索、自我进化的 SkillDAG、动态重规划、CBKB 策展、多层稳定性保障、可复现包、大数据结果卸载、技能记忆化、CodeAct 缓存、跨进程沙盒化工具调用以及领域模板市场。

---

## 问题所在

计算生物学处在一个痛苦的交叉点：

| 方案 | 优势 | 致命弱点 |
|---|---|---|
| **turnkey 流程管线** (Galaxy, nf-core) | 可复现、经过验证 | 僵化——参数稍有偏差流程就中断 |
| **笔记本集合** (Scanpy, Seurat) | 灵活、有教育意义 | 碎片化、手动操作、无法规模化复现 |
| **通用 LLM 智能体** (ChatGPT, Claude Code) | 对话式、通用 | 没有生物信息学领域知识；会幻觉化包名、忽略批次效应 |
| **工作流引擎** (Snakemake, Nextflow) | 可扩展、声明式 | 需要专家编排；对数据状态没有语义理解 |

**HomomicsLab 是第四种选择**：一个领域原生智能体平台，既懂生物学也懂工程——从自然语言规划分析策略，以沙盒精度执行，以领域感知的检查解读结果，并捕获每一个决策以实现可复现性。

---

## 当前状态

HomomicsLab 是一套**生产就绪的智能体框架**，内置能力库正在不断扩展。核心架构、执行引擎、稳定性保障和可扩展机制均已实现并经过测试。实际能力随安装的技能和领域数量与质量而增长。

| 能力 | 状态 | 说明 |
|---|---|---|
| 智能体编排（意图→计划→执行） | ✅ 已实现 | `Orchestrator`、`PlanEngine`、`TaskDecomposer`、`TurnRunner` |
| 动态智能体角色 | ✅ 已实现 | YAML 可配置的 `RoleDefinition` + `DynamicAgent` |
| 假设驱动探索 | ✅ 已实现 | `ExplorationEngine` 蓝图 → 批判 → 证据报告 |
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
| CBKB 与自动策展 | 🟡 框架就绪 | 接口已实现；循环需要足够执行历史 |
| SkillDAG 自进化 | 🟡 框架就绪 | 图记录执行；边升级需要重复成功运行 |
| 稠密语义搜索 | 🟡 可选 | 需配置 `HOMOMICS_SEMANTIC_SEARCH_MODEL` |
| 智能体自进化 | 🟡 框架就绪 | 对个人用户默认关闭定时任务 |

> **隐私优先**：HomomicsLab 设计为可自托管、本地可运行。除非你显式配置外部 LLM API 或云存储，否则数据不会离开你的机器。

---

## v0.5.0 新特性

### 意图-centric 执行
- 默认路径现在以**用户意图 + 数据状态**为中心，而不是强制每个请求走固定领域/阶段管线。
- `use_skill_reference` 让 CodeAct 以精选技能为参考资料生成紧凑脚本，而不是运行僵化的 skill 入口。
- Data preflight 在路由前检查上传文件，因此简单请求（如描述性统计）不会继承 8 步管线。

### 跨进程工具调用沙盒
- `backend/homomics_lab/tools/invoke_tool.py` 提供跨进程边界调用原子工具的统一协议。
- 支持 `local`、`bubblewrap`、`container` 后端，使高风险工具调用在隔离沙盒中运行。

### CodeAct 代码缓存
- `backend/homomics_lab/execution/code_cache.py` 基于任务描述 embedding 缓存 CodeAct 生成的代码。
- 相似任务命中缓存，无需再次调用 LLM，降低成本和延迟。

### 前端"保存为 Skill"
- Skill Manager UI 新增**保存为 Skill**按钮，可将成功的 CodeAct 运行提升为可复用的 `SKILL.md + scripts/` 包。

### 现代化前端 UI/UX
- 组件库、亮/暗主题、命令面板、设置面板、支持 Markdown/LaTeX/代码高亮的聊天、拖拽上传、会话切换、工作流画布。

### 任务编排与资源调度
- 可插拔执行后端：`LocalScheduler`、`SlurmScheduler`、`NextflowRunner`。
- Nextflow DSL2 模板注册表将分析意图映射到精选工作流模板。
- nf-core 集成支持流程发现、下载、JSON 参数模式加载、profile 检测与执行。

---

## HomomicsLab 的独特之处

### 1. 端到端分析闭环

从 *"分析我的 PBMC 数据集并找出每个 cluster 的 marker 基因"* 到一份**自包含的 HTML 报告，包含 UMAP、DE 表格和方法章节**——一次对话完成。

生命周期：**意图分析 → 自适应规划 → 执行 → 解读 → 报告 → 可复现包**。

### 2. 领域原生智能

- **策略模板**：`PlanEngine` 使用可扩展的领域策略模板编码正确操作顺序。
- **数据状态自适应**：计划根据数据特征变化——检测到批次效应 → 注入整合；质量低 → 收紧 QC。
- **SkillDAG**：自我进化的知识图谱，从执行历史和 `domain.yaml` 种子中学习技能间关系。

### 3. 自我进化的技能生态系统

- **SkillDAG** 发现 `followed_by`、`conflicts_with`、`alternative_to` 关系。
- **语义发现**：TF-IDF + 可选稠密嵌入。
- **自动生成**：从自然语言需求生成新技能。
- **统一格式**：内置与外部技能使用完全相同的 `SKILL.md + scripts/` 格式。
- **从 CodeAct 提升**：成功的 CodeAct 运行可提升为可复用技能。

### 4. 多层稳定性保障

| 层级 | 防御机制 | 防止的问题 |
|---|---|---|
| **L1 — 模式验证** | 每个技能输入/输出对照声明的 JSON Schema 验证 | 类型不匹配、缺少字段、静默损坏 |
| **L2 — 版本锁定** | 项目级锁定：技能版本、脚本 SHA-256、pip freeze、Python 版本 | "昨天还能跑"的漂移 |
| **L2 — 回归测试** | 从已知良好执行记录基线；检测输出漂移 | 静默改变结果的技能更新 |
| **L2 — 代码安全** | 执行前对 LLM 生成 CodeAct 代码做静态审计 | 危险导入、路径遍历、shell 注入 |

### 5. 完整可复现性

`ReproducibilityEngine` 捕获精确代码、计划、HITL 决策、环境锁和技能版本锁。

### 6. 数据溯源作为一等公民

```
workspaces/{project_id}/
├── data/               # 原始数据 — 只读保护
├── intermediate/       # 带 SHA-256 校验和的步骤工件
├── outputs/            # 最终交付物
├── logs/               # 执行日志
└── .metadata/          # 工件注册表、血缘图谱、快照、version.lock
```

### 7. 动态智能体角色

YAML 可配置角色，而非硬编码智能体类：

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

### 8. 大数据与技能记忆化

- **DataStore** 自动将 pandas `DataFrame` → Parquet、`AnnData` → H5AD、大对象卸载到文件。
- **SkillCache** 以 `skill_id + inputs + fingerprint` 的 SHA-256 键值记忆化确定性技能执行。
- **CodeActCache** 基于任务描述 embedding 相似度缓存生成代码。

### 9. 安全与信任模型

- 导入技能默认标记为 `trusted=false`。
- `POST /api/skills/{id}/trust` 切换信任状态。
- 高风险工具携带 `risk_level=high`。
- `HOMOMICS_INTERACTIVE_MODE=true` 要求高风险工具调用前显式批准。
- `HOMOMICS_FORCE_SANDBOX=true` 使 shell/代码执行走 bubblewrap/容器沙盒。

---

## 快速开始

### Docker（推荐）

```bash
docker compose up --build
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

如需使用本地/嵌入式模型，配置兼容的本地推理端点：

```env
HOMOMICS_LLM_PROVIDER=openai-compatible
HOMOMICS_LLM_BASE_URL=http://localhost:11434/v1
HOMOMICS_LLM_MODEL=qwen2.5:14b
```

> 本地模型最适合意图分析和简单技能选择，复杂 CodeAct 生成仍受益于前沿模型。

---

## 任务编排与资源调度

| 后端 | 适用场景 | 工作原理 |
|---|---|---|
| **Local** | 快速迭代、小数据、笔记本/WSL | Python/R/Bash 技能在 API 进程或本地子进程沙盒中运行 |
| **SLURM** | HPC 集群、长时任务 | `SlurmScheduler` 将技能代码转为 `sbatch` 脚本，通过 `squeue`/`sacct` 监控并回流结果 |
| **Nextflow** | 可复现流程、nf-core | `NextflowRunner` 渲染 DSL2 模板或调用 nf-core 流程，基于参数模式与 profile 执行 |

### Nextflow 与 nf-core 集成

- **模板注册表**将 `rnaseq_analysis`、`single_cell_analysis` 等高层意图映射到精选 Nextflow DSL2 模板。
- **NFCoreManager** 发现可用 nf-core 流程、本地缓存、加载 JSON 参数模式、检测执行器 profile 并执行。
- **参数安全**：nf-core 流程参数在提交前按已发布模式校验。

---

## 项目结构

```
HomomicsLab/
├── backend/
│   ├── homomics_lab/            # 主 Python 包
│   │   ├── agent/               # 编排、规划、意图、探索
│   │   ├── api/                 # FastAPI 路由
│   │   ├── cli/                 # `homomics` 命令行工具
│   │   ├── domain/              # 领域加载器、注册表、市场、domains/
│   │   ├── execution/           # CodeAct 引擎、缓存、安全审计
│   │   ├── hpc/                 # 本地 / SLURM / Nextflow 调度器
│   │   ├── jobs/                # 后台任务队列与运行器
│   │   ├── knowledge/           # CBKB 知识库
│   │   ├── skills/              # 技能加载器、运行时、注册表、DAG、商店
│   │   ├── stability/           # 模式验证、版本锁定、回归测试
│   │   ├── tools/               # 工具注册表、审批、跨进程调用
│   │   ├── workspace/           # 工作空间、工件、血缘管理
│   │   └── main.py              # FastAPI 应用工厂
│   └── tests/                   # pytest 套件
├── frontend/                    # React 18 + TypeScript + Vite
├── deploy/helm/homomicslab/     # Helm chart
├── skills/                      # 运行时技能目录
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

内置领域位于 `backend/homomics_lab/domains/`：
- `single-cell-transcriptomics/`
- `spatial-transcriptomics/`

---

## API 端点

### 聊天与执行
| 端点 | 描述 |
|---|---|
| `POST /api/chat/send` | 向智能体发送消息 |
| `POST /api/chat/hitl/respond` | 响应 HITL 检查点 |
| `WS /api/chat/ws/{session_id}` | 实时聊天 WebSocket |
| `POST /api/chat/sla` | 执行前评估置信度/执行模式 |

### 技能
| 端点 | 描述 |
|---|---|
| `GET /api/skills/` | 列出所有技能 |
| `GET /api/skills/search?q=` | 关键词搜索技能 |
| `POST /api/skills/import` | 从路径/git/zip 导入技能 |
| `POST /api/skills/{id}/trust` | 标记技能信任/不信任 |
| `POST /api/skills/promote` | 将 CodeAct 运行提升为可复用技能 |

### 计划与任务
| 端点 | 描述 |
|---|---|
| `GET /api/plan/{plan_id}` | 获取计划详情 |
| `POST /api/plan/{plan_id}/approve` | 批准计划 |
| `GET /api/execution/{job_id}/status` | 获取任务执行状态 |

### 领域
| 端点 | 描述 |
|---|---|
| `GET /api/domains/` | 列出可用领域模板 |
| `POST /api/domains/import` | 从路径/git/zip 导入领域 |
| `POST /api/domains/{id}/export` | 导出领域模板为 zip |

---

## CLI

```bash
# 初始化新领域
homomics init metagenomics --phases "qc,denoising,taxonomy,diversity"

# 验证 domain.yaml
homomics validate domain.yaml

# 安装领域
homomics install ./metagenomics --domains-dir ./backend/homomics_lab/domains

# 从描述生成领域
homomics generate "16S amplicon analysis with DADA2 and QIIME2"

# 列出已安装领域
homomics list --domains-dir ./backend/homomics_lab/domains
```

---

## 测试

```bash
cd backend
pytest tests/ -q
```

覆盖范围包括智能体层、技能层、稳定性层、工作空间层、可复现性层、领域层和工具层。

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

- **后端**: Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy, sentence-transformers, sqlite-vec
- **前端**: React 18, TypeScript, Tailwind CSS, Zustand, TanStack Query, Plotly.js
- **工作流**: Nextflow (DSL2), SLURM (sbatch/sacct)
- **部署**: Docker, Docker Compose, Helm, nginx

---

## 路线图

下一步重点：
- 扩展单细胞、空间、基因组、宏基因组等领域的内置和社区技能覆盖。
- 随着执行历史积累，强化自进化闭环。
- 改善个人用户开箱体验（本地模型默认、示例数据集、引导式上手）。
- 加固个人设备上的长任务可靠性和资源监控。

---

## 许可

本项目采用 **GNU Affero General Public License v3.0 (AGPL-3.0)** 许可。
详见 [LICENSE](./LICENSE)。
