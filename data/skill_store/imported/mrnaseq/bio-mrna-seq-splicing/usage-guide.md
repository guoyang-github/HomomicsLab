# Usage Guide: bio-mrna-seq-splicing

## When to Use
Use this skill when your research question involves alternative splicing, exon inclusion, or isoform switching rather than just gene-level differential expression.

## Inputs
- **rMATS-turbo**: sorted BAM files + GTF annotation
- **SUPPA2**: transcript TPM matrix (from Salmon/kallisto) + GTF

## Outputs
- PSI (percent spliced in) tables per event type (SE, A5SS, A3SS, MXE, RI)
- Differential splicing results (FDR, delta PSI)
- Significant event lists and visualization

## Quick Start
### rMATS-turbo
```bash
rmats.py --b1 ctrl_bams.txt --b2 treat_bams.txt --gtf annotation.gtf \
    -t paired --readLength 150 --nthread 8 --od rmats_output --tmp rmats_tmp
```

### SUPPA2
```bash
suppa.py generateEvents -i annotation.gtf -o events/ -f ioe
suppa.py psiPerEvent -i events/ -e transcript_tpm.tsv -o psi_output
suppa.py diffSplice -m empirical -i events/ -p ctrl.psi treat.psi -e events.ioe -o diff_output
```

## Tips
- **rMATS** is more sensitive for novel junctions but requires BAMs.
- **SUPPA2** is faster and works from transcript abundances, but depends on annotation completeness.
- Filter significant events by **FDR < 0.05** and **|delta PSI| > 0.1**.

## Workflow Position
**Upstream**: `bio-mrna-seq-alignment` (rMATS) or `bio-mrna-seq-quantification` (SUPPA2)  
**Downstream**: Validation, isoform-level visualization
