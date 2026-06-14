# 图表自动嵌入对话：实现方案对比

> 问题：分析过程中产生的图表，如何以组件形式嵌入对话的合理位置？
> 现状：前端已支持 `plot` 和 `plot_data` 消息类型，但后端未实现自动发送。

---

## 一、方案总览

| 方案 | 核心职责 | 本质 | 与另两个方案的关系 |
|:---|:---|:---|:---|
| **A. InterpretationEngine 附加图表** | phase 完成后，在文本解读中附加相关图表 | 生成逻辑 | 主方案 |
| **B. TurnRunner 检测可视化输出** | 统一检测所有 task 输出的 `plot_path`/`plot_data` | 生成逻辑 | A 的补充 |
| **C. WebSocket 实时推送** | 将图表消息实时推送到前端 | 传输机制 | 必须配合 A 或 B |

**推荐组合：A（主要）+ B（补充）+ C（传输）**

---

## 二、方案 A：InterpretationEngine 附加图表

### 核心思想

`InterpretationEngine.interpret_phase()` 是每个 phase 完成后被调用的。既然它负责生成"这段结果说明了什么"，那么它也最适合决定"这段结果应该配什么图"。

### 实现方式

```python
@dataclass
class PlotAttachment:
    plot_type: str           # "umap" | "violin" | "heatmap" | "qc_distribution"
    title: str
    caption: str
    data: Optional[Dict] = None      # plot_data 格式（交互式）
    image_base64: Optional[str] = None  # plot 格式（静态）
    file_path: Optional[str] = None     # workspace 中的文件路径

@dataclass
class Interpretation:
    summary: str
    key_findings: List[str]
    quality_assessment: Optional[QualityAssessment]
    recommendations: List[Recommendation]
    plots: List[PlotAttachment] = field(default_factory=list)  # ← 新增
    confidence: float = 0.8
```

```python
class InterpretationEngine:
    def interpret_phase(self, phase, skill_output, data_state, cbkb=None):
        # 1. 生成文本解读（现有逻辑）
        quality = self._assess_quality(phase, skill_output)
        summary = self._generate_summary(phase, skill_output, quality)
        findings = self._extract_findings(phase, skill_output, quality)
        recommendations = self._generate_recommendations(phase, skill_output, quality, data_state)
        
        # 2. 【新增】提取可视化附件
        plots = self._extract_plots(phase, skill_output)
        
        return Interpretation(
            summary=summary,
            key_findings=findings,
            quality_assessment=quality,
            recommendations=recommendations,
            plots=plots,
        )
    
    def _extract_plots(self, phase, skill_output):
        """从技能输出中提取可展示的图表。"""
        plots = []
        
        # Case 1: 技能直接返回 plot_data
        if "plot_data" in skill_output:
            plots.append(PlotAttachment(
                plot_type=skill_output.get("plot_type", "unknown"),
                title=skill_output.get("title", f"{phase.phase_type} plot"),
                caption=skill_output.get("caption", ""),
                data=skill_output["plot_data"],
            ))
        
        # Case 2: 技能返回 plot_path（PNG/SVG 文件）
        elif "plot_path" in skill_output:
            plots.append(PlotAttachment(
                plot_type=skill_output.get("plot_type", "unknown"),
                title=skill_output.get("title", f"{phase.phase_type} plot"),
                caption=skill_output.get("caption", ""),
                file_path=skill_output["plot_path"],
            ))
        
        # Case 3: 根据 phase 类型和输出推断应该展示什么图
        elif phase.phase_type in ("qc", "spatial_qc"):
            if "input_cells" in skill_output and "output_cells" in skill_output:
                # 可以生成一个 QC 过滤率的简单柱状图
                plots.append(self._build_qc_plot(skill_output))
        
        elif phase.phase_type in ("clustering", "spatial_clustering"):
            if "umap_path" in skill_output:
                plots.append(PlotAttachment(
                    plot_type="umap",
                    title="Clustering UMAP",
                    file_path=skill_output["umap_path"],
                ))
        
        return plots
```

### 优点

| 优点 | 说明 |
|:---|:---|
| **语义位置最合理** | 图表作为"解读"的一部分，出现在"文本说明 + 数据证据"的上下文中 |
| **职责清晰** | InterpretationEngine 本来就理解 phase 的类型和输出，由它决定配什么图最自然 |
| **按 phase 组织** | 每个 phase 的图表独立，不会出现"一张图不知道该跟谁"的问题 |
| **可解释性强** | 图表旁边就是 summary 和 findings，用户知道"为什么展示这张图" |
| **异常时也能展示** | 即使 QC 质量差，也可以展示 QC 分布图帮助诊断 |

### 缺点

| 缺点 | 说明 |
|:---|:---|
| **不覆盖纯可视化请求** | 如果用户只说"画个 UMAP"，没有 phase 解读，这里不会触发 |
| **需要解读前置** | 必须先调用 interpret_phase，如果跳过解读就不会展示图表 |
| **图表类型受限** | 只能附加与当前 phase 直接相关的图 |

