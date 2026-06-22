# HomomicsLab v0.6 作图能力详细设计方案

> 目标：在 HomomicsLab 中集成一套面向生物医学研究的"对话式统计作图"能力，覆盖 GraphPad Prism 的核心使用场景，同时保留系统已有的 Skill、Domain、CBKB、Provenance、RO-Crate 体系。

---

## 1. 设计定位与边界

### 1.1 目标场景

1. 生物学家/临床医生上传一个 Excel/CSV，说"帮我比较三组小鼠肿瘤体积"，系统自动完成统计检验并生成 Nature 风格发表图。
2. 用户说"把 Control 组改成灰色，Y 轴改成 Tumor Volume (mm³)"，系统在原有图表基础上直接修改并重新渲染。
3. 用户可以将图表、统计结果、复现 Notebook 一并导出到 RO-Crate。

### 1.2 明确不做

- **不做**完整的拖拽式 GUI 绘图编辑器（不重新发明 Prism 界面）。
- **不做**实时交互式 Dashboard（不替代 Plotly Dash/Shiny）。
- **不做**非生物医学通用可视化（系统已有 `/api/viz/plot` 负责通用 bioinfo plot，本次聚焦统计+发表图）。

### 1.3 核心设计决策

| 决策 | 说明 |
|------|------|
| 以 Skill 为载体 | 复用本地已有的 `Stat-Viz-Skills`，包装为 HomomicsLab 可识别的 `SKILL.md + scripts/`。 |
| 一个主 Skill + 多 Action | `bio-statistics-visualization` 一个 skill，通过 `action` 字段分发到导入/统计/作图/导出/修图。 |
| 数据与图分离 | 原始数据进入 `WorkspaceManager.data/`，图表作为 `output` artifact 注册。 |
| 复现 Notebook 为一级产物 | 每次出图同时生成 `notebooks/figure_<id>.ipynb`，与图表一起进入 provenance。 |
| 自然语言修图 | 复用 `biostat_viz.vision.editor.VisionEditSkill`，支持纯文本命令；圈选修图作为二期扩展。 |

---

## 2. 架构概览

```
用户上传 CSV ──► 前端 FigureWorkbench ──► POST /api/viz/sessions/{id}/render
                              │
                              ▼
                  ┌───────────────────────┐
                  │  viz_biomedical domain │  (domain.yaml 中声明 phases/intents/roles)
                  └───────────────────────┘
                              │
                              ▼
                  ┌───────────────────────┐
                  │ bio-statistics-       │  (SKILL.md + scripts/python/run.py)
                  │  visualization skill  │
                  │  - import_data        │
                  │  - stat_test          │
                  │  - render             │
                  │  - export             │
                  │  - vision_edit        │
                  └───────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  WorkspaceManager      biostat_viz package     ProvenanceRecorder
  (data/ outputs/       (DataImportSkill,       (记录输入数据、代码、
   notebooks/ logs/)    StatTestSkill,           输出图表 checksum、参数)
                        FigureRenderer,
                        ExportEngine,
                        VisionEditSkill)
```

---

## 3. 依赖与部署

### 3.1 包依赖

在 skill 目录下声明依赖，不污染 HomomicsLab 主环境：

```text
backend/homomics_lab/skills/imported/local/bio-statistics-visualization/
├── SKILL.md
├── requirements.txt              # 主依赖
├── environment.yml               # 可选 conda 依赖
├── scripts/
│   └── python/
│       └── run.py                # HomomicsLab 统一入口
└── notebooks/
    └── figure_template.ipynb     # 导出模板
```

`requirements.txt`：

```text
pydantic>=2.0
pandas>=2.0
numpy>=1.24
scipy>=1.11
statsmodels>=0.14
pingouin>=0.5
lifelines>=0.27
matplotlib>=3.7
seaborn>=0.12
Pillow>=10.0
openpyxl>=3.1
nbformat>=5.9
```

> 注：`biostat_viz` 包源码可直接以 `src/biostat_viz` 复制到 skill 目录内，或作为相对路径安装。建议直接在 skill 目录内携带源码，避免外部路径依赖。

### 3.2 安装方式

