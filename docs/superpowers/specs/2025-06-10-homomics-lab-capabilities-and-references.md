# HomomicsLab 能力清单与参考来源分析

> 文档日期：2025-06-10  
> 版本：v0.2.0（累积）  
> 测试覆盖：291 tests passing  
> 代码规模：79 后端 Python 文件 + 28 前端 TypeScript/TSX 文件

---

## 一、项目定位

HomomicsLab 是一个**通用生物信息学 Agent 平台**，支持单细胞/空间多组学、基因组学、蛋白质组学分析流程。核心设计理念是**"从被动执行工具到主动智能分析伙伴"**的跃迁——不仅执行分析步骤，更理解生物学意义、推荐下一步、管理实验上下文。

---

## 二、已实现功能清单（按模块）

### 2.1 Agent 编排层

| 功能 | 实现文件 | 说明 |
|------|---------|------|
| **任务分解** | `agent/task_decomposer.py` | 将用户意图分解为可执行任务树（TaskTree），支持单细胞标准流程的硬编码模板 |
| **意图分析** | `agent/intent_analyzer.py` | 规则+关键词的意图分类器，识别直接回答/单步/复杂工作流 |
| **统一执行循环** | `agent/turn_runner.py` | **TurnRunner** 统一处理每轮对话，6 种执行模式：DIRECT_RESPONSE / SINGLE_STEP / WORKFLOW / AWAITING_HITL / RESUME_HITL / ERROR |
| **多 Agent 调度** | `agent/orchestrator.py` | 拓扑排序执行任务树，支持重试、退避、HITL 暂停 |
| **Agent 注册** | `agent/agent_registry.py` + `factory.py` | 动态注册 Bioinfo/Viz/Experiment/Planner/QA/Report Agent |
| **动态角色** | `agent/base_agent.py` | 基础 Agent 抽象类，当前为硬编码类型，v0.3 将升级为动态角色注入 |
| **计划生成** | `agent/plan_engine.py` (设计中) | 基于 SkillDAG 的动态计划生成（开发中） |
| **结果解读** | `agent/interpretation.py` (设计中) | LLM-based 分析结果主动解读与推荐（开发中） |

### 2.2 状态与任务管理

| 功能 | 实现文件 | 说明 |
|------|---------|------|
| **任务树** | `tasks/task_tree.py` + `models.py` | DAG 任务依赖管理，支持拓扑排序执行 |
| **状态机** | `tasks/state_machine.py` | TaskStatus 状态流转（pending → running → completed/failed/awaiting_human） |
| **工作记忆** | `context/working_memory.py` | 会话级短期记忆，固定长度消息队列（默认 20 条） |
| **上下文压缩** | `context/compressor.py` + `relevance_filter.py` + `summarizer.py` | 智能相关性过滤 + 摘要 + 去重 |

### 2.3 Skills 生态系统

| 功能 | 实现文件 | 说明 |
|------|---------|------|
| **统一技能目录** | `skills/builtin/` + `external_loader.py` | 内置/外部技能统一格式：SKILL.md + scripts/python/run.py。废弃了 inline Python 字符串方式 |
| **外部技能加载** | `skills/external_loader.py` | 解析 SKILL.md YAML frontmatter，自动推断 scripts/ 目录，支持 Python/R/mixed |
| **技能注册表** | `skills/registry.py` | SkillRegistry 支持关键词搜索 + 语义搜索 |
| **技能执行器** | `skills/runtime.py` | SkillRuntimeExecutor 统一执行路径（不再区分 builtin/external），metadata["scripts_dir"] 决定代码来源 |
| **沙箱执行** | `skills/sandbox.py` | LocalSandbox：Python/R 子进程执行，资源限制（内存/CPU/文件大小），危险模块拦截 |
| **HPC 调度** | `hpc/scheduler.py` + `slurm_scheduler.py` + `nextflow_runner.py` | 三种后端：Local / SLURM / Nextflow，自动检测 `get_scheduler("auto")` |
| **技能性能追踪** | `skills/tracker.py` | SQLite 持久化执行记录，含 duration/success/output_size/executor_type/CPU%/GPU%/memory/cost |
| **资源采样** | `skills/tracker.py` (ResourceSampler) | psutil + pynvml 采样，上下文管理器方式使用 |
| **成本估算** | `skills/tracker.py` (CostConfig) | 基于 CPU/GPU/内存使用的 USD 成本估算 |
| **技能自进化** | `skills/evolution.py` | A/B 测试框架，比较技能变体，统计显著性检验 |
| **技能自动生成** | `skills/generator.py` | SkillTemplateBuilder + SkillGenerator，从自然语言需求生成 SKILL.md + 脚本 |
| **TF-IDF 搜索** | `skills/semantic_search.py` | 基于 sklearn 的关键词搜索 |
| **密集向量搜索** | `skills/semantic_search_v2.py` | 基于 sentence-transformers (all-MiniLM-L6-v2) 的语义搜索 |

