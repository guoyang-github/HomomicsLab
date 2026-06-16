---
name: bio-mrna-seq-alignment
description: Splice-aware alignment of bulk mRNA-seq reads using STAR and HISAT2. Covers index generation, basic/two-pass alignment, stranded settings, and BAM sorting. Use when aligning reads to a reference genome.
tool_type: cli
primary_tool: STAR
---

# mRNA-seq Alignment

## Overview

Align bulk mRNA-seq reads using splice-aware aligners. This skill covers both STAR (high sensitivity, feature-rich) and HISAT2 (memory-efficient), with best-practice parameters for each.

*Reference examples tested with: STAR 2.7.11b+, HISAT2 2.2.1+, samtools 1.19+*

## STAR

### Generate Genome Index

```bash
STAR --runMode genomeGenerate \
    --runThreadN 8 \
    --genomeDir star_index/ \
    --genomeFastaFiles reference.fa \
    --sjdbGTFfile annotation.gtf \
    --sjdbOverhang 149    # Set to read_length - 1 for your data
```

### Basic Paired-End Alignment

```bash
STAR --runThreadN 8 \
    --genomeDir star_index/ \
    --readFilesIn reads_1.fq.gz reads_2.fq.gz \
    --readFilesCommand zcat \
    --outFileNamePrefix sample_ \
    --outSAMtype BAM SortedByCoordinate
```

### Two-Pass Mode (Novel Junctions)

```bash
STAR --runThreadN 8 \
    --genomeDir star_index/ \
    --readFilesIn r1.fq.gz r2.fq.gz \
    --readFilesCommand zcat \
    --outFileNamePrefix sample_ \
    --outSAMtype BAM SortedByCoordinate \
    --twopassMode Basic
```

### Quantification Mode

```bash
STAR --runThreadN 8 \
    --genomeDir star_index/ \
    --readFilesIn r1.fq.gz r2.fq.gz \
    --readFilesCommand zcat \
    --outFileNamePrefix sample_ \
    --outSAMtype BAM SortedByCoordinate \
    --quantMode GeneCounts
```

Output `sample_ReadsPerGene.out.tab` columns:
1. Gene ID
2. Unstranded counts
3. Forward strand counts
4. Reverse strand counts

### ENCODE Recommended Settings

```bash
STAR --runThreadN 8 \
    --genomeDir star_index/ \
    --readFilesIn r1.fq.gz r2.fq.gz \
    --readFilesCommand zcat \
    --outFileNamePrefix sample_ \
    --outSAMtype BAM SortedByCoordinate \
    --outSAMunmapped Within \
    --outSAMattributes NH HI AS NM MD \
    --outFilterType BySJout \
    --outFilterMultimapNmax 20 \
    --outFilterMismatchNmax 999 \
    --outFilterMismatchNoverReadLmax 0.04 \
    --outFilterScoreMinOverLread 0.66 \
    --outFilterMatchNminOverLread 0.66 \
    --alignIntronMin 20 \
    --alignIntronMax 1000000 \
    --alignMatesGapMax 1000000 \
    --alignSJoverhangMin 8 \
    --alignSJDBoverhangMin 1
```

---

## HISAT2

### Build Index

```bash
# With splice sites and exons (recommended)
# These helper scripts ship with HISAT2
hisat2_extract_splice_sites.py annotation.gtf > splice_sites.txt
hisat2_extract_exons.py annotation.gtf > exons.txt

hisat2-build -p 8 \
    --ss splice_sites.txt \
    --exon exons.txt \
    reference.fa hisat2_index
```

### Basic Alignment

```bash
# Paired-end -> sorted BAM
hisat2 -p 8 -x hisat2_index \
    -1 r1.fq.gz -2 r2.fq.gz | \
    samtools sort -@ 4 -o aligned.sorted.bam -

samtools index aligned.sorted.bam
```

### Stranded Libraries

```bash
# Reverse stranded (Illumina TruSeq - most common)
hisat2 -p 8 -x hisat2_index \
    --rna-strandness RF \
    -1 r1.fq.gz -2 r2.fq.gz | \
    samtools sort -@ 4 -o aligned.sorted.bam -

# Forward stranded
hisat2 -p 8 -x hisat2_index \
    --rna-strandness FR \
    -1 r1.fq.gz -2 r2.fq.gz | \
    samtools sort -@ 4 -o aligned.sorted.bam -
```

### Two-Pass Alignment (Manual)

```bash
# Pass 1: collect junctions
for r1 in *_R1.fq.gz; do
    base=$(basename $r1 _R1.fq.gz)
    r2="${base}_R2.fq.gz"
    hisat2 -p 8 -x hisat2_index \
        --novel-splicesite-outfile ${base}_splices.txt \
        -1 $r1 -2 $r2 -S /dev/null
done

# Combine
sort -u *_splices.txt > combined_splices.txt

# Pass 2: realign
for r1 in *_R1.fq.gz; do
    base=$(basename $r1 _R1.fq.gz)
    r2="${base}_R2.fq.gz"
    hisat2 -p 8 -x hisat2_index \
        --novel-splicesite-infile combined_splices.txt \
        -1 $r1 -2 $r2 | \
        samtools sort -@ 4 -o ${base}.sorted.bam -
done
```

---

## Memory Comparison

| Aligner | Human Genome Memory |
|---------|---------------------|
| STAR | ~30 GB |
| HISAT2 | ~8 GB |

## Related Skills

- `bio-mrna-seq-qc-preprocessing` - Upstream FASTQ QC
- `bio-mrna-seq-quantification` - Gene-level counting or pseudo-alignment
- `bio-mrna-seq-pipeline` - End-to-end workflow
