# 设计文档：持久化会话状态与长期记忆接入

**日期**：2026-06-15  
**主题**：Persistent Session State & Long-Term Memory Integration  
**状态**：待实现  

---

## 1. 目标与范围

### 1.1 目标

让 HomomicsLab 作为面向个人用户的生物信息学通用 Agent 具备以下基础能力：

1. **会话持久化**：服务重启后，用户的工作记忆（WorkingMemory）和任务树（TaskTree）不丢失。
2. **长期记忆可用**：每次对话时，Agent 能主动利用历史分析、参数偏好、项目上下文。
3. **个性化基础**：为后续"越用越懂你"的进化能力（参数偏好学习、SOP 提炼等）提供数据入口。

### 1.2 范围

本次实现将包含：

- 新增 `SessionStore`：持久化 `WorkingMemory` 与 `TaskTree`。
- 新增 `MemoryManager`：统一封装 `WorkingMemory`、`SemanticMemory`、`CBKB` 三类记忆的读取与写入。
- 新增 `ContextSnapshot`：定义一次对话轮次中需要被记忆的关键上下文。
- 修改 `TurnRunner`：在 `run_turn` 前后接入 `MemoryManager`。
- 修改 `api/chat.py`：用持久化 store 替换内存中的 `_sessions`、`_task_trees`、`_session_project_ids`。
- 增加配置项：`session_store_url`、`session_ttl_days` 等。

本次实现**不包含**：

- 修改 `SemanticMemory` 或 `CBKB` 的内部存储格式。
- 修改 `PlanEngine`、`Orchestrator` 等核心规划/执行逻辑。
- 引入事件溯源（Event Sourcing）。
- 分布式共享会话存储（先保证单实例可用，接口预留扩展）。

---

## 2. 架构与新增组件

```
┌─────────────────────────────────────────┐
│           API Layer (chat.py)           │
│  - 不再持有内存 _sessions/_task_trees    │
│  - 通过 SessionStore 读写会话状态        │
└─────────────────────────────────────────┘
                   │
┌─────────────────────────────────────────┐
│           TurnRunner                    │
│  - run_turn 前：load_context()          │
│  - run_turn 后：persist_turn()          │
└─────────────────────────────────────────┘
                   │
        ┌─────────┴─────────┐
        ▼                   ▼
┌───────────────┐   ┌─────────────────┐
│ MemoryManager │   │   SessionStore  │
│ 统一记忆入口   │   │  会话状态持久化  │
└───────┬───────┘   └─────────────────┘
        │
   ┌────┼────┐
   ▼    ▼    ▼
WorkingMemory  SemanticMemory  CBKB
```

### 2.1 新增组件

| 组件 | 文件建议位置 | 职责 |
|------|--------------|------|
| `SessionStore` | `homomics_lab/context/session_store.py` | 持久化 `WorkingMemory` 与 `TaskTree` 的抽象接口与默认 SQLite 实现 |
| `MemoryManager` | `homomics_lab/context/memory_manager.py` | 统一封装工作记忆、语义记忆、CBKB 的读取/写入，对外提供单一调用点 |
| `ContextSnapshot` | `homomics_lab/context/models.py` | 定义一次对话轮次中需要被记录的关键上下文 |

### 2.2 修改组件

| 组件 | 修改内容 |
|------|----------|
| `TurnRunner` | `__init__` 接收可选 `memory_manager`；`run_turn` 中调用 `enrich_context` 与 `persist_turn` |
| `api/chat.py` | 移除内存字典，使用 `MemoryManager.load_session` 与 `persist_turn` |
| `config.py` | 增加 `session_store_url`、`session_ttl_days`、`enable_semantic_memory` 等配置 |
| `TaskTree` | 补充 Pydantic 序列化/反序列化方法 |

---

## 3. 数据流

### 3.1 单轮对话数据流