### 2.4 上下文与记忆

| 功能 | 实现文件 | 说明 |
|------|---------|------|
| **语义记忆** | `context/semantic_memory.py` | sqlite-vec 向量数据库，384-dim 嵌入，支持 conversation/task/experiment/note 类型 |
| **混合检索** | `context/semantic_memory.py` | 语义相似度 + 时间范围过滤 + 类型过滤 |
| **实验记录** | `context/experiment_logger.py` | 时间戳笔记（SQLite），支持标签、元数据、按时间范围/标签检索 |
| **MEMORY.md 生成** | `context/experiment_logger.py` | 自动生成 Markdown 格式实验日志（按日期分组） |
| **用户画像** | `context/user_profile.py` (设计中) | 个人知识库，持久化偏好与数据集特征（参考 CowAgent） |

### 2.5 可视化与报告

| 功能 | 实现文件 | 说明 |
|------|---------|------|
| **静态图表** | `viz/generator.py` | matplotlib 生成 6 种图表：UMAP/heatmap/violin/bar/scatter/histogram |
| **交互式图表** | `viz/plotly_adapter.py` + `frontend/src/components/shared/PlotChart.tsx` | Plotly.js 交互式渲染，后端返回 JSON 数据，前端 react-plotly.js 渲染 |
| **报告生成** | `reports/generator.py` + `templates.py` | HTML（CSS 样式）/ Markdown 导出，含执行时间线、图表、参数表格 |
| **PDF 导出** | `reports/templates.py` | WeasyPrint HTML→PDF 转换 |
| **报告 API** | `api/reports.py` | 创建/添加章节/添加步骤/添加图表/HTML/PDF/Markdown 导出 |

### 2.6 MCP 与外部工具

| 功能 | 实现文件 | 说明 |
|------|---------|------|
| **生物数据库查询** | `mcp/tools.py` | BioDatabaseTools：PubMed 搜索/获取、UniProt 搜索、GEO 数据集搜索 |
| **MCP 客户端** | `mcp/client.py` | BioMCPClient：支持 embedded（直接调用）和 stdio（MCP 协议）两种模式 |
| **MCP 服务器** | `mcp/server.py` | FastMCP 服务器，暴露 pubmed_search/uniprot_search/geo_search 工具 |

### 2.7 项目管理

| 功能 | 实现文件 | 说明 |
|------|---------|------|
| **项目 CRUD** | `api/projects.py` | 创建/列表/获取项目 |
| **项目导出** | `projects/__init__.py` (ProjectExporter) | 打包为 .homomics ZIP：project.json + MEMORY.md + notes.json + config.json + README.txt |
| **项目导入** | `projects/__init__.py` (ProjectImporter) | 从 .homomics 恢复项目，重建 SQLite 笔记数据库 |
| **工作目录** | `workspace/manager.py` (设计中) | 项目级持久化工作目录（当前使用 tmp_path，即将升级） |

### 2.8 监控与运维

| 功能 | 实现文件 | 说明 |
|------|---------|------|
| **健康检查** | `doctor/__init__.py` + `api/health.py` | 6 项诊断：Python 版本、核心依赖、可选依赖、技能系统、磁盘空间、HPC 调度器 |
| **API 端点** | `api/` 目录 | Chat / Projects / Skills / Viz / Reports / SkillGenerator / Health / Files |

### 2.9 前端

