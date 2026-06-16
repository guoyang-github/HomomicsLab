---
name: bio-genomics-reads-preprocess
description: 原始测序数据预处理，包括接头修剪、质量过滤和碱基校正。使用fastp一体化工具完成。Use when cleaning raw FASTQ files.
tool_type: cli
primary_tool: fastp
prerequisites:
  - 已完成原始数据QC
---

# 数据预处理

使用fastp进行一体化的FASTQ预处理，包括接头检测与修剪、质量过滤、长度过滤和碱基校正。

## 1. fastp基础用法

### 单端数据

```bash
fastp -i input.fq.gz -o clean.fq.gz
```

### 双端数据（推荐）

```bash
fastp -i R1.fq.gz -I R2.fq.gz -o clean.R1.fq.gz -O clean.R2.fq.gz
```

### 生成QC报告

```bash
fastp -i R1.fq.gz -I R2.fq.gz -o clean.R1.fq.gz -O clean.R2.fq.gz \
    --html fastp_report.html --json fastp_report.json
```

## 2. 接头修剪

### 自动检测接头（推荐）

```bash
fastp -i R1.fq.gz -I R2.fq.gz -o clean.R1.fq.gz -O clean.R2.fq.gz \
    --detect_adapter_for_pe  # 双端自动检测
```

### 指定接头序列

```bash
fastp -i R1.fq.gz -o clean.fq.gz \
    --adapter_sequence AGATCGGAAGAGCACACGTCT \
    --adapter_sequence_r2 AGATCGGAAGAGCGTCGTGT
```

### 常见接头序列

| 平台 | Read 1接头 | Read 2接头 |
|------|------------|------------|
| TruSeq | AGATCGGAAGAGCACACGTCTGAA | AGATCGGAAGAGCGTCGTGTAGGG |
| Nextera | CTGTCTCTTATACACATCT | CTGTCTCTTATACACATCT |
| Small RNA | TGGAATTCTCGGGTGCCAAGG | - |

## 3. 质量过滤

### 基础质量过滤

```bash
fastp -i R1.fq.gz -I R2.fq.gz -o clean.R1.fq.gz -O clean.R2.fq.gz \
    --qualified_quality_phred 20 \      # 质量阈值Q20
    --unqualified_percent_limit 40      # 允许40%碱基低于阈值
```

### 滑动窗口修剪（推荐）

```bash
fastp -i R1.fq.gz -I R2.fq.gz -o clean.R1.fq.gz -O clean.R2.fq.gz \
    --cut_front \                       # 从5'端修剪
    --cut_tail \                        # 从3'端修剪
    --cut_window_size 4 \               # 窗口大小4bp
    --cut_mean_quality 20               # 平均质量阈值Q20
```

### 长度过滤

```bash
fastp -i R1.fq.gz -I R2.fq.gz -o clean.R1.fq.gz -O clean.R2.fq.gz \
    --length_required 50 \              # 最小长度50bp
    --length_limit 150                  # 最大长度150bp
```

## 4. 高级功能

### 碱基校正（双端重叠区）

```bash
fastp -i R1.fq.gz -I R2.fq.gz -o clean.R1.fq.gz -O clean.R2.fq.gz \
    --correction \                      # 启用碱基校正
    --overlap_len_require 30            # 最小重叠长度
```

### 去除低复杂度序列

```bash
fastp -i R1.fq.gz -o clean.fq.gz \
    --low_complexity_filter \
    --complexity_threshold 30           # 复杂度阈值
```

### 全局裁剪

```bash
# 去除前10bp（可能存在测序偏差）
fastp -i R1.fq.gz -o clean.fq.gz -f 10

# 去除后10bp
fastp -i R1.fq.gz -o clean.fq.gz -t 10
```

## 5. WGS vs WES预处理参数对比

### WGS推荐参数

```bash
fastp \
    -i ${SAMPLE}_R1.fq.gz -I ${SAMPLE}_R2.fq.gz \
    -o ${OUTDIR}/clean.R1.fq.gz -O ${OUTDIR}/clean.R2.fq.gz \
    --detect_adapter_for_pe \
    --qualified_quality_phred 20 \
    --length_required 50 \
    --cut_front \
    --cut_tail \
    --cut_window_size 4 \
    --cut_mean_quality 20 \
    --html ${OUTDIR}/fastp.html \
    --json ${OUTDIR}/fastp.json \
    -w 8                                # 8线程
```

### WES推荐参数

```bash
fastp \
    -i ${SAMPLE}_R1.fq.gz -I ${SAMPLE}_R2.fq.gz \
    -o ${OUTDIR}/clean.R1.fq.gz -O ${OUTDIR}/clean.R2.fq.gz \
    --detect_adapter_for_pe \
    --qualified_quality_phred 20 \
    --length_required 30 \              # WES可适当降低
    --cut_front \
    --cut_tail \
    --correction \                      # WES可启用碱基校正
    --overlap_len_require 20 \
    --html ${OUTDIR}/fastp.html \
    --json ${OUTDIR}/fastp.json \
    -w 8
```

### 参数差异总结

| 参数 | WGS | WES | 原因 |
|------|-----|-----|------|
| length_required | 50 | 30 | WES片段通常更短 |
| correction | 可选 | 推荐 | WES重叠区更多 |
| cut_mean_quality | 20 | 20 | 一致 |
| 线程数 | 8 | 8 | 一致 |

## 6. 批量预处理脚本

```bash
#!/bin/bash
# preprocess_batch.sh

INDIR=$1      # 输入目录
OUTDIR=$2     # 输出目录
TYPE=${3:-wgs} # wgs或wes

mkdir -p ${OUTDIR}

# 设置type-specific参数
if [ "${TYPE}" == "wes" ]; then
    LEN_REQ=30
    CORRECTION="--correction"
else
    LEN_REQ=50
    CORRECTION=""
fi

for R1 in ${INDIR}/*_R1.fq.gz; do
    SAMPLE=$(basename ${R1} _R1.fq.gz)
    R2=${INDIR}/${SAMPLE}_R2.fq.gz

    echo "Processing ${SAMPLE}..."

    fastp \
        -i ${R1} -I ${R2} \
        -o ${OUTDIR}/${SAMPLE}_R1.clean.fq.gz \
        -O ${OUTDIR}/${SAMPLE}_R2.clean.fq.gz \
        --detect_adapter_for_pe \
        --qualified_quality_phred 20 \
        --length_required ${LEN_REQ} \
        --cut_front --cut_tail \
        --cut_window_size 4 \
        --cut_mean_quality 20 \
        ${CORRECTION} \
        --html ${OUTDIR}/${SAMPLE}_fastp.html \
        --json ${OUTDIR}/${SAMPLE}_fastp.json \
        -w 8
done

echo "Preprocessing complete. Reports in ${OUTDIR}/"
```

## 7. 输出解读

### HTML报告关键指标

| 指标 | 说明 | 良好标准 |
|------|------|----------|
| Total reads | 原始reads数 | 根据实验设计 |
| Filtered reads | 过滤reads数 | <20% |
| Q20 bases | Q20以上碱基比例 | >85% |
| Q30 bases | Q30以上碱基比例 | >80% |
| GC content | GC含量 | 接近物种预期 |
| Adapter trimmed | 接头修剪reads数 | 根据原始数据 |

## 相关技能

- bio-genomics-reads-qc - 预处理前的质控
- bio-genomics-alignment - 使用clean数据进行比对
