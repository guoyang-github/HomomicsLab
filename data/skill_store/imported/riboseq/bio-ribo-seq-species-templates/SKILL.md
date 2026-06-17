---
name: bio-ribo-seq-species-templates
description: Provide standardized species-specific parameter templates for Ribo-seq analysis. Use when configuring preprocessing, alignment, P-site offset, and QC parameters for human, mouse, yeast, or plant samples.
tool_type: mixed
primary_tool: bash
---

## Version Compatibility

Reference examples tested with: STAR 2.7.11+, Bowtie2 2.5.3+, cutadapt 4.4+

Before using code patterns, verify installed versions match. If versions differ:
- CLI: `<tool> --version` then `<tool> --help` to confirm flags

If code throws errors, introspect the installed package and adapt the example to match the actual API rather than retrying.

# Ribo-seq Species Parameter Templates

**"Set up Ribo-seq parameters for my organism"** → Select a standardized parameter template for human/mouse, yeast (*S. cerevisiae*), or plant (Arabidopsis/rice) to ensure correct adapter sequences, footprint size ranges, rRNA databases, and P-site offsets.

## Supported Species

| Species | Key Identifier | Typical Footprint Size | P-site Offset Range |
|---------|---------------|------------------------|---------------------|
| Human (*Homo sapiens*) | `human` | 28-32 nt | 12-15 |
| Mouse (*Mus musculus*) | `mouse` | 28-32 nt | 12-15 |
| Yeast (*Saccharomyces cerevisiae*) | `yeast` | 27-31 nt | 12-14 |
| Arabidopsis (*Arabidopsis thaliana*) | `arabidopsis` | 27-30 nt | 13-15 |
| Rice (*Oryza sativa*) | `rice` | 27-30 nt | 13-15 |

## Parameter Template Files

Generate a species config file to standardize downstream analysis:

```bash
# Generate species config
bash generate_species_config.sh human > species_config.sh
source species_config.sh
```

## Human / Mouse (Default)

```bash
SPECIES="human"
ADAPTER_SEQ="CTGTAGGCACCATCAAT"        # TruSeq small RNA / NEBNext compatible
RNA_SEQ_ADAPTER_R1="AGATCGGAAGAGCACACGTCTGAACTCCAGTCA"
RNA_SEQ_ADAPTER_R2="AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT"
MIN_LENGTH=28
MAX_LENGTH=32
P_SITE_OFFSETS="12:12:13:13:14"        # 28:12, 29:12, 30:13, 31:13, 32:14
P_SITE_OFFSETS_JSON='{"28": 12, "29": 12, "30": 13, "31": 13, "32": 14}'
P_SITE_OFFSET_MIN=10
P_SITE_OFFSET_MAX=16
RRNA_DB="silva-euk-18s-id95,silva-euk-28s-id98"  # SILVA eukaryotic rRNA
STAR_ALIGN_INTRON_MAX=1                # Ribo-seq footprints should not span splice junctions
RNA_SEQ_ALIGN_INTRON_MAX=1000000       # mRNA-seq only
STAR_ALIGN_SJDB_OVERHANG=49
GTF_FEATURE="exon"
STOP_CODON_READTHROUGH="false"
CHLOROPLAST_RRNA=""                    # Not applicable
MITO_RRNA_FILTER="MT-"                 # Filter mitochondrial rRNA annotations
```

## Yeast (*S. cerevisiae*)