| 功能 | 实现文件 | 说明 |
|------|---------|------|
| **聊天界面** | `frontend/src/components/chat/` | MessageBubble、TodoList、HITLRequest、文本/图表/错误消息类型 |
| **工作区** | `frontend/src/components/workspace/Workspace.tsx` | 4 个标签：Workflow / Reports / Skills / Generate |
| **交互式图表** | `frontend/src/components/shared/PlotChart.tsx` | react-plotly.js 懒加载，Suspense fallback，错误处理 |
| **技能浏览器** | `frontend/src/components/skills/` | 搜索、分类浏览、技能生成器 UI |
| **报告查看器** | `frontend/src/components/reports/` | 报告列表 + HTML/MD 查看 |
| **状态管理** | `frontend/src/stores/` | Zustand store |

### 2.10 部署

| 功能 | 说明 |
|------|------|
| **Docker** | docker-compose + Dockerfile（后端）+ Dockerfile（前端）+ nginx.conf |
| **CI/CD** | GitHub Actions 工作流 |
| **CORS** | FastAPI CORS 中间件，支持 localhost:5173/3000 |

---

## 三、参考 Agent / Tools 分析

### 3.1 原始参考（项目启动阶段）

| 来源 | 类型 | 采纳了什么 | 弃用了什么 | 原因 |
|------|------|-----------|-----------|------|
| **Biomni** (snap-stanford) | 生物信息学 Agent | 单细胞分析流程设计、实验辅助概念、HITL 交互模式 | 具体的实现细节未公开，无法直接参考 | 概念验证级别的参考，验证生物信息学 Agent 的可行性 |
| **Hermes** (nousresearch) | 通用 Agent | Agent 编排思想、多步骤任务分解 | 过于通用，缺乏生物信息学针对性 | 仅作通用架构参考 |
| **DeerFlow2** (bytedance) | 研究 Agent | 动态工作流、多 Agent 协作 | 字节跳动的内部设计未完全开源，无法深度参考 | 工作流动态编排的理念被吸收到 PlanEngine 设计中 |
| **OmicVerse** (omicverse) | 生物信息学库 | 分析流程的标准步骤（QC→降维→聚类→注释） | 作为 Python 库而非 Agent 框架，无 Agent 能力 | 仅用于验证分析步骤的合理性 |
| **AutoScientists** (mims-harvard) | 科研 Agent | 长程任务能力、计划分解、正确性验证 | 未开源具体实现 | 长程任务分解的理念被吸收到 TaskDecomposer |
| **Superpowers** (Claude 插件) | 开发方法论 | subagent-driven-development、writing-plans、TDD、git-worktrees | — | 开发流程方法论，直接指导了项目的开发方式 |

### 3.2 外部技能来源

| 来源 | 说明 |
|------|------|
| **NanoResearch-Skills** | 74 个外部技能目录，SKILL.md + scripts/ 格式。是 HomomicsLab 技能生态的核心数据来源。通过 ExternalSkillLoader 加载到 SkillRegistry。 |

### 3.3 Phase 3 参考（架构升级阶段）

| 来源 | 类型 | 采纳了什么 | 弃用了什么 | 原因 |
|------|------|-----------|-----------|------|
| **OpenSquilla** (opensquilla) | 开源 Agent 平台 | 技能目录结构、MCP 集成理念 | 具体的 MCP 实现方式未深度参考 | 验证了目录化技能 + MCP 的可行性 |
| **Ruflo** (ruvnet) | 多 Agent 编排 | **Dynamic Workflows**（可复用多步骤模板） | Swarm 协调（100+ Agent 拓扑、Raft 共识、Gossip 协议） | Swarm 对于当前单机/小团队部署过度工程化；Dynamic Workflows 直接启发了 PlanEngine 设计 |
| **SkillDAG** (Ericbai06) | 技能选择 | **DAG 关系建模**（依赖/冲突/专业化）取代相似度匹配 | 完整的自演化图边注册机制（过于复杂） | DAG 拓扑推断分析路径的核心思想被采纳，边信息简化为 SKILL.md optional 字段 |
| **Odysseus** (pewdiepie-archdaemon) | 本地 AI 工作空间 | 持久化记忆设计（ChromaDB）、MCP 集成模式、agent_loop 结构 | 完整的本地优先替代方案（Email/Calendar/PWA 等无关功能） | agent_loop 的模块化设计被参考；持久化记忆已部分实现为 SemanticMemory |
| **CowAgent** (zhayujie) | 个人 Agent | **Personal Knowledge Base**（用户偏好学习、长期记忆） | — | 直接启发了 UserProfile 模块设计 |
| **Claude Code / OpenClaw** | AI 编程助手 | **L1/L2/L3 渐进披露机制**（Session 启动→模型判断相关→执行时按需） | — | 直接启发了 Skill Disclosure System 的三层架构 |

