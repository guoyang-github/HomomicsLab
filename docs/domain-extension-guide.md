# HomomicsLab 领域扩展完整指南

> **目标读者**: 希望将 HomomicsLab 从当前的单细胞/空间转录组扩展到基因组学、蛋白组学、微生物组学、代谢组学等其他计算生物学领域的开发者。
>
> **核心前提**: HomomicsLab 的架构是领域无关的。扩展过程本质上是**"配置 + 注册"**，而非**"架构重构"**。
>
> **本文示例**: 以 **宏基因组学 (Metagenomics / 16S Amplicon Sequencing)** 为完整示例，展示从零到可运行的全过程。

---

## 一、扩展全景图

将新领域接入 HomomicsLab，需要完成以下 8 个步骤。其中前 5 步是**必须的最小集合**（MVP），后 3 步是**生产级完善**。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        领域扩展步骤（以宏基因组学为例）                        │
├─────┬─────────────────────────────┬─────────────────────────────────────────┤
│ 步骤 │ 操作                         │ 涉及文件/组件                            │
├─────┼─────────────────────────────┼─────────────────────────────────────────┤
│  1  │ 注册领域技能 (Skills)         │ skills/metagenomics_*/SKILL.md + scripts/│
│  2  │ 扩展意图分析 (Intent)         │ agent/intent_analyzer.py                 │
│  3  │ 扩展数据状态 (DataState)      │ agent/plan/models.py                     │
│  4  │ 创建分析策略 (Strategy)       │ agent/plan/strategies.py                 │
│  5  │ 种子技能图谱 (SkillDAG)       │ skills/skill_dag_seeds.yaml              │
│  6  │ 定义智能体角色 (Roles)        │ agent/core/roles/metagenomicist.yaml     │
│  7  │ 注册领域 SOP (CBKB)           │ 运行时通过 CBKB API                      │
│  8  │ 编写领域测试 (Tests)          │ tests/test_metagenomics_*.py             │
└─────┴─────────────────────────────┴─────────────────────────────────────────┘
```

---

## 二、步骤详解：以宏基因组学 (16S) 为例

### 步骤 1: 注册领域技能 (Skills) — **必须**

#### 作用
技能是 HomomicsLab 执行分析的原子单位。每个技能 = `SKILL.md` (元数据 + 模式定义) + `scripts/` (执行代码)。

宏基因组学 16S 分析的典型流程：
```
原始序列 (FASTQ)
    → QC (cutadapt / fastp)         [技能: metagenomics_qc]
    → 去宿主 (bowtie2 host removal)  [技能: metagenomics_dehost]
    → ASV 去噪 (DADA2 / Deblur)     [技能: metagenomics_denoise]
    → 物种注释 (Qiime2 / VSEARCH)   [技能: metagenomics_taxonomy]
    → 功能预测 (PICRUSt2)           [技能: metagenomics_function]
    → 多样性分析 (alpha/beta)       [技能: metagenomics_diversity]
    → 可视化                        [技能: metagenomics_plot]
```

#### 实现

创建技能目录和 `SKILL.md`：

```bash
mkdir -p skills/builtin/metagenomics_qc/scripts/python
mkdir -p skills/builtin/metagenomics_denoise/scripts/python
mkdir -p skills/builtin/metagenomics_taxonomy/scripts/python
mkdir -p skills/builtin/metagenomics_diversity/scripts/python
```

**`skills/builtin/metagenomics_qc/SKILL.md`**:

```yaml
---
id: metagenomics_qc
name: Metagenomics QC
description: Quality control and adapter trimming for 16S amplicon sequencing data
category: metagenomics
runtime: python
input_schema:
  type: object
  required: [fastq_dir, output_dir]
  properties:
    fastq_dir:
      type: string
      description: "Directory containing paired-end FASTQ files"
    output_dir:
      type: string
      description: "Output directory for trimmed reads"
    min_length:
      type: integer
      default: 100
      description: "Minimum read length after trimming"
    quality_threshold:
      type: integer
      default: 20
      description: "Minimum base quality score"
output_schema:
  type: object
  required: [trimmed_reads_dir, n_samples, total_reads, passed_reads]
  properties:
    trimmed_reads_dir:
      type: string
    n_samples:
      type: integer
    total_reads:
      type: integer
    passed_reads:
      type: integer
    qc_report_path:
      type: string
---

# Metagenomics QC

Trim adapters, filter low-quality reads, and remove short reads from 16S amplicon data.

## When to Use

- Raw FASTQ files need preprocessing before denoising
- User mentions "QC", "trim", "filter", "quality control" for metagenomics data

## Parameters

