---
name: bio-genomics-workflow-wgs-germline
description: 完整的WGS生殖细胞变异检测工作流，从FASTQ到注释VCF的全流程。Use for end-to-end WGS germline variant calling.
tool_type: workflow
primary_tool: multiple
depends_on:
  - bio-genomics-reads-qc
  - bio-genomics-reads-preprocess
  - bio-genomics-alignment
  - bio-genomics-bam-qc-recalibration
  - bio-genomics-variant-snp-indel
  - bio-genomics-variant-filter-norm
  - bio-genomics-variant-interpretation
workflow: true
---

# WGS生殖细胞变异检测工作流

完整的全基因组测序(WGS)分析流程，从原始FASTQ到临床可解读的变异报告。

## 流程概览

```
FASTQ输入
    │
    ├── [1. QC] ────────────────► FastQC/MultiQC
    │                              └─ 检查: Q30>85%, 重复率<30%
    │
    ├── [2. Preprocess] ────────► fastp修剪
    │                              └─ 输出: clean FASTQ
    │
    ├── [3. Alignment] ─────────► bwa-mem2比对
    │                              ├─ markdup标记重复
    │                              └─ 输出: analysis-ready BAM
    │
    ├── [4. BQSR] ──────────────► BaseRecalibrator
    │                              ├─ ApplyBQSR
    │                              └─ 输出: recalibrated BAM
    │
    ├── [5. Variant Calling] ───► HaplotypeCaller(GVCF)
    │                              └─ 输出: gVCF
    │
    ├── [6. Joint Genotyping] ──► GenomicsDBImport
    │                              ├─ GenotypeGVCFs
    │                              └─ 输出: 队列VCF
    │
    ├── [7. Filter & Norm] ─────► bcftools norm
    │                              ├─ Hard Filter/VQSR
    │                              └─ 输出: filtered VCF
    │
    └── [8. Annotation] ────────► VEP注释
                                   ├─ ClinVar
                                   └─ 输出: 可解读报告
```

## 预期运行时间和资源

| 阶段 | 时间(30x WGS) | 内存 | 并行度 |
|------|---------------|------|--------|
| QC | 10 min | 2GB | 样本级 |
| Preprocess | 30 min | 4GB | 样本级 |
| Alignment | 2-3 hours | 16GB | 8线程 |
| BQSR | 1 hour | 8GB | 8线程 |
| Variant Call | 3-4 hours | 8GB | 8线程 |
| Joint Genotype | 1-2 hours | 16GB | 队列级 |
| Filter | 30 min | 8GB | 单线程 |
| Annotation | 2 hours | 4GB | 4线程 |
| **总计/样本** | **~12小时** | **16GB** | - |

## 完整工作流脚本

```bash
#!/bin/bash
# wgs_germline_pipeline.sh
set -euo pipefail

# 配置
SAMPLE=$1
REF=$2
R1=$3
R2=$4
OUTDIR=$5
DBSNP=$6
KNOWN_INDELS=$7
THREADS=${8:-8}

mkdir -p ${OUTDIR}/{qc,clean,aligned,vcf,annotation}

echo "=========================================="
echo "WGS Germline Pipeline"
echo "Sample: ${SAMPLE}"
echo "=========================================="

# Stage 1: QC
echo "[1/8] Quality Control..."
fastqc -t 4 ${R1} ${R2} -o ${OUTDIR}/qc/

# Stage 2: Preprocess
echo "[2/8] Preprocessing..."
fastp -i ${R1} -I ${R2} \
    -o ${OUTDIR}/clean/${SAMPLE}_R1.fq.gz \
    -O ${OUTDIR}/clean/${SAMPLE}_R2.fq.gz \
    --detect_adapter_for_pe \
    --qualified_quality_phred 20 \
    --length_required 50 \
    --cut_front --cut_tail \
    --html ${OUTDIR}/qc/${SAMPLE}_fastp.html \
    -w ${THREADS}

# Stage 3: Alignment
echo "[3/8] Alignment..."
bwa-mem2 mem -t ${THREADS} \
    -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1" \
    ${REF} \
    ${OUTDIR}/clean/${SAMPLE}_R1.fq.gz \
    ${OUTDIR}/clean/${SAMPLE}_R2.fq.gz | \
    samtools view -@ 4 -bS - | \
    samtools sort -@ 4 -o ${OUTDIR}/aligned/${SAMPLE}.sorted.bam -

samtools fixmate -m -@ 4 ${OUTDIR}/aligned/${SAMPLE}.sorted.bam - | \
    samtools sort -@ 4 - | \
    samtools markdup -@ 4 - ${OUTDIR}/aligned/${SAMPLE}.bam
samtools index ${OUTDIR}/aligned/${SAMPLE}.bam
rm ${OUTDIR}/aligned/${SAMPLE}.sorted.bam

# Stage 4: BQSR
echo "[4/8] BQSR..."
gatk BaseRecalibrator \
    -R ${REF} \
    -I ${OUTDIR}/aligned/${SAMPLE}.bam \
    --known-sites ${DBSNP} \
    --known-sites ${KNOWN_INDELS} \
    -O ${OUTDIR}/aligned/${SAMPLE}.recal.table

gatk ApplyBQSR \
    -R ${REF} \
    -I ${OUTDIR}/aligned/${SAMPLE}.bam \
    --bqsr-recal-file ${OUTDIR}/aligned/${SAMPLE}.recal.table \
    -O ${OUTDIR}/aligned/${SAMPLE}.recal.bam
samtools index ${OUTDIR}/aligned/${SAMPLE}.recal.bam

# Stage 5: Variant Calling (GVCF)
echo "[5/8] Variant Calling..."
gatk HaplotypeCaller \
    -R ${REF} \
    -I ${OUTDIR}/aligned/${SAMPLE}.recal.bam \
    -O ${OUTDIR}/vcf/${SAMPLE}.g.vcf.gz \
    -ERC GVCF \
    -native-pair-hmm-threads ${THREADS}

echo "=========================================="
echo "Sample processing complete: ${SAMPLE}"
echo "Next: Joint genotyping with other samples"
echo "=========================================="
```