### 3.4 技术栈参考

| 技术/库 | 来源/参考 | 用途 |
|---------|----------|------|
| **sentence-transformers** (all-MiniLM-L6-v2) | Hugging Face | 语义搜索嵌入 |
| **sqlite-vec** | SQLite 扩展 | 向量数据库存储 |
| **Plotly.js** | Plotly | 交互式科学图表 |
| **WeasyPrint** | Kozea | HTML→PDF 转换 |
| **MCP (Model Context Protocol)** | Anthropic | 外部工具标准化协议 |
| **FastAPI** | — | Web API 框架 |
| **React + Vite + Tailwind** | — | 前端技术栈 |
| **Zustand** | — | 前端状态管理 |

---

## 四、架构演进

### v0.1.0 MVP（48 tasks）
- Agent 编排、TODO 追踪、HITL、基础技能执行
- 78 tests

### v0.1.5 Phase 2
- 74 外部技能集成、HPC 调度（SLURM/Nextflow）、技能自进化、语义搜索

### v0.2.0 Phase 3（当前）
- 技能统一目录结构、TurnRunner、sqlite-vec 语义记忆、Doctor 健康检查、实验笔记、MCP 集成、成本追踪、交互式图表、PDF 导出、项目分享
- **291 tests**

### v0.3.0 规划中
- LLM Router（多后端）
- PlanEngine（动态计划生成）
- InterpretationEngine（主动解读）
- SkillDAG（结构化技能选择）
- Skill 渐进披露 L2/L3
- WorkspaceManager（持久化工作目录）
- UserProfile（个人知识库）
- 动态 Agent 角色（废弃硬编码 Agent 类）

---

## 五、设计哲学总结

### 5.1 "取所长，不拼凑"的具体实践

1. **Ruflo 的 Swarm → 简化**：不实现 100+ Agent 拓扑和共识算法，而是将"多专家协作"简化为"动态角色注入"（同一 LLM 切换 system prompt）。

2. **SkillDAG 的自演化 → 简化**：不实现完整的边注册和演化机制，而是将 DAG 边作为 SKILL.md 的 optional 字段，降低用户自建技能的门槛。

3. **Odysseus 的完整平台 → 裁剪**：只采纳 agent_loop 和持久化记忆设计，不引入 Email/Calendar/PWA 等无关模块。

4. **Biomni/AutoScientists 的概念 → 落地**：将"长程任务"从概念验证落地为具体的 TaskTree + TurnRunner + StateMachine 实现。

### 5.2 关键取舍

| 取舍点 | 选择 | 原因 |
|--------|------|------|
| TF-IDF vs Chroma/FAISS | 保留 TF-IDF + sentence-transformers + sqlite-vec | 当前 77 个技能的规模不需要重型向量数据库；sqlite-vec 足够且零运维 |
| 多用户系统 vs 项目导出分享 | 先实现项目导出分享，延迟多用户账号系统 | 科研协作的核心是"可复现的分析包"而非实时协同编辑 |
| 静态 PNG vs 交互式 Plotly | 两者并存：API 保留 PNG，新增 JSON 数据端点 | 后端服务可能无浏览器环境，PNG 用于报告；交互式用于前端 |
| 硬编码 Agent 类 vs 动态角色 | v0.2 保留硬编码，v0.3 升级为动态角色 | 渐进演进，避免一次性重构风险 |

---

## 六、统计

| 指标 | 数值 |
|------|------|
| 后端 Python 文件 | 79 |
| 前端 TS/TSX 文件 | 28 |
| 测试总数 | 291 |
| 技能总数 | 3 builtin + 74 external = 77 |
| 图表类型 | 6（UMAP/heatmap/violin/bar/scatter/histogram）|
| 报告格式 | 3（HTML/Markdown/PDF）|
| MCP 工具 | 3（pubmed_search/uniprot_search/geo_search）|
| HPC 后端 | 3（local/SLURM/Nextflow）|
| 语义搜索引擎 | 2（TF-IDF + sentence-transformers）|
| 健康检查项 | 6 |
| Git commits | 20+ |
