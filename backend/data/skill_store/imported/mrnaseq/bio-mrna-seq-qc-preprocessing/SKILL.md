---
name: bio-mrna-seq-qc-preprocessing
description: FASTQ-level quality control and preprocessing for bulk mRNA-seq. Covers FastQC, fastp/Trimmomatic adapter trimming, and MultiQC aggregation. Use before alignment or pseudo-alignment.
tool_type: mixed
primary_tool: fastp
---

# mRNA-seq QC and Preprocessing

## Overview

Perform quality control on raw FASTQ files, trim adapters/low-quality bases, and generate an aggregated MultiQC report before downstream alignment or quantification.

*Reference examples tested with: FastQC 0.12+, fastp 0.23+, Trimmomatic 0.39, MultiQC 1.22+*

## FastQC Per-Sample QC

```bash
# Run FastQC on all FASTQ files
fastqc *.fastq.gz -t 8 -o fastqc_output/

# Inspect HTML reports for:
# - Per-base sequence quality (Q30 > 80%)
# - Adapter content (< 5%)
# - Per-base N content (< 5%)
# - Sequence duplication level
```

## Tool Selection

| Tool | Best For | Notes |
|------|----------|-------|
| **fastp** | Default choice; all modern Illumina data | Faster, auto-detects adapters, outputs JSON/HTML, all-in-one QC + trim |
| **Trimmomatic** | When you need precise adapter clipping with custom adapter files | Slower, more explicit parameter control; useful for non-Illumina platforms or when adapter sequences are known exactly |

**Rule of thumb**: Use fastp for all standard Illumina RNA-seq. Use Trimmomatic only if you have a specific reason (custom adapter sequences, established pipeline, or non-standard sequencing platform).

---

## fastp Trimming (Recommended)

```bash
# Paired-end
fastp \
    -i sample_R1.fastq.gz -I sample_R2.fastq.gz \
    -o sample_clean_R1.fastq.gz -O sample_clean_R2.fastq.gz \
    --detect_adapter_for_pe \
    --cut_front --cut_tail \
    --cut_window_size 4 --cut_mean_quality 20 \
    --length_required 36 \
    --thread 8 \
    --json sample_fastp.json \
    --html sample_fastp.html

# Single-end
fastp \
    -i sample.fastq.gz \
    -o sample_clean.fastq.gz \
    --cut_front --cut_tail \
    --cut_window_size 4 --cut_mean_quality 20 \
    --length_required 36 \
    --thread 8
```

## Trimmomatic Alternative

```bash
# Paired-end
java -jar trimmomatic.jar PE -threads 8 \
    sample_R1.fastq.gz sample_R2.fastq.gz \
    sample_R1_paired.fastq.gz sample_R1_unpaired.fastq.gz \
    sample_R2_paired.fastq.gz sample_R2_unpaired.fastq.gz \
    ILLUMINACLIP:TruSeq3-PE.fa:2:30:10 \
    LEADING:3 TRAILING:3 SLIDINGWINDOW:4:15 MINLEN:36
```

## Batch Preprocessing

```bash
#!/bin/bash
for r1 in *_R1.fastq.gz *_R1.fq.gz; do
    [ -e "$r1" ] || continue
    base="${r1%_R1.*}"
    r2="${base}_R2${r1#${base}_R1}"
    fastp -i "$r1" -I "$r2" \
        -o "${base}_clean_R1${r1#${base}_R1}" -O "${base}_clean_R2${r1#${base}_R1}" \
        --detect_adapter_for_pe --cut_front --cut_tail \
        --cut_window_size 4 --cut_mean_quality 20 \
        --length_required 36 --thread 8 \
        --json "${base}_fastp.json" --html "${base}_fastp.html"
done
```

## MultiQC Aggregation

```bash
# Aggregate FastQC and fastp reports
multiqc fastqc_output/ . --filename mrnaseq_qc_report --outdir multiqc/
```

## QC Thresholds

| Metric | Good | Warning | Fail |
|--------|------|---------|------|
| Per-base Q30 | > 80% | 70-80% | < 70% |
| Adapter content | < 5% | 5-10% | > 10% |
| Median read length | >= 36 bp | 25-35 bp | < 25 bp |
| Per-base N content | < 5% | 5-10% | > 10% |

## Related Skills

- `bio-mrna-seq-alignment` - Downstream read alignment
- `bio-mrna-seq-quantification` - Pseudo-alignment quantification
- `bio-mrna-seq-pipeline` - End-to-end workflow