- `fastq_dir` (required) - Directory with paired-end FASTQ files
- `output_dir` (required) - Output directory
- `min_length` - Minimum read length (default: 100)
- `quality_threshold` - Minimum base quality (default: 20)

## Outputs

- `trimmed_reads_dir` - Path to trimmed reads
- `n_samples` - Number of samples processed
- `total_reads` - Total reads before QC
- `passed_reads` - Reads passing QC
```

**`skills/builtin/metagenomics_qc/scripts/python/run.py`**:

```python
"""QC and adapter trimming for 16S amplicon data."""

import json
import sys
import os


def main(skill_inputs: dict) -> dict:
    """Execute the skill."""
    fastq_dir = skill_inputs["fastq_dir"]
    output_dir = skill_inputs["output_dir"]
    min_length = skill_inputs.get("min_length", 100)
    quality_threshold = skill_inputs.get("quality_threshold", 20)

    os.makedirs(output_dir, exist_ok=True)

    # 实际实现会调用 cutadapt / fastp / trimmomatic
    # 以下为示意结构
    n_samples = len([f for f in os.listdir(fastq_dir) if f.endswith(".fastq.gz")])

    return {
        "trimmed_reads_dir": output_dir,
        "n_samples": n_samples,
        "total_reads": n_samples * 50000,   # 示意
        "passed_reads": n_samples * 45000,   # 示意: 90% pass rate
        "qc_report_path": os.path.join(output_dir, "qc_report.html"),
        "min_length": min_length,
        "quality_threshold": quality_threshold,
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
```

#### 为什么必须
没有技能 = 没有可执行的分析步骤。SkillRegistry 只认识 `SKILL.md + scripts/` 格式的技能。这是 HomomicsLab 与外部工具交互的唯一标准化接口。

#### 同技能的其他示例

**`metagenomics_denoise`** (DADA2 / Deblur):
```yaml
input_schema:
  required: [trimmed_reads_dir, output_dir]
  properties:
    trimmed_reads_dir: {type: string}
    output_dir: {type: string}
    trunc_len: {type: integer, default: 240}
    max_ee: {type: integer, default: 2}
output_schema:
  required: [asv_table_path, n_asvs, rep_seqs_path]
  properties:
    asv_table_path: {type: string}
    n_asvs: {type: integer}
    rep_seqs_path: {type: string}
```

**`metagenomics_taxonomy`** (Qiime2 classifier):
```yaml
input_schema:
  required: [rep_seqs_path, classifier_path]
  properties:
    rep_seqs_path: {type: string}
    classifier_path: {type: string, description: "Pre-trained SILVA/Greengenes classifier"}
    confidence: {type: number, default: 0.7}
output_schema:
  required: [taxonomy_path, classified_asvs]
  properties:
    taxonomy_path: {type: string}
    classified_asvs: {type: integer}
```

**`metagenomics_diversity`** (Alpha/Beta diversity):
```yaml
input_schema:
  required: [asv_table_path, metadata_path]
  properties:
    asv_table_path: {type: string}
    metadata_path: {type: string}
    rarefaction_depth: {type: integer, default: 10000}
    group_column: {type: string}
output_schema:
  required: [alpha_div_path, beta_div_path, pcoa_plot_path]
  properties:
    alpha_div_path: {type: string}
    beta_div_path: {type: string}
    pcoa_plot_path: {type: string}
```

---

### 步骤 2: 扩展意图分析器 (IntentAnalyzer) — **必须**

#### 作用
IntentAnalyzer 将用户的自然语言请求转换为结构化的 `UserIntent`。当前代码硬编码了单细胞/空间关键词，如果不扩展，用户说 *"分析我的 16S 测序数据"* 会被错误分类为 `analysis_type="general"`，PlanEngine 会 fallback 到空的 `GENERIC_ANALYSIS` 策略。

#### 当前问题代码

```python
# agent/intent_analyzer.py (当前)
class IntentAnalyzer:
    SINGLE_CELL_KEYWORDS = ["单细胞", "single cell", "scRNA", "10x", "scanpy", "seurat", "PBMC", "细胞", "cell"]
    SPATIAL_KEYWORDS = ["空间", "spatial", "visium", "xenium", "merfish"]
    # ... 没有宏基因组学关键词

    async def analyze(self, message: str) -> UserIntent:
        if any(kw in text for kw in self.SINGLE_CELL_KEYWORDS):
            analysis_type = "single_cell_analysis"
        elif any(kw in text for kw in self.SPATIAL_KEYWORDS):
            analysis_type = "spatial_analysis"
        # ... fallback 到 "general"
```

#### 推荐实现：从硬编码改为配置驱动

**最佳实践**：将关键词和意图映射提取为配置文件，而非硬编码在 Python 中。

**`agent/core/intents/metagenomics.yaml`**:

```yaml
# 新文件：领域意图定义
domain: metagenomics
analysis_type: metagenomics_analysis
keywords:
  - "宏基因组"
  - "16S"
  - "amplicon"
  - "microbiome"
  - "肠道菌群"
  - "qiime"
  - "dada2"
  - "otu"
  - "asv"
  - "taxonomy"
  - "物种注释"
  - "多样性"
  - "alpha diversity"
  - "beta diversity"
  - "picrust"
  - "功能预测"
complexity_indicators:
  - "全流程"
  - "完整分析"
  - "pipeline"
data_scale_patterns:
  - r'(\d+)\s*个样本'
  - r'(\d+)\s*samples'
```

**修改 `agent/intent_analyzer.py`**:

```python
import yaml
from pathlib import Path

class IntentAnalyzer:
    def __init__(self, intents_dir: str = None):
        self.intents_dir = Path(intents_dir) if intents_dir else Path(__file__).parent / "core" / "intents"
        self._load_domain_intents()

    def _load_domain_intents(self):
        """Load intent definitions from YAML configs."""
        self.domain_configs = {}
        if self.intents_dir.exists():
            for yaml_file in self.intents_dir.glob("*.yaml"):
                with open(yaml_file) as f:
                    config = yaml.safe_load(f)
                    self.domain_configs[config["analysis_type"]] = config

    async def analyze(self, message: str) -> UserIntent:
        text = message.lower()

        # 1. QA check (highest priority)
        if any(kw in text for kw in ["什么是", "how to", "怎么", "如何", "explain"]):
            return UserIntent(analysis_type="qa", complexity="direct_response")

        # 2. Domain-specific intent matching (from YAML configs)
        for analysis_type, config in self.domain_configs.items():
            keywords = config.get("keywords", [])
            if any(kw in text for kw in keywords):
                complexity = self._determine_complexity(text, config)
                return UserIntent(
                    analysis_type=analysis_type,
                    complexity=complexity,
                    domain_knowledge=[config["domain"]],
                )

        # 3. Fallback
        return UserIntent(analysis_type="general", complexity="single_step")

    def _determine_complexity(self, text: str, config: dict) -> str:
        indicators = config.get("complexity_indicators", [])
        if any(kw in text for kw in indicators):
            return "complex"
        return "single_step"
```

#### 为什么必须
PlanEngine 通过 `StrategyLibrary.select(intent_analysis_type)` 匹配策略。如果 IntentAnalyzer 返回 `"general"`，PlanEngine 只能匹配 `GENERIC_ANALYSIS` —— 一个只有 4 个空壳阶段的 fallback 策略，没有任何领域知识。用户说 *"做宏基因组分析"* 却得到一个空的通用计划，等于系统无法工作。

---

### 步骤 3: 扩展数据状态 (DataState) — **必须**

#### 作用
`DataState` 是 PlanEngine 做自适应决策的"传感器"。当前的 `DataState` 有单细胞特有的字段（`has_qc`, `has_normalization`, `has_pca`, `has_clustering`, `has_annotation`, `n_cells`, `n_genes`, `batch_detected` 等）。宏基因组学需要完全不同的状态维度。

#### 当前问题

```python
# agent/plan/models.py (当前)
@dataclass
class DataState:
    current_phase: Optional[str] = None
    has_qc: bool = False
    has_normalization: bool = False
    has_pca: bool = False
    has_clustering: bool = False
    has_annotation: bool = False
    n_cells: Optional[int] = None        # ← 宏基因组学没有 "cells"
    n_genes: Optional[int] = None        # ← 宏基因组学没有 "genes"
    n_batches: Optional[int] = None
    batch_detected: bool = False
    low_quality: bool = False
    large_scale: bool = False
```

宏基因组学需要的状态：
- `has_qc` — 通用，保留
- `has_denoising` — 是否已完成 ASV/OTU 去噪
- `has_taxonomy` — 是否已完成物种注释
- `has_function` — 是否已完成功能预测
- `n_samples` — 样本数量（替代 `n_cells`）
- `n_asvs` / `n_otus` — ASV/OTU 数量（替代 `n_genes`）
- `rarefaction_applied` — 是否已做稀疏化
- `paired_end` — 是否是双端测序
- `primer_trimmed` — 是否已去除引物
- `host_contamination` — 宿主污染程度

#### 推荐实现：通用化 DataState

**方案 A：添加领域字段（最小改动）**

```python
# agent/plan/models.py
@dataclass
class DataState:
    # === 通用字段（所有领域共用）===
    current_phase: Optional[str] = None
    has_qc: bool = False
    low_quality: bool = False
    n_samples: Optional[int] = None

    # === 单细胞/空间转录组字段 ===
    has_normalization: bool = False
    has_pca: bool = False
    has_clustering: bool = False
    has_annotation: bool = False
    n_cells: Optional[int] = None
    n_genes: Optional[int] = None
    n_batches: Optional[int] = None
    batch_detected: bool = False
    large_scale: bool = False

    # === 宏基因组学字段 ===
    has_denoising: bool = False
    has_taxonomy: bool = False
    has_function: bool = False
    n_asvs: Optional[int] = None
    n_otus: Optional[int] = None
    rarefaction_applied: bool = False
    paired_end: bool = True
    primer_trimmed: bool = False
    host_contamination: Optional[float] = None

    # === 基因组学字段（预留）===
    has_alignment: bool = False
    has_variant_calling: bool = False
    has_annotation: bool = False  # 与单细胞的 annotation 语义不同，可重命名
    coverage_depth: Optional[float] = None

    # === 蛋白组学字段（预留）===
    has_search: bool = False
    has_quantification: bool = False
    n_proteins: Optional[int] = None
    n_peptides: Optional[int] = None
```

**方案 B：更通用的设计（推荐长期演进）**

```python
# agent/plan/models.py
@dataclass
class DataState:
    """Domain-extensible data state."""
    current_phase: Optional[str] = None
    has_qc: bool = False
    low_quality: bool = False
    n_samples: Optional[int] = None

    # 领域特定状态存储在字典中，避免 dataclass 无限膨胀
    domain_state: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default=None):
        """Get a state value, checking both direct fields and domain_state."""
        return getattr(self, key, self.domain_state.get(key, default))

    def set(self, key: str, value: Any):
        """Set a state value."""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.domain_state[key] = value
