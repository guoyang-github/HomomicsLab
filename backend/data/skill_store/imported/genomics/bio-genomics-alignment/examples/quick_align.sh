#!/bin/bash
# 快速比对示例

SAMPLE="test_sample"
REF="GRCh38.fa"
R1="${SAMPLE}_R1.fq.gz"
R2="${SAMPLE}_R2.fq.gz"

# 一步完成比对、排序、标记重复
bwa-mem2 mem -t 8 -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA" \
    ${REF} ${R1} ${R2} | \
    samtools view -@ 4 -bS - | \
    samtools sort -@ 4 - | \
    samtools markdup -@ 4 - ${SAMPLE}.bam

samtools index ${SAMPLE}.bam
samtools flagstat ${SAMPLE}.bam > ${SAMPLE}.flagstat

echo "Alignment complete: ${SAMPLE}.bam"
