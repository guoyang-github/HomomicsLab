# God-class 拆分建议

## 现状

随着功能增加，以下模块已经成长为承载过多职责的 "god class"。它们不易测试、变更影响面大，并逐渐成为并发和协作扩展的瓶颈。

## 建议拆分方向

### 1. `agent/turn_runner.py` (~2600 行)

当前职责：
- 单轮对话状态机
- 工具调用循环
- LLM 调用与后处理
- 记忆/上下文注入
- HITL 暂停/恢复
- 代码执行与产物处理

拆分方案：
- `TurnPlanner`：决定本轮使用哪些工具/技能。
- `ToolExecutionLoop`：负责 tool call -> 执行 -> 结果回灌。
- `TurnContextAssembler`：拼接 system prompt、记忆、历史消息。
- `TurnStateMachine`：管理 pending/completed/awaiting_human 等状态迁移。

### 2. `agent/orchestrator.py` (~1200 行)

当前职责：
- 任务树执行调度
- 子代理创建与委派
- 资源预算控制
- 错误恢复与重试策略

拆分方案：
- `TaskScheduler`：只负责把 ready tasks 按依赖顺序调度。
- `AgentPool`/`AgentResolver`：根据 phase/skill 选择并创建子代理。
- `ExecutionBudgetGuard`：累计耗时/费用并触发暂停。
- `RecoveryDirector`：统一处理失败、重试、replan、HITL 升级。

### 3. `skills/runtime.py` (~850 行)

当前职责：
- 技能发现与激活
- 依赖安装
- 沙箱选择（subprocess/docker/container）
- 执行与结果解析
- 性能追踪与审计

拆分方案：
- `SkillResolver`：把 skill_id 解析为可执行单元。
- `DependencyInstaller`：pip/conda/R 包安装策略。
- `SandboxStrategy` 策略族：`SubprocessSandbox`、`DockerSandbox`、`ContainerSandbox`。
- `SkillExecutionAuditor`：记录执行日志、成本、缓存命中。

### 4. `context/memory_backend.py` (~830 行)

当前职责：
- 向量检索
- 图检索
- 全文检索
- 记忆评分与合并
- rerank

拆分方案：
- `VectorMemoryBackend`
- `GraphMemoryBackend`
- `FullTextMemoryBackend`
- `MemoryComposer`：组合多种检索结果并 rerank。

### 5. `skills/capability_index.py` (~540 行)

当前职责：
- 技能/工具/SOP 索引
- 向量嵌入
- 图关系维护
- 反馈闭环

拆分方案：
- `SkillIndexer` / `ToolIndexer` / `SOPIndexer`
- `EmbeddingPipeline`
- `CapabilityGraphManager`
- `FeedbackIncorporator`

### 6. `agent/plan/engine.py` (~650 行)

当前职责：
- 策略选择
- 骨架生成
- 状态检查
- 技能检索与填充
- gap 检测与风险评估
- reproducibility context 组装

拆分方案：
- `StrategySelector`
- `SkeletonBuilder`
- `SkillAssignmentEngine`
- `GapDetector`
- `ReproducibilityContextBuilder`

## 实施原则

1. **先写接口再拆实现**：为每个新组件定义清晰的输入/输出契约，避免旧逻辑在拆分中被意外改动。
2. **保持外部 API 不变**：`TurnRunner.run_turn(...)`、`Orchestrator.execute(...)` 等入口方法签名暂时不变，内部委托给新组件。
3. **逐步迁移测试**：每拆出一个组件，就把对应单元测试从旧类搬到新组件，避免一次性回归。
4. **依赖注入**：用构造函数注入替换 `get_default_registry()` 等全局访问点，方便测试与多租户场景。

## 优先级

| 优先级 | 类 | 理由 |
|--------|-----|------|
| P1 | `TurnRunner` | 最大、变更最频繁，影响所有对话路径 |
| P1 | `Orchestrator` | 执行核心，拆分后便于并行执行与资源隔离 |
| P2 | `SkillRuntimeExecutor` | 安全边界清晰，拆分后便于新增沙箱后端 |
| P2 | `MemoryBackend` | 多种后端耦合，拆分后便于按需部署 |
| P3 | `CapabilityIndex` | 索引逻辑稳定，拆分收益高但风险低 |
| P3 | `PlanEngine` | 规划逻辑已较模块化，拆分成本低 |
