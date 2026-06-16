---
name: bio-ribo-seq-orf-detection
description: Detect translated ORFs from Ribo-seq data including uORFs and novel ORFs using RiboCode and RibORF. Use when identifying translated regions beyond annotated coding sequences.
tool_type: mixed
primary_tool: RiboCode
---

## Version Compatibility

Reference examples tested with: BioPython 1.83+, pandas 2.2+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters
- CLI: `<tool> --version` then `<tool> --help` to confirm flags

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

# ORF Detection

**"Detect translated ORFs from my Ribo-seq data"** → Identify actively translated open reading frames including uORFs and novel ORFs using 3-nucleotide periodicity as evidence of active translation.
- CLI: `RiboCode` for periodicity-based ORF detection
- Python: Manual ORF scanning and filtering by Ribo-seq coverage

## Standard Output Directory

```
results/05_orf_detection/
├── {sample}_ORF_result.txt
├── {sample}_ORF_result.html
├── {sample}_binomial_test.txt
└── detected_orfs.bed
```

## RiboCode Workflow

**Goal:** Detect actively translated ORFs from Ribo-seq data using 3-nucleotide periodicity as evidence of translation.

**Approach:** Prepare transcript annotations, then run RiboCode with specified read lengths to identify ORFs with significant periodicity.

```bash
mkdir -p results/05_orf_detection

# Step 1: Prepare annotation
prepare_transcripts \
    -g results/00_index/annotation_clean.gtf \
    -f results/00_index/genome.fa \
    -o results/05_orf_detection/ribocode_annot

# Step 2: Create RiboCode config
cat > results/05_orf_detection/config.txt <<EOF
SampleName  AlignmentFile  Stranded
sample1     results/02_ribo_preprocessing/sample1.sorted.bam    yes
EOF

# Step 3: Run RiboCode
RiboCode \
    -a results/05_orf_detection/ribocode_annot \
    -c results/05_orf_detection/config.txt \
    -l 27,28,29,30 \
    -o results/05_orf_detection/sample1
```

## One-Step RiboCode

```bash
RiboCode_onestep \
    -g results/00_index/annotation_clean.gtf \
    -r results/02_ribo_preprocessing/sample1.sorted.bam \
    -f results/00_index/genome.fa \
    -l 27,28,29,30 \
    -o results/05_orf_detection/sample1
```

## RiboCode Output

| File | Description |
|------|-------------|
| *_ORF_result.txt | Detected ORFs with coordinates |
| *_ORF_result.html | Interactive visualization |
| *_binomial_test.txt | Statistical test results |

## Parse RiboCode Results

```python
import pandas as pd

def load_ribocode_orfs(filepath):
    '''Load RiboCode ORF predictions'''
    df = pd.read_csv(filepath, sep='\t')

    categories = {
        'annotated': df[df['ORF_type'] == 'annotated'],
        'uORF': df[df['ORF_type'] == 'uORF'],
        'dORF': df[df['ORF_type'] == 'dORF'],
        'novel': df[df['ORF_type'].isin(['novel', 'noncoding'])]
    }

    return df, categories
```

## Alternative: RibORF

```bash
RibORF.py \
    -f results/00_index/genome.fa \
    -r results/02_ribo_preprocessing/sample1.sorted.bam \
    -g results/00_index/annotation_clean.gtf \
    -o results/05_orf_detection/riborf/sample1
```

## Manual ORF Detection

```python
from Bio import SeqIO
from Bio.Seq import Seq

def find_orfs(sequence, min_length=30):
    '''Find all ORFs in a sequence'''
    start_codon = 'ATG'
    stop_codons = ['TAA', 'TAG', 'TGA']
    orfs = []
    seq = str(sequence).upper()

    for frame in range(3):
        for i in range(frame, len(seq) - 2, 3):
            codon = seq[i:i+3]
            if codon == start_codon:
                for j in range(i + 3, len(seq) - 2, 3):
                    if seq[j:j+3] in stop_codons:
                        orf_length = j - i + 3
                        if orf_length >= min_length:
                            orfs.append({
                                'start': i, 'end': j + 3, 'frame': frame,
                                'length': orf_length, 'sequence': seq[i:j+3]
                            })
                        break
    return orfs

def detect_translated_orfs(orfs, coverage_data, min_coverage=10):
    '''Filter ORFs by Ribo-seq coverage'''
    translated = []
    for orf in orfs:
        cov = coverage_data[orf['start']:orf['end']]
        if sum(cov) >= min_coverage:
            translated.append(orf)
    return translated
```

## uORF Analysis

```python
def find_uorfs(transcript, cds_start):
    '''Find upstream ORFs before main CDS'''
    utr5 = transcript[:cds_start]
    uorfs = find_orfs(utr5)

    for uorf in uorfs:
        if uorf['end'] <= cds_start:
            uorf['type'] = 'contained'
        else:
            uorf['type'] = 'overlapping'

    return uorfs
```

## ORF Categories

| Type | Description |
|------|-------------|
| annotated | Known CDS in annotation |
| uORF | Upstream of main CDS |
| dORF | Downstream of main CDS |
| internal | Within CDS, different frame |
| noncoding | In annotated non-coding RNA |
| novel | Unannotated region |

## Related Skills

- bio-ribo-seq-ribosome-periodicity - Validates data quality and provides P-site offsets
- bio-ribo-seq-orf-quantification - Quantifies detected ORFs and runs differential analysis
- bio-ribo-seq-translation-efficiency - Quantifies gene-level translation
- bio-ribo-seq-ribosome-stalling - Analyzes codon-level pausing in detected ORFs
