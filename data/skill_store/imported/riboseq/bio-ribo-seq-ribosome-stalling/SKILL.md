---
name: bio-ribo-seq-ribosome-stalling
description: Detect ribosome pausing and stalling sites from Ribo-seq data at codon resolution. Use when studying translational regulation, identifying pause sites, or analyzing codon-specific translation dynamics.
tool_type: python
primary_tool: Plastid
---

## Version Compatibility

Reference examples tested with: BioPython 1.83+, numpy 1.26+, scipy 1.12+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

# Ribosome Stalling Detection

**"Find ribosome pause sites in my data"** → Detect codon-level ribosome stalling and pausing events from Ribo-seq footprint density, identifying positions with abnormally high ribosome occupancy.

## Standard Input

- Aligned BAM: `results/02_ribo_preprocessing/{sample}.sorted.bam`
- P-site offsets: `results/03_periodicity/{sample}_psite_offsets.json`
- Annotation: `results/00_index/annotation_clean.gtf`

## Concept

Ribosome stalling/pausing occurs when ribosomes slow or stop at specific codons:
- Rare codons (low tRNA availability)
- Specific amino acid motifs (polyproline)
- Regulatory pause sites (upstream of stress response genes)
- Nascent chain interactions

## Calculate Codon-Level Occupancy

```bash
python scripts/get_codon_occupancy.py \
  --bam results/02_ribo_preprocessing/sample1.sorted.bam \
  --gtf results/00_index/annotation_clean.gtf \
  --offset 12 \
  --out results/07_stalling/codon_occupancy.json
```

## Identify Pause Sites

```bash
python scripts/find_pause_sites.py \
  --occupancy results/07_stalling/codon_occupancy.json \
  --zscore 3.0 \
  --out results/07_stalling/pause_sites.json
```

## Codon-Specific Occupancy Table

```bash
python scripts/codon_occupancy_table.py \
  --bam results/02_ribo_preprocessing/sample1.sorted.bam \
  --gtf results/00_index/annotation_clean.gtf \
  --offset 12 \
  --out results/07_stalling/codon_means.tsv
```

## Correlate with tRNA Abundance

```bash
python scripts/correlate_trna.py \
  --occupancy results/07_stalling/codon_means.tsv \
  --trna data/trna_abundance.json
```

## Extract Pause Motifs

```bash
python scripts/extract_pause_motifs.py \
  --pauses results/07_stalling/pause_sites.json \
  --sequences data/transcript_sequences.json \
  --window 10 \
  --out results/07_stalling/pause_motifs.txt
```

## Known Pause Motifs

| Motif | Description |
|-------|-------------|
| PPP | Polyproline (ribosome tunnel interaction) |
| XPX | Proline-containing |
| D/E-rich | Negatively charged nascent chain |
| Stop codon context | Influenced by nucleotides around stop |

## Related Skills

- bio-ribo-seq-ribosome-periodicity - Provides P-site offsets via JSON
- bio-ribo-seq-riboseq-preprocessing - Provides aligned BAM
- bio-ribo-seq-orf-detection - Context for pause sites
- bio-ribo-seq-translation-efficiency - Gene-level translation context