```
1. 用户发送消息
   │
   ▼
2. chat.py 从 MemoryManager 加载 WorkingMemory + TaskTree
   │   （若 session 不存在则新建）
   ▼
3. TurnRunner.run_turn(session_id, user_message, ...)
   │
   ├── 3.1 MemoryManager.enrich_context(project_id, user_message, working_memory)
   │       ├── 从 SemanticMemory 检索相关历史分析/参数/异常
   │       ├── 从 CBKB 读取该项目的参数偏好、成功模式
   │       └── 将检索结果注入 working_memory.pinned_items / extra_context
   │
   ├── 3.2 现有流程：intent → plan → execute → result
   │
   └── 3.3 MemoryManager.persist_turn(session_id, project_id, ...)
           ├── 更新 WorkingMemory（消息、当前 task_id、pinned_items）
           ├── 把 TaskTree 写回 SessionStore
           ├── 将关键结果/决策摘要写入 SemanticMemory
           └── 把可学习的参数/模式异步写入 CBKB
   ▼
4. chat.py 返回响应给用户
```

### 3.2 服务启动/重启恢复

- 无需特殊恢复逻辑。
- 用户下次发送消息时，`MemoryManager.load_session(session_id)` 自动从 `SessionStore` 恢复之前的工作记忆与任务树。
- 任务状态由 `TaskStateMachine` 继续推进。

### 3.3 长期记忆写入策略

**写入时机**：每轮执行完成后，异步写入 `SemanticMemory` 与 `CBKB`。

**写入内容**：

- 用户消息与 Agent 回复摘要
- 生成的 plan 摘要（策略、phase 序列、关键参数）
- 每个完成的 phase/skill 的结果摘要
- HITL 决策及其参数
- 检测到的异常及处理方式

**不写入**：

- 原始大数据文件内容（只写路径/ResultReference）
- 完整错误堆栈
- 用户敏感信息

---

## 4. 接口设计

### 4.1 `SessionStore`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.tasks.task_tree import TaskTree


@dataclass
class SessionState:
    session_id: str
    project_id: str
    working_memory: WorkingMemory
    task_tree: Optional[TaskTree]
    updated_at: datetime


class SessionStore(ABC):
    @abstractmethod
    async def get(self, session_id: str) -> Optional[SessionState]: ...

    @abstractmethod
    async def save(self, state: SessionState) -> None: ...

    @abstractmethod
    async def delete(self, session_id: str) -> None: ...

    @abstractmethod
    async def cleanup_expired(self, ttl_days: int) -> int: ...
```

默认实现 `SQLiteSessionStore`，使用 JSON 序列化后存入 SQLite。

### 4.2 `MemoryManager`

```python
from typing import Any, Dict, Optional, Tuple

from homomics_lab.context.session_store import SessionState, SessionStore
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.context.semantic_memory import SemanticMemory
from homomics_lab.agent.turn_runner import TurnResult
from homomics_lab.tasks.task_tree import TaskTree


class MemoryManager:
    def __init__(
        self,
        session_store: SessionStore,
        semantic_memory: Optional[SemanticMemory] = None,
        cbkb: Optional[CBKB] = None,
    ) -> None:
        self.session_store = session_store
        self.semantic_memory = semantic_memory
        self.cbkb = cbkb

    async def load_session(
        self,
        session_id: str,
        project_id: str,
    ) -> Tuple[WorkingMemory, Optional[TaskTree]]:
        """从 SessionStore 加载会话；若不存在则新建。"""
        ...

    async def enrich_context(
        self,
        project_id: str,
        user_message: str,
        working_memory: WorkingMemory,
    ) -> Dict[str, Any]:
        """检索相关历史，返回给 TurnRunner 使用的额外上下文。"""
        ...

    async def persist_turn(
        self,
        session_id: str,
        project_id: str,
        user_message: str,
        turn_result: TurnResult,
        working_memory: WorkingMemory,
        task_tree: Optional[TaskTree],
    ) -> None:
        """持久化本轮状态并更新长期记忆。"""
        ...
```

### 4.3 `TurnRunner` 改动

`__init__` 增加可选依赖：

```python
class TurnRunner:
    def __init__(
        self,
        ...,
        memory_manager: Optional[MemoryManager] = None,
    ) -> None:
        ...
        self.memory_manager = memory_manager
