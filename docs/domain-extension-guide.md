# HomomicsLab 领域扩展完全指南（v0.4.1 — 智能化扩展）

> **目标读者**: 希望将 HomomicsLab 扩展到基因组学、蛋白组学、微生物组学、代谢组学等领域的开发者。
>
> **核心前提**: HomomicsLab 的架构是领域无关的。扩展过程已从"手动修改 5+ 分散文件"升级为"单文件声明 + CLI 一键生成 + LLM 辅助 + 运行时热加载"。
>
> **本文示例**: 以 **宏基因组学 (16S Amplicon Sequencing)** 为完整示例。

---

## 一、快速开始（30 秒扩展一个领域）

```bash
# 方法 1: CLI 脚手架生成
homomics domain init metagenomics \
  --phases "qc,dehost,denoising,taxonomy,diversity,function,visualization"

# 方法 2: LLM 辅助生成（需要 OPENAI_API_KEY）
homics domain generate \
  "16S amplicon sequencing analysis: QC with cutadapt, denoise with DADA2, classify with SILVA, diversity analysis with QIIME2, functional prediction with PICRUSt2"

# 验证
cd metagenomics
homomics validate domain.yaml

# 安装到 HomomicsLab
homomics install . --domains-dir ../backend/homomics_lab/domains
```

完成。不需要修改任何 Python 代码。

---

## 二、扩展全景图（新旧对比）

### v0.4.0（手动扩展）→ v0.4.1（智能化扩展）

| 步骤 | v0.4.0 手动方式 | v0.4.1 智能化方式 | 时间对比 |
|:---|:---|:---|:---|
| 1. 技能注册 | 手动创建 `skills/*/SKILL.md + scripts/` | `homomics domain init` 自动生成骨架 | 30 min → 2 min |
| 2. 意图分析 | 硬编码 Python 关键词列表 | `domain.yaml` 中的 `intents:` 声明，自动加载 | 15 min → 0 min |
| 3. 数据状态 | 修改 `models.py` 添加字段 | `domain_state` 命名空间自动隔离 | 10 min → 0 min |
| 4. 分析策略 | 修改 `strategies.py` 添加常量 | `domain.yaml` 中的 `phases:` + `state_checks:` | 30 min → 5 min |
| 5. DAG 种子 | 修改 `skill_dag_seeds.yaml` | `domain.yaml` 中的 `dag_seeds:` | 10 min → 3 min |
| 6. 角色定义 | 创建 `roles/*.yaml` | `domain.yaml` 中的 `roles:` | 10 min → 2 min |
| 7. SOP | 运行时 API 调用 | `domain.yaml` 中的 `sops:` | 15 min → 5 min |
| 8. 测试 | 手动编写 | `homomics domain init` 生成测试骨架 | 20 min → 2 min |
| **总计** | **~2.5 人天** | **~20 分钟** | **提升 ~18 倍** |

---

## 三、核心组件：`domain.yaml` 单文件声明

`domain.yaml` 是 HomomicsLab v0.4.1 引入的**单文件领域声明格式**。一个文件替代了原来分散在 5+ 位置的配置。

### 完整示例：宏基因组学