```

#### 为什么必须
`StateCheck` 的条件函数直接读取 `DataState` 的字段：

```python
StateCheck(
    condition=lambda ds: ds.batch_detected,   # ← 读取 DataState.batch_detected
    action="insert",
    target="batch_correction",
    after="qc",
)
```

如果宏基因组学的策略需要检查 `host_contamination > 0.1` 来决定是否插入去宿主步骤，但 `DataState` 没有 `host_contamination` 字段，这个 `StateCheck` 就无法表达。

---

### 步骤 4: 创建分析策略 (AnalysisStrategy) — **必须**

#### 作用
策略模板定义了一个领域的"标准分析骨架"。PlanEngine 根据用户意图选择策略，然后根据 `DataState` 自适应调整骨架（插入、跳过、修改参数）。

#### 实现

在 `agent/plan/strategies.py` 中注册新策略：

```python
# ─────────────────────────────────────────
# 宏基因组学策略
# ─────────────────────────────────────────

METAGENOMICS_16S_STANDARD = AnalysisStrategy(
    name="metagenomics_16s_standard",
    description="Standard 16S amplicon sequencing analysis pipeline (QIIME2 / DADA2 workflow)",
    applicable_intents=[
        "metagenomics_analysis",
        "16S",
        "amplicon",
        "microbiome",
        "qiime",
        "dada2",
        "肠道菌群",
    ],
    skeleton=[
        Phase(phase_type="qc", required=True, description="QC and adapter trimming"),
        Phase(phase_type="dehost", required=False, description="Remove host contamination"),
        Phase(phase_type="denoising", required=True, description="ASV denoising (DADA2/Deblur)"),
        Phase(phase_type="taxonomy", required=True, description="Taxonomic classification"),
        Phase(phase_type="diversity", required=False, description="Alpha and beta diversity analysis"),
        Phase(phase_type="function", required=False, description="Functional prediction (PICRUSt2)"),
        Phase(phase_type="visualization", required=False, description="Generate diversity plots and taxonomic bar charts"),
    ],
    state_checks=[
        # 如果宿主污染率 > 10%，插入去宿主步骤
        StateCheck(
            condition=lambda ds: ds.host_contamination is not None and ds.host_contamination > 0.1,
            action="insert",
            target="dehost",
            after="qc",
        ),
        # 如果样本数 < 3，跳过多样性分析（统计效力不足）
        StateCheck(
            condition=lambda ds: ds.n_samples is not None and ds.n_samples < 3,
            action="skip",
            target="diversity",
        ),
        # 如果用户未提供 metadata，跳过多样性分析（需要分组信息）
        StateCheck(
            condition=lambda ds: not ds.get("has_metadata", False),
            action="skip",
            target="diversity",
        ),
        # 如果数据质量低（通过率低），收紧去噪参数
        StateCheck(
            condition=lambda ds: ds.low_quality,
            action="modify_param",
            target="denoising",
            value={"max_ee": 1, "trunc_len": 200},
        ),
        # 如果 ASV 数量 > 50,000，标记为大规模数据集
        StateCheck(
            condition=lambda ds: ds.n_asvs is not None and ds.n_asvs > 50000,
            action="modify_param",
            target="denoising",
            value={"use_pool": True, "n_threads": 8},
        ),
    ],
)
```

然后在 `StrategyLibrary._register_defaults()` 中注册：

```python
def _register_defaults(self) -> None:
    self.register(SINGLE_CELL_STANDARD)
    self.register(SPATIAL_TRANSCRIPTOMICS)
    self.register(QC_ONLY)
    self.register(METAGENOMICS_16S_STANDARD)  # ← 新增
