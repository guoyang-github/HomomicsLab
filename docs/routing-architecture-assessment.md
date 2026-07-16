# 意图识别与路由分发架构评估

> 本文档严肃梳理 HomomicsLab 的意图识别与不同处理路径的路由逻辑，判定其是否为最佳实践，重点核查 **domain / phase / skill / CodeAct** 四者的关系。
>
> 结论基于代码逐行核查，所有引用附 `文件:行号`。核查覆盖：`agent/intent/analyzer.py`、`agent/turn_intent_router.py`、`agent/turn_runner.py`、`agent/task_decomposer.py`、`agent/plan/engine.py`、`skills/runtime.py`、`agent/orchestrator.py`。

---

## 0. 一句话结论

意图识别（L1）与 domain→phase→skill（L4）的设计是**清醒的最佳实践**——级联守门 + 领域策略做骨架、SkillDAG 只做选择的分离很到位。但 **"pipeline vs CodeAct"这一层是断的**：`mode_selector` 产出 `execution_mode`，执行分发（L5）却不读它、只按 skill 自身 runtime type 分叉，CodeAct 实为失败兜底。即"选择走哪条路"与"实际怎么走"是两套独立机制。最该修的是 **R1：接通或正式降格 `mode_selector`**，否则自进化选模（`mode_selection_lore.db`）在生产路径上空转。

---

## 一、真实链路：5 层路由（非 1 层）

路由不是一处决策，而是 5 层串联：

| 层 | 位置 | 决策内容 | 输入 → 输出 |
|---|---|---|---|
| **L1 意图识别** | `agent/intent/analyzer.py:291 CascadeIntentAnalyzer.analyze` | 识别 analysis_type + interaction_mode + scope + complexity | message → UserIntent（keyword→LLM→embedding→融合→澄清 级联） |
| **L2 会话路由** | `agent/turn_intent_router.py:53 IntentRouter.route` | 按 interaction_mode 分发 | intent → clarify/answer/viz/mcp/执行；执行再按 scope 分 single_step/workflow |
| **L3 规划器选择** | `agent/task_decomposer.py:414 _make_routing_decision` | 选哪个 planner | intent → DOMAIN_TEMPLATE / OPEN_AGENT / STANDALONE / CROSS_DOMAIN |
| **L4 计划生成** | `agent/plan/engine.py:119 PlanEngine.plan` | domain 策略 → phases → 每 phase 选 skill | intent+DataState → PlanResult(phases, selected_skill, execution_mode) |
| **L5 执行分发** | `skills/runtime.py:_dispatch_execute` + `orchestrator._try_codeact_fallback` | 每个 skill 怎么跑 | skill 自身 runtime type → mcp/code_act/declarative/script |

调用链：`TurnRunner._run_turn_once`（`turn_runner.py:680`）→ analyzer.analyze → `IntentRouter.route`（`:1784 _route_by_intent` 转发）→ `task_decomposer.decompose_with_plan` → `_make_routing_decision` → 选定 planner → `PlanEngine.plan` → `runtime._dispatch_execute` / orchestrator。

---

## 二、domain / phase / skill / CodeAct 的真实关系（核查后）

```
domain.yaml
  ├─ strategies      ── PlanEngine 用作 plan 骨架（首选）
  ├─ phases[]        ── 每个 phase 声明 candidate_skills + default_skill
  └─ prompts/sops    ── 进 prompt 上下文

PlanEngine.plan (L4) — agent/plan/engine.py:119:
  strategy → phases[] → 每个 phase 经 _select_skill_for_phase (:507) 选 1 个 skill
    优先级: domain candidate_skills > retrieval+rerank > SkillDAG > registry
  → mode_selector 给 plan 设 execution_mode (pipeline/codeact/auto) — :242-243

执行 (L5) — 关键：runtime._dispatch_execute 按【skill 自身 runtime type】分叉，NOT 按 plan.execution_mode
  ├─ mcp skill                         → ToolRegistry
  ├─ metadata["code_act"]=True         → _execute_code_act           (runtime.py:643)
  ├─ declarative/agent/cli/workflow/container → AgentSkillExecutor   (LLM tool-calling，CodeAct 风格)
  └─ script skill                       → _execute_from_dir           (沙箱跑脚本)
  orchestrator 另有 CodeAct: skill 执行失败时 _try_codeact_fallback 兜底 (:1107)
```

### "CodeAct" 在系统里有 3 个不同角色
1. `metadata["code_act"]=True` 的 skill 类型（`runtime.py:643`）
2. declarative/agent skill 经 `AgentSkillExecutor`（LLM tool-calling 循环，CodeAct 风格）
3. orchestrator `_try_codeact_fallback`（skill 失败的恢复路径，`orchestrator.py:1107`）

