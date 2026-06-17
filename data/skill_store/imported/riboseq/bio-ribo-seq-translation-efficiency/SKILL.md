---
name: bio-ribo-seq-translation-efficiency
description: Calculate translation efficiency (TE) as the ratio of ribosome occupancy to mRNA abundance. Use when comparing translational regulation between conditions or identifying genes with altered translation independent of transcription.
tool_type: mixed
primary_tool: riborex
---

## Version Compatibility

Reference examples tested with: DESeq2 1.42+, numpy 1.26+, pandas 2.2+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

# Translation Efficiency

**"Calculate translation efficiency from my Ribo-seq and mRNA-seq"** → Compute the ratio of ribosome occupancy to mRNA abundance per gene to identify translational regulation independent of transcription changes.

## Standard Input / Output

Inputs:
- `results/02_ribo_preprocessing/*.sorted.bam` or `results/04_differential/ribo_counts.tsv`
- `results/02_rna_preprocessing/counts/rna_counts_matrix.tsv`

Outputs:
```
results/04_differential/
├── te_values.csv
├── deseq2_te_results.csv
└── riborex_results.csv
```

## Concept

Translation Efficiency (TE) = Ribo-seq reads / mRNA-seq reads

- TE > 1: Efficiently translated (more ribosomes per mRNA)
- TE < 1: Poorly translated
- Changes in TE indicate translational regulation

## Concept: From Counts to Translation Efficiency

### TE Formula

Raw Ribo-seq counts reflect both **transcription** (how much mRNA is present) and **translation** (how many ribosomes are loaded). To isolate translational regulation, we normalize ribosome occupancy by mRNA abundance:

```
RPK  = reads / (gene_length_kb)
TPM  = RPK / (sum(RPK) / 1e6)
TE   = TPM_ribo / TPM_rna
log2_TE = log2(TE + pseudocount)
```

- **Ribo-seq**: counted over the **CDS** only (ribosomes occupy the coding sequence).
- **mRNA-seq**: counted over the **full transcript** (including UTRs), because RNA-seq captures the entire mature mRNA.

### DESeq2 Interaction Model

To test whether a gene's translation efficiency changes between conditions (e.g., treatment vs. control), a **full interaction model** is used:

```
~ condition + assay + condition:assay
```

Where:
- `condition` = biological condition (control / treatment)
- `assay` = measurement type (ribo / rna)
- `condition:assay` = the **interaction term**, capturing differential TE

The design matrix looks like this:

| Sample | Condition | Assay |
|--------|-----------|-------|
| ctrl_1 | control   | ribo  |
| ctrl_2 | control   | ribo  |
| treat_1| treatment | ribo  |
| treat_2| treatment | ribo  |
| ctrl_1 | control   | rna   |
| ctrl_2 | control   | rna   |
| treat_1| treatment | rna   |
| treat_2| treatment | rna   |

The `condition:assay` contrast tells you whether the **ribo/rna ratio** (i.e., TE) differs between treatment and control.

### Why Not Simple Division?

A naive `ribo / rna` fold change ignores:
- **Library size differences** between Ribo-seq and RNA-seq
- **Gene length differences** (longer genes accumulate more reads)
- **Variance structure** (RNA-seq and Ribo-seq have different dispersions)

DESeq2 models these explicitly, providing more reliable p-values and fold changes.

## Calculate TE from BAM Files

```bash
python scripts/calculate_te.py \
  --ribo-bam results/02_ribo_preprocessing/sample1.sorted.bam \
  --rna-bam results/02_rna_preprocessing/sample1.sorted.bam \
  --gtf results/00_index/annotation_clean.gtf \
  --out results/04_differential/te_values.csv
```

## Differential TE with riborex

```bash
Rscript scripts/run_riborex.R \
  results/04_differential/ribo_counts.tsv \
  results/02_rna_preprocessing/counts/rna_counts_matrix.tsv \
  results/04_differential/sample_conditions.tsv \
  results/04_differential/riborex_results.csv
```

## Differential TE with DESeq2 Interaction Model

```bash
Rscript scripts/deseq2_interaction_te.R \
  results/04_differential/ribo_counts.tsv \
  results/02_rna_preprocessing/counts/rna_counts_matrix.tsv \
  results/04_differential/sample_conditions.tsv \
  results/04_differential/deseq2_te_results.csv
```

## Normalize Counts and Compute TE Matrix

```bash
python scripts/normalize_counts.py \
  --ribo results/04_differential/ribo_tpm.csv \
  --rna results/02_rna_preprocessing/counts/rna_tpm.csv \
  --method tpm \
  --out results/04_differential/te_matrix.csv
```

## Interpretation

| Log2 TE Change | Interpretation |
|----------------|----------------|
| > 1 | Strong translational activation |
| 0.5 - 1 | Moderate activation |
| -0.5 - 0.5 | No significant change |
| -1 - -0.5 | Moderate repression |
| < -1 | Strong translational repression |

## Related Skills

- bio-ribo-seq-rna-preprocessing - Generates mRNA-seq count matrix
- bio-ribo-seq-riboseq-preprocessing - Generates Ribo-seq BAMs/counts
- bio-ribo-seq-differential-occupancy - Overlaps conceptually but uses Ribo-seq only or Xtail
- bio-ribo-seq-orf-quantification - ORF-level differential analysis
