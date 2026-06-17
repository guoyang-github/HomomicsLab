# Usage Guide: bio-mrna-seq-qc-bam

## When to Use
Use this skill after read alignment to assess RNA-seq library quality from BAM files. It complements FASTQ-level QC by measuring splice-aware alignment metrics, rRNA contamination, strandedness, and transcript integrity.

## Inputs
- Aligned, sorted BAM files
- Gene annotation BED or GTF
- Optional: reference flat file and rRNA interval list for Picard

## Outputs
- RSeQC reports (strandedness, gene body coverage, read distribution, TIN)
- Picard RNA-seq metrics
- Duplication and insert size statistics
- Aggregated MultiQC report

## Quick Start
1. **Strandedness**: `infer_experiment.py -i aligned.bam -r genes.bed`
2. **Gene body coverage**: `geneBody_coverage.py -i aligned.bam -r genes.bed -o coverage`
3. **Read distribution**: `read_distribution.py -i aligned.bam -r genes.bed`
4. **TIN scores**: `tin.py -i aligned.bam -r genes.bed`
5. **Picard CollectRnaSeqMetrics** for comprehensive metrics
6. Aggregate everything with `multiqc`.

## Tips
- **rRNA %**: PolyA libraries should be < 5%; rRNA-depleted libraries < 10%.
- **Strandedness**: ~1 for reverse (1++,1--) indicates standard Illumina TruSeq RF.
- **TIN > 70** is good; < 50 suggests severe RNA degradation.
- Even gene body coverage = good quality; 3' bias = degradation or polyA artifact.

## Workflow Position
**Upstream**: `bio-mrna-seq-alignment`  
**Downstream**: `bio-mrna-seq-quantification` or `bio-mrna-seq-qc-exploratory`
