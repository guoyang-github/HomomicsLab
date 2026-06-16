> 技术解读：把 README.zh.md 中的设计决策用更直观的方式讲清楚。
> 适合：想快速理解 HomomicsLab 技术架构、模块关系和设计理念的开发者。

# HomomicsLab 技术解读

## 一、先建立整体观感

### 1.1 一句话

HomomicsLab 是一个**让自然语言请求能够安全、可复现地驱动生物信息学分析执行的 Agent 操作系统**。

### 1.2 用人体做类比

如果把整个系统比作一个人：

| 系统模块 | 人体对应 | 作用 |
|---|---|---|
| **用户界面 / API** | 感官和语言中枢 | 接收请求、反馈结果 |
| **IntentAnalyzer + PlanEngine** | 大脑皮层 | 理解意图、制定计划 |
| **DynamicAgent / AgentCore** | 神经系统 | 调度具体执行单元 |
| **CodeAct** | 手和肌肉 | 真正动手执行代码 |
| **Skill** | 器官 / 工具 | 完成确定任务 |
| **SkillDAG + CBKB** | 长期记忆 + 经验库 | 知道什么该先做、什么参数更好 |
| **StabilityGuard** | 免疫系统 | 防止错误执行造成损害 |
| **ReproducibilityEngine** | 海马体 / 实验记录本 | 记住完整执行过程，能重放 |
| **Workspace / DataStore** | 工作台和档案柜 | 存放数据、产物和血缘 |
| **Execution Scheduler** | 交通调度中心 | 决定任务走本地、集群还是 Nextflow |

这个类比的关键是：**大模型只负责“想”，系统负责“做”和“记”。**

---

## 二、核心问题：为什么需要这么多层？

### 2.1 直接让 LLM 写代码执行有什么问题？

假设你让 ChatGPT 分析 PBMC 数据：

```
用户：分析我的 PBMC 单细胞数据
LLM：好的，用 scanpy 读取，然后 QC、归一化、PCA、聚类...
```

问题：
1. **幻觉**：可能调用不存在的 API，如 `sc.pp.combat()`
2. **不可控**：不知道会生成什么代码，有没有危险操作
3. **不可复现**：三个月后换台机器，包版本变了，结果变了
4. **无领域知识**：不知道单细胞分析的标准流程、常见陷阱
5. **无状态**：不会根据数据特征调整计划

### 2.2 HomomicsLab 的解法

它不把 LLM 当成终点，而是当成**规划层的一个输入源**。

```
用户请求
   ↓
IntentAnalyzer（理解要做什么）
   ↓
PlanEngine（根据领域策略生成计划）
   ↓
DynamicAgent（选择执行者）
   ↓
CodeAct / SkillRuntime（在沙盒中执行）
   ↓
StabilityGuard（验证输入输出）
   ↓
InterpretationEngine（解释结果、检测异常）
   ↓
ReproducibilityEngine（打包审计记录）
```

每一层都有明确职责，LLM 只在“理解”和“生成代码”两处参与，其他由规则系统保证。

---

## 三、逐层技术解读

### 3.1 用户请求 → IntentAnalyzer

#### 做什么？
把自然语言解析成结构化的 `UserIntent`：

```python
UserIntent(
    analysis_type="single_cell_analysis",
    domain="single_cell",
    complexity="complex",
    keywords=["pbmc", "cluster", "marker"],
    constraints={"has_qc": False, "n_samples": 6}
)
```

#### 怎么做的？
- 从 `domain.yaml` 加载意图关键词
- 级联识别：关键词匹配 → embedding 相似度 → LLM → 澄清

#### 为什么重要？
没有这一步，LLM 只能“猜”用户要什么。IntentAnalyzer 把模糊请求变成结构化输入，后续模块才好处理。

---

### 3.2 PlanEngine：计划的生成与调整

#### 核心问题
PlanEngine **不**是直接遍历 SkillDAG 找路径。  
它从 `domain.yaml` 的策略模板出发，根据数据状态生成计划。

#### 一个具体例子

