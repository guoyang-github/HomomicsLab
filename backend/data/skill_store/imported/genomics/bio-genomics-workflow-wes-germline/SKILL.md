---
name: bio-genomics-workflow-wes-germline
description: 完整的WES生殖细胞变异检测工作流，从FASTQ到注释VCF的全流程。Use for end-to-end WES germline variant calling.
tool_type: workflow
primary_tool: multiple
depends_on:
  - bio-genomics-reads-qc
  - bio-genomics-reads-preprocess
  - bio-genomics-alignment
  - bio-genomics-variant-snp-indel
  - bio-genomics-variant-filter-norm
  - bio-genomics-variant-interpretation
workflow: true
---

# WES生殖细胞变异检测工作流

完整的外显子组测序(WES)分析流程，针对捕获区域进行高效分析。

## WGS vs WES关键差异

| 项目 | WGS | WES (本流程) |
|------|-----|--------------|
| 分析区域 | 全基因组(~3Gb) | 捕获区(~30-60Mb) |
| BQSR | 强烈推荐 | 可选 |
| 覆盖度 | 30x均匀 | 100x目标区 |
| 重复率阈值 | <30% | <50% |
| 过滤策略 | VQSR或Hard | 仅Hard Filter |
| 运行时间 | ~12小时 | ~3小时 |
| 存储需求 | ~100GB/样本 | ~10GB/样本 |

## 流程概览

```
FASTQ输入
    │
    ├── [1. QC] ────────────────► FastQC/MultiQC
    │                              └─ 检查: Q30>90%, 重复率<50%
    │
    ├── [2. Preprocess] ────────► fastp修剪(可启用校正)
    │                              └─ 输出: clean FASTQ
    │
    ├── [3. Alignment] ─────────► bwa-mem2 + target BED过滤
    │                              ├─ markdup标记重复
    │                              └─ 输出: target BAM
    │
    ├── [4. Target QC] ─────────► mosdepth覆盖度分析
    │                              └─ 检查: >95%@20x
    │
    ├── [5. Variant Calling] ───► HaplotypeCaller(-L targets)
    │                              └─ 输出: gVCF
    │
    ├── [6. Joint Genotyping] ──► GenomicsDBImport(-L targets)
    │                              ├─ GenotypeGVCFs
    │                              └─ 输出: 队列VCF
    │
    ├── [7. Filter & Norm] ─────► bcftools norm
    │                              ├─ Hard Filter(严格深度)
    │                              └─ 输出: filtered VCF
    │
    └── [8. Annotation] ────────► VEP注释
                                   ├─ ClinVar
                                   └─ 输出: 可解读报告
```

## 预期运行时间和资源

| 阶段 | 时间 | 内存 | 并行度 |
|------|------|------|--------|
| QC | 10 min | 2GB | 样本级 |
| Preprocess | 20 min | 4GB | 样本级 |
| Alignment | 30 min | 16GB | 8线程 |
| Target QC | 5 min | 4GB | 单线程 |
| Variant Call | 30 min | 8GB | 8线程 |
| Joint Genotype | 30 min | 16GB | 队列级 |
| Filter | 10 min | 8GB | 单线程 |
| Annotation | 30 min | 4GB | 4线程 |
| **总计/样本** | **~3小时** | **16GB** | - |

## 需要准备的文件

1. **参考基因组**: GRCh38.fa + 索引
2. **捕获芯片定义**: targets.bed (根据试剂盒)
   - Agilent SureSelect
   - IDT xGen
   - Roche NimbleGen
3. **interval_list**: targets.interval_list (GATK格式)

## 完整工作流脚本

