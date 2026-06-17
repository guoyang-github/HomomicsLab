# Usage Guide: bio-mrna-seq-alignment

## When to Use
Use this skill after FASTQ preprocessing when you need genome-aligned BAM files for downstream gene counting, splice analysis, or visualization.

## Inputs
- Clean FASTQ files (paired-end or single-end)
- Reference genome FASTA
- Gene annotation GTF

## Outputs
- Sorted BAM files (`.sorted.bam` + `.bai`)
- Alignment logs (mapping rates, splice junctions)
- Optional: STAR gene counts (`ReadsPerGene.out.tab`)

## Quick Start
### Choose Your Aligner
- **STAR**: best for sensitivity, two-pass mode, and fusion detection; requires ~30 GB RAM for human.
- **HISAT2**: best when memory is limited (~8 GB RAM); excellent splicing accuracy.

### Typical STAR Command
```bash
STAR --runThreadN 8 --genomeDir star_index/ \
    --readFilesIn clean_R1.fq.gz clean_R2.fq.gz \
    --readFilesCommand zcat \
    --outSAMtype BAM SortedByCoordinate \
    --outFileNamePrefix sample_
```

## Tips
- Match `--sjdbOverhang` to `read_length - 1` during index generation.
- Use `--twopassMode Basic` for better novel junction detection.
- Check `Log.final.out` for overall alignment rate (> 70% is good).

## Workflow Position
**Upstream**: `bio-mrna-seq-qc-preprocessing`  
**Downstream**: `bio-mrna-seq-quantification` (featureCounts) or `bio-mrna-seq-splicing` (rMATS)
