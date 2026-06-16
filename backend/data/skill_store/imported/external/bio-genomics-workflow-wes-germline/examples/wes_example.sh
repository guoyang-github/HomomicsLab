#!/bin/bash
# WES Germline分析完整流程示例
# 用法: ./wes_example.sh <样本名> <R1.fastq.gz> <R2.fastq.gz> <targets.bed> <输出目录>

set -euo pipefail

SAMPLE=$1
R1=$2
R2=$3
TARGETS=$4
OUTDIR=$5

REF="/path/to/GRCh38.fa"
THREADS=8

echo "=== WES Germline Pipeline Example ==="
echo "Sample: ${SAMPLE}"
echo "Start: $(date)"

mkdir -p ${OUTDIR}/{qc,clean,aligned,vcf}

# Step 1: QC
echo "[1/6] QC..."
fastqc -t 4 ${R1} ${R2} -o ${OUTDIR}/qc/

# Step 2: Preprocess (WES可启用correction)
echo "[2/6] Preprocessing..."
fastp -i ${R1} -I ${R2} \
    -o ${OUTDIR}/clean/R1.fq.gz \
    -O ${OUTDIR}/clean/R2.fq.gz \
    --detect_adapter_for_pe \
    --correction \
    --length_required 30 \
    --html ${OUTDIR}/qc/fastp.html

# Step 3: Alignment (WES关键差异: -L targets.bed)
echo "[3/6] Alignment with target filter..."
bwa-mem2 mem -t ${THREADS} \
    -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA" \
    ${REF} ${OUTDIR}/clean/R1.fq.gz ${OUTDIR}/clean/R2.fq.gz | \
    samtools view -@ 4 -bS -L ${TARGETS} - | \
    samtools sort -@ 4 -o ${OUTDIR}/aligned/${SAMPLE}.sorted.bam -

samtools markdup ${OUTDIR}/aligned/${SAMPLE}.sorted.bam \
    ${OUTDIR}/aligned/${SAMPLE}.bam
samtools index ${OUTDIR}/aligned/${SAMPLE}.bam

# Step 4: Target QC
echo "[4/6] Target coverage..."
mosdepth -t 4 --by ${TARGETS} ${OUTDIR}/qc/${SAMPLE} ${OUTDIR}/aligned/${SAMPLE}.bam

# Step 5: Variant Calling (WES必须使用-L)
echo "[5/6] Variant Calling..."
gatk HaplotypeCaller -R ${REF} \
    -I ${OUTDIR}/aligned/${SAMPLE}.bam \
    -L ${TARGETS} \
    -O ${OUTDIR}/vcf/${SAMPLE}.g.vcf.gz -ERC GVCF

gatk GenotypeGVCFs -R ${REF} \
    -V ${OUTDIR}/vcf/${SAMPLE}.g.vcf.gz \
    -L ${TARGETS} \
    -O ${OUTDIR}/vcf/${SAMPLE}.vcf.gz

# Step 6: Filter (WES深度过滤范围更大)
echo "[6/6] Filtering..."
bcftools norm -f ${REF} -m-any ${OUTDIR}/vcf/${SAMPLE}.vcf.gz | \
    bcftools filter -e 'QUAL<30 || DP<20 || DP>500' | \
    bcftools view -f PASS -Oz -o ${OUTDIR}/vcf/${SAMPLE}.filtered.vcf.gz

echo "Done: $(date)"
echo "Output: ${OUTDIR}/vcf/${SAMPLE}.filtered.vcf.gz"
