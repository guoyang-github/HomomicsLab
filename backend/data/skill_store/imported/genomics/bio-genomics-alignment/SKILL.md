---
name: bio-genomics-alignment
description: 序列比对核心流程，包括参考基因组索引、BWA-MEM2比对、排序、重复标记和BAM索引。Use when aligning reads to reference genome.
tool_type: cli
primary_tool: bwa-mem2/samtools
prerequisites:
  - 已预处理的clean FASTQ文件
  - 参考基因组FASTA文件
---

# 序列比对核心流程

从clean FASTQ文件到analysis-ready BAM文件的完整流程，包括参考基因组索引、比对、排序、重复标记和质控。

## 1. 参考基因组准备（一次性）

### 下载参考基因组

```bash
# GRCh38 (推荐)
wget https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz
gunzip GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz
mv GCA_000001405.15_GRCh38_no_alt_analysis_set.fna GRCh38.fa

# 或使用GATK bundle
wget https://storage.googleapis.com/genomics-public-data/resources/broad/hg38/v0/Homo_sapiens_assembly38.fasta
```

### 建立索引（必须）

```bash
# bwa-mem2索引 (约30GB)
bwa-mem2 index GRCh38.fa
# 输出: GRCh38.fa.0123, .amb, .ann, .bwt.2bit.64, .pac

# samtools索引 (用于faidx)
samtools faidx GRCh38.fa
# 输出: GRCh38.fa.fai

# GATK字典
samtools dict GRCh38.fa -o GRCh38.dict
# 或使用gatk: gatk CreateSequenceDictionary -R GRCh38.fa
```

### 索引文件说明

| 文件扩展名 | 工具 | 用途 |
|------------|------|------|
| .0123 | bwa-mem2 | BWT索引 |
| .amb, .ann, .pac | bwa-mem2 | 后缀数组 |
| .bwt.2bit.64 | bwa-mem2 | 2bit编码索引 |
| .fai | samtools | 快速序列获取 |
| .dict | GATK | 序列字典 |

## 2. BWA-MEM2比对

### 基础比对

```bash
bwa-mem2 mem -t 8 GRCh38.fa read1.fq read2.fq > aligned.sam
```

### 添加Read Group（GATK必需）

```bash
bwa-mem2 mem -t 8 \
    -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1\tPU:lane1" \
    GRCh38.fa read1.fq read2.fq > aligned.sam
```

### Read Group标签说明

| 标签 | 说明 | 示例 |
|------|------|------|
| ID | Read Group标识 | 样品_文库_批次 |
| SM | 样品名 | NA12878 |
| PL | 测序平台 | ILLUMINA, PACBIO, ONT |
| LB | 文库 | lib1, lib2 |
| PU | 平台单元 | flowcell.lane.barcode |
| CN | 测序中心 | BGI, Novogene |
| DT | 测序日期 | 2024-01-15 |

## 3. 管道化流程（推荐）

### WGS完整流程

```bash
# 一步完成：比对 -> SAM转BAM -> 排序
bwa-mem2 mem -t 8 \
    -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1" \
    GRCh38.fa \
    ${SAMPLE}_R1.clean.fq.gz \
    ${SAMPLE}_R2.clean.fq.gz | \
    samtools view -@ 4 -bS - | \
    samtools sort -@ 4 -o ${SAMPLE}.sorted.bam -

# 标记重复
samtools fixmate -m -@ 4 ${SAMPLE}.sorted.bam - | \
    samtools sort -@ 4 - | \
    samtools markdup -@ 4 - ${SAMPLE}.markdup.bam

# 建立索引
samtools index ${SAMPLE}.markdup.bam

# 清理中间文件
rm ${SAMPLE}.sorted.bam
```

### WES完整流程（关键差异：-L参数）

```bash
# WES在比对接段添加target BED过滤，减少BAM大小
bwa-mem2 mem -t 8 \
    -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1" \
    GRCh38.fa \
    ${SAMPLE}_R1.clean.fq.gz \
    ${SAMPLE}_R2.clean.fq.gz | \
    samtools view -@ 4 -bS -L targets.bed - | \  # 仅保留目标区域
    samtools sort -@ 4 -o ${SAMPLE}.sorted.bam -

# 后续步骤与WGS相同
samtools fixmate -m -@ 4 ${SAMPLE}.sorted.bam - | \
    samtools sort -@ 4 - | \
    samtools markdup -@ 4 - ${SAMPLE}.markdup.bam

samtools index ${SAMPLE}.markdup.bam
rm ${SAMPLE}.sorted.bam
```

## 4. 重复标记详解

### 使用samtools（推荐，更快）

```bash
# 两步法
samtools fixmate -m -@ 4 in.bam - | \
    samtools sort -@ 4 - | \
    samtools markdup -@ 4 - out.bam

# 查看重复统计
samtools markdup -s -@ 4 in.bam out.bam 2>&1 | tee markdup.stats
```

### 使用GATK MarkDuplicates（与GATK生态更兼容）

```bash
gatk MarkDuplicates \
    -I ${SAMPLE}.sorted.bam \
    -O ${SAMPLE}.markdup.bam \
    -M ${SAMPLE}.dup_metrics.txt \
    --REMOVE_DUPLICATES false \
    --CREATE_INDEX true
```

### 重复标记统计解读

```bash
# 从metrics文件提取关键指标
grep -A 1 "LIBRARY" ${SAMPLE}.dup_metrics.txt

# 或从flagstat
samtools flagstat ${SAMPLE}.markdup.bam | grep "duplicates"
```

## 5. BAM索引与验证