```yaml
# domain.yaml 片段
phases:
  - id: qc
    skills: [scanpy_qc]
  - id: normalize
    skills: [scanpy_normalize]
  - id: pca
    skills: [scanpy_pca]
  - id: cluster
    skills: [scanpy_cluster]
  - id: marker
    skills: [scanpy_marker]

state_checks:
  - condition: "batch_detected"
    action: insert
    target: integrate
    after: qc
```

执行时：

```
初始计划：qc → normalize → pca → cluster → marker

执行 qc 后发现 batch_detected = true
→ 自动插入 integrate 步骤

调整后的计划：qc → integrate → normalize → pca → cluster → marker
```

#### 为什么这样设计？
- **Strategy templates 提供“正确顺序”**：什么步骤应该在什么前面，这是领域知识
- **state_checks 提供“自适应”**：数据状态变化时，计划跟着变
- **SkillDAG 提供“替代方案”**：某个 skill 失败时，知道可以换哪个

三层配合：模板保底、状态调整、DAG 兜底。

---

### 3.3 CodeAct：执行基座

#### 为什么叫“基座”？
因为它不是完成某个具体任务的能力，而是**生成和执行代码的通用机制**。

#### CodeAct 能调用的东西

```
CodeAct 生成的代码
    │
    ├── 调用 Skill ──────→ scanpy_qc、plot_umap
    │
    ├── 调用 Tool ───────→ pubmed_search、file_write
    │
    └── 调用底层库 ──────→ scanpy、pandas、numpy
```

#### 一个例子

```python
# Agent 自动生成
import scanpy as sc
from homomics_lab.runtime import skill

# 调用 skill
adata = skill.call("scanpy_io", {"path": "pbmc3k.h5ad"})
qc = skill.call("scanpy_qc", {"adata": adata})

# 调用底层库
sc.pp.normalize_total(qc, target_sum=1e4)
sc.pp.log1p(qc)

# 调用 tool
pubmed = tool.call("pubmed_search", {"query": "PBMC marker genes"})
```

#### 为什么需要 CodeAct？
因为固定 skill pipeline 无法处理：
- 循环（批量处理 100 个样本）
- 分支（如果 QC 失败则重试）
- 动态组合（根据中间结果选择下一步）

CodeAct 让 Agent 能写真正的程序，而不是只能调用固定函数。

---

### 3.4 Skill 生态系统：活的能力单元

#### 为什么 Skill 不是普通插件？

普通插件：安装 → 调用 → 遗忘

HomomicsLab 的 Skill：

```
发现 → 验证 → 执行 → 进化 → 沉淀
```

#### 每个阶段的含义

1. **发现**
   - 用户问："我要做降维"
   - TF-IDF 找到 `pca`、`umap` 等关键词命中
   - sentence-transformers 理解语义，召回 `scanpy_pca`、`scanpy_umap`、`scanpy_tsne`

2. **验证**
   - 检查输入是否符合 SKILL.md 中声明的 JSON Schema
   - 比如 `scanpy_qc` 需要 `adata_path: string`

3. **执行**
   - 在沙盒中运行
   - 结果通过 SHA-256 键缓存

4. **进化**
   - SkillDAG 记录：`scanpy_qc` → `scanpy_pca` → `scanpy_cluster`
   - 边从 `CANDIDATE` 升级为 `CONFIRMED`

5. **沉淀**
   - 一次成功的 CodeAct 执行，可以通过 UI “保存为 Skill”
   - 变成正式的 `SKILL.md + scripts/` 包

#### 统一格式

```
skill_id/
├── SKILL.md              # 元数据 + 输入输出 schema
├── scripts/
│   ├── python/main.py
│   └── r/main.R
└── tests/
```

内置 skill 和外部 skill 格式完全一样，只是 `metadata["source"]` 不同。

---

### 3.5 执行调度层：本地、SLURM、Nextflow

#### 为什么需要多种执行后端？

生物信息学任务的规模差异极大：

- 开发调试：几百 MB 的单细胞数据，本地几分钟跑完
- 常规分析：几十 GB 的转录组数据，需要多核服务器
- 生产流程：上百样本的全基因组/单细胞项目，必须上 HPC 或云

HomomicsLab 把"执行什么"和"在哪里执行"解耦。Agent 负责生成计划，**Execution Scheduler** 负责把同一份计划分发到合适的后端。

#### 三种后端