```bash
# 方式一：随 HomomicsLab 启动自动发现
# 将 Stat-Viz-Skills 复制到 data/skill_store/imported/local/bio-statistics-visualization/
# bootstrap 时由 SkillStore 加载

# 方式二：运行时导入
curl -X POST /api/skills/import \
  -d '{"source": "/path/to/Stat-Viz-Skills/bio-statistics-visualization", "namespace": "local"}'
```

---

## 4. Skill 设计：`bio-statistics-visualization`

### 4.1 SKILL.md 核心 frontmatter

```yaml
---
name: bio-statistics-visualization
version: "1.0.0"
description: |
  Guide users through biomedical statistical analysis and publication-grade
  figure generation via natural language. Supports data import, assumption-checked
  statistical tests (ANOVA, t-test, survival, curve fit), journal-themed plotting
  (Nature/Cell/Science), natural-language figure editing, and reproducible notebook export.
category: visualization
author: HomomicsLab (adapted from Stat-Viz-Skills)
license: MIT
runtime:
  type: python
  dependencies: requirements.txt
input_schema:
  action:
    type: string
    enum: [import_data, stat_test, render, export, vision_edit, smart_inspect, full_pipeline]
    required: true
  project_id:
    type: string
    required: true
  session_id:
    type: string
    required: true
  params:
    type: object
    required: true
output_schema:
  success:
    type: boolean
  outputs:
    type: object
  artifacts:
    type: array
  interpretation:
    type: string
---
```

### 4.2 `scripts/python/run.py` 统一入口