```

#### 为什么必须
策略是 PlanEngine 的"领域知识库"。没有宏基因组学策略，即使用户说 *"分析我的 16S 数据"*，PlanEngine 也不知道该做什么。它会生成一个空的 `GENERIC_ANALYSIS` 计划，里面只有 `data_loading → exploratory → analysis → visualization` 四个没有任何实质内容的阶段。

策略的核心价值：
- **骨架 (skeleton)**: 告诉系统"宏基因组学分析的标准步骤是什么"
- **状态检查 (state_checks)**: 告诉系统"当数据出现 X 特征时，应该做 Y 调整"
- **意图映射 (applicable_intents)**: 告诉系统"当用户提到这些关键词时，使用本策略"

---

### 步骤 5: 种子技能图谱 (SkillDAG) — **推荐**

#### 作用
SkillDAG 记录技能之间的关系（`followed_by`, `conflicts_with`, `alternative_to`, `depends_on`）。种子边为系统提供一个初始的"骨架知识"，后续边会在运行时从执行历史中自动学习进化。

#### 实现

在 `skills/skill_dag_seeds.yaml` 中添加宏基因组学种子边：

```yaml
# === Metagenomics 16S standard flow ===
- from: metagenomics_qc
  to: metagenomics_dehost
  type: followed_by
  context: "QC → remove host contamination"