| 后端 | 对应类 | 适用场景 |
|---|---|---|
| **本地执行** | `LocalScheduler` | 开发、小数据、快速验证 |
| **SLURM 集群** | `SlurmScheduler` | HPC 长时任务、多核并行 |
| **Nextflow 流程** | `NextflowRunner` | 可复现流程、nf-core 工作流 |

#### 执行流程

```
AgentCore 生成 skill 代码
        ↓
Orchestrator 选择 scheduler
        ↓
LocalScheduler  →  子进程 / 沙盒运行
SlurmScheduler  →  渲染 sbatch → sbatch → squeue/sacct 监控
NextflowRunner  →  渲染 DSL2 模板 → nextflow run
        ↓
执行结果 + stdout/stderr 回流
        ↓
DataStore 卸载大结果
```

#### nf-core 集成

`NFCoreManager` 把 nf-core 的数百个流程变成 Agent 可调用的能力：

1. **发现**：调用 `nf-core pipelines list`，缓存元数据
2. **下载**：把流程拉到本地缓存，避免每次都联网
3. **加载 schema**：读取 `nextflow_schema.json`，知道哪些参数必填、哪些可选
4. **检测 profile**：自动判断 `docker` / `singularity` / `conda` / `slurm` 是否可用
5. **执行**：生成 `nextflow run` 命令并提交

这样用户不需要手写 Nextflow DSL，只需要说：

> “对我的 FASTQ 数据跑 nf-core/rnaseq，用 GRCh38 参考基因组。”

Agent 自动完成参数填充、profile 选择、结果监控。

#### 对可复现性的意义

Nextflow 和 nf-core 本身强调容器化、版本锁定；HomomicsLab 再叠加自己的 `ReproducibilityBundle`，记录：

- Agent 生成的代码
- 实际提交的 sbatch / nextflow 命令
- 执行器版本（Nextflow、SLURM、容器镜像）
- 输出产物和血缘

---

### 3.6 单文件领域声明

#### 核心思想

扩展一个组学领域，不需要改 Python 代码，只需要写一个 YAML。

#### `domain.yaml` 包含什么？

```yaml
domain: metagenomics_16s

# 1. 分析策略
phases: [qc, denoising, taxonomy, diversity]

# 2. 状态触发的计划调整
state_checks:
  - condition: "host_contamination > 0.1"
    action: insert
    target: dehost

# 3. 意图识别
intents:
  - analysis_type: metagenomics_analysis
    keywords: ["16S", "microbiome"]

# 4. 角色定义
roles:
  - role_id: metagenomicist
    allowed_skills: [metagenomics_qc, metagenomics_taxonomy]

# 5. SOP
sops:
  - id: sop_16s_v1
    title: 16S Analysis SOP

# 6. DAG 种子
dag_seeds:
  - from: metagenomics_qc
    to: metagenomics_denoise
```

#### 为什么一个文件就够了？

因为 DomainLoader 会把这个文件拆开，分别注册到不同模块：

```
domain.yaml
    │
    ├── phases / state_checks → StrategyLibrary（PlanEngine 用）
    │
    ├── intents → IntentAnalyzer
    │
    ├── roles → RoleRegistry（AgentCore 用）
    │
    ├── sops → CBKB
    │
    ├── dag_seeds → SkillDAG
    │
    └── skills/ → SkillRegistry
```

这样新增领域时，核心架构代码完全不用改。

---

### 3.7 多层稳定性防线

#### 为什么需要这么多层？

因为 Agent 执行的是代码，代码可能：
- 参数传错
- 包版本不对
- 生成危险代码
- 结果悄悄变了

每一层防一种风险：

```
用户请求
   ↓
L1 Schema 校验        ← 防止类型错误、缺字段
   ↓
L2 版本锁定           ← 防止环境漂移
L2 回归基线           ← 防止结果悄悄变化
   ↓
L3 代码安全审计        ← 防止危险代码
L3 沙盒执行           ← 防止影响主机
   ↓
HITL 人工审批         ← 关键节点人工把关
   ↓
执行结果
```

#### 具体例子

**L1 Schema**：
```python
# skill 声明需要 adata_path: string
输入：{"adata_path": 123}  # int，不是 string
结果：SchemaValidationError，提前拦截
```

