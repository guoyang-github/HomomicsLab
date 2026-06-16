#!/bin/bash
# WGS Germline分析完整流程示例
# 用法: ./wgs_example.sh <样本名> <R1.fastq.gz> <R2.fastq.gz> <输出目录>

set -euo pipefail

SAMPLE=$1
R1=$2
R2=$3
OUTDIR=$4

# 参考路径（需根据实际环境修改）
REF="/path/to/GRCh38.fa"
DBSNP="/path/to/dbsnp.vcf.gz"
KNOWN_INDELS="/path/to/known_indels.vcf.gz"

THREADS=8

echo "=== WGS Germline Pipeline Example ==="
echo "Sample: ${SAMPLE}"
echo "Start: $(date)"

mkdir -p ${OUTDIR}/{qc,clean,aligned,vcf}

# Step 1: QC
echo "[1/7] QC..."
fastqc -t 4 ${R1} ${R2} -o ${OUTDIR}/qc/

# Step 2: Preprocess
echo "[2/7] Preprocessing..."
fastp -i ${R1} -I ${R2} \
    -o ${OUTDIR}/clean/R1.fq.gz \
    -O ${OUTDIR}/clean/R2.fq.gz \
    --detect_adapter_for_pe \
    --cut_front --cut_tail \
    --html ${OUTDIR}/qc/fastp.html

# Step 3: Alignment
echo "[3/7] Alignment..."
bwa-mem2 mem -t ${THREADS} \
    -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA" \
    ${REF} ${OUTDIR}/clean/R1.fq.gz ${OUTDIR}/clean/R2.fq.gz | \
    samtools sort -@ 4 -o ${OUTDIR}/aligned/${SAMPLE}.sorted.bam -

samtools markdup ${OUTDIR}/aligned/${SAMPLE}.sorted.bam \
    ${OUTDIR}/aligned/${SAMPLE}.bam
samtools index ${OUTDIR}/aligned/${SAMPLE}.bam

# Step 4: BQSR
echo "[4/7] BQSR..."
gatk BaseRecalibrator -R ${REF} -I ${OUTDIR}/aligned/${SAMPLE}.bam \
    --known-sites ${DBSNP} -O ${OUTDIR}/aligned/recal.table

gatk ApplyBQSR -R ${REF} -I ${OUTDIR}/aligned/${SAMPLE}.bam \
    --bqsr-recal-file ${OUTDIR}/aligned/recal.table \
    -O ${OUTDIR}/aligned/${SAMPLE}.recal.bam

# Step 5: Variant Calling
echo "[5/7] Variant Calling..."
gatk HaplotypeCaller -R ${REF} \
    -I ${OUTDIR}/aligned/${SAMPLE}.recal.bam \
    -O ${OUTDIR}/vcf/${SAMPLE}.g.vcf.gz -ERC GVCF

# Step 6: Genotyping (单样本，无需GenomicsDB)
gatk GenotypeGVCFs -R ${REF} \
    -V ${OUTDIR}/vcf/${SAMPLE}.g.vcf.gz \
    -O ${OUTDIR}/vcf/${SAMPLE}.vcf.gz

# Step 7: Filter
echo "[7/7] Filtering..."
bcftools norm -f ${REF} -m-any \
    ${OUTDIR}/vcf/${SAMPLE}.vcf.gz | \
    bcftools filter -e 'QUAL<30 || DP<10' | \
    bcftools view -f PASS -Oz -o ${OUTDIR}/vcf/${SAMPLE}.filtered.vcf.gz

echo "Done: $(date)"
echo "Output: ${OUTDIR}/vcf/${SAMPLE}.filtered.vcf.gz"