- from: metagenomics_qc
  to: metagenomics_denoise
  type: followed_by
  context: "QC → ASV denoising (if no host contamination)"

- from: metagenomics_dehost
  to: metagenomics_denoise
  type: followed_by
  context: "Host removal → ASV denoising"

- from: metagenomics_denoise
  to: metagenomics_taxonomy
  type: followed_by
  context: "ASV table → taxonomic classification"

- from: metagenomics_taxonomy
  to: metagenomics_diversity
  type: followed_by
  context: "Taxonomy → diversity analysis"

- from: metagenomics_taxonomy
  to: metagenomics_function
  type: followed_by
  context: "Taxonomy → functional prediction"

# === Hard dependencies ===
- from: metagenomics_denoise
  to: metagenomics_qc
  type: depends_on
  context: "Denoising requires QC-filtered reads"

- from: metagenomics_taxonomy
  to: metagenomics_denoise
  type: depends_on
  context: "Taxonomy requires ASV representative sequences"

- from: metagenomics_function
  to: metagenomics_taxonomy
  type: depends_on
  context: "PICRUSt2 requires taxonomy annotations"

# === Conflicts ===
- from: metagenomics_denoise
  to: metagenomics_otu_clustering
  type: conflicts_with
  context: "ASV and OTU are redundant approaches to the same data"

# === Alternatives ===
- from: metagenomics_denoise
  to: metagenomics_otu_clustering
  type: alternative_to
  context: "OTU clustering is an alternative to ASV denoising"

- from: metagenomics_taxonomy
  to: metagenomics_taxonomy_blast
  type: alternative_to
  context: "BLAST-based taxonomy is an alternative to classifier-based taxonomy"
```

#### 为什么推荐（非必须）
SkillDAG 的种子边是**bootstrap 数据**，不是强制要求。即使没有种子边，SkillDAG 也会在运行时从执行历史中**自动学习**技能关系（`CANDIDATE` → `CONFIRMED`）。但种子边的作用是：

1. **冷启动加速**: 新领域没有历史数据时，种子边提供初始的指导关系
2. **防止早期错误**: 没有种子边时，系统可能在积累足够数据前做出次优选择
3. **文档价值**: 种子边本身就是领域最佳实践的文档化

对于生产环境，建议提供种子边；对于实验环境，可以依赖运行时学习。

---

### 步骤 6: 定义智能体角色 (Roles) — **推荐**

#### 作用
AgentCore 的 1+N 模型中，Analyst 协调，Specialists 按需生成。角色的 YAML 配置决定了 Specialist 能访问哪些技能、工具和权限。

#### 实现

创建 `agent/core/roles/metagenomicist.yaml`：

```yaml
role_id: metagenomicist
name: Metagenomicist
description: Specialist in microbiome and metagenomics analysis
allowed_skills:
  - metagenomics_qc
  - metagenomics_dehost
  - metagenomics_denoise
  - metagenomics_taxonomy
  - metagenomics_function
  - metagenomics_diversity
  - metagenomics_plot
  - data_loader
