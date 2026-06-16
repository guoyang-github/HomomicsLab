#!/bin/bash
# CNVkit germline CNV分析示例

SAMPLE="patient_001"
REF="GRCh38.fa"
TARGETS="exome_targets.bed"
OUTDIR="cnv_results"

mkdir -p ${OUTDIR}

echo "=== CNV Analysis ==="

# 目标区域准备
echo "[1/4] Preparing targets..."
cnvkit.py target ${TARGETS} --annotate refFlat.txt --split -o ${OUTDIR}/targets.bed
cnvkit.py access ${REF} -o ${OUTDIR}/access.bed
cnvkit.py antitarget ${OUTDIR}/targets.bed --access ${OUTDIR}/access.bed -o ${OUTDIR}/antitargets.bed

# 覆盖度计算
echo "[2/4] Computing coverage..."
cnvkit.py coverage ${SAMPLE}.bam ${OUTDIR}/targets.bed -o ${OUTDIR}/${SAMPLE}.targetcoverage.cnn
cnvkit.py coverage ${SAMPLE}.bam ${OUTDIR}/antitargets.bed -o ${OUTDIR}/${SAMPLE}.antitargetcoverage.cnn

# 使用flat参考（无正常样本）
echo "[3/4] Creating flat reference..."
cnvkit.py reference --fasta ${REF} --targets ${OUTDIR}/targets.bed --antitargets ${OUTDIR}/antitargets.bed -o ${OUTDIR}/flat_ref.cnn

# CNV calling
echo "[4/4] CNV calling..."
cnvkit.py fix ${OUTDIR}/${SAMPLE}.targetcoverage.cnn ${OUTDIR}/${SAMPLE}.antitargetcoverage.cnn ${OUTDIR}/flat_ref.cnn -o ${OUTDIR}/${SAMPLE}.cnr
cnvkit.py segment ${OUTDIR}/${SAMPLE}.cnr -o ${OUTDIR}/${SAMPLE}.cns
cnvkit.py call ${OUTDIR}/${SAMPLE}.cns --ploidy 2 -o ${OUTDIR}/${SAMPLE}.call.cns

# 可视化
cnvkit.py scatter ${OUTDIR}/${SAMPLE}.cnr -s ${OUTDIR}/${SAMPLE}.cns -o ${OUTDIR}/${SAMPLE}_scatter.pdf
cnvkit.py genemetrics ${OUTDIR}/${SAMPLE}.cnr -s ${OUTDIR}/${SAMPLE}.cns -o ${OUTDIR}/${SAMPLE}_genes.tsv

echo "Done. Results in ${OUTDIR}/"