```bash
SPECIES="yeast"
ADAPTER_SEQ="CTGTAGGCACCATCAAT"        # TruSeq small RNA
RNA_SEQ_ADAPTER_R1="AGATCGGAAGAGCACACGTCTGAACTCCAGTCA"
RNA_SEQ_ADAPTER_R2="AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT"
MIN_LENGTH=27
MAX_LENGTH=31
P_SITE_OFFSETS="12:12:13:13:14"        # 27:12, 28:12, 29:13, 30:13, 31:14
P_SITE_OFFSETS_JSON='{"27": 12, "28": 12, "29": 13, "30": 13, "31": 14}'
P_SITE_OFFSET_MIN=10
P_SITE_OFFSET_MAX=16
RRNA_DB="silva-fungal"                 # Ensembl Fungal / SILVA yeast rRNA
STAR_ALIGN_INTRON_MAX=1                # Ribo-seq footprints should not span splice junctions
RNA_SEQ_ALIGN_INTRON_MAX=1             # Yeast has few introns
STAR_ALIGN_SJDB_OVERHANG=49
GTF_FEATURE="CDS"
STOP_CODON_READTHROUGH="true"          # Yeast has known readthrough
CHLOROPLAST_RRNA=""
MITO_RRNA_FILTER=""

# Yeast-specific: No extensive 5' UTR filtering (most yeast genes have short UTRs)
FILTER_SHORT_UTR5="false"
```

## Arabidopsis (*A. thaliana*)

```bash
SPECIES="arabidopsis"
ADAPTER_SEQ="CTGTAGGCACCATCAAT"        # TruSeq small RNA
RNA_SEQ_ADAPTER_R1="AGATCGGAAGAGCACACGTCTGAACTCCAGTCA"
RNA_SEQ_ADAPTER_R2="AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT"
MIN_LENGTH=27
MAX_LENGTH=30
P_SITE_OFFSETS="13:13:14:14"           # 27:13, 28:13, 29:14, 30:14
P_SITE_OFFSETS_JSON='{"27": 13, "28": 13, "29": 14, "30": 14}'
P_SITE_OFFSET_MIN=11
P_SITE_OFFSET_MAX=17
RRNA_DB="silva-plant-16s-id90,silva-plant-23s-id98"  # Plant rRNA + chloroplast
STAR_ALIGN_INTRON_MAX=1                # Ribo-seq footprints should not span splice junctions
RNA_SEQ_ALIGN_INTRON_MAX=5000          # mRNA-seq only
STAR_ALIGN_SJDB_OVERHANG=49
GTF_FEATURE="exon"
STOP_CODON_READTHROUGH="false"
CHLOROPLAST_RRNA="ATCG"                # Chloroplast chromosome prefix
MITO_RRNA_FILTER=""

# Arabidopsis-specific: Remove chloroplast and mitochondrial rRNA reads aggressively
REMOVE_ORGANELLE_RRNA="true"
```

## Rice (*O. sativa*)

```bash
SPECIES="rice"
ADAPTER_SEQ="CTGTAGGCACCATCAAT"        # TruSeq small RNA
RNA_SEQ_ADAPTER_R1="AGATCGGAAGAGCACACGTCTGAACTCCAGTCA"
RNA_SEQ_ADAPTER_R2="AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT"
MIN_LENGTH=27
MAX_LENGTH=30
P_SITE_OFFSETS="13:13:14:14"           # 27:13, 28:13, 29:14, 30:14
P_SITE_OFFSETS_JSON='{"27": 13, "28": 13, "29": 14, "30": 14}'
P_SITE_OFFSET_MIN=11
P_SITE_OFFSET_MAX=17
RRNA_DB="silva-plant-16s-id90,silva-plant-23s-id98"  # Plant rRNA
STAR_ALIGN_INTRON_MAX=1                # Ribo-seq footprints should not span splice junctions
RNA_SEQ_ALIGN_INTRON_MAX=10000         # mRNA-seq only
STAR_ALIGN_SJDB_OVERHANG=49
GTF_FEATURE="exon"
STOP_CODON_READTHROUGH="false"
CHLOROPLAST_RRNA="OsCG"                # Chloroplast chromosome prefix (RAP-DB)
MITO_RRNA_FILTER=""
REMOVE_ORGANELLE_RRNA="true"
```

## Bash Template Generator