allowed_tools:
  - file_read
  - file_write
  - file_list
  - shell_exec
permissions:
  can_execute: true
  can_spawn_specialist: false
  max_concurrent_tasks: 4
priority: 2
```

#### 为什么推荐
没有角色定义时，AgentCore 无法为宏基因组学任务分配正确的 Specialist。`resolve_agent_for_task()` 会 fallback 到 Analyst，而 Analyst 的角色可能不包含宏基因组学技能，导致任务无法执行。

角色隔离的价值：
- **权限控制**: 宏基因组 Specialist 不能访问单细胞技能（反之亦然），防止领域混淆
- **资源分配**: 可以为不同领域的 Specialist 配置不同的并发限制
- **专业化提示**: 角色的 `description` 会注入到 Agent 的系统提示中，影响代码生成质量

---

### 步骤 7: 注册领域 SOP (CBKB) — **生产级**

#### 作用
CBKB 的 LabSOP 层存储最佳实践模板。通过 API 注册宏基因组学 SOP，使 CBKBCurator 能够：
- 检测实际分析是否偏离 SOP
- 自动提取新的最佳实践
- 生成叙事报告时引用 SOP

#### 实现

```python
from homomics_lab.knowledge.cbkb import CBKB, LabSOP

cbkb = CBKB()

sop = LabSOP(
    id="sop_16s_qiime2_v1",
    title="16S Amplicon Analysis Standard Operating Procedure (QIIME2 Workflow)",
    version="1.0.0",
    category="metagenomics",
    locked=False,
    content="""
## Standard 16S Analysis Workflow

### 1. QC and Trimming
- Trim adapters with cutadapt
- Minimum read length: 100bp
- Minimum quality: Q20
- Expected pass rate: > 85%

### 2. Denoising (DADA2)
- trunc_len: auto-determined from quality profile
- max_ee: 2
- chimera removal: consensus method

### 3. Taxonomy
- Classifier: SILVA 138 99% OTUs
- Confidence threshold: 0.7
- Unclassified ASVs: report but exclude from downstream

### 4. Diversity
- Rarefaction depth: determined from rarefaction curve knee
- Alpha metrics: Shannon, Simpson, Observed OTUs
- Beta metric: Bray-Curtis (unweighted) + weighted UniFrac
- PCoA + PERMANOVA for group comparison

### 5. Quality Gates
- If pass rate < 70% → escalate to user (possible sequencing failure)
- If n_samples < 3 → skip diversity analysis
- If host contamination > 15% → mandatory dehosting step
""",
)

cbkb.create_sop(sop)
```

#### 为什么生产级
SOP 不是系统运行的必要条件（没有 SOP，系统仍然可以执行分析）。但 SOP 在以下场景中至关重要：

1. **质量控制**: CBKBCurator 可以比较实际执行与 SOP 的差异，标记偏离
2. **新人培训**: SOP 本身就是可执行的文档
3. **审计合规**: GLP/GMP 环境需要可版本控制的 SOP
4. **自动进化**: AgentEvolutionEngine 可以从成功的执行中提取模式，提议更新 SOP

---

### 步骤 8: 编写领域测试 — **必须**

#### 作用
确保新领域的端到端流程正确工作。测试覆盖：意图分析 → 策略选择 → 计划生成 → 状态检查 → 技能执行 → CBKB 归档。

#### 实现

**`tests/test_metagenomics_integration.py`**:

```python
import pytest
from homomics_lab.agent.intent_analyzer import IntentAnalyzer, UserIntent
from homomics_lab.agent.plan.strategies import StrategyLibrary, METAGENOMICS_16S_STANDARD
from homomics_lab.agent.plan.models import DataState
from homomics_lab.agent.core.agent_core import AgentCore
from homomics_lab.skills.registry import SkillRegistry


