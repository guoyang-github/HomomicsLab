# Usage Guide: bio-mrna-seq-quantification

## When to Use
Use this skill when you need to convert aligned BAMs or raw FASTQs into a gene/transcript count matrix ready for statistical analysis.

## Inputs
- **Alignment-based**: sorted BAM files + GTF annotation
- **Alignment-free**: clean FASTQ files + transcriptome index (Salmon/kallisto)

## Outputs
- Gene-level count matrix (rows = genes, columns = samples)
- TPM/abundance matrix (for Salmon/kallisto)
- Summary statistics (assignment rate, mapping rate)

## Quick Start
### Path A: Alignment-Based (featureCounts)
```bash
featureCounts -p --countReadPairs -a annotation.gtf -o counts.txt *.bam
```

### Path B: Alignment-Free (Salmon)
```bash
salmon quant -i salmon_index -l A -1 R1.fq.gz -2 R2.fq.gz -o sample_quant -p 8
```

### Combine to Matrix (Python)
```python
counts = pd.DataFrame({s: pd.read_csv(f'{s}_quant/quant.sf', sep='\t', index_col=0)['NumReads'] for s in samples})
```

## Tips
- **Strandedness matters**: use `infer_experiment.py` (RSeQC) to determine library strandedness before setting `-s` in featureCounts.
- **Discard multi-mappers** (`-M` off) for standard DE analysis.
- **tximport / tximeta**: use in R to summarize transcript-level Salmon/kallisto outputs to gene-level counts for DESeq2. `tximeta` is preferred because it automatically attaches metadata and verifies the reference version.
- **Salmon single-end**: do not use `-l A` (auto-detect); explicitly set `-l SR` or `-l U`.

## Workflow Position
**Upstream**: `bio-mrna-seq-alignment` or `bio-mrna-seq-qc-preprocessing`  
**Downstream**: `bio-mrna-seq-count-prep`