```bash
#!/bin/bash
# wes_germline_pipeline.sh
set -euo pipefail

# 配置
SAMPLE=$1
REF=$2
TARGETS=$3         # targets.bed
INTERVALS=$4       # targets.interval_list (GATK格式)
R1=$5
R6=$6
OUTDIR=$7
THREADS=${8:-8}

mkdir -p ${OUTDIR}/{qc,clean,aligned,vcf,annotation}

echo "=========================================="
echo "WES Germline Pipeline"
echo "Sample: ${SAMPLE}"
echo "Target: ${TARGETS}"
echo "=========================================="

# Stage 1: QC
echo "[1/8] Quality Control..."
fastqc -t 4 ${R1} ${R2} -o ${OUTDIR}/qc/

# Stage 2: Preprocess
echo "[2/8] Preprocessing..."
# WES: 可启用碱基校正，长度要求较低
fastp -i ${R1} -I ${R2} \
    -o ${OUTDIR}/clean/${SAMPLE}_R1.fq.gz \
    -O ${OUTDIR}/clean/${SAMPLE}_R2.fq.gz \
    --detect_adapter_for_pe \
    --qualified_quality_phred 20 \
    --length_required 30 \          # WES可降低
    --cut_front --cut_tail \
    --correction \                  # WES可启用
    --html ${OUTDIR}/qc/${SAMPLE}_fastp.html \
    -w ${THREADS}

# Stage 3: Alignment (WES关键差异: -L targets)
echo "[3/8] Alignment with target filter..."
bwa-mem2 mem -t ${THREADS} \
    -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1" \
    ${REF} \
    ${OUTDIR}/clean/${SAMPLE}_R1.fq.gz \
    ${OUTDIR}/clean/${SAMPLE}_R2.fq.gz | \
    samtools view -@ 4 -bS -L ${TARGETS} - | \    # 仅保留目标区域
    samtools sort -@ 4 -o ${OUTDIR}/aligned/${SAMPLE}.sorted.bam -

samtools fixmate -m -@ 4 ${OUTDIR}/aligned/${SAMPLE}.sorted.bam - | \
    samtools sort -@ 4 - | \
    samtools markdup -@ 4 - ${OUTDIR}/aligned/${SAMPLE}.bam
samtools index ${OUTDIR}/aligned/${SAMPLE}.bam
rm ${OUTDIR}/aligned/${SAMPLE}.sorted.bam

# Stage 4: Target QC
echo "[4/8] Target Coverage QC..."
mosdepth -t 4 --by ${TARGETS} ${OUTDIR}/qc/${SAMPLE} ${OUTDIR}/aligned/${SAMPLE}.bam

# 计算关键指标
COVERAGE=$(zcat ${OUTDIR}/qc/${SAMPLE}.regions.bed.gz | \
    awk '{sum+=$4; n++} END {printf "%.1f", sum/n}')
echo "Mean target coverage: ${COVERAGE}x"

# Stage 5: Variant Calling (WES: 必须使用-L)
echo "[5/8] Variant Calling (-L targets)..."
gatk HaplotypeCaller \
    -R ${REF} \
    -I ${OUTDIR}/aligned/${SAMPLE}.bam \
    -L ${INTERVALS} \                   # WES关键参数
    -O ${OUTDIR}/vcf/${SAMPLE}.g.vcf.gz \
    -ERC GVCF \
    -native-pair-hmm-threads ${THREADS}

echo "=========================================="
echo "Sample processing complete: ${SAMPLE}"
echo "Next: Joint genotyping with other samples"
echo "=========================================="
```

### 队列联合基因分型脚本(WES)

```bash
#!/bin/bash
# wes_joint_analysis.sh

COHORT=$1
REF=$2
INTERVALS=$3       # WES必须使用intervals
GVCF_DIR=$4
OUTDIR=$5
mkdir -p ${OUTDIR}

# 创建sample map
echo "Creating sample map..."
ls ${GVCF_DIR}/*.g.vcf.gz | awk -F'/' '{sample=$NF; gsub(/\.g\.vcf\.gz$/, "", sample); print sample "\t" $0}' \
    > ${OUTDIR}/sample_map.txt

# Stage 6: Joint Genotyping (WES: 必须使用-L)
echo "[6/8] Joint Genotyping with intervals..."
gatk GenomicsDBImport \
    --genomicsdb-workspace-path ${OUTDIR}/genomicsdb \
    --sample-name-map ${OUTDIR}/sample_map.txt \
    -L ${INTERVALS}                     # WES关键参数

gatk GenotypeGVCFs \
    -R ${REF} \
    -V gendb://${OUTDIR}/genomicsdb \
    -L ${INTERVALS} \                   # WES关键参数
    -O ${OUTDIR}/${COHORT}.vcf.gz

# Stage 7: Filter & Normalize (WES: 更严格的深度过滤)
echo "[7/8] Filtering and Normalization..."
bcftools norm -f ${REF} -m-any ${OUTDIR}/${COHORT}.vcf.gz -Oz -o ${OUTDIR}/${COHORT}.norm.vcf.gz

# WES: 深度过滤范围更大 (20-500)
bcftools filter -e 'QUAL<30 || INFO/DP<20 || INFO/DP>500 || INFO/FS>60' \
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
echo "WES Pipeline Complete!"
echo "Output: ${OUTDIR}/${COHORT}.vep.vcf.gz"
echo "=========================================="
```

## 捕获芯片BED文件准备

```bash
# 下载Agilent SureSelect Human All Exon V6
# 或使用试剂盒提供的BED文件

# 转换为GATK interval_list
picard BedToIntervalList \
    I=targets.bed \
    SD=reference.dict \
    O=targets.interval_list

# 添加侧翼(可选，用于分析剪接位点)
bedtools slop -i targets.bed -g genome.txt -b 50 > targets_flank50.bed
```

## WES特定QC指标

| 指标 | 期望值 | 检查点 |
|------|--------|--------|
| Q30比例 | >90% | Stage 1 |
| 比对率 | >95% | Stage 3 |
| 重复率 | <50% | Stage 3 |
| 目标区覆盖度 | >95% @20x | Stage 4 |
| 目标区平均深度 | 100x | Stage 4 |
| 均一性(PCT_0.2xMean) | >80% | Stage 4 |
| Ti/Tv比率 | ~2.8-3.0 | Stage 7 |
| SNP数量 | ~2-5万 | Stage 7 |

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 目标区覆盖度低 | 捕获效率差 | 检查捕获试剂，补测 |
| 重复率过高 | PCR过度扩增 | 优化文库制备 |
| GC偏差严重 | 捕获偏好 | 使用GC校正工具 |
| 目标区外变异多 | 未使用-L参数 | 添加interval限制 |
| 变异数过少 | 覆盖度不足 | 确保100x覆盖 |

## 相关技能

- bio-genomics-workflow-wgs-germline - WGS版本工作流
- bio-genomics-variant-structural - 结构变异检测(不推荐用于WES)