```python
"""bio-statistics-visualization skill entrypoint."""
import json
import sys
import uuid
from pathlib import Path

from biostat_viz.data.importer import DataImportSkill
from biostat_viz.analysis.stat_tests import StatTestSkill
from biostat_viz.plotting.renderer import FigureRenderer
from biostat_viz.plotting.export import ExportEngine
from biostat_viz.plotting.types import FigureSpec, PlotType, ThemeName, PublicationParameters
from biostat_viz.vision.editor import VisionEditSkill


def _workspace_paths(project_id: str, session_id: str):
    base = Path(__file__).parents[5] / "data"  # 或从 skill_inputs["workspace_base"] 传入
    ws = base / "workspaces" / project_id
    return {
        "data": ws / "data",
        "outputs": ws / "outputs",
        "notebooks": ws / "outputs" / "notebooks",
        "logs": ws / "logs",
    }


def action_import_data(skill_inputs: dict) -> dict:
    paths = _workspace_paths(skill_inputs["project_id"], skill_inputs["session_id"])
    params = skill_inputs["params"]
    source = params["source"]  # 文件名或绝对路径
    df = pd.read_excel(paths["data"] / source) if source.endswith((".xlsx", ".xls")) else pd.read_csv(paths["data"] / source)

    prism_df = DataImportSkill().import_data(df, table_type_hint=params.get("table_type"))
    # 序列化 PrismDataFrame 到 Parquet + JSON metadata
    data_id = f"prism_{uuid.uuid4().hex[:8]}"
    parquet_path = paths["data"] / f"{data_id}.parquet"
    meta_path = paths["data"] / f"{data_id}.json"
    prism_df.data.to_parquet(parquet_path)
    meta_path.write_text(prism_df.metadata.model_dump_json())

    return {
        "success": True,
        "outputs": {
            "data_id": data_id,
            "table_type": prism_df.table_type.value,
            "group_columns": prism_df.metadata.group_columns,
            "quality_warnings": prism_df.quality_report.warnings,
        },
        "artifacts": [
            {"type": "data", "path": str(parquet_path), "mime": "application/octet-stream"},
            {"type": "data", "path": str(meta_path), "mime": "application/json"},
        ],
        "interpretation": (
            f"检测到数据表类型: {prism_df.table_type.value}，"
            f"分组列: {prism_df.metadata.group_columns}。"
            f"质量警告: {prism_df.quality_report.warnings or '无'}"
        ),
    }


def action_stat_test(skill_inputs: dict) -> dict:
    paths = _workspace_paths(skill_inputs["project_id"], skill_inputs["session_id"])
    params = skill_inputs["params"]
    data_id = params["data_id"]
    df = pd.read_parquet(paths["data"] / f"{data_id}.parquet")
    metadata = TableMetadata.model_validate_json((paths["data"] / f"{data_id}.json").read_text())
    prism_df = PrismDataFrame(table_type=metadata.table_type, data=df, metadata=metadata)

    result = StatTestSkill().run(prism_df, test_name=params["test_name"], auto_downgrade=params.get("auto_downgrade", False))
    result_id = f"analysis_{uuid.uuid4().hex[:8]}"
    result_path = paths["data"] / f"{result_id}.json"
    result_path.write_text(result.model_dump_json())

    return {
        "success": True,
        "outputs": {
            "result_id": result_id,
            "test_name": result.test_name,
            "p_values": result.p_values,
            "statistics": result.statistics,
            "assumptions": result.assumptions.model_dump() if result.assumptions else None,
            "post_hoc": [ph.model_dump() for ph in result.post_hoc] if result.post_hoc else [],
        },
        "artifacts": [{"type": "data", "path": str(result_path), "mime": "application/json"}],
        "interpretation": result.interpretation,
    }


def action_render(skill_inputs: dict) -> dict:
    paths = _workspace_paths(skill_inputs["project_id"], skill_inputs["session_id"])
    params = skill_inputs["params"]

    # 加载数据与分析结果
    df = pd.read_parquet(paths["data"] / f"{params['data_id']}.parquet")
    metadata = TableMetadata.model_validate_json((paths["data"] / f"{params['data_id']}.json").read_text())
    prism_df = PrismDataFrame(table_type=metadata.table_type, data=df, metadata=metadata)

    analysis = None
    if params.get("result_id"):
        analysis = AnalysisResult.model_validate_json(
            (paths["data"] / f"{params['result_id']}.json").read_text()
        )

    spec = FigureSpec(
        plot_type=PlotType(params["plot_type"]),
        data=prism_df,
        analysis=analysis,
        theme=ThemeName(params.get("theme", "nature")),
        dimensions=Dimensions(**params.get("dimensions", {})),
        annotations=[Annotation(**a) for a in params.get("annotations", [])],
        overrides=Overrides(**params.get("overrides", {})),
    )

    fig = FigureRenderer().render(spec)
    figure_id = params.get("figure_id") or f"fig_{uuid.uuid4().hex[:8]}"
    out_dir = paths["outputs"] / figure_id
    out_dir.mkdir(parents=True, exist_ok=True)

    asset = ExportEngine().export(
        fig,
        output_dir=out_dir,
        base_name=figure_id,
        formats=params.get("formats", ["svg", "png"]),
        params=PublicationParameters(**params.get("publication_parameters", {})),
    )

    # 生成可复现 Notebook
    notebook = _build_notebook(spec, asset)
    nb_path = paths["notebooks"] / f"{figure_id}.ipynb"
    nbformat.write(notebook, nb_path)

    return {
        "success": True,
        "outputs": {
            "figure_id": figure_id,
            "formats": {k: str(v) for k, v in asset.formats.items()},
            "spec": spec.model_dump(mode="json"),
        },
        "artifacts": [
            {"type": "output", "path": str(p), "mime": f"image/{fmt}" if fmt != "svg" else "image/svg+xml"}
            for fmt, p in asset.formats.items()
        ] + [{"type": "output", "path": str(nb_path), "mime": "application/x-ipynb+json"}],
        "interpretation": f"已生成{figure_id}，格式: {list(asset.formats.keys())}",
    }


def action_vision_edit(skill_inputs: dict) -> dict:
    """基于自然语言命令修改已有 FigureSpec 并重新渲染。"""
    paths = _workspace_paths(skill_inputs["project_id"], skill_inputs["session_id"])
    params = skill_inputs["params"]
    # 读取上次 spec
    spec_path = paths["outputs"] / params["figure_id"] / f"{params['figure_id']}_spec.json"
    spec = FigureSpec.model_validate_json(spec_path.read_text())

    editor = VisionEditSkill()
    for command in params["commands"]:
        spec = editor.process_command(command, spec)

    # 重新走 render 逻辑（可复用 action_render 的 helper）
    return _render_from_spec(skill_inputs, spec)


def main(skill_inputs: dict) -> dict:
    action = skill_inputs["action"]
    dispatch = {
        "import_data": action_import_data,
        "stat_test": action_stat_test,
        "render": action_render,
        "export": action_render,       # render 已包含 export
        "vision_edit": action_vision_edit,
        "smart_inspect": action_smart_inspect,
        "full_pipeline": action_full_pipeline,
    }
    fn = dispatch.get(action)
    if fn is None:
        return {"success": False, "error": f"Unknown action: {action}"}
    return fn(skill_inputs)


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    print(json.dumps(main(skill_inputs)))
```

