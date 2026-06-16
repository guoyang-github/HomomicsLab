---
name: bio-genomics-reads-qc
description: 原始测序数据质量控制，包括FastQC质量评估、MultiQC汇总和FastQ Screen污染筛查。Use when performing QC on raw FASTQ files.
tool_type: cli
primary_tool: FastQC/MultiQC/FastQ Screen
prerequisites:
  - 了解Phred质量分数
  - 理解WGS和WES的质量差异
---

# 原始数据质量控制

对原始FASTQ文件进行全面的质量控制，包括单样本质量评估、批量汇总和污染筛查。

## 1. FastQC单样本质控

### 基础用法

```bash
# 单文件
fastqc sample.fastq.gz

# 多样本
fastqc *.fastq.gz

# 指定输出目录和线程
fastqc -t 4 -o qc_reports/ *.fastq.gz
```

### 关键质控模块

| 模块 | 内容 | 通过标准 |
|------|------|----------|
| Per base sequence quality | 每个碱基位置的质量分数 | Q30 > 85% (WGS), > 90% (WES) |
| Per sequence quality scores | 质量分数分布 | 主峰在Q30以上 |
| Per base sequence content | 碱基组成 | 前12bp可有波动，之后应平衡 |
| Per sequence GC content | GC含量分布 | 单一峰，无异常偏移 |
| Sequence duplication levels | 重复序列水平 | < 30% (WGS), < 50% (WES) |
| Adapter content | 接头序列含量 | < 1% |
| Overrepresented sequences | 过表达序列 | 检查是否有接头或rRNA |

### 解读质量分数

| Phred分数 | 错误率 | 质量 |
|-----------|--------|------|
| Q40 | 0.01% | 极佳 |
| Q30 | 0.1% | 良好 (Illumina标准) |
| Q20 | 1% | 可接受 |
| Q10 | 10% | 差 |

## 2. MultiQC批量汇总

### 基础用法

```bash
# 汇总当前目录所有FastQC报告
multiqc .

# 指定输入和输出目录
multiqc raw_qc/ -o multiqc_report/

# 自定义报告名称
multiqc . -n project_qc_report
```

### 常用选项

```bash
# 仅包含FastQC模块
multiqc . -m fastqc

# 排除特定样本
multiqc . --ignore-samples '*negative*'

# 导出数据为表格
multiqc . --export
```

### 输出文件

- `multiqc_report.html` - 交互式HTML报告
- `multiqc_data/` - 原始数据表格
  - `multiqc_general_stats.txt` - 汇总统计
  - `multiqc_fastqc.txt` - FastQC详细数据

## 3. FastQ Screen污染筛查

### 用途

检测样品中的：
- 跨物种污染
- 细菌/病毒污染
- 接头序列
- PhiX spike-in
- 样品混淆

### 基础用法

```bash
# 基础筛查
fastq_screen sample.fastq.gz

# 指定配置文件
fastq_screen --conf screen.conf --outdir screen_results/ *.fastq.gz

# 增加抽样数量（默认10万条）
fastq_screen --subset 200000 sample.fastq.gz
```

### 配置文件示例

```
# screen.conf
DATABASE Human /path/to/human/GRCh38
DATABASE Mouse /path/to/mouse/GRCm39
DATABASE Ecoli /path/to/ecoli
DATABASE PhiX /path/to/phix
DATABASE Adapters /path/to/adapters
DATABASE rRNA /path/to/rrna

THREADS 8
```

### 结果解读

| 样品类型 | 预期模式 |
|----------|----------|
| 人源样品 | >90% Human, <1% others |
| 小鼠样品 | >90% Mouse, <1% others |
| 存在PhiX | ~10% PhiX (正常) |
| 污染样品 | 多个物种显著比例 |

## 4. WGS vs WES质控要点对比

### 关键指标差异

| 质控指标 | WGS标准 | WES标准 | 说明 |
|----------|---------|---------|------|
| Q30比例 | >85% | >90% | WES预期质量更高 |
| 重复率 | <30% | <50% | WES捕获效率导致重复偏高 |
| GC含量 | 40-60% | 检查捕获偏好 | WES需关注目标区域GC偏差 |
| 接头污染 | <1% | <1% | 通用标准 |
| 目标区域覆盖度 | N/A | 后续步骤评估 | WES特有 |

### 常见问题及处理

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 3'端质量下降 | 正常测序衰减 | 使用fastp进行3'端修剪 |
| 高重复率 | PCR过度扩增/低复杂度 | 检查文库制备，可能需要更多起始DNA |
| GC偏差 | 文库制备偏好 | 考虑使用GC校正工具 |
| 接头污染 | 短插入片段 | 强制接头修剪 |
| 高rRNA比例 | rRNA去除失败 | 检查样品质量，重新制备 |

## 5. 批量QC流程示例

```bash
#!/bin/bash
# qc_pipeline.sh - 通用QC流程

SAMPLE=$1
TYPE=${2:-wgs}  # wgs或wes
OUTDIR="qc/${SAMPLE}"

mkdir -p ${OUTDIR}

echo "=== Step 1: FastQC ==="
fastqc -t 4 ${SAMPLE}_R*.fastq.gz -o ${OUTDIR}/

echo "=== Step 2: FastQ Screen ==="
fastq_screen --conf fastq_screen.conf \
    --outdir ${OUTDIR}/screen \
    ${SAMPLE}_R1.fastq.gz

echo "=== QC Summary ==="
echo "Sample: ${SAMPLE}"
echo "Type: ${TYPE}"

# 提取关键指标进行自动评估
unzip -p ${OUTDIR}/${SAMPLE}_R1_fastqc.zip \
    ${SAMPLE}_R1_fastqc/summary.txt | \
    awk -F'\t' '{print $1 "\t" $2}'
```

## 相关技能

- bio-genomics-reads-preprocess - 基于QC结果进行数据清洗
- bio-genomics-alignment - 比对后的BAM质控
