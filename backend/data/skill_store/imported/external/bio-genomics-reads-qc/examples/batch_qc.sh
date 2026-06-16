#!/bin/bash
# FastQC + MultiQC 批量QC示例

INDIR="raw_data"
OUTDIR="qc_results"

mkdir -p ${OUTDIR}

# Step 1: 运行FastQC
echo "Running FastQC..."
fastqc -t 8 ${INDIR}/*.fastq.gz -o ${OUTDIR}/

# Step 2: 运行MultiQC汇总
echo "Running MultiQC..."
multiqc ${OUTDIR}/ -o ${OUTDIR}/multiqc_report/

echo "QC complete. Report: ${OUTDIR}/multiqc_report/multiqc_report.html"
