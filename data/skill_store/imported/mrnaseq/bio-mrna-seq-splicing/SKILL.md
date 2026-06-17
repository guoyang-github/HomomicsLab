---
name: bio-mrna-seq-splicing
description: Alternative splicing analysis for bulk mRNA-seq. Covers PSI quantification with SUPPA2 and rMATS-turbo, differential splicing detection, and isoform switching. Use when analyzing splice events and isoform ratios.
tool_type: mixed
primary_tool: rMATS-turbo
---


Reference examples tested with: rMATS-turbo 4.3.0, SUPPA2 2.3, regtools 1.0.0, leafcutter (GitHub master)

# mRNA-seq Splicing Analysis

## Overview

Quantify alternative splicing events and detect differential splicing between conditions from bulk mRNA-seq data.

## Event Types

| Type | Code | Description |
|------|------|-------------|
| Skipped exon | SE | Exon inclusion/exclusion |
| Alternative 5' splice site | A5SS | Alternative donor site |
| Alternative 3' splice site | A3SS | Alternative acceptor site |
| Mutually exclusive exons | MXE | One of two exons included |
| Retained intron | RI | Intron retention |

---

## Tool Selection

| Tool | Input | Best For |
|------|-------|----------|
| rMATS-turbo | BAM | Novel junctions, statistical testing |
| SUPPA2 | TPM | Speed, isoform-aware |
| leafcutter | BAM | Novel events, annotation-free |

---

## rMATS-turbo (BAM-based)

`rmats.py` is the main executable script included in the **rMATS-turbo** package.


### Differential Splicing

```bash
# Create BAM lists
echo -e "sample1.bam\nsample2.bam" > condition1_bams.txt
echo -e "sample3.bam\nsample4.bam" > condition2_bams.txt

# Determine read length from FASTQ if not already known
# READ_LEN=$(zcat sample_R1.fastq.gz | awk 'NR%4==2 {print length($0)}' | head -1000 | awk '{sum+=$1; count++} END {printf "%d", sum/count}')

rmats.py \
    --b1 condition1_bams.txt \
    --b2 condition2_bams.txt \
    --gtf annotation.gtf \
    -t paired \
    --readLength ${READ_LEN:-150} \
    --nthread 8 \
    --od rmats_output \
    --tmp rmats_tmp
```

### Filter Results

```python
import pandas as pd

se = pd.read_csv('rmats_output/SE.MATS.JCEC.txt', sep='\t')
sig_se = se[(se['FDR'] < 0.05) & (abs(se['IncLevelDifference']) > 0.1)]
```

---

## SUPPA2 (TPM-based)

`suppa.py` is the main executable script included in the **SUPPA2** package.

### Generate Events and PSI

```bash
# Generate event definitions
suppa.py generateEvents -i annotation.gtf -o events/ -f ioe

# Calculate PSI per event
suppa.py psiPerEvent -i events/ -e transcript_tpm.tsv -o psi_output
```

### Differential PSI

```bash
suppa.py diffSplice -m empirical -i events/ \
    -p control.psi treated.psi -e psi_output/events.ioe \
    -o suppa_diff_output -pa -l 10 -c
```

---



## leafcutter

**leafcutter** is an annotation-free method for quantifying RNA splicing from aligned reads.

### Install

```bash
git clone https://github.com/davidaknowles/leafcutter.git
# R package (required for differential splicing)
R CMD INSTALL leafcutter/leafcutter
```

### Intron Quantification

```bash
# Typical workflow:
# 1. Extract junctions from BAMs using regtools
for bam in *.bam; do
    regtools junctions extract -a 8 -m 50 -M 500000 "$bam" -o "${bam%.bam}.junc"
done

# 2. Cluster junctions across samples
python leafcutter/clustering/leafcutter_cluster.py \
    -j junc_files.txt \
    -m 30 \
    -o leafcutter_clusters \
    -l 500000

# 3. Differential splicing (R script)
Rscript leafcutter/scripts/leafcutter_ds.R \
    leafcutter_clusters_perind_numers.counts.gz \
    groups.txt \
    -o leafcutter_ds_output
```

## Related Skills

- `bio-mrna-seq-alignment` - Generate BAM input
- `bio-mrna-seq-quantification` - Generate transcript TPM
- `bio-mrna-seq-pipeline` - End-to-end workflow