### mode_selector 产出的 execution_mode 实际去哪了
全仓 grep `execution_mode` 消费点（排除定义/赋值/序列化）：
- `agent/sla.py:37,71,141` —— SLA/风险评分元数据
- `agent/plan/mode_selection_lore.py` —— lore DB（docstring）
- `agent/plan/models.py:344,371` —— PlanResult 序列化
- `evaluation/mode_benchmark.py:412` —— benchmark 读它评估 selector 准确度

**orchestrator、runtime 均不读 `execution_mode`** 来决定怎么跑。即 mode_selector 选了 pipeline/codeact，执行路径不消费。

---

## 三、最佳实践逐层评估

### ✅ L1 意图级联 — 基本是最佳实践
`analyzer.analyze`（`:291`）5 层级联：keyword 守门 → LLM 优先 → embedding 补充 → 融合 → 真歧义才澄清。
- keyword 快路仅放行 `interaction_mode="answer"`（`:308`），不让工具意图绕过 LLM——严谨
- 工具意图一律 `direct_response`（`:847`）、meta-source 问句回退 qa（`:338`）——有专门防误路由守门

**瑕疵**：
- `_determine_complexity`（`:847`）里 `sequential_markers` 在两处重复硬编码（`:881` 与 `:905`）
- `len(text.split())>15`（`:898`）对中文失真（中文 split 的 token 数 ≠ 复杂度）
- **新旧两套意图表示并存**：新 `interaction_mode`/`scope` vs 旧 `complexity`/`analysis_type`，靠 `_legacy_to_intent_type`（`:1158`）桥接——双 schema 是维护负担

### ✅ L4 域策略做骨架（非 SkillDAG 遍历）— 最强、最正确
`engine.py` 文件头明确：plan 骨架来自 domain 策略模板，SkillDAG 只做 skill 选择。这是"生物结构来自领域知识、图只在大规模 skill 库时增值"的正确判断，可审计可解释。`_select_skill_for_phase`（`:507`）优先级清晰：domain 候选 > retrieval+rerank > SkillDAG > registry。`_apply_learned_defaults`（`:562`）注入 CBKB 参数（≥3 样本）。

### ✅ L2 会话路由 — 合理
`IntentRouter.route`（`:53`）按 `interaction_mode` 干净分发：clarify / answer / visualization_edit / mcp / 执行；执行再按 `scope` 分 single_step / workflow。`_run_turn_once`（`:680`）依次做 memory enrich → capability_index search → context_engine build → analyzer.analyze → route。链条清晰，L2→L3 是串联非冗余。

### ⚠️ L3 规划器选择 — 双轨技术债
`_make_routing_decision`（`:414`）有 `if settings.capability_first_routing_enabled:` 分叉：
- 新轨：`CapabilityAssembler.assemble`（`:148`）决定 route
- 旧轨（"kept for backward compatibility"）：`_should_use_cross_domain/standalone/open_agent` 三条硬规则（`:149,209,227`）

**问题**：两套路由规则并存、由 flag 切换，单一决策点双源真相。且新轨里还要 `if open_agent but has_domain_strategy → redirect DOMAIN_TEMPLATE`（`:451`）这种事后纠正——说明 CapabilityAssembler 命中率不够稳，靠 override 兜。

### ❌ L2+L5 的 mode_selector ↔ 执行脱节 — 最大问题
- `mode_selector`（`agent/plan/mode_selector.py`）正经地用 skill_coverage/gap_count + 持久 lore（`mode_selection_lore.db`）选 pipeline/codeact，写进 `plan.execution_mode`（`engine.py:242-243`）
- 但 L5 执行分发根本不读它——`runtime._dispatch_execute` 只看 skill 自己的 runtime type
- 后果：mode_selector 是"幽灵控制杆"——benchmark 能测它选得对不对，但选完对真实执行无影响

### ⚠️ "CodeAct" 概念重载
同一名词承担 3 角色（code_act skill 类型 / agent 执行风格 / 失败回退），概念模型模糊。三处看到 "codeact" 指不同东西。

---

## 四、是否最佳实践？总判定

| 维度 | 判定 |
|---|---|
| 意图识别级联 | ✅ 最佳实践（小瑕疵：硬编码启发式 + 双意图表示） |
| domain→phase→skill 的骨架/选择分离 | ✅ 最佳实践（项目最强点） |
| 会话路由（interaction_mode 分发） | ✅ 合理 |
| 规划器选择 | ⚠️ 双轨技术债（capability_first vs legacy） |
| **mode_selector ↔ 执行脱节** | ❌ 非最佳实践——控制杆未接线 |
| CodeAct 概念一致性 | ⚠️ 三角色重载 |

**核心**：意图识别与 domain/phase/skill 关系是最佳实践（级联守门 + 领域策略做骨架 + SkillDAG 只做选择）。但"pipeline vs CodeAct"这一层是断的——mode_selector 的 execution_mode 不驱动执行，真实执行按 skill 自身 runtime type 分叉，CodeAct 是失败兜底。即"选择走哪条路"与"实际怎么走"是两套独立机制。