### 4.3 `full_pipeline` action（一键作图）

把上面步骤串起来，供 `TurnRunner` 直接调用：

```python
def action_full_pipeline(skill_inputs: dict) -> dict:
    params = skill_inputs["params"]
    # 1) import
    import_res = action_import_data(skill_inputs)
    if not import_res["success"]:
        return import_res
    skill_inputs["params"]["data_id"] = import_res["outputs"]["data_id"]

    # 2) stat_test（自动推断）
    if "test_name" not in params:
        params["test_name"] = _infer_test(import_res["outputs"])
    stat_res = action_stat_test(skill_inputs)
    if not stat_res["success"]:
        return stat_res
    skill_inputs["params"]["result_id"] = stat_res["outputs"]["result_id"]

    # 3) render
    return action_render(skill_inputs)
```

---

## 5. Domain 设计：`viz_biomedical`

```yaml
# backend/homomics_lab/domains/viz_biomedical/domain.yaml
domain: viz_biomedical
display_name: Biomedical Visualization
version: "1.0.0"
description: Publication-grade statistical figures for biomedical research.

phases:
  - id: data_import
    required: true
    default_skill: bio-statistics-visualization
  - id: statistical_test
    required: false
    default_skill: bio-statistics-visualization
  - id: figure_render
    required: true
    default_skill: bio-statistics-visualization
  - id: figure_edit
    required: false
    default_skill: bio-statistics-visualization
  - id: export
    required: false
    default_skill: bio-statistics-visualization

phase_transitions:
  - from: data_import
    to: statistical_test
    type: followed_by
  - from: statistical_test
    to: figure_render
    type: followed_by
  - from: figure_render
    to: figure_edit
    type: followed_by
  - from: figure_edit
    to: figure_render
    type: followed_by
  - from: figure_render
    to: export
    type: followed_by

intents:
  - analysis_type: biomedical_plotting
    keywords:
      - "作图"
      - "画图"
      - "Prism"
      - "箱线图"
      - "小提琴图"
      - "柱状图"
      - "ANOVA"
      - "t-test"
      - "生存曲线"
      - "统计图"
      - "发表图"
    examples:
      - "帮我画一张三组小鼠肿瘤体积的箱线图"
      - "用 Nature 风格展示对照组和药物组的差异"
      - "做 Kaplan-Meier 生存曲线"

roles:
  - role_id: viz_specialist
    allowed_skills: [bio-statistics-visualization]
    allowed_tools: [file_read, file_write, shell_exec]
    permissions: [execute_script, read_project_data]

sops:
  - id: figure_export_sop
    title: 发表级图表导出 SOP
    steps:
      - 确认目标期刊主题（Nature/Cell/Science）
      - 检查坐标轴标签、单位、字体/字号
      - 导出 SVG + PNG/TIFF（300 dpi）
      - 生成可复现 Jupyter Notebook
```

---

## 6. API 设计

扩展现有 `/api/viz`，新增面向项目与 session 的路由。

