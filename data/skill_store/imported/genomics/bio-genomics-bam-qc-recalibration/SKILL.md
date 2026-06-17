---
name: bio-genomics-bam-qc-recalibration
description: BAM文件质控、覆盖度分析和碱基质量分数重校准(BQSR)。Use for BAM quality control and recalibration before variant calling.
tool_type: cli
primary_tool: GATK/samtools/mosdepth
prerequisites:
  - 已比对的BAM文件
  - 已知变异位点数据库
---

# BAM质控与校准

在变异检测前对BAM文件进行质量控制、覆盖度分析和碱基质量分数重校准(BQSR)，以确保变异检测的准确性。

## 1. 覆盖度分析

### 使用mosdepth（推荐，最快）

```bash
# 安装: conda install -c bioconda mosdepth

# WGS: 全局覆盖度
mosdepth -t 4 --fast-mode ${SAMPLE} ${SAMPLE}.bam

# WES: 目标区域覆盖度
mosdepth -t 4 --by targets.bed ${SAMPLE} ${SAMPLE}.bam

# 指定阈值统计
mosdepth -t 4 --thresholds 10,20,30,50,100 ${SAMPLE} ${SAMPLE}.bam
```

### 输出文件解读

| 文件 | 内容 |
|------|------|
| `.mosdepth.global.dist.txt` | 全基因组覆盖分布 |
| `.mosdepth.region.dist.txt` | 按区域覆盖分布 |
| `.regions.bed.gz` | 每个区域的平均深度 |
| `.thresholds.bed.gz` | 各阈值覆盖比例 |

### 覆盖度计算示例

```bash
# WGS平均覆盖度
zcat ${SAMPLE}.mosdepth.global.dist.txt | \
    awk '{sum+=$1*$2; total+=$2} END {print "Mean depth:", sum/total}'

# WES目标区域覆盖度
zcat ${SAMPLE}.regions.bed.gz | \
    awk '{sum+=$4; n++} END {print "Mean target coverage:", sum/n}'

# 计算20x以上覆盖比例 (WES关键指标)
zcat ${SAMPLE}.thresholds.bed.gz | \
    awk -v thresh=20 '{for(i=4;i<=NF;i++) if($i>=thresh) print $0}' | wc -l
```

### 使用samtools depth

```bash
# 全基因组（较慢）
samtools depth ${SAMPLE}.bam | awk '{sum+=$3; n++} END {print "Mean:", sum/n}'

# 指定区域
samtools depth -r chr1:1000000-2000000 ${SAMPLE}.bam

# BED区域
samtools depth -b targets.bed ${SAMPLE}.bam > target_depth.txt
```

## 2. 插入片段分析

```bash
# 使用samtools stats
samtools stats -F SECONDARY ${SAMPLE}.bam | grep ^IS > insert_size.txt

# 或使用Picard
picard CollectInsertSizeMetrics \
    I=${SAMPLE}.bam \
    O=${SAMPLE}.insert_metrics.txt \
    H=${SAMPLE}.insert_hist.pdf \
    M=0.5  # 忽略超过此百分位的片段
```

## 3. 碱基质量分数重校准(BQSR)

BQSR通过分析已知变异位点周围的系统性质量误差，校正碱基质量分数。

### 需要的已知位点数据库

```bash
# 下载GATK bundle资源
dbsnp="dbsnp_146.hg38.vcf.gz"
known_indels="Mills_and_1000G_gold_standard.indels.hg38.vcf.gz"
known_snps="1000G_phase1.snps.high_confidence.hg38.vcf.gz"
```

### Step 1: BaseRecalibrator

```bash
gatk BaseRecalibrator \
    -R GRCh38.fa \
    -I ${SAMPLE}.bam \
    --known-sites ${dbsnp} \
    --known-sites ${known_indels} \
    -O ${SAMPLE}.recal_data.table
```

### Step 2: ApplyBQSR

```bash
gatk ApplyBQSR \
    -R GRCh38.fa \
    -I ${SAMPLE}.bam \
    --bqsr-recal-file ${SAMPLE}.recal_data.table \
    -O ${SAMPLE}.recal.bam

# 建立索引
samtools index ${SAMPLE}.recal.bam
```

### Step 3: 验证校准效果（可选）

```bash
# 对校准后的BAM再次运行BaseRecalibrator
gatk BaseRecalibrator \
    -R GRCh38.fa \
    -I ${SAMPLE}.recal.bam \
    --known-sites ${dbsnp} \
    -O ${SAMPLE}.post_recal_data.table

# 生成比较图
gatk AnalyzeCovariates \
    -before ${SAMPLE}.recal_data.table \
    -after ${SAMPLE}.post_recal_data.table \
    -plots ${SAMPLE}.recal_plots.pdf
```

### BQSR输出解读