### 队列联合基因分型脚本

```bash
#!/bin/bash
# joint_analysis.sh

COHORT=$1
REF=$2
GVCF_DIR=$3
OUTDIR=$4
mkdir -p ${OUTDIR}

# 创建sample map
echo "Creating sample map..."
ls ${GVCF_DIR}/*.g.vcf.gz | awk -F'/' '{sample=$NF; gsub(/\.g\.vcf\.gz$/, "", sample); print sample "\t" $0}' \
    > ${OUTDIR}/sample_map.txt

# Stage 6: Joint Genotyping
echo "[6/8] Joint Genotyping..."
gatk GenomicsDBImport \
    --genomicsdb-workspace-path ${OUTDIR}/genomicsdb \
    --sample-name-map ${OUTDIR}/sample_map.txt

gatk GenotypeGVCFs \
    -R ${REF} \
    -V gendb://${OUTDIR}/genomicsdb \
    -O ${OUTDIR}/${COHORT}.vcf.gz

# Stage 7: Filter & Normalize
echo "[7/8] Filtering and Normalization..."
bcftools norm -f ${REF} -m-any ${OUTDIR}/${COHORT}.vcf.gz -Oz -o ${OUTDIR}/${COHORT}.norm.vcf.gz

bcftools filter -e 'QUAL<30 || INFO/DP<10 || INFO/DP>200 || INFO/FS>60' \
    ${OUTDIR}/${COHORT}.norm.vcf.gz -Oz -o ${OUTDIR}/${COHORT}.hard.vcf.gz

bcftools view -f PASS ${OUTDIR}/${COHORT}.hard.vcf.gz -Oz -o ${OUTDIR}/${COHORT}.filtered.vcf.gz
bcftools index ${OUTDIR}/${COHORT}.filtered.vcf.gz

# Stage 8: Annotation
echo "[8/8] Annotation..."
vep -i ${OUTDIR}/${COHORT}.filtered.vcf.gz \
    -o ${OUTDIR}/${COHORT}.vep.vcf \
    --vcf --cache --offline \
    --assembly GRCh38 \
    --everything --pick \
    --fork 4

bgzip ${OUTDIR}/${COHORT}.vep.vcf
bcftools index ${OUTDIR}/${COHORT}.vep.vcf.gz

echo "=========================================="
echo "WGS Pipeline Complete!"
echo "Output: ${OUTDIR}/${COHORT}.vep.vcf.gz"
echo "=========================================="
```

## 输出文件说明

| 目录 | 文件 | 说明 |
|------|------|------|
| qc/ | *_fastqc.html | FastQC报告 |
| qc/ | *_fastp.html | fastp预处理报告 |
| clean/ | *_R*.fq.gz | 清洗后FASTQ |
| aligned/ | *.bam | 比对后BAM |
| aligned/ | *.recal.bam | BQSR后BAM |
| vcf/ | *.g.vcf.gz | 单样本gVCF |
| vcf/ | ${COHORT}.vcf.gz | 队列原始VCF |
| vcf/ | ${COHORT}.filtered.vcf.gz | 过滤后VCF |
| annotation/ | ${COHORT}.vep.vcf.gz | 注释后VCF |

## WGS特定QC指标

| 指标 | 期望值 | 检查点 |
|------|--------|--------|
| Q30比例 | >85% | Stage 1 |
| 比对率 | >95% | Stage 3 |
| 重复率 | <30% | Stage 3 |
| 平均覆盖度 | 30x | Stage 4 |
| Ti/Tv比率 | ~2.1 | Stage 7 |
| SNP数量 | ~400万 | Stage 7 |

## 相关技能

- bio-genomics-workflow-wes-germline - WES版本工作流
- bio-genomics-variant-structural - 结构变异检测