---

## 五、优化建议（按价值排序）

### R1（高）接通或降格 mode_selector
现状 mode_selector 是幽灵。二选一：
- **接通**：`execution_mode=="pipeline"` → 整 plan 走 `runtime.run_nextflow_plan`；`=="codeact"` → 整 plan 委托 `AgentSkillExecutor`；`=="auto"` 才按 skill runtime type 逐个分发
- **降格**：文档明确 `execution_mode` 仅为"建议/可观测/风险评估"字段，mode_selector 退化为风险评估输入，停止暗示它选执行路径

不处理则自进化选模（`mode_selection_lore.db`，v2 引入）在生产路径空转——benchmark 学到的先验不影响真实执行。**这是 v2 评审遗漏的实质问题**。

**涉及文件**：`skills/runtime.py:_dispatch_execute`、`agent/orchestrator.py`、`agent/plan/mode_selector.py`、`agent/plan/engine.py:242`
**风险**：中——改变执行分发，需回归 `test_execution`/`test_agent`
**验证**：`pytest backend/tests/test_execution backend/tests/test_agent -q`；新增"execution_mode 真实驱动分发"断言

### R2（中）合并 L3 双轨路由
`capability_first_routing_enabled` 一旦验证稳定，删除 legacy 三规则（`task_decomposer.py:209,227,149`），单一真相。当前双轨 + override 兜底是回归测试重灾区。

**涉及文件**：`agent/task_decomposer.py`、`agent/plan/capability_assembler.py`
**风险**：中
**验证**：`pytest backend/tests/test_plan -q`

### R3（中）合并 L1 双意图表示
`interaction_mode`/`scope` 与 `complexity` 二选一，移除 `_legacy_to_intent_type`（`:1158`）桥。否则每加新意图类型都要维护两套字段。

**涉及文件**：`agent/intent/analyzer.py`、`UserIntent` 模型
**风险**：中（触及意图层全链路）
**验证**：`pytest backend/tests/test_agent -q`

### R4（低）L1 启发式去重
`_determine_complexity`（`:847`）的 `sequential_markers` 去重（`:881`/`:905`）；`len(text.split())>15`（`:898`）换语言无关信号（如意图子项数 + phase 数）。

**涉及文件**：`agent/intent/analyzer.py`
**风险**：低
**验证**：`pytest backend/tests/test_agent -k intent`

### R5（低）CodeAct 概念去歧义
文档明确三角色：code_act skill / agent-loop 执行风格 / failure fallback，或统一命名，避免新人混淆。

**涉及文件**：文档（`docs/architecture.md`）+ `skills/runtime.py` 注释
**风险**：极低

---

## 六、与其他评估文档的关系

- 本文聚焦**路由分发架构**，与 `architecture-assessment-v3-revisit.md`（整体成熟度）互补。
- 本文 R1 校正了 v2 复审对 P3-2/G2 的判断——v2 称"选模自进化端到端闭合"，但端到端验证仅到 `mode_selection_lore.db` 持久化，**未验证 execution_mode 真实驱动执行**。经本文核查，该闭环在生产执行路径上**未接线**，属 v2 复审的盲点。

## 七、实施记录

R1–R5 已按"接通/统一"方向实施（不考虑向后兼容）：

- **R1**: `Orchestrator` 读取 `context["execution_mode"]`；`codeact` 模式直接 CodeAct 执行，`fixed_pipeline` 模式关闭 CodeAct fallback，`auto` 保持原行为。测试覆盖三种模式。
- **R2**: 删除 `capability_first_routing_enabled` flag 与 `_should_use_*` 三个 legacy 静态方法，`CapabilityAssembler` 成为唯一路由决策点。
- **R3**: 删除 `_legacy_to_intent_type` 桥；`UserIntent` 以 `interaction_mode`/`scope`/`domain`/`target` 为 v2 source of truth，`analysis_type`/`complexity` 作为派生投影保留。
- **R4**: `_determine_complexity` 中 `sequential_markers` 提取为类常量并去重；`len(text.split()) > 15` 改为字符长度阈值，兼容 CJK。
- **R5**: `docs/architecture.md` 新增 "CodeAct Terminology" 章节，`skills/runtime.py` 顶部 docstring 明确三角色区分。

验证：`pytest backend/tests/test_agent backend/tests/test_capabilities backend/tests/test_knowledge -q` 通过。

---

## 七、一句话总评

L1 意图级联与 L4 domain→phase→skill 是最佳实践；L3 双轨、L1 双意图表示是可收敛的技术债；**唯一非最佳实践的硬伤是 mode_selector↔执行脱节（R1）**——自进化选模的持久 lore 在生产路径上空转，需接通或正式降格。
