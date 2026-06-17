---
name: bio-ribo-seq-ribosome-periodicity
description: Validate Ribo-seq data quality by checking 3-nucleotide periodicity and calculating P-site offsets. Use when assessing library quality or determining read offsets for downstream analysis.
tool_type: python
primary_tool: Plastid
---

## Version Compatibility

Reference examples tested with: matplotlib 3.8+, numpy 1.26+, pysam 0.22+, scipy 1.12+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- CLI: `<tool> --version` then `<tool> --help` to confirm flags

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

# Ribosome Periodicity Analysis

**"Check if my Ribo-seq data shows triplet periodicity"** → Validate Ribo-seq library quality by verifying 3-nucleotide translocation patterns and calculating P-site offsets from metagene profiles.

## Standard Output

```
results/03_periodicity/
├── {sample}_psite_offsets.json
├── {sample}_metagene_start.pdf
└── periodicity_summary.txt
```

The JSON file is the standardized handoff to downstream skills:
```json
{
  "sample": "sample1",
  "offsets": {"28": 12, "29": 12, "30": 13, "31": 13, "32": 14},
  "periodicity_score": 0.72,
  "quality_pass": true
}
```

## Calculate P-site Offset

```bash
python scripts/calculate_psite_offset.py \
  --bam results/02_ribo_preprocessing/sample1.sorted.bam \
  --gtf results/00_index/annotation_clean.gtf
```

## Save P-site Offsets to JSON

```bash
python scripts/save_psite_offsets.py \
  --sample sample1 \
  --offsets '{"28":12,"29":12,"30":13,"31":13,"32":14}' \
  --score 0.72
```

## Plot Metagene Periodicity

```bash
python scripts/plot_metagene_periodicity.py \
  --npz metagene_profile.npz \
  --out results/03_periodicity/sample1_metagene_start.pdf
```

## Calculate Periodicity Score

```bash
python scripts/calculate_periodicity.py \
  --bam results/02_ribo_preprocessing/sample1.sorted.bam \
  --gtf results/00_index/annotation_clean.gtf \
  --offset 12
```

## Validate with RiboCode

```bash
bash scripts/batch_ribocode.sh \
  results/00_index/annotation_clean.gtf \
  results/02_ribo_preprocessing/sample1.sorted.bam \
  results/00_index/genome.fa \
  results/03_periodicity/ribocode_validation \
  sample1
```

## Concept: How P-site Offset is Determined

The **P-site** (peptidyl-tRNA binding site) is the active center of the ribosome where peptide bond formation occurs. In Ribo-seq, the P-site is inferred from the 5' end of the ribosome-protected fragment (RPF) using a **read-length-specific offset**:

```
P-site position = 5' end position of read + offset(read_length)
```

Because differently sized footprints correspond to slightly different ribosome conformations (e.g., 80S vs. pre/post-termination complexes), the optimal offset can vary by 1–2 nucleotides between 28 nt and 32 nt reads. Therefore, **offsets should be estimated independently for each footprint length**.

### Periodicity Score

The quality of a P-site offset is quantified by the strength of **3-nucleotide periodicity** around start codons:

```python
frame0 = sum(reads at positions where position % 3 == 0)
frame1 = sum(reads at positions where position % 3 == 1)
frame2 = sum(reads at positions where position % 3 == 2)
total  = frame0 + frame1 + frame2

periodicity_score = (frame0 / total) - ((frame1 + frame2) / 2 / total)
```

| Score | Interpretation |
|-------|----------------|
| > 0.5 | Excellent periodicity |
| 0.3 – 0.5 | Marginal; check library quality |
| < 0.3 | Poor; likely non-ribosomal contamination |

### Per-Length Offset Estimation (Python)

```python
import pysam
from plastid import GTF2_TranscriptAssembler

def estimate_offset_per_length(bam_path, gtf_path, read_len, offset_range=range(10, 16)):
    '''Find the offset that maximizes frame-0 occupancy at CDS starts.'''
    transcripts = [tx for tx in GTF2_TranscriptAssembler(gtf_path) if tx.cds_start]
    best_offset = 12
    best_score = -1.0

    with pysam.AlignmentFile(bam_path, 'rb') as bam:
        for offset in offset_range:
            frame0 = 0
            total = 0
            for tx in transcripts:
                for read in bam.fetch(tx.chrom, max(0, tx.cds_start - 50), tx.cds_start + 50):
                    if read.is_unmapped or read.query_length != read_len:
                        continue
                    pos_5p = read.reference_start if not read.is_reverse else read.reference_end
                    rel = pos_5p - tx.cds_start
                    if tx.strand == '-':
                        rel = tx.cds_start - pos_5p
                    psite = rel - offset if tx.strand == '+' else rel + offset
                    if -50 <= psite <= 50:
                        total += 1
                        if int(psite) % 3 == 0:
                            frame0 += 1
            score = (frame0 / total) - ((total - frame0) / 2 / total) if total else 0
            if score > best_score:
                best_score = score
                best_offset = offset

    return best_offset, best_score
```

## P-site Offset Table

Common P-site offsets by read length (5' end mapping):

| Read Length | Human/Mouse | Yeast | Arabidopsis/Rice |
|-------------|-------------|-------|------------------|
| 27 nt | - | 12 | 13 |
| 28 nt | 12 | 12 | 13 |
| 29 nt | 12 | 13 | 13 |
| 30 nt | 13 | 13 | 14 |
| 31 nt | 13 | 14 | 14 |
| 32 nt | 14 | - | - |

Use species-templates skill for organism-specific starting values.

## Related Skills

- bio-ribo-seq-riboseq-preprocessing - Provides aligned BAM input
- bio-ribo-seq-species-templates - Provides species-specific offset starting values
- bio-ribo-seq-orf-detection - Uses P-site offsets
- bio-ribo-seq-orf-quantification - Uses P-site offsets for corrected counting
- bio-ribo-seq-translation-efficiency - Requires proper positioning
- bio-ribo-seq-ribosome-stalling - Reads psite_offsets.json for codon-level analysis
- bio-ribo-seq-metagene-visualization - Creates publication figures from metagene data