```bash
#!/bin/bash
# generate_species_config.sh

SPECIES=$1

case $SPECIES in
  human|mouse)
    cat <<'EOF'
SPECIES="$SPECIES"
ADAPTER_SEQ="CTGTAGGCACCATCAAT"
RNA_SEQ_ADAPTER_R1="AGATCGGAAGAGCACACGTCTGAACTCCAGTCA"
RNA_SEQ_ADAPTER_R2="AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT"
MIN_LENGTH=28
MAX_LENGTH=32
P_SITE_OFFSETS="12:12:13:13:14"
P_SITE_OFFSETS_JSON='{"28": 12, "29": 12, "30": 13, "31": 13, "32": 14}'
RRNA_DB="silva-euk-18s-id95,silva-euk-28s-id98"
STAR_ALIGN_INTRON_MAX=1
RNA_SEQ_ALIGN_INTRON_MAX=1000000
STAR_ALIGN_SJDB_OVERHANG=49
GTF_FEATURE="exon"
STOP_CODON_READTHROUGH="false"
MITO_RRNA_FILTER="MT-"
EOF
    ;;
  yeast)
    cat <<'EOF'
SPECIES="yeast"
ADAPTER_SEQ="CTGTAGGCACCATCAAT"
RNA_SEQ_ADAPTER_R1="AGATCGGAAGAGCACACGTCTGAACTCCAGTCA"
RNA_SEQ_ADAPTER_R2="AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT"
MIN_LENGTH=27
MAX_LENGTH=31
P_SITE_OFFSETS="12:12:13:13:14"
P_SITE_OFFSETS_JSON='{"27": 12, "28": 12, "29": 13, "30": 13, "31": 14}'
RRNA_DB="silva-fungal"
STAR_ALIGN_INTRON_MAX=1
RNA_SEQ_ALIGN_INTRON_MAX=1
STAR_ALIGN_SJDB_OVERHANG=49
GTF_FEATURE="CDS"
STOP_CODON_READTHROUGH="true"
FILTER_SHORT_UTR5="false"
EOF
    ;;
  arabidopsis)
    cat <<'EOF'
SPECIES="arabidopsis"
ADAPTER_SEQ="CTGTAGGCACCATCAAT"
RNA_SEQ_ADAPTER_R1="AGATCGGAAGAGCACACGTCTGAACTCCAGTCA"
RNA_SEQ_ADAPTER_R2="AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT"
MIN_LENGTH=27
MAX_LENGTH=30
P_SITE_OFFSETS="13:13:14:14"
P_SITE_OFFSETS_JSON='{"27": 13, "28": 13, "29": 14, "30": 14}'
RRNA_DB="silva-plant-16s-id90,silva-plant-23s-id98"
STAR_ALIGN_INTRON_MAX=1
RNA_SEQ_ALIGN_INTRON_MAX=5000
STAR_ALIGN_SJDB_OVERHANG=49
GTF_FEATURE="exon"
STOP_CODON_READTHROUGH="false"
CHLOROPLAST_RRNA="ATCG"
REMOVE_ORGANELLE_RRNA="true"
EOF
    ;;
  rice)
    cat <<'EOF'
SPECIES="rice"
ADAPTER_SEQ="CTGTAGGCACCATCAAT"
RNA_SEQ_ADAPTER_R1="AGATCGGAAGAGCACACGTCTGAACTCCAGTCA"
RNA_SEQ_ADAPTER_R2="AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT"
MIN_LENGTH=27
MAX_LENGTH=30
P_SITE_OFFSETS="13:13:14:14"
P_SITE_OFFSETS_JSON='{"27": 13, "28": 13, "29": 14, "30": 14}'
RRNA_DB="silva-plant-16s-id90,silva-plant-23s-id98"
STAR_ALIGN_INTRON_MAX=1
RNA_SEQ_ALIGN_INTRON_MAX=10000
STAR_ALIGN_SJDB_OVERHANG=49
GTF_FEATURE="exon"
STOP_CODON_READTHROUGH="false"
CHLOROPLAST_RRNA="OsCG"
REMOVE_ORGANELLE_RRNA="true"
EOF
    ;;
  *)
    echo "Unknown species: $SPECIES" >&2
    exit 1
    ;;
esac
```