```yaml
domain: metagenomics_16s
description: Standard 16S amplicon sequencing analysis pipeline (QIIME2 / DADA2)
version: "1.0.0"

# ── 分析策略 ──
phases:
  - id: qc
    required: true
    description: QC and adapter trimming
    skills: [metagenomics_qc]

  - id: dehost
    required: false
    description: Remove host contamination
    skills: [metagenomics_dehost]

  - id: denoising
    required: true
    description: ASV denoising (DADA2/Deblur)
    skills: [metagenomics_denoise]

  - id: taxonomy
    required: true
    description: Taxonomic classification
    skills: [metagenomics_taxonomy]

  - id: diversity
    required: false
    description: Alpha and beta diversity
    skills: [metagenomics_diversity]

  - id: visualization
    required: false
    description: Generate plots
    skills: [metagenomics_plot]

# ── 状态自适应 ──
state_checks:
  - condition: "host_contamination > 0.1"
    action: insert
    target: dehost
    after: qc

  - condition: "n_samples < 3"
    action: skip
    target: diversity

  - condition: "low_quality"
    action: modify_param
    target: denoising
    value: {max_ee: 1, trunc_len: 200}

# ── 意图识别 ──
intents:
  - analysis_type: metagenomics_analysis
    keywords:
      - "宏基因组"
      - "16S"
      - "microbiome"
      - "qiime"
      - "dada2"
    complexity_indicators:
      - "全流程"
      - "pipeline"

# ── SkillDAG 种子 ──
dag_seeds:
  - from: metagenomics_qc
    to: metagenomics_denoise
    type: followed_by
    context: "QC → denoising"

  - from: metagenomics_denoise
    to: metagenomics_taxonomy
    type: followed_by
    context: "Denoising → taxonomy"

# ── 智能体角色 ──
roles:
  - role_id: metagenomicist
    name: Metagenomicist
    allowed_skills:
      - metagenomics_qc
      - metagenomics_denoise
      - metagenomics_taxonomy
    allowed_tools: [file_read, file_write, shell_exec]
    permissions:
      can_execute: true
    priority: 2

# ── 标准操作程序 ──
sops:
  - id: sop_16s_v1
    title: 16S Amplicon Analysis SOP
    version: "1.0.0"
    content: |
      ## Standard 16S Workflow
      1. QC: cutadapt, min length 100bp, Q20
      2. Denoising: DADA2, max_ee=2
      3. Taxonomy: SILVA 138, confidence=0.7

# ── 数据状态模式 ──
data_state_schema:
  host_contamination:
    type: number
    description: Host contamination rate (0.0-1.0)
  n_asvs:
    type: integer
    description: Number of ASVs after denoising

# ── 技能目录（相对路径）─
skills_dir: skills
```

### 字段说明

| 字段 | 必需 | 说明 |
|:---|:---|:---|
| `domain` | ✅ | 领域唯一标识符 |
| `phases` | ✅ | 分析阶段骨架（PlanEngine 策略来源） |
| `state_checks` | | 数据状态触发的计划调整 |
| `intents` | ✅ | 用户意图识别配置 |
| `dag_seeds` | | SkillDAG 初始种子边 |
| `roles` | | AgentCore 角色定义 |
| `sops` | | CBKB 标准操作程序 |
| `data_state_schema` | | 领域特定 DataState 字段文档 |
| `skills_dir` | | 技能目录相对路径 |

---

## 四、CLI 工具详解

### `homomics domain init` — 初始化领域骨架

```bash
# 基础用法
homomics domain init metagenomics

# 指定阶段
homomics domain init metagenomics \
  --phases "qc,denoising,taxonomy,diversity"

# 从模板生成
homomics domain init genomics \
  --template genomics \
  --output ./domains

# 输出
# metagenomics/
# ├── domain.yaml          # 完整声明文件
# └── skills/              # 技能目录
```

### `homomics domain validate` — 验证声明完整性

```bash
homomics validate domain.yaml
# Syntax: OK (metagenomics_16s v1.0.0)
# Validation: OK
# Summary:
#   Phases: 7
#   State checks: 5
#   Intents: 1
#   DAG seeds: 6
#   Roles: 1
#   SOPs: 1
```

验证器检查：
- YAML 语法和 Pydantic Schema 合规性
- Phase 引用的技能是否已注册
- StateCheck 的目标阶段是否存在
- DAG 种子引用的技能是否已知
- 意图类型是否重复
- 条件表达式的语法有效性

### `homomics domain generate` — LLM 辅助生成

```bash
export OPENAI_API_KEY=sk-...

homomics domain generate \
  "Proteomics DIA analysis: search with DIA-NN, quantify with MSstats, differential expression with Perseus. Skip quantification if fewer than 3 replicates per condition."

# 自动生成：
# - domain.yaml（完整策略、状态检查、意图）
# - skills/（SKILL.md 骨架 + Python 脚本 stub）
# - 所有配置基于领域知识
```

### `homomics domain install` — 安装领域

```bash
# 从本地目录
homomics install ./metagenomics --domains-dir ./backend/homomics_lab/domains

# 从 Git 仓库
homomics install https://github.com/my-lab/homomics-metagenomics.git

# 安装后自动加载，无需重启
```

