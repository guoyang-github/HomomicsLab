---
name: bio-ribo-seq-index-building
description: Build reference indexes for Ribo-seq analysis including STAR genome index, bowtie2 transcriptome/rRNA indexes, and GTF preprocessing. Use before running the Ribo-seq pipeline.
tool_type: cli
primary_tool: STAR
---

## Version Compatibility

Reference examples tested with: STAR 2.7.11+, Bowtie2 2.5.3+, samtools 1.19+

Before using code patterns, verify installed versions match. If versions differ:
- CLI: `<tool> --version` then `<tool> --help` to confirm flags

If code throws errors, introspect the installed package and adapt the example to match the actual API rather than retrying.

# Ribo-seq Index Building

**"Build reference indexes for my Ribo-seq analysis"** → Generate STAR genome index, bowtie2 transcriptome/rRNA indexes, and preprocess GTF annotations. Run this step once before the main pipeline.

## Output Directory Structure

```
results/00_index/
├── star_genome/
├── bowtie2_transcriptome/
├── bowtie2_rrna/
├── genome.fa
├── transcriptome.fa
├── annotation.gtf
└── annotation_clean.gtf
```

## Prerequisites

- Genome FASTA (`genome.fa`)
- Annotation GTF (`annotation.gtf`)
- rRNA FASTA for depletion (`rrna.fa`)

## Step 1: Preprocess GTF

**Goal:** Clean and filter the annotation GTF for downstream tools (STAR, Plastid, RiboCode).

```bash
# Create output directory
mkdir -p results/00_index

# Filter to standard chromosomes and protein-coding / lncRNA genes
# Remove entries with missing gene_id or transcript_id
awk -F'\t' '
  $1 !~ /^#/ && $3 ~ /gene|transcript|exon|CDS|UTR|start_codon|stop_codon/ {
    if ($9 ~ /gene_id/ && $9 ~ /transcript_id/) {
      print
    }
  }
' annotation.gtf > results/00_index/annotation_clean.gtf
```

### Yeast GTF Special Handling

Yeast annotations often use `CDS` features directly with short or absent UTRs. Do not filter out `CDS`-only records.

```bash
# For yeast: keep CDS features explicitly
grep -E '^#|CDS|exon|gene|transcript|start_codon|stop_codon' yeast.gtf \
  > results/00_index/annotation_clean.gtf
```

### Plant GTF Special Handling

Plant GTFs may include chloroplast and mitochondrial annotations. By default, cytoplasmic Ribo-seq workflows filter these out. If your study targets organellar translation, retain the original annotation instead.

```bash
# Cytoplasmic Ribo-seq: exclude chloroplast and mitochondrial genes
# Arabidopsis chloroplast: ATCG*, mitochondrial: ATMG*
# NOTE: Remove the grep -vE lines below if you are studying organellar translation.
grep -vE '^ATCG|^ATMG' annotation.gtf > results/00_index/annotation_nuclear.gtf

# Organelle-specific analysis: keep only ATCG* / OsCG*
grep -E '^ATCG|^ATMG' annotation.gtf > results/00_index/annotation_organelle.gtf
```

## Step 2: Generate Transcriptome FASTA

```bash
# Using gffread (recommended)
gffread -w results/00_index/transcriptome.fa \
  -g genome.fa results/00_index/annotation_clean.gtf

# Alternative: gffread from cufflinks package
# gffread annotation_clean.gtf -g genome.fa -w transcriptome.fa
```

## Step 3: Build STAR Genome Index

```bash
# Determine read length for sjdbOverhang (default 49 for Ribo-seq ~50bp max)
SJDB_OVERHANG=49

STAR --runMode genomeGenerate \
  --genomeDir results/00_index/star_genome/ \
  --genomeFastaFiles genome.fa \
  --sjdbGTFfile results/00_index/annotation_clean.gtf \
  --sjdbOverhang $SJDB_OVERHANG \
  --runThreadN 8
```

### Yeast STAR Index

Yeast has few spliced genes; `sjdbOverhang` can remain standard.

```bash
STAR --runMode genomeGenerate \
  --genomeDir results/00_index/star_genome/ \
  --genomeFastaFiles genome.fa \
  --sjdbGTFfile results/00_index/annotation_clean.gtf \
  --sjdbOverhang 49 \
  --genomeSAindexNbases 10 \
  --runThreadN 8
```

### Plant STAR Index

Larger genomes (rice) may require increased `--genomeChrBinNbits`.

```bash
STAR --runMode genomeGenerate \
  --genomeDir results/00_index/star_genome/ \
  --genomeFastaFiles genome.fa \
  --sjdbGTFfile results/00_index/annotation_clean.gtf \
  --sjdbOverhang 49 \
  --genomeChrBinNbits 18 \
  --runThreadN 16
```

## Step 4: Build Bowtie2 Transcriptome Index

```bash
# For transcriptome alignment or rRNA removal
mkdir -p results/00_index/bowtie2_transcriptome

bowtie2-build results/00_index/transcriptome.fa \
  results/00_index/bowtie2_transcriptome/transcriptome

# Also build genome index if needed
mkdir -p results/00_index/bowtie2_genome
bowtie2-build genome.fa results/00_index/bowtie2_genome/genome
```

## Step 5: Build rRNA Index

```bash
mkdir -p results/00_index/bowtie2_rrna

bowtie2-build rrna.fa results/00_index/bowtie2_rrna/rrna

# Optional: build SortMeRNA index
# sortmerna --ref rrna.fa --index 1 --idx-dir results/00_index/sortmerna_rrna/
```

## Complete Bash Script

```bash
#!/bin/bash
# build_indexes.sh

GENOME_FA=$1
GTF=$2
RRNA_FA=$3
OUTDIR="results/00_index"
SJDB_OVERHANG=${4:-49}

mkdir -p "$OUTDIR"/star_genome "$OUTDIR"/bowtie2_transcriptome \
  "$OUTDIR"/bowtie2_rrna "$OUTDIR"/bowtie2_genome

# Clean GTF
awk -F'\t' '$1 !~ /^#/ && $9 ~ /gene_id/ && $9 ~ /transcript_id/' "$GTF" \
  > "$OUTDIR"/annotation_clean.gtf

# Transcriptome FASTA
gffread -w "$OUTDIR"/transcriptome.fa -g "$GENOME_FA" "$OUTDIR"/annotation_clean.gtf

# STAR index
STAR --runMode genomeGenerate \
  --genomeDir "$OUTDIR"/star_genome/ \
  --genomeFastaFiles "$GENOME_FA" \
  --sjdbGTFfile "$OUTDIR"/annotation_clean.gtf \
  --sjdbOverhang "$SJDB_OVERHANG" \
  --runThreadN 8

# Bowtie2 indexes
bowtie2-build "$OUTDIR"/transcriptome.fa "$OUTDIR"/bowtie2_transcriptome/transcriptome
bowtie2-build "$GENOME_FA" "$OUTDIR"/bowtie2_genome/genome
bowtie2-build "$RRNA_FA" "$OUTDIR"/bowtie2_rrna/rrna

echo "Index building complete. Output: $OUTDIR"
```

## Related Skills

- bio-ribo-seq-species-templates - Retrieve organism-specific `sjdbOverhang` and GTF handling rules
- bio-ribo-seq-riboseq-preprocessing - Uses the indexes built here
- bio-ribo-seq-rna-preprocessing - Uses the same STAR genome index