class TestMetagenomicsIntentAnalysis:
    """Test intent analyzer recognizes metagenomics requests."""

    @pytest.mark.asyncio
    async def test_16s_intent(self):
        analyzer = IntentAnalyzer()
        intent = await analyzer.analyze("分析我的 16S 测序数据")
        assert intent.analysis_type == "metagenomics_analysis"
        assert intent.complexity == "single_step"

    @pytest.mark.asyncio
    async def test_microbiome_full_pipeline_intent(self):
        analyzer = IntentAnalyzer()
        intent = await analyzer.analyze("做肠道菌群的完整宏基因组分析流程")
        assert intent.analysis_type == "metagenomics_analysis"
        assert intent.complexity == "complex"
        assert "metagenomics" in intent.domain_knowledge

    @pytest.mark.asyncio
    async def test_qiime_intent(self):
        analyzer = IntentAnalyzer()
        intent = await analyzer.analyze("用 QIIME2 处理我的 amplicon 数据")
        assert intent.analysis_type == "metagenomics_analysis"


class TestMetagenomicsStrategy:
    """Test strategy selection and plan generation."""

    def test_strategy_registration(self):
        lib = StrategyLibrary()
        assert lib.get("metagenomics_16s_standard") is not None

    def test_strategy_selection(self):
        lib = StrategyLibrary()
        strategy = lib.select("metagenomics_analysis")
        assert strategy.name == "metagenomics_16s_standard"

    def test_skeleton_generation(self):
        strategy = METAGENOMICS_16S_STANDARD
        data_state = DataState(has_qc=False, n_samples=10)
        phases = strategy.generate_skeleton(data_state)
        phase_types = [p.phase_type for p in phases]
        assert "qc" in phase_types
        assert "denoising" in phase_types
        assert "taxonomy" in phase_types

    def test_host_contamination_insert(self):
        """If host contamination > 10%, dehost step should be inserted."""
        strategy = METAGENOMICS_16S_STANDARD
        data_state = DataState(
            has_qc=True,
            host_contamination=0.15,
            n_samples=10,
        )
        phases = strategy.generate_skeleton(data_state)
        phase_types = [p.phase_type for p in phases]
        assert "dehost" in phase_types

    def test_low_sample_skip_diversity(self):
        """If n_samples < 3, diversity should be skipped."""
        strategy = METAGENOMICS_16S_STANDARD
        data_state = DataState(
            has_qc=True,
            n_samples=2,
        )
        phases = strategy.generate_skeleton(data_state)
        phase_types = [p.phase_type for p in phases]
        assert "diversity" not in phase_types

    def test_low_quality_modify_params(self):
        """If data quality is low, denoising params should tighten."""
        strategy = METAGENOMICS_16S_STANDARD
        data_state = DataState(
            has_qc=True,
            low_quality=True,
        )
        phases = strategy.generate_skeleton(data_state)
        denoising_phase = next(p for p in phases if p.phase_type == "denoising")
        assert denoising_phase.parameters.get("max_ee") == 1


class TestMetagenomicsSkillRegistration:
    """Test skills are discoverable and executable."""

    def test_metagenomics_skills_loaded(self):
        registry = SkillRegistry()
        registry.load_all()
        assert registry.get("metagenomics_qc") is not None
        assert registry.get("metagenomics_denoise") is not None
        assert registry.get("metagenomics_taxonomy") is not None

    def test_skill_schema_validation(self):
        """Skill inputs/outputs must validate against declared schemas."""
        from homomics_lab.stability.schema_validator import SchemaValidator
        from homomics_lab.skills.registry import SkillRegistry

        registry = SkillRegistry()
        registry.load_all()
        skill = registry.get("metagenomics_qc")

        # Valid input
        valid_input = {
            "fastq_dir": "/data/fastq",
            "output_dir": "/data/qc",
            "min_length": 100,
            "quality_threshold": 20,
        }
        assert SchemaValidator.validate(skill.input_schema, valid_input).is_valid

        # Invalid input (missing required)
        invalid_input = {"fastq_dir": "/data/fastq"}
        result = SchemaValidator.validate(skill.input_schema, invalid_input)
        assert not result.is_valid


class TestMetagenomicsAgentResolution:
    """Test AgentCore correctly assigns metagenomics tasks to specialists."""

    def test_metagenomics_task_routing(self):
        """Metagenomics tasks should be routed to metagenomicist specialist."""
        # This tests AgentCore.resolve_agent_for_task()
        pass  # Implementation depends on AgentCore setup

    def test_skill_dag_conflict_detection(self):
        """ASV denoising and OTU clustering should be flagged as conflicting."""
        from homomics_lab.skills.skill_dag import SkillDAG
        dag = SkillDAG()
        # dag.load_seeds()  # loads from skill_dag_seeds.yaml
        conflicts = dag.get_conflicts("metagenomics_denoise")
        assert "metagenomics_otu_clustering" in conflicts