### `homomics domain list` — 列出已安装领域

```bash
homomics list --domains-dir ./backend/homomics_lab/domains
# Installed domains (3):
#   single_cell_standard (v1.0.0)
#   spatial_transcriptomics (v1.0.0)
#   metagenomics_16s (v1.0.0)
```

---

## 五、运行时热加载

### 无需重启的扩展

```python
from homomics_lab.domain.hot_reload import DomainHotReloader, SkillHotReloader
from homomics_lab.domain.registry import get_domain_registry
from homomics_lab.domain.loader import DomainLoader
from homomics_lab.skills.registry import get_default_registry
from homomics_lab.agent.plan.strategies import StrategyLibrary

# 初始化热加载器
registry = get_domain_registry()
loader = DomainLoader(get_default_registry(), StrategyLibrary())
domain_reloader = DomainHotReloader(registry, loader)
skill_reloader = SkillHotReloader(get_default_registry())

# 监控领域文件变化
domain_reloader.watch_domain(Path("./domains/metagenomics/domain.yaml"))

# 监控技能目录变化
skill_reloader.watch_skills_directory(Path("./domains/metagenomics/skills"))

# 启动监控（后台 asyncio 任务）
await domain_reloader.start()
await skill_reloader.start()
```

热加载行为：
- `domain.yaml` 修改 → 自动卸载旧领域 → 重新加载新配置 → 更新 StrategyLibrary
- `SKILL.md` 修改 → 重新解析技能元数据 → 更新 SkillRegistry
- `scripts/*.py` 修改 → 重新加载执行代码 → 下次调用使用新版本

---

## 六、DataState 通用化：领域状态隔离

v0.4.1 重构了 `DataState`，引入 `domain_state` 命名空间，避免字段膨胀：

```python
from homomics_lab.agent.plan.models import DataState

ds = DataState(has_qc=True, n_samples=10)

# 单细胞领域状态
ds.set("n_cells", 5000, domain="single_cell")
ds.set("batch_detected", True, domain="single_cell")

# 宏基因组学领域状态
ds.set("host_contamination", 0.15, domain="metagenomics")
ds.set("n_asvs", 45000, domain="metagenomics")

# 通用访问（自动搜索所有命名空间）
print(ds.get("n_cells"))           # 5000
print(ds.get("host_contamination")) # 0.15
print(ds.get("nonexistent"))        # None

# 指定命名空间访问
print(ds.get("n_asvs", domain="metagenomics"))  # 45000

# 生成上下文描述
print(ds.to_context())
# "QC completed, 10 samples, single_cell.n_cells=5000,
#  single_cell.batch_detected, metagenomics.host_contamination=0.15,
#  metagenomics.n_asvs=45000"
```

`StateCheck` 条件表达式自动支持命名空间字段：

```yaml
state_checks:
  - condition: "host_contamination > 0.1"
    # 自动在 domain_state["metagenomics"] 中查找 host_contamination
```

---

## 七、配置驱动意图分析器

v0.4.1 的 `IntentAnalyzer` 不再硬编码关键词，而是从 `DomainRegistry` 动态加载：

```python
from homomics_lab.agent.intent_analyzer_v2 import IntentAnalyzer

analyzer = IntentAnalyzer(use_domain_registry=True)

# 自动识别宏基因组学意图
intent = await analyzer.analyze("分析我的 16S 测序数据")
print(intent.analysis_type)  # "metagenomics_analysis"
print(intent.confidence)      # 1.2 (基于关键词匹配分数)

# 支持多语言
intent = await analyzer.analyze("Do microbiome analysis on my gut samples")
print(intent.analysis_type)  # "metagenomics_analysis"

# 复杂度自动判断
intent = await analyzer.analyze("做肠道菌群的完整宏基因组分析流程")
print(intent.complexity)      # "complex" (匹配 complexity_indicators)
```

### 运行时注册新意图

```python
analyzer.register_intent("proteomics_analysis", {
    "domain": "proteomics",
    "keywords": ["proteomics", "DIA", "质谱", "MaxQuant"],
    "complexity_indicators": ["workflow", "pipeline"],
})
```

---

## 八、扩展到其他领域的快速对照