```

`run_turn` 中：

```python
async def run_turn(self, session_id, user_message, working_memory, project_id, ...):
    # 1. 用长期记忆增强上下文
    extra_context = {}
    if self.memory_manager is not None:
        extra_context = await self.memory_manager.enrich_context(
            project_id, user_message, working_memory
        )

    # 2. 原有逻辑 ...

    # 3. 持久化
    if self.memory_manager is not None:
        await self.memory_manager.persist_turn(
            session_id=session_id,
            project_id=project_id,
            user_message=user_message,
            turn_result=turn_result,
            working_memory=working_memory,
            task_tree=turn_result.task_tree,
        )

    return turn_result
```

### 4.4 `api/chat.py` 改动

移除内存字典：

```python
# 移除
# _sessions: dict[str, WorkingMemory] = {}
# _task_trees: dict[str, TaskTree] = {}
# _session_project_ids: dict[str, str] = {}
```

改为：

```python
memory_manager: MemoryManager = request.app.state.memory_manager
working_memory, task_tree = await memory_manager.load_session(
    request.session_id, request.project_id
)
```

`send_message` 中不再需要手动保存，`TurnRunner` 已负责持久化。

---

## 5. 持久化、性能与兼容性

### 5.1 存储选型

| 数据 | 存储 | 原因 |
|------|------|------|
| `WorkingMemory` + `TaskTree` | SQLite（默认）/ PostgreSQL | 结构化、可查询、轻量 |
| `SemanticMemory` | sqlite-vec（已存在） | 复用现有实现 |
| `CBKB` | SQLite（已存在） | 复用现有实现 |

### 5.2 序列化

- `WorkingMemory` 已有 `to_json` / `from_json`。
- `TaskTree` 需要补充 `model_dump` / `model_validate` 序列化方法（基于 Pydantic）。
- `ChatMessage.content` 使用 Pydantic `mode="json"` 序列化。

### 5.3 性能考虑

- `enrich_context` 中的检索数量受限：
  - `SemanticMemory.search(top_k=5)`
  - CBKB 参数偏好只取最近 N 条（如最近 20 条）
- `persist_turn` 中的 CBKB 写入改为**异步后台任务**，不阻塞用户响应。
- 每轮一次 SessionStore 写操作，数据量小，不会成为瓶颈。

### 5.4 向后兼容

- `MemoryManager` 是可选依赖。未配置时，`TurnRunner` 行为与现在一致。
- 未配置 `session_store_url` 时，默认使用 SQLite 路径 `./data/sessions.db`。
- 现有测试若直接构造 `TurnRunner` 而不传 `memory_manager`，应继续通过。

---

## 6. 错误处理与边界情况

### 6.1 记忆层失败不中断主流程

- `enrich_context()` 异常 → 记录 warning，返回空上下文，继续执行。
- `persist_turn()` 异常 → 记录 error，仍返回响应给用户。
- 语义记忆模型未加载 → 优雅降级为无长期记忆模式。

### 6.2 会话状态损坏

- `SessionStore.get()` 反序列化失败 → 记录 error，返回新会话。
- 提供 `/api/health/memory` 健康检查端点。

### 6.3 并发

- 同一 session 的并发请求主要靠前端/队列避免。
- 如需严格并发控制，后续可在 `SessionStore.save()` 加入版本号/乐观锁。

### 6.4 隐私与数据保留

- Session 数据默认保留 90 天，可配置。
- 提供删除接口，用户可清除自己的历史。

---

## 7. 测试策略

### 7.1 单元测试

- `SQLiteSessionStore`：save / load / delete / 缺失 session / 过期清理。
- `MemoryManager`：mock `SemanticMemory` 与 `CBKB`，验证 enrich/persist 调用路径。
- `TurnRunner`：无 memory_manager 时行为不变；有 memory_manager 时 enrich/persist 被调用。

### 7.2 集成测试

- 启动服务 → 发送消息 → 重启服务 → 再次发送消息，验证上下文恢复。
- 连续两轮相关消息，验证第二轮能检索到第一轮摘要。

### 7.3 回归测试

- 确保 `api/chat.py` API 契约不变。
- 确保无 `MemoryManager` 时系统仍可运行。

---

## 8. 后续可扩展方向

- 将会话状态从 SQLite 升级到 PostgreSQL/R Redis。
- 让 `PlanEngine` 主动消费 CBKB 的参数偏好与成功模式。
- 引入用户显式反馈（ thumbs up/down ）来改进语义记忆检索排序。
- 基于会话历史做意图预测与主动建议。