## JSON Config Generator

```python
import json

SPECIES_PARAMS = {
    "human": {
        "adapter_seq": "CTGTAGGCACCATCAAT",
        "rna_seq_adapter_r1": "AGATCGGAAGAGCACACGTCTGAACTCCAGTCA",
        "rna_seq_adapter_r2": "AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT",
        "min_length": 28,
        "max_length": 32,
        "p_site_offsets": {28: 12, 29: 12, 30: 13, 31: 13, 32: 14},
        "rrna_db": ["silva-euk-18s-id95", "silva-euk-28s-id98"],
        "star_intron_max": 1,
        "gtf_feature": "exon",
        "stop_codon_readthrough": False
    },
    "mouse": {
        "adapter_seq": "CTGTAGGCACCATCAAT",
        "rna_seq_adapter_r1": "AGATCGGAAGAGCACACGTCTGAACTCCAGTCA",
        "rna_seq_adapter_r2": "AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT",
        "min_length": 28,
        "max_length": 32,
        "p_site_offsets": {28: 12, 29: 12, 30: 13, 31: 13, 32: 14},
        "rrna_db": ["silva-euk-18s-id95", "silva-euk-28s-id98"],
        "star_intron_max": 1,
        "gtf_feature": "exon",
        "stop_codon_readthrough": False
    },
    "yeast": {
        "adapter_seq": "CTGTAGGCACCATCAAT",
        "rna_seq_adapter_r1": "AGATCGGAAGAGCACACGTCTGAACTCCAGTCA",
        "rna_seq_adapter_r2": "AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT",
        "min_length": 27,
        "max_length": 31,
        "p_site_offsets": {27: 12, 28: 12, 29: 13, 30: 13, 31: 14},
        "rrna_db": ["silva-fungal"],
        "star_intron_max": 1,
        "gtf_feature": "CDS",
        "stop_codon_readthrough": True,
        "filter_short_utr5": False
    },
    "arabidopsis": {
        "adapter_seq": "CTGTAGGCACCATCAAT",
        "rna_seq_adapter_r1": "AGATCGGAAGAGCACACGTCTGAACTCCAGTCA",
        "rna_seq_adapter_r2": "AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT",
        "min_length": 27,
        "max_length": 30,
        "p_site_offsets": {27: 13, 28: 13, 29: 14, 30: 14},
        "rrna_db": ["silva-plant-16s-id90", "silva-plant-23s-id98"],
        "star_intron_max": 5000,
        "gtf_feature": "exon",
        "stop_codon_readthrough": False,
        "chloroplast_rrna": "ATCG",
        "remove_organelle_rrna": True
    },
    "rice": {
        "adapter_seq": "CTGTAGGCACCATCAAT",
        "rna_seq_adapter_r1": "AGATCGGAAGAGCACACGTCTGAACTCCAGTCA",
        "rna_seq_adapter_r2": "AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT",
        "min_length": 27,
        "max_length": 30,
        "p_site_offsets": {27: 13, 28: 13, 29: 14, 30: 14},
        "rrna_db": ["silva-plant-16s-id90", "silva-plant-23s-id98"],
        "star_intron_max": 10000,
        "gtf_feature": "exon",
        "stop_codon_readthrough": False,
        "chloroplast_rrna": "OsCG",
        "remove_organelle_rrna": True
    }
}

def write_species_json(species, outpath):
    with open(outpath, 'w') as f:
        json.dump(SPECIES_PARAMS[species], f, indent=2)
```

## Related Skills

- bio-ribo-seq-index-building - Use STAR_ALIGN_SJDB_OVERHANG from template when building indexes
- bio-ribo-seq-riboseq-preprocessing - Use adapter, length, and rRNA params from template
- bio-ribo-seq-ribosome-periodicity - Use p_site_offsets from template as starting values
