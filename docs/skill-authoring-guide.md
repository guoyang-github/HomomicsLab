# HomomicsLab Skill 编写指南

> 本文档说明如何为 HomomicsLab 编写 skill，并解释 agent/声明式 skill 与脚本型 skill 的选择标准。

---

## 1. Skill 是什么？

Skill 是 HomomicsLab 中可复用的能力单元。每个 skill 是一个目录，至少包含一个 `SKILL.md` 文件：

```text
my-skill/
├── SKILL.md                  # 必填：元数据 + 使用说明
├── scripts/                  # 可选：参考代码或可执行脚本
│   └── python/
│       ├── run.py            # 可选：脚本型 skill 的入口
│       └── helpers.py        # 可选：辅助函数
├── requirements.txt          # 可选：Python 依赖
└── examples/                 # 可选：示例输入/输出
```

---

## 2. 渐进披露模型

HomomicsLab 采用三层渐进披露：

| 层级 | 内容 | 大小 | 加载时机 |
|------|------|------|----------|
| Level 1 | 元数据：名称、描述、schema、关键词 | ~100 词 | 始终在上下文/索引中 |
| Level 2 | `SKILL.md` 正文 | < 5,000 词 | 技能被匹配/执行时加载 |
| Level 3 | 捆绑资源：`scripts/`、`examples/`、数据文件 | 无上限 | Agent 按需读取或执行时加载 |

**设计原则**：不要把所有内容一次性塞进上下文。元数据用于检索和规划，正文用于 Agent 推理，脚本只在需要时读取。

---

## 3. Skill 类型选择

### 3.1 Agent/声明式 Skill（推荐默认）

适用于：

- 方法论、科研设计、文献写作、流程编排
- 输入输出难以用 rigid schema 描述
- 需要 LLM 根据上下文灵活决策
- 来自 Claude Code / OpenClaw 生态

示例 frontmatter：

```yaml
---
name: scientific-research-design
version: "1.0.0"
description: Help users design rigorous biomedical experiments.
tool_type: agent        # 或 runtime.type: agent
allowed-tools:
  - file_read
  - file_write
  - shell_exec
inputs:
  research_question:
    type: string
    required: true
outputs:
  design_report:
    type: string
---
```

特点：

- HomomicsLab 会把 `SKILL.md` 正文作为 prompt 交给 LLM。
- 如果存在 `scripts/`，Agent 会自动获得 `file_read` 工具，可读取参考代码。
- 不保证完全确定性，不可缓存，但生态兼容性最好。

### 3.2 脚本型 Skill

适用于：

- 确定性计算（统计检验、数据过滤、格式转换）
- 需要严格可复现、版本锁定、缓存
- 输出需要被下游 skill 稳定消费

示例 frontmatter：

```yaml
---
name: bio-statistics-visualization
version: "1.0.0"
description: Generate publication-grade statistical figures.
tool_type: python
entrypoint: scripts/python/run.py   # 明确入口
inputs:
  action:
    type: string
    enum: [import_data, stat_test, render]
  params:
    type: object
outputs:
  success:
    type: boolean
  outputs:
    type: object
---
```

入口脚本约定：

- 必须能被 HomomicsLab 直接执行。
- 通过 `__inputs__` 读取输入（sandbox 注入）。
- 把结果赋给 `result` 变量；如果定义了 `main(skill_inputs)`，系统会自动调用它。
- 入口优先顺序：
  1. `SKILL.md` frontmatter 中的 `entrypoint`
  2. `scripts/python/run.py`（Python）或 `scripts/r/run.R`（R）

脚本型 skill 的 `scripts/` 下可以包含多个文件，但只有入口会被执行；其他文件应被入口 import 或引用。

### 3.3 Knowledge Skill

适用于只读参考，不执行：

```yaml
---
name: lab-sop
version: "1.0.0"
description: Standard operating procedures for the lab.
tool_type: knowledge
---
```

---

## 4. 何时把 Agent Skill "硬化"为脚本型？

| 阶段 | 建议 |
|------|------|
| 初期 | 写成 agent skill，快速验证需求 |
| 稳定后 | 如果输入输出明确、执行路径固定，加 `entrypoint` 改为脚本型 |
| 生产环境 | 核心分析步骤必须用脚本型，确保可复现和缓存 |

---

## 5. 与 Claude Code / OpenClaw 的兼容性

HomomicsLab 优先兼容 Claude Code 风格的 `SKILL.md`：

- `tool_type` 会被映射为 `runtime.type`。
- `allowed-tools` / `disallowed-tools` 会被解析。
- `scripts/` 下的代码作为参考，不会被自动执行。
- 额外 frontmatter（`entrypoint`、`code_act`、`category` 等）会被 HomomicsLab 读取，Claude Code 会忽略它们。

**最佳实践**：编写 `SKILL.md` 时把正文写得对 Claude Code 友好，把 HomomicsLab 专用执行细节放在 `entrypoint` 和 `scripts/` 里。

---

## 6. 安全与信任

- 外部导入的 skill 默认 `trusted=false`。
- 脚本型 skill 在被信任之前不会执行。
- Agent skill 即使被信任，也只能调用 `allowed-tools` 中声明的工具。
- `file_read` 自动授予给带 `scripts/` 的 agent skill，但限制只能读取 skill 自己的 `source_dir` 下的文件。

---

## 7. 快速检查清单

在提交新 skill 前确认：

- [ ] `name`、`version`、`description` 准确简洁
- [ ] `tool_type` 选择正确：`agent` / `python` / `knowledge` / `cli`
- [ ] 脚本型 skill 提供了 `entrypoint` 或 `scripts/python/run.py`
- [ ] 输入输出 schema 完整（agent skill 可放宽）
- [ ] `scripts/` 中的非入口文件不会单独执行
- [ ] `requirements.txt` 声明了所有依赖
- [ ] 示例和测试放在 `examples/` 或 `tests/`
