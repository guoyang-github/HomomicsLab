# TurnRunner / Orchestrator 拆分方案

> 目标：把 `backend/homomics_lab/agent/turn_runner.py`（~2600 行）中堆积的多种职责拆分到独立的、可单测的协作者中，让 `TurnRunner` 只保留“编排一次对话 turn”的薄壳，`Orchestrator` 只保留“任务树调度/执行”的核心。

## 1. 现状问题

- `TurnRunner` 同时承担：意图路由、任务分解、工具调用、Agent 循环、HITL 处理、风险评分、响应生成、 debate 处理、MCP 工具格式化、工作流执行、错误处理等。
- 结果是：
  - 单文件过长，新增功能只能继续往里塞；
  - 单元测试需要构造大量依赖；
  - `Orchestrator` 被 TurnRunner 当作可选执行器使用，边界模糊。

## 2. 拆分后的整体协作

```
run_turn(session, user_message)
  │
  ▼
IntentRouter ──► TaskPlanner ──► RiskAssessor
  │                                  │
  ▼                                  ▼
ResponseGenerator              PlanExecutor / Orchestrator
  │                                  │
  ▼                                  ▼
Result                          Result
  │
  ▼
TurnRunner（组合上述组件并返回统一 result）
```

## 3. 建议的新模块与职责

### 3.1 `agent/intent_router.py` — `IntentRouter`

**职责**：根据用户输入 + 上下文决定走哪条执行路径。

**从 TurnRunner 迁入的方法**：

- `_route_by_intent`
- `_build_debate_resolved_intent`
- `_is_domain_template_analysis`
- 部分直接响应入口判断逻辑（来自 `run_turn` / `_run_turn_once`）

**对外接口**：

```python
class IntentRouter:
    async def route(self, user_message: str, working_memory: WorkingMemory, context: ContextBundle) -> RouteDecision
```

### 3.2 `agent/response_generator.py` — `ResponseGenerator`

**职责**：直接回答、问候、QA、信息请求、澄清等非执行型响应的生成。

**从 TurnRunner 迁入的方法**：

- `_handle_direct_response`
- `_handle_clarification`
- `_generate_greeting_response`
- `_generate_qa_response`
- `_generate_information_request_response`
- `_generate_general_help_response`
- `_generate_direct_response_via_llm`
- `_generate_followup_suggestions`

**对外接口**：

```python
class ResponseGenerator:
    async def generate(self, intent: UserIntent, working_memory: WorkingMemory) -> AgentResponse
```

### 3.3 `agent/tool_executor.py` — `ToolExecutor`

**职责**：统一执行 tool / MCP / skill 调用，并格式化结果。

**从 TurnRunner 迁入的方法**：

- `_handle_mcp_tool`
- `_handle_agent_loop`
- `_create_tool_approval_hitl`
- `_summarize_mcp_result`
- `_format_pubmed_search`
- `_format_pubmed_fetch`

**对外接口**：

```python
class ToolExecutor:
    async def execute(self, call: ToolCall, context: ExecutionContext) -> ToolResult
```

### 3.4 `agent/hitl_handler.py` — `HITLHandler`

**职责**：处理所有需要人类介入的 checkpoint（debate、tool 审批、通用 HITL）。

**从 TurnRunner 迁入的方法**：

- `respond_to_tool_approval`
- `resume_hitl`
- `_extract_hitl`
- `_build_hitl_result`
- debate 相关入口逻辑

**对外接口**：

```python
class HITLHandler:
    async def create_checkpoint(self, task: TaskNode) -> HITLCheckpoint
    async def resume(self, checkpoint_id: str, choice: str, params: dict) -> TurnResult
```

### 3.5 `agent/risk_assessor.py` — `RiskAssessor`

**职责**：对计划/工具调用进行风险评分，决定是否进入审批流程。

**从 TurnRunner 迁入的方法**：

- `_evaluate_risk`
- `_build_risk_prompt`
- `_parse_risk_score`
- `_heuristic_risk_score`

**对外接口**：

```python
class RiskAssessor:
    async def assess(self, plan: Plan, context: ContextBundle) -> RiskAssessment
```

### 3.6 `agent/plan_executor.py` — `PlanExecutor`

**职责**：把已批准的 Plan 变成可执行任务树并驱动执行，作为 `Orchestrator` 的薄封装。

**从 TurnRunner 迁入的方法**：

- `_handle_workflow`
- `_handle_single_step`
- `_build_workflow_result`
- `_build_initial_progress`
- `_tree_progress`
- `_enqueue_execution`

**对外接口**：

```python
class PlanExecutor:
    async def execute(self, plan: Plan, project_id: str, callbacks: Callbacks) -> ExecutionResult
```

### 3.7 `agent/orchestrator.py` — `Orchestrator` 瘦身

**保留职责**：

- 任务树的调度、依赖解析、状态推进；
- 与 `Worker`/JobService 的对接；
- phase gate 与 replan 的触发判断（具体策略可继续外置）。

**建议迁出**：

- LLM 驱动的任务分解 -> `TaskPlanner`（可复用现有 `TaskDecomposer`）；
- 结果解释/摘要 -> `InterpretationEngine`；
- 工具调用细节 -> `ToolExecutor`。

## 4. `TurnRunner` 瘦身后的形状

```python
class TurnRunner:
    def __init__(
        self,
        intent_router: Optional[IntentRouter] = None,
        response_generator: Optional[ResponseGenerator] = None,
        risk_assessor: Optional[RiskAssessor] = None,
        plan_executor: Optional[PlanExecutor] = None,
        hitl_handler: Optional[HITLHandler] = None,
        memory_manager: Optional[MemoryManager] = None,
        llm_client: Optional[LLMClient] = None,
        trace_store=None,
    ):
        ...

    async def run_turn(self, ...) -> TurnResult:
        # 1. 加载上下文
        # 2. 路由决策
        # 3. 直接响应 或 生成计划 或 执行计划
        # 4. 风险审批 / HITL 分支
        # 5. 返回统一 TurnResult
```

剩余代码预计从 2600 行降到 300 行以内。

## 5. 迁移顺序（低风险渐进式）

1. **第一阶段**：提取 `ResponseGenerator` 和 `RiskAssessor`；它们相对独立，不影响执行路径。
2. **第二阶段**：提取 `ToolExecutor`；把 MCP 格式化逻辑整体迁出。
3. **第三阶段**：提取 `HITLHandler`；统一 debate / tool approval / 通用 HITL 入口。
4. **第四阶段**：提取 `PlanExecutor`，让 `Orchestrator` 只保留底层调度。
5. **第五阶段**：引入 `IntentRouter`，把 `run_turn` 中的分支判断集中化。
6. **第六阶段**：清理 `TurnRunner` 中已迁出的私有方法，添加缺失的单元测试。

## 6. 接口不变性保证

- `TurnRunner.run_turn`、`regenerate_response`、`respond_to_tool_approval` 的对外签名保持不变；
- `api/chat.py` 等调用方无需修改；
- `TurnResult` dataclass 保持现有字段，仅内部生成逻辑重新分配。

## 7. 验收标准

- `turn_runner.py` 行数 < 500；
- 新增协作者每个都有独立单元测试；
- 现有 `backend/tests/test_api/test_chat.py` 与 `test_agent` 相关测试全部通过；
- 不破坏 API 行为与前端交互。