### 建立索引

```bash
samtools index ${SAMPLE}.markdup.bam
# 输出: ${SAMPLE}.markdup.bam.bai
```

### BAM验证

```bash
# 检查BAM完整性
samtools quickcheck ${SAMPLE}.markdup.bam

# 验证排序
samtools view -H ${SAMPLE}.markdup.bam | grep "@HD"
# 应包含 SO:coordinate
```

## 6. BAM质控统计

### Flagstat（快速概览）

```bash
samtools flagstat ${SAMPLE}.markdup.bam > ${SAMPLE}.flagstat
```

### 详细统计

```bash
samtools stats ${SAMPLE}.markdup.bam > ${SAMPLE}.stats

# 关键指标
head -30 ${SAMPLE}.stats
```

### 插入片段分布（双端数据）

```bash
# 提取插入片段大小
samtools stats -F SECONDARY ${SAMPLE}.markdup.bam | \
    grep ^IS | cut -f 2- > ${SAMPLE}.insert_size.txt

# 或使用picard
picard CollectInsertSizeMetrics \
    I=${SAMPLE}.markdup.bam \
    O=${SAMPLE}.insert_metrics.txt \
    H=${SAMPLE}.insert_hist.pdf
```

### 覆盖度统计

```bash
# 使用samtools depth
samtools depth ${SAMPLE}.markdup.bam | \
    awk '{sum+=$3; n++} END {print "Mean depth:", sum/n}'

# 或使用mosdepth（更快）
mosdepth -t 4 ${SAMPLE} ${SAMPLE}.markdup.bam
```

## 7. WGS vs WES对比

### 关键差异

| 项目 | WGS | WES | 说明 |
|------|-----|-----|------|
| 比对目标 | 全基因组 | 捕获区域(~1-2%) | WES更快 |
| BAM大小 | ~50-100GB | ~5-10GB | WES小10倍 |
| 重复率阈值 | <30% | <50% | WES容忍更高 |
| 覆盖度 | 30x均匀 | 100x目标区 | WES更深 |
| 比对率 | >95% | >95% | 相同标准 |
| 错配率 | <1% | <1% | 相同标准 |

### 质控阈值

| 指标 | WGS标准 | WES标准 | 检查命令 |
|------|---------|---------|----------|
| 比对率 | >95% | >95% | `samtools flagstat` |
| 重复率 | <30% | <50% | `samtools flagstat` |
| 错配率 | <1% | <1% | `samtools stats` |
| 目标区覆盖 | N/A | >95% @20x | `mosdepth --by targets.bed` |
| 平均深度 | 30x | 100x | `samtools depth` |

## 8. 完整批量脚本

```bash
#!/bin/bash
# alignment_pipeline.sh

SAMPLE=$1
REF=$2
R1=$3
R2=$4
OUTDIR=$5
TYPE=${6:-wgs}  # wgs或wes
TARGETS=${7:-""}  # WES需要

THREADS=8
mkdir -p ${OUTDIR}

echo "=== [1/4] Alignment ==="
if [ "${TYPE}" == "wes" ] && [ -n "${TARGETS}" ]; then
    # WES模式：添加target过滤
    bwa-mem2 mem -t ${THREADS} \
        -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1" \
        ${REF} ${R1} ${R2} | \
        samtools view -@ 4 -bS -L ${TARGETS} - | \
        samtools sort -@ 4 -o ${OUTDIR}/${SAMPLE}.sorted.bam -
else
    # WGS模式
    bwa-mem2 mem -t ${THREADS} \
        -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1" \
        ${REF} ${R1} ${R2} | \
        samtools view -@ 4 -bS - | \
        samtools sort -@ 4 -o ${OUTDIR}/${SAMPLE}.sorted.bam -
fi

echo "=== [2/4] Mark Duplicates ==="
samtools fixmate -m -@ 4 ${OUTDIR}/${SAMPLE}.sorted.bam - | \
    samtools sort -@ 4 - | \
    samtools markdup -@ 4 - ${OUTDIR}/${SAMPLE}.bam

echo "=== [3/4] Index BAM ==="
samtools index ${OUTDIR}/${SAMPLE}.bam

echo "=== [4/4] QC Statistics ==="
samtools flagstat ${OUTDIR}/${SAMPLE}.bam > ${OUTDIR}/${SAMPLE}.flagstat
samtools stats ${OUTDIR}/${SAMPLE}.bam > ${OUTDIR}/${SAMPLE}.stats

# 清理
rm ${OUTDIR}/${SAMPLE}.sorted.bam

echo "=== Alignment Complete ==="
echo "BAM: ${OUTDIR}/${SAMPLE}.bam"
echo "Index: ${OUTDIR}/${SAMPLE}.bam.bai"
echo "Stats: ${OUTDIR}/${SAMPLE}.flagstat"
```

## 9. 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 比对率低(<90%) | 参考基因组错误/污染 | 检查参考版本，运行FastQ Screen |
| 重复率过高(>50% WGS) | PCR过度扩增 | 检查文库制备，可能需更多起始DNA |
| BAM未排序 | 流程错误 | 重新运行samtools sort |
| RG标签缺失 | bwa未添加-R参数 | 重新比对或使用gatk AddOrReplaceReadGroups |
| 索引错误 | BAM不完整 | 重新建立索引或重新生成BAM |

## 相关技能

- bio-genomics-reads-preprocess - 获取clean FASTQ
- bio-genomics-bam-qc-recalibration - BAM质控和BQSR
- bio-genomics-variant-snp-indel - 使用BAM进行变异检测
