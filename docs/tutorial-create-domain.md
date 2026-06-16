> 目标：从零开始创建一个 HomomicsLab 领域（domain），包含分析策略、意图识别、角色和 3 个技能。

# 教程：从零创建一个领域

## 前置条件

- HomomicsLab 后端已启动（`uvicorn homomics_lab.main:app --port 8080`）
- 已安装 `homomics` CLI（`pip install -e ".[dev,test]"`）

## 步骤 1：初始化领域目录

```bash
homomics domain init metagenomics_16s --phases "qc,denoising,taxonomy,diversity"
```

这会生成 `metagenomics_16s/domain.yaml` 骨架。

## 步骤 2：编辑 domain.yaml

```yaml
domain: metagenomics_16s
display_name: "16S Metagenomics"
description: "16S rRNA amplicon analysis domain"

phases:
  - id: qc
    skills: [fastqc, multiqc]
  - id: denoising
    skills: [dada2_denoise]
  - id: taxonomy
    skills: [assign_taxonomy]
  - id: diversity
    skills: [alpha_diversity, beta_diversity]

state_checks:
  - condition: "low_quality"
    action: insert
    target: additional_qc
    after: qc

intents:
  - analysis_type: metagenomics_analysis
    keywords: ["16S", "microbiome", "amplicon"]

roles:
  - role_id: metagenomicist
    name: Metagenomics Specialist
    allowed_skills: [fastqc, multiqc, dada2_denoise, assign_taxonomy, alpha_diversity, beta_diversity]
    allowed_tools: [file_read, file_write, shell_exec]
    permissions:
      can_execute: true
      can_spawn_specialist: false
      max_concurrent_tasks: 3

sops:
  - id: sop_16s_v1
    title: 16S Analysis SOP
    steps:
      - "Run QC on raw reads"
      - "Denoise with DADA2"
      - "Assign taxonomy against Silva"
      - "Compute diversity metrics"

dag_seeds:
  - from: fastqc
    to: dada2_denoise
    relation: followed_by
  - from: dada2_denoise
    to: assign_taxonomy
    relation: followed_by
```

## 步骤 3：创建技能

### fastqc

```bash
mkdir -p metagenomics_16s/skills/fastqc/scripts/python
```

`metagenomics_16s/skills/fastqc/SKILL.md`：

```yaml
---
id: fastqc
name: FastQC
version: "1.0"
category: qc
runtime:
  type: python
input_schema:
  type: object
  properties:
    reads:
      type: string
  required: [reads]
output_schema:
  type: object
  properties:
    report_path:
      type: string
---
Run FastQC quality control on FASTQ reads.
```

`metagenomics_16s/skills/fastqc/scripts/python/main.py`：

```python
import subprocess
from pathlib import Path

def run(inputs):
    reads = Path(inputs["reads"])
    outdir = Path("./fastqc_output")
    outdir.mkdir(exist_ok=True)
    subprocess.run(["fastqc", str(reads), "-o", str(outdir)], check=True)
    return {"report_path": str(outdir / f"{reads.stem}_fastqc.html")}
```

重复上述步骤创建 `dada2_denoise`、`assign_taxonomy` 等技能。

## 步骤 4：验证并安装

```bash
homomics validate metagenomics_16s/domain.yaml
homomics install metagenomics_16s --domains-dir ./domains
```

## 步骤 5：测试

```bash
curl -X POST http://localhost:8080/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1, "message": "分析我的16S数据"}'
```

如果 PlanEngine 正确匹配到 `metagenomics_analysis` 意图，就会按 qc → denoising → taxonomy → diversity 的顺序执行。

## 常见问题

| 问题 | 原因 | 解决 |
|---|---|---|
| `Phase references unknown skill` | 技能未加载 | 将技能放入 `skills/` 目录并重启/热加载 |
| `Intent not recognized` | 关键词未命中 | 在 `intents` 中增加同义词 |
| 计划未按预期调整 | state_checks 条件未触发 | 确保前置技能输出对应字段到 data_state |