```python
# backend/homomics_lab/api/viz.py

class CreateVizSessionRequest(BaseModel):
    project_id: str
    source_filename: str          # 已上传至 workspace data/ 的文件
    table_type_hint: str | None = None

class RenderRequest(BaseModel):
    session_id: str
    action: Literal["stat_test", "render", "vision_edit", "full_pipeline"]
    params: dict

class FigureListResponse(BaseModel):
    figure_id: str
    formats: dict[str, str]
    preview_url: str
    created_at: str


@router.post("/sessions")
async def create_session(request: CreateVizSessionRequest):
    """创建一次作图会话：导入并验证数据。"""
    session_id = uuid.uuid4().hex[:12]
    result = await _execute_skill(
        skill_id="bio-statistics-visualization",
        action="import_data",
        project_id=request.project_id,
        session_id=session_id,
        params={"source": request.source_filename, "table_type": request.table_type_hint},
    )
    return {"session_id": session_id, **result}


@router.post("/sessions/{session_id}/render")
async def render(session_id: str, request: RenderRequest):
    """执行统计检验、渲染图表或自然语言修图。"""
    result = await _execute_skill(
        skill_id="bio-statistics-visualization",
        action=request.action,
        project_id=request.project_id,
        session_id=session_id,
        params=request.params,
    )
    return result


@router.get("/projects/{project_id}/figures")
async def list_figures(project_id: str):
    """列出项目下所有图表 artifact。"""
    ws = WorkspaceManager(settings.data_dir, project_id)
    figures = []
    for artifact in ws.list_artifacts(artifact_type="output"):
        if artifact.metadata.get("kind") == "figure":
            figures.append({
                "figure_id": artifact.metadata["figure_id"],
                "formats": artifact.metadata["formats"],
                "preview_url": f"/api/files/{project_id}/{artifact.relative_path}",
                "created_at": artifact.created_at,
            })
    return figures


@router.post("/projects/{project_id}/figures/{figure_id}/edit")
async def edit_figure(project_id: str, figure_id: str, request: VisionEditRequest):
    """自然语言修图。"""
    result = await _execute_skill(
        skill_id="bio-statistics-visualization",
        action="vision_edit",
        project_id=project_id,
        session_id=request.session_id,
        params={"figure_id": figure_id, "commands": request.commands},
    )
    return result
```

> 复用现有的 `SkillRuntimeExecutor.execute()` 作为 `_execute_skill` 的实现。

---

## 7. 前端设计

### 7.1 页面/组件

```text
frontend/src/components/Figures/
├── FigureWorkbench.tsx          # 主工作区
├── FigureUploadStep.tsx         # 数据上传
├── FigureConfigPanel.tsx        # 图表/统计/主题配置
├── FigurePreview.tsx            # 图表预览
├── FigureEditChat.tsx           # 自然语言修图输入
├── FigureGallery.tsx            # 项目图表列表
└── hooks/useVizSession.ts       # session 状态管理
```

### 7.2 典型交互流程

1. **上传数据**：`FigureUploadStep` 调用 `/api/files/{project_id}/upload` 把文件写入 workspace `data/`。
2. **创建会话**：`POST /api/viz/sessions` 触发 `import_data`，返回 `data_id` 和检测到的表类型。
3. **配置并渲染**：用户在 `FigureConfigPanel` 选择 plot_type / theme / test，点击"生成图表"，调用 `/api/viz/sessions/{id}/render`（action=full_pipeline）。
4. **预览**：`FigurePreview` 显示返回的 base64 PNG 或 SVG URL。
5. **自然语言修图**：`FigureEditChat` 收集命令，调用 `/api/viz/sessions/{id}/render`（action=vision_edit），刷新预览。
6. **导出**：用户点击"导出发表包"，系统打包 SVG/PNG/TIFF + Notebook + 统计结果 JSON。

### 7.3 与现有 UI 融合
- 顶部导航新增 **Figures** 入口。
- Chat 中识别 `biomedical_plotting` 意图时，自动打开 `FigureWorkbench` 并预填数据。
- 使用现有 `components/ui` 的 `Card`, `Tabs`, `Button`, `Select`, `Toast`。

---

## 8. 可复现性与治理

### 8.1 Provenance 记录

每次 skill 执行后，`SkillRuntimeExecutor` 已自动调用 `ProvenanceRecorder.record()`。对于作图，需要额外在 skill 输出 `metadata` 中补充：

```json
{
  "provenance": {
    "data_checksum": "sha256:...",
    "test_name": "one_way_anova",
    "plot_type": "box",
    "theme": "nature",
    "notebook_path": "outputs/notebooks/fig_xxx.ipynb"
  }
}
```

### 8.2 Notebook 导出

`action_render` 生成的 `outputs/notebooks/{figure_id}.ipynb` 包含：
- 读取原始数据的代码
- `DataImportSkill` / `StatTestSkill` / `FigureRenderer` 调用
- 最终图表展示

### 8.3 RO-Crate 导出

复用现有 `/api/projects/{project_id}/export/rocrate`：
- `outputs/` 下的图表、Notebook 自动进入 crate。
- `provenance.db` 中的 `ExecutionProvenance` 记录转为 `CreateAction`。