```

#### 为什么必须
- **回归保护**: 防止后续修改破坏宏基因组学流程
- **文档价值**: 测试本身就是领域流程的可执行文档
- **集成验证**: 确保意图分析 → 策略选择 → 计划生成 → 技能执行 的完整链路畅通

---

## 三、扩展到其他领域的快速对照

| 领域 | 典型技能 | 关键 DataState 字段 | 核心策略 | 意图关键词 |
|---|---|---|---|---|
| **基因组学 (GWAS)** | `bwa_mem`, `gatk_haplotypecaller`, `vep_annotate`, `plink_gwas` | `has_alignment`, `has_variant_calling`, `coverage_depth`, `n_variants` | `genomics_gwas_standard` | "GWAS", "全基因组", "variant", "SNP", "plink", "GATK" |
| **蛋白组学 (DIA)** | `dia_nn_search`, `percolator`, `perseus_de`, `msstats` | `has_search`, `has_quantification`, `n_proteins`, `n_peptides`, `missing_rate` | `proteomics_dia_standard` | "proteomics", "DIA", "质谱", "MaxQuant", "蛋白组" |
| **代谢组学 (LC-MS)** | `xcms_peakpicking`, `camara_anno`, `metaboanalyst` | `has_peak_picking`, `has_annotation`, `n_features`, `qc_cv_threshold` | `metabolomics_lcms_standard` | "metabolomics", "代谢组", "LC-MS", "XCMS", "代谢物" |
| **表观遗传 (ChIP-seq)** | `bowtie2_chip`, `macs2_callpeak`, `deeptools`, `homer_motif` | `has_alignment`, `has_peaks`, `peak_count`, `frip_score` | `epigenomics_chipseq_standard` | "ChIP-seq", "表观遗传", "peak calling", "MACS2" |
| **宏基因组 (WGS)** | `kraken2`, `bracken`, `humann3`, `metaphlan` | `has_taxonomy`, `has_function`, `n_reads_classified` | `metagenomics_wgs_standard` | "宏基因组", "metagenomics", "Kraken", "HUMAnN" |

---

## 四、常见陷阱与最佳实践

### 陷阱 1: Phase 类型命名冲突

不同领域可能使用相同的 `phase_type` 名称但语义不同。例如：
- 单细胞的 `annotation` = 细胞类型注释
- 基因组学的 `annotation` = 变异功能注释 (VEP)

**解决方案**: 使用领域前缀：`sc_annotation`, `genomics_annotation`。

### 陷阱 2: DataState 字段膨胀

每扩展一个领域就添加 10 个字段，`DataState` 会迅速膨胀到几十个字段。

**解决方案**: 长期演进方向是使用 `domain_state: Dict[str, Any]` 存储领域特定状态（见步骤 3 方案 B）。

### 陷阱 3: 意图关键词重叠

"QC" 在单细胞和宏基因组学中都是有效关键词，可能导致意图误判。

**解决方案**: 
- 使用更具体的关键词（如 `scanpy_qc` vs `fastp_qc`）
- 结合数据文件格式判断（`.h5ad` → 单细胞, `.fastq` + `16S` → 宏基因组）
- 在 `UserIntent` 中增加 `domain_hint` 字段

### 陷阱 4: Skill 的 `category` 字段未正确使用

`category` 字段用于 SkillRegistry 的过滤和搜索。如果不正确设置，语义搜索可能返回不相关的结果。

**最佳实践**: 
```yaml
category: metagenomics   # 不是 "single-cell" 或 "general"
```

### 陷阱 5: 忽略 Schema 的 `description` 字段

Schema 的 `description` 不仅用于文档，还用于 LLM 生成代码时的提示词注入。

**最佳实践**: 为每个参数写清晰的描述，包含默认值、单位、取值范围。

---

## 五、总结：扩展的本质

将 HomomicsLab 扩展到新领域，本质上是回答三个问题：

1. **这个领域的标准分析流程是什么？** → 答案写入 `AnalysisStrategy` 的 skeleton
2. **当数据出现什么特征时，流程应该如何调整？** → 答案写入 `AnalysisStrategy` 的 state_checks
3. **这个领域有哪些工具，它们的输入输出是什么？** → 答案写入 `SKILL.md + scripts/`

HomomicsLab 的**架构层**（AgentCore, PlanEngine, DynamicReplanningEngine, SkillDAG, CBKB, ReproducibilityEngine）完全不需要修改。扩展是**配置层的填充**，而非**架构层的重构**。

> **单细胞 → 宏基因组学的扩展工作量**: ~4 个 SKILL.md + 1 个策略定义 + 1 个意图 YAML + 1 个角色 YAML + ~15 个测试 = **约 1-2 人天**（不含技能脚本的实际实现）。