`recal_data.table` 包含以下信息：
- ReadGroup: 不同read group的校正
- QualityScore: 质量分数的系统性偏差
- Cycle: 测序循环（read位置）的影响
- Context: 序列上下文（二核苷酸）的影响

## 4. WGS vs WES差异

### BQSR适用性

| 项目 | WGS | WES | 说明 |
|------|-----|-----|------|
| BQSR推荐度 | 强烈推荐 | 可选 | WES捕获偏差影响BQSR效果 |
| 运行时间 | 2-3小时 | 30分钟 | WES数据量小 |
| 质量改善 | 明显 | 有限 | WES本身质量通常较高 |
| 是否必需 | 是 | 否 | GATK最佳实践要求不同 |

### 覆盖度要求

| 指标 | WGS标准 | WES标准 |
|------|---------|---------|
| 平均深度 | ≥30x | ≥100x |
| 目标区覆盖度 | N/A | ≥95% @20x |
| 均一性(PCT_0.2xMean) | >80% | >80% |
| 重复率 | <30% | <50% |

### WES特定质控

```bash
# 计算目标区域捕获效率
mosdepth -t 4 --by targets.bed ${SAMPLE} ${SAMPLE}.bam

# 提取关键指标
zcat ${SAMPLE}.regions.bed.gz | awk '
{
    sum+=$4; n++;
    if($4>=20) c20++;
    if($4>=50) c50++;
    if($4>=100) c100++;
}
END {
    print "Mean coverage:", sum/n;
    print "Pct >=20x:", c20/n*100;
    print "Pct >=50x:", c50/n*100;
    print "Pct >=100x:", c100/n*100;
}'
```

## 5. 综合质控报告

### 使用QualiMap

```bash
# WGS
qualimap bamqc -bam ${SAMPLE}.bam -outdir qualimap_report/

# WES
qualimap bamqc -bam ${SAMPLE}.bam \
    -gff targets.bed \
    -outdir qualimap_report/
```

### 关键质控指标检查清单

```bash
#!/bin/bash
# bam_qc_check.sh

BAM=$1
TYPE=${2:-wgs}
TARGETS=$3

echo "=== BAM QC Report ==="
echo "Sample: ${BAM}"
echo "Type: ${TYPE}"

# 基础统计
samtools flagstat ${BAM} | head -6

# 平均深度
if [ "${TYPE}" == "wes" ] && [ -n "${TARGETS}" ]; then
    DEPTH=$(samtools depth -b ${TARGETS} ${BAM} | awk '{sum+=$3; n++} END {printf "%.1f", sum/n}')
    echo "Mean target depth: ${DEPTH}x"
else
    DEPTH=$(samtools depth ${BAM} | awk '{sum+=$3; n++} END {printf "%.1f", sum/n}')
    echo "Mean genome depth: ${DEPTH}x"
fi

# 插入片段大小
samtools stats ${BAM} | grep "insert size average" | cut -f 4-

echo "=== QC Check Complete ==="
```

## 6. 完整BQSR流程脚本

```bash
#!/bin/bash
# bqsr_pipeline.sh

SAMPLE=$1
REF=$2
BAM=$3
DBSNP=$4
KNOWN_INDELS=$5
OUTDIR=$6

mkdir -p ${OUTDIR}

echo "=== [1/3] BaseRecalibrator ==="
gatk BaseRecalibrator \
    -R ${REF} \
    -I ${BAM} \
    --known-sites ${DBSNP} \
    --known-sites ${KNOWN_INDELS} \
    -O ${OUTDIR}/${SAMPLE}.recal_data.table

echo "=== [2/3] ApplyBQSR ==="
gatk ApplyBQSR \
    -R ${REF} \
    -I ${BAM} \
    --bqsr-recal-file ${OUTDIR}/${SAMPLE}.recal_data.table \
    -O ${OUTDIR}/${SAMPLE}.recal.bam

echo "=== [3/3] Index and Verify ==="
samtools index ${OUTDIR}/${SAMPLE}.recal.bam
samtools quickcheck ${OUTDIR}/${SAMPLE}.recal.bam

echo "BQSR Complete: ${OUTDIR}/${SAMPLE}.recal.bam"
```

## 7. 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| BQSR失败 | 缺少known sites | 确保dbsnp和indel文件正确 |
| 覆盖度过低 | 测序深度不足 | 检查测序量，考虑重测序 |
| WES覆盖不均 | 捕获效率差 | 检查捕获试剂，考虑补测 |
| 重复率过高 | PCR过度扩增 | 使用更多起始DNA |
| 插入片段异常 | 文库制备问题 | 检查片段选择步骤 |

## 相关技能

- bio-genomics-alignment - 生成输入BAM
- bio-genomics-variant-snp-indel - 使用recalibrated BAM进行变异检测