### 适用场景

- ✅ 标准分析流程中每个主要 phase 完成后（QC → Clustering → DE → Viz）
- ✅ 需要图文结合解释结果的场景
- ✅ 异常诊断时展示证据图

---

## 三、方案 B：TurnRunner 检测可视化输出

### 核心思想

`TurnRunner` 是对话轮次的统一入口。无论 phase 是什么、是否触发解读，只要 task 的输出中包含可视化产物（`plot_path` / `plot_data` / `figure`），就自动包装为聊天消息发送。

### 实现方式

```python
class TurnRunner:
    async def _execute_task_with_visualization(self, task, working_memory, project_id):
        """Execute a task and auto-embed any visualization output."""
        orchestrator = self._get_orchestrator()
        
        # 执行任务
        results = await orchestrator.run_tree(task.tree)
        
        # 检测所有结果中的可视化输出
        plot_messages = []
        for task_id, result in results.items():
            if self._has_visualization(result):
                msg = self._build_plot_message(task_id, result)
                if msg:
                    plot_messages.append(msg)
                    working_memory.add_message(msg)
        
        return results, plot_messages
    
    def _has_visualization(self, result: Any) -> bool:
        """Check if a task result contains visualization output."""
        if not isinstance(result, dict):
            return False
        return any(key in result for key in [
            "plot_path", "plot_data", "figure", "image_base64",
            "umap_path", "tsne_path", "heatmap_path", "violin_path",
        ])
    
    def _build_plot_message(self, task_id: str, result: Dict) -> Optional[ChatMessage]:
        """Build a plot chat message from task result."""
        # 优先使用 plot_data（交互式）
        if "plot_data" in result:
            return ChatMessage(
                type=MessageType.PLOT_DATA,
                content={
                    "plot_type": result.get("plot_type", "unknown"),
                    "title": result.get("title", "Analysis Plot"),
                    "data": result["plot_data"],
                    "caption": result.get("caption", ""),
                    "task_id": task_id,
                },
                sender="agent",
            )
        
        # 其次使用 plot_path，转换为 base64
        if "plot_path" in result:
            image_base64 = self._file_to_base64(result["plot_path"])
            return ChatMessage(
                type=MessageType.PLOT,
                content={
                    "plot_type": result.get("plot_type", "unknown"),
                    "title": result.get("title", "Analysis Plot"),
                    "image_base64": image_base64,
                    "caption": result.get("caption", ""),
                    "task_id": task_id,
                },
                sender="agent",
            )
        
        return None
```

### 优点

| 优点 | 说明 |
|:---|:---|
| **覆盖所有场景** | 不依赖 InterpretationEngine，纯可视化请求也能捕获 |
| **统一处理** | 所有可视化输出走同一套逻辑，便于维护 |
| **不侵入 phase 逻辑** | 不需要修改 InterpretationEngine，新增可视化技能自动支持 |
| **灵活** | 可以根据 task 输出动态决定发送什么 |

### 缺点

| 缺点 | 说明 |
|:---|:---|
| **TurnRunner 变重** | TurnRunner 需要了解技能输出格式，违反单一职责原则 |
| **图表可能缺乏上下文** | 只发送图表，没有配套的文本解读，用户可能不知道图说明了什么 |
| **容易重复发送** | 如果 InterpretationEngine 也发了图，可能造成同一图表出现两次 |
| **需要约定输出格式** | 所有可视化技能必须统一输出 `plot_path` / `plot_data`，否则检测不到 |

### 适用场景

- ✅ 用户明确说"画个 UMAP""展示聚类结果"等纯可视化请求
- ✅ 快速实现，不修改 InterpretationEngine
- ✅ 需要捕获所有可能的可视化输出

---

## 四、方案 C：WebSocket 实时推送

### 核心思想

图表消息生成后，通过 WebSocket 实时推送到前端，而不是等 HTTP 请求完成后再返回。

### 实现方式

```python
# API 层
class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections.setdefault(session_id, []).append(websocket)
    
    async def disconnect(self, session_id: str, websocket: WebSocket):
        self.connections[session_id].remove(websocket)
    
    async def broadcast_to_session(self, session_id: str, message: Dict):
        for ws in self.connections.get(session_id, []):
            await ws.send_json(message)


# 在 TurnRunner / Orchestrator 中
async def send_plot_to_frontend(self, session_id: str, plot_message: ChatMessage):
    """Send plot message to frontend via WebSocket."""
    await self.ws_manager.broadcast_to_session(
        session_id,
        {
            "type": "chat_message",
            "message": plot_message.model_dump(),
        }
    )
```

```python
# Nextflow weblog 场景
@app.post("/webhook/nextflow")
async def nextflow_webhook(event: NextflowEvent):
    # Nextflow 完成一个 process 就推送一次
    if event.event in ("process_completed", "process_started"):
        # 如果是可视化 process，生成 plot 消息并推送
        if is_visualization_process(event.process):
            plot_msg = await generate_plot_from_nextflow_event(event)
            await ws_manager.broadcast_to_session(
                event.runId,
                {"type": "chat_message", "message": plot_msg.model_dump()}
            )
```