**L2 版本锁定**：
```python
# 锁定文件记录 scanpy==1.10.0
# 三个月后环境变成 scanpy==1.11.0
VersionLockMismatch → 提醒用户环境变了
```

**L3 沙盒**：
```python
# LLM 生成代码尝试 os.system("rm -rf /")
# 在 bubblewrap 沙盒中执行，无法影响主机
```

---

### 3.8 可复现性：ReproducibilityBundle

#### 为什么 Git commit 不够？

Git 只能记录代码版本，但分析还依赖：
- 运行时的参数
- 人类的修改和审批
- 包版本
- skill 版本
- 数据状态

#### Bundle 里有什么？

```
ReproducibilityBundle/
├── code/
│   └── generated_analysis.py    # Agent 生成的完整代码
├── plan/
│   └── plan_result.json         # 执行计划
├── hitl/
│   └── decisions.json           # 人类审批记录
├── env/
│   ├── pip_freeze.txt           # pip 依赖
│   └── python_version.txt       # Python 版本
└── skills/
    └── version_lock.json        # skill 版本 + 脚本 SHA
```

#### 价值

别人拿到这个 bundle，可以：
1. 重跑得到相同结果
2. 审查每一步做了什么
3. 发表论文时作为方法补充材料

---

### 3.9 数据工程：DataStore 与缓存

#### 生信数据的问题

单细胞数据一个 `AnnData` 对象可能几百 MB。如果每次 API 调用都把它序列化成 JSON：
- 内存爆炸
- 网络传输慢
- 容易出错

#### DataStore 的做法

```python
# skill 返回一个 DataFrame
result = pd.DataFrame(...)

# DataStore 自动判断：太大，存成 Parquet
DataStore.save(result) → 返回 ResultReference

# API 传的是小对象
{"type": "ResultReference", "path": ".../result.parquet"}
```

映射规则：
- `DataFrame` → Parquet
- `AnnData` → H5AD
- 大对象 → pickle
- 小对象 → 内联 JSON

#### 缓存

- **SkillCache**：相同输入（skill_id + inputs + fingerprint）直接命中，秒级返回
- **CodeActCache**：相似任务描述命中 embedding 缓存，不再调用 LLM

---

### 3.10 CBKB：结构化的领域记忆

#### 不是普通向量数据库

普通向量 DB：存一段文本，按相似度检索。  
CBKB：按生信分析本体组织，每条记录有明确类型和来源。

#### 五层结构

| 层级 | 存储 | 例子 |
|---|---|---|
| **ExperimentGraph** | 实验节点和关系 | 分析 A 和分析 B 共用同一 QC 策略 |
| **ParameterLore** | 参数 → 结果质量 | PBMC 数据 `resolution=0.6` historically 聚类效果最好 |
| **AnomalyArchive** | 异常记录 | 批次效应 >30% 时 Harmony 优于 scVI |
| **LabSOP** | 标准操作程序 | 实验室版本化的最佳实践 |
| **SkillEvolutionLog** | SkillDAG 边状态历史 | QC→PCA→Cluster 已确认 47 次 |

#### 关键约束

每条记录都可追溯到：
- 某个 `ReproducibilityBundle`
- 某个 `Workspace` 产物
- 某条 `SkillDAG` 边

所以 CBKB 不是黑盒，而是**可审计的经验库**。

---

### 3.11 动态角色与多智能体

#### 为什么不硬编码 Agent 类？

传统系统：
```python
class BioinfoAgent: ...
class VizAgent: ...
```

问题：每新增一种专家就要改代码。

HomomicsLab：
```yaml
role_id: visualization
name: Visualization Specialist
allowed_skills: [plot_umap, plot_heatmap]
allowed_tools: [file_read, file_write]
permissions:
  can_execute: true
```

角色是配置，运行时动态实例化。

#### 运行时模型

```
        Analyst（常驻协调者）
           │
    ┌──────┼──────┐
    ↓      ↓      ↓
 Specialist Specialist Reviewer
  (按需)    (按需)   (校验高风险)
```

#### 多智能体集群

- **并行执行**：4 个样本同时跑 QC
- **共识投票**：3 个专家独立调用 peaks，投票决定最终结果
- **广播协调**：Supervisor 同步上下文

---