---

## 9. 测试计划

| 测试 | 层级 | 说明 |
|------|------|------|
| `test_viz_skill_import_data` | skill 单元 | 上传 CSV → 检测为 column 类型 |
| `test_viz_skill_stat_test` | skill 单元 | 三组数据 → one_way_anova → 结果含 F/p/post_hoc |
| `test_viz_skill_render` | skill 单元 | 生成 SVG/PNG 文件与 Notebook |
| `test_viz_skill_vision_edit` | skill 单元 | "make control gray" → spec.overrides 更新 |
| `test_viz_api_full_pipeline` | API 集成 | 端到端调用 `/api/viz/sessions/{id}/render` |
| `test_viz_domain_intent` | 领域/意图 | "画箱线图"被识别为 `biomedical_plotting` |
| `test_viz_provenance` | 可复现 | 验证 provenance 记录含数据 checksum 与 notebook 路径 |

---

## 10. 实施阶段

### Phase 1：MVP（1–2 周）
- [ ] 将 `Stat-Viz-Skills` 复制/适配为 `bio-statistics-visualization` skill。
- [ ] 实现 `run.py` 的 `import_data`、`stat_test`、`render` action。
- [ ] 新增 `viz_biomedical` domain。
- [ ] 扩展 `/api/viz`：新增 sessions + render 接口。
- [ ] 前端 `FigureWorkbench` 基础版（上传 + 配置 + 预览）。
- [ ] 测试：column 数据 + ANOVA/t-test + bar/box 图。

### Phase 2：自然语言修图与多格式导出（1 周）
- [ ] 接入 `VisionEditSkill`。
- [ ] 实现 SVG/PNG/TIFF/PDF 多格式导出。
- [ ] 生成可复现 Notebook。
- [ ] 前端新增 `FigureEditChat`。

### Phase 3：高级统计与临床衔接（1–2 周）
- [ ] 支持 survival、curve fit、heatmap。
- [ ] 支持多图排版（`multi_panel`）。
- [ ] 与 `clinical_research` domain 共享 `bio-statistics-visualization` skill。
- [ ] 图表资产注册到 `WorkspaceManager`，支持 `/projects/{id}/figures` 列表。

---

## 11. 与 Stat-Viz-Skills 的映射

| Stat-Viz-Skills 模块 | HomomicsLab 中使用位置 | 说明 |
|----------------------|------------------------|------|
| `biostat_viz.data.importer.DataImportSkill` | `run.py::action_import_data` | 数据导入与表类型检测 |
| `biostat_viz.analysis.stat_tests.StatTestSkill` | `run.py::action_stat_test` | 假设检验与自动降级 |
| `biostat_viz.plotting.renderer.FigureRenderer` | `run.py::action_render` | 根据 `FigureSpec` 渲染 |
| `biostat_viz.plotting.export.ExportEngine` | `run.py::action_render` | 多格式导出 |
| `biostat_viz.vision.editor.VisionEditSkill` | `run.py::action_vision_edit` | 自然语言修图 |
| `biostat_viz.wizard.session` | 前端 `useVizSession` | 会话状态管理可借鉴 |
| `examples/` | `notebooks/figure_template.ipynb` | 复现 Notebook 模板 |

---

## 12. 风险与回退

| 风险 | 回退方案 |
|------|----------|
| `biostat_viz` 依赖与 HomomicsLab 主环境冲突 | 使用 skill 隔离 `requirements.txt` + 子进程执行；必要时用 conda env |
| LLM 自然语言修图解析失败 | `VisionEditSkill` 返回未识别命令列表，前端提示用户改用结构化面板 |
| 复杂多图排版超出当前 package 能力 | 二期再引入 `matplotlib.gridspec` 手动编排；MVP 只做单图 |
| 统计假设不满足导致结果不可靠 | `StatTestSkill` 自动检测并在输出中明确报告假设违反，必要时降级 |

---

## 13. 结论

本方案通过**一个主 Skill + 一个 Domain + 一组 API + 一个前端工作台**，把 `Stat-Viz-Skills` 的统计作图能力无缝接入 HomomicsLab。所有产物（数据、统计结果、图表、Notebook）都进入现有 workspace / provenance / RO-Crate 体系，保持系统的一致性与可复现性。