### 优点

| 优点 | 说明 |
|:---|:---|
| **实时性最好** | 图表生成后立即出现在对话中，无需等待整个 workflow 完成 |
| **用户体验最佳** | 长时间分析时，用户能看到阶段性成果，减少焦虑 |
| **与 HTTP 解耦** | 不依赖请求的响应周期，异步执行也能推送 |
| **支持持续更新** | 同一个图表可以多次更新（如参数调整后的新图） |

### 缺点

| 缺点 | 说明 |
|:---|:---|
| **不是生成逻辑** | 必须与 A 或 B 结合使用，单独 C 无法工作 |
| **增加系统复杂度** | 需要 WebSocket 连接管理、断线重连、会话关联 |
| **需要状态同步** | 如果用户刷新页面，需要能从数据库恢复历史消息 |
| **测试更复杂** | 需要异步测试 WebSocket 消息 |

### 适用场景

- ✅ 长时间运行的分析流程
- ✅ 需要实时看到阶段性成果的场景
- ✅ 多图表连续生成的场景

---

## 五、综合对比矩阵

| 维度 | 方案 A | 方案 B | 方案 C |
|:---|:---|:---|:---|
| **职责清晰度** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐（仅传输） |
| **语义位置合理性** | ⭐⭐⭐ | ⭐⭐ | — |
| **覆盖完整度** | ⭐⭐ | ⭐⭐⭐ | — |
| **实时性** | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **实现复杂度** | 中 | 中 | 中（需配合 A/B） |
| **与现有系统耦合** | 低 | 中 | 低 |
| **可维护性** | 高 | 中 | 高 |
| **可测试性** | 高 | 中 | 中 |
| **避免重复发送** | 易 | 难 | 易 |
| **上下文完整性** | 高 | 低 | — |

---

## 六、推荐方案：A + B + C 组合

### 组合策略

```
用户请求
    ↓
PlanEngine 生成计划
    ↓
Orchestrator 执行 task
    ↓
【方案 A】InterpretationEngine 生成 phase 解读 + 图表附件
    ↓
【方案 B】TurnRunner 兜底检测 task 输出中的可视化产物
    ↓
去重合并（避免 A 和 B 重复发送同一张图）
    ↓
【方案 C】WebSocket 实时推送到前端
    ↓
前端 MessageBubble 渲染 plot / plot_data
```

### 分工规则

| 场景 | 负责方案 | 原因 |
|:---|:---|:---|
| 标准 phase 完成后 | **A** | 图表作为解读的一部分，上下文完整 |
| 纯可视化请求 | **B** | 没有 phase 解读，需要兜底捕获 |
| 长时间运行 workflow | **C** | 实时推送，提升用户体验 |
| 图表已存在于 workspace | **B** | 直接读取文件路径，转换为 base64 |
| 需要交互式图表 | **A 或 B** 生成 plot_data | C 负责传输 |

### 去重机制

```python
@dataclass
class PlotMessageKey:
    """用于去重的图表标识。"""
    task_id: str
    plot_type: str
    # 可以加入文件路径或数据哈希

class PlotMessageDeduplicator:
    def __init__(self):
        self._sent_plots: Set[PlotMessageKey] = set()
    
    def should_send(self, key: PlotMessageKey) -> bool:
        if key in self._sent_plots:
            return False
        self._sent_plots.add(key)
        return True
```

---

## 七、具体实施建议

### 实施顺序（推荐）

```
Step 1: 后端新增 MessageType.PLOT 和 MessageType.PLOT_DATA（5 分钟）
n        ↓
Step 2: 实现方案 A（InterpretationEngine 附加图表）（1 天）
n        ↓
Step 3: 实现方案 B 的简化版（TurnRunner 检测 plot_path/plot_data）（0.5 天）
n        ↓
Step 4: 添加 A/B 去重逻辑（0.5 天）
n        ↓
Step 5: 实现方案 C（WebSocket 实时推送）（1 天）
n        ↓
Step 6: 前端验证 + 回归测试（0.5 天）
n        ↓
总计: 3.5 天
```

### 风险点

| 风险 | 缓解措施 |
|:---|:---|
| A 和 B 重复发送图表 | 使用 `PlotMessageDeduplicator` 去重 |
| base64 图片过大 | 大图片改用 `plot_data` 或 file_reference |
| WebSocket 断线消息丢失 | 前端重连后从 working_memory 恢复历史消息 |
| 所有可视化技能输出格式不一致 | 制定 SKILL.md 输出规范，强制 `plot_data` 或 `plot_path` |

---

## 八、一句话结论

> **最佳方案是"A 为主、B 兜底、C 传输"的组合。InterpretationEngine 负责在 phase 解读时附加图表（语义位置最合理），TurnRunner 负责捕获未被 InterpretationEngine 覆盖的纯可视化输出（覆盖完整度最高），WebSocket 负责实时推送到前端（用户体验最好）。**
