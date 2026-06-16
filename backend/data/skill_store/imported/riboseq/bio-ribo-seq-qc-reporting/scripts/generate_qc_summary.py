#!/usr/bin/env python3
"""Generate a summary CSV of key QC metrics per sample."""
import argparse
import os
import re
import json
import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samplesheet", required=True)
    parser.add_argument("--flagstat-dir", default="results/02_ribo_preprocessing")
    parser.add_argument("--psite-dir", default="results/03_periodicity")
    parser.add_argument("--out", default="results/01_qc/qc_summary.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.samplesheet)
    records = []
    for _, row in df.iterrows():
        sample = row['sample']
        flagstat = os.path.join(args.flagstat_dir, f'{sample}.flagstat')
        total, mapped = 0, 0
        if os.path.exists(flagstat):
            with open(flagstat) as f:
                content = f.read()
            m_total = re.search(r'(\d+)\s+\+\s+\d+\s+in total', content)
            m_mapped = re.search(r'(\d+)\s+\+\s+\d+\s+mapped \(', content)
            if m_total:
                total = int(m_total.group(1))
            if m_mapped:
                mapped = int(m_mapped.group(1))

        psite_json = os.path.join(args.psite_dir, f'{sample}_psite_offsets.json')
        periodicity_score = np.nan
        if os.path.exists(psite_json):
            with open(psite_json) as f:
                pdata = json.load(f)
                periodicity_score = pdata.get('periodicity_score', np.nan)

        records.append({
            'sample': sample,
            'total_reads': total,
            'mapped_reads': mapped,
            'mapping_rate': mapped / total if total else np.nan,
            'periodicity_score': periodicity_score
        })

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    pd.DataFrame(records).to_csv(args.out, index=False)
    print(f"Saved QC summary to {args.out}")


if __name__ == "__main__":
    main()