## 四、一次完整执行的数据流

以 "分析 PBMC 单细胞数据" 为例：

```
1. 用户："分析我的 PBMC 数据"
   ↓
2. IntentAnalyzer
   → UserIntent(analysis_type="single_cell_analysis", ...)
   ↓
3. PlanEngine
   → 从 single_cell domain.yaml 加载策略
   → 初始计划：qc → normalize → pca → cluster → marker
   ↓
4. AgentCore 分配 DynamicAgent
   → Analyst + Specialist(QC) + Specialist(Visualization)
   ↓
5. SkillRuntime 执行 scanpy_qc
   → Schema 校验 → 沙盒执行 → DataStore 卸载结果
   → SkillCache 缓存结果
   ↓
6. InterpretationEngine
   → "QC 过滤 12% 细胞，正常"
   → 发现 batch_detected = true
   ↓
7. DynamicReplanningEngine
   → 在 qc 后插入 integrate 步骤
   ↓
8. 继续执行 integrate → normalize → pca → cluster → marker
   ↓
9. 生成 HTML 报告
   ↓
10. ReproducibilityEngine.finalize()
    → 打包 code + plan + hitl + env + skill versions
    → 写入 Workspace/.metadata/
    → CBKB 记录 experiment node、parameter lore
   ↓
11. 返回结果给用户
```

---

## 五、与通用 Agent 的技术差异

### 5.1 为什么通用 LLM Agent 做不好生信？

| 问题 | 通用 Agent | HomomicsLab |
|---|---|---|
| **领域知识** | 只靠 prompt 和训练数据 | `domain.yaml` + SkillDAG + CBKB 内建 |
| **执行** | 生成代码，用户手动复制 | 沙盒执行，自动返回结果 |
| **状态理解** | 无 DataState | `DataState` + `state_checks` 驱动计划 |
| **可复现** | 无 | ReproducibilityBundle |
| **安全** | 代码直接运行 | 代码审计 + 沙盒 + HITL |
| **错误处理** | 失败即止 | SkillDAG 找替代 skill + replan |

### 5.2 为什么传统平台不够？

| 问题 | Galaxy / nf-core | HomomicsLab |
|---|---|---|
| **输入方式** | GUI 拖拽 / 命令行 | 自然语言 |
| **灵活性** | 固定 workflow | 数据状态驱动动态计划 |
| **可解释性** | pipeline 黑盒 | phase 级摘要 |
| **学习成本** | 高 | 低 |

---

## 六、关键设计决策

### 6.1 为什么 PlanEngine 不直接遍历 SkillDAG？

因为 SkillDAG 是从执行历史中**学习出来的关系**，它适合推荐和兜底，但不适合作为计划的主要来源。

领域策略模板才是计划的“主心骨”，SkillDAG 是“参谋”。

### 6.2 为什么 CodeAct 和 Skill 要分开？

- **Skill**：确定性、可缓存、可验证
- **CodeAct**：灵活性、可组合、处理复杂逻辑

两者互补：简单任务走 skill pipeline，复杂任务走 CodeAct。

### 6.3 为什么 CBKB 不是简单向量库？

因为科研需要**可审计的经验**。向量库只能告诉你“这段文本相似”，CBKB 能告诉你：
- 这个参数上次在什么数据上用过
- 结果好不好
- 为什么好
- 能不能复现

---

## 七、适合什么时候用？

### 当前最适合
- 个人研究者本地分析
- 小型实验室标准化流程
- 教学演示和可复现实验

### 还需要成长
- 大规模分布式分析
- 超大规模 skill 生态
- 自动化论文写作

---

## 八、术语表

| 术语 | 含义 |
|---|---|
| **Skill** | 原子能力，完成一个确定任务 |
| **CodeAct** | Agent 生成并执行代码的机制 |
| **SkillDAG** | 技能关系图，记录技能间依赖、冲突、替代关系 |
| **CBKB** | 计算生物学知识库，五层结构化记忆 |
| **domain.yaml** | 单文件领域声明 |
| **ReproducibilityBundle** | 可复现审计包 |
| **DataState** | 分析过程中的数据状态 |
| **HITL** | Human-in-the-loop，人工审批 |
| **ResultReference** | 大数据对象的轻量引用 |