### 单文件声明示例

| 领域 | 核心阶段 | 关键 StateCheck | 意图关键词 |
|:---|:---|:---|:---|
| **基因组学 (GWAS)** | `alignment → variant_calling → annotation → gwas` | `coverage_depth < 10 → skip_gwas` | "GWAS", "全基因组", "GATK" |
| **蛋白组学 (DIA)** | `search → quantification → de_analysis` | `n_replicates < 3 → skip_de` | "proteomics", "DIA", "质谱" |
| **代谢组学 (LC-MS)** | `peak_picking → alignment → annotation → stats` | `qc_cv > 0.3 → flag_drift` | "metabolomics", "代谢组", "XCMS" |
| **表观遗传 (ChIP)** | `alignment → peak_calling → motif → visualization` | `frip < 0.01 → flag_quality` | "ChIP-seq", "表观遗传", "MACS2" |
| **宏基因组 (WGS)** | `qc → classify → function → pathway` | `host_reads > 50% → flag` | "宏基因组", "Kraken", "HUMAnN" |

### LLM 辅助生成提示词模板

```bash
# 基因组学
homomics domain generate \
  "Whole genome sequencing variant calling: BWA-MEM alignment, GATK HaplotypeCaller for SNP/indel calling, VEP annotation, PLINK for GWAS. Skip GWAS if fewer than 100 samples."

# 蛋白组学
homomics domain generate \
  "DIA proteomics: DIA-NN search against spectral library, MSstats for protein quantification, Perseus for differential expression. Use MaxLFQ for label-free quantification."

# 代谢组学
homomics domain generate \
  "LC-MS metabolomics: XCMS for peak picking and alignment, CAMERA for annotation, MetaboAnalyst for statistical analysis and pathway enrichment."
```

---

## 九、常见陷阱（已在新架构中自动避免）

| 陷阱 | v0.4.0 手动扩展 | v0.4.1 自动防护 |
|:---|:---|:---|
| Phase 类型命名冲突 | 不同领域都用 `annotation` | `domain.yaml` 中的 `id` 自动带领域前缀 |
| DataState 字段膨胀 | 每加一个领域 +10 个字段 | `domain_state` 命名空间隔离 |
| 意图关键词重叠 | "QC" 同时匹配单细胞和宏基因组 | 置信度评分 + 上下文歧义检测 |
| 技能引用死链 | 策略引用不存在的技能 | `homomics validate` 自动检测 |
| 忘记注册策略 | 写了策略但没加到 StrategyLibrary | `DomainLoader.load()` 自动注册 |
| 忘记重启服务 | 新增技能不生效 | 热加载自动生效 |
| YAML 语法错误 | 启动时崩溃 | `homomics validate` 提前捕获 |

---

## 十、总结：扩展的本质

### v0.4.1 的核心改进

1. **单文件声明** (`domain.yaml`) — 替代 5+ 分散配置文件
2. **CLI 脚手架** (`homomics domain init/validate/install`) — 替代手动创建目录和文件
3. **LLM 辅助生成** (`homomics domain generate`) — 替代从零手写配置
4. **运行时热加载** — 替代重启服务
5. **DataState 命名空间** — 替代字段膨胀
6. **配置驱动意图分析** — 替代硬编码关键词

### 架构层零修改原则

> **AgentCore, PlanEngine, DynamicReplanningEngine, SkillDAG, CBKB, CBKBCurator, ReproducibilityEngine, AgentSwarm, AgentEvolutionEngine, SchemaValidator, VersionLocker** — 这些核心组件在 v0.4.1 中**完全不需要修改**。
>
> 扩展新领域 = 写一个 `domain.yaml` + 运行 `homomics validate` + `homomics install`。

### 工作量对比

| 任务 | v0.4.0 | v0.4.1 |
|:---|:---|:---|
| 单细胞 → 宏基因组学 | ~1.5 人天 | **~20 分钟** |
| 验证配置正确性 | 运行全量测试 | **`homomics validate` 秒级** |
| 调试配置错误 | 服务启动失败 → 排查 | **验证器精确指出问题行** |
| 支持新团队成员 | 阅读 5+ 文件理解扩展方式 | **`homomics domain init` 自解释** |
