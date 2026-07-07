#!/usr/bin/env nextflow

nextflow.enable.dsl = 2

params.samplesheet = "samplesheet.csv"
params.outdir = "results"
params.min_genes = 200
params.min_cells = 3
params.mt_threshold = 5.0
params.n_top_genes = 2000
params.n_pcs = 30
params.n_neighbors = 15
params.leiden_resolution = 0.5
params.threads = 4

process SC_QC {
    tag "$sample"
    container 'quay.io/biocontainers/scanpy:1.9.8--pyhdfd78af_0'

    input:
        tuple val(sample), path(input_path)
    output:
        tuple val(sample), path("${sample}_qc.h5ad"), emit: h5ad

    """
    python - << 'PYEOF'
    import anndata
    anndata.settings.allow_write_nullable_strings = True
    import scanpy as sc
    adata = sc.read("${input_path}")
    adata.var['mt'] = adata.var_names.str.startswith('MT-')
    sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], percent_top=None, log1p=False, inplace=True)
    sc.pp.filter_cells(adata, min_genes=${params.min_genes})
    sc.pp.filter_genes(adata, min_cells=${params.min_cells})
    adata = adata[adata.obs.pct_counts_mt < ${params.mt_threshold}, :]
    adata.write("${sample}_qc.h5ad")
    PYEOF
    """
}

process SC_NORMALIZE {
    tag "$sample"
    container 'quay.io/biocontainers/scanpy:1.9.8--pyhdfd78af_0'

    input:
        tuple val(sample), path(h5ad)
    output:
        tuple val(sample), path("${sample}_normalized.h5ad"), emit: h5ad

    """
    python - << 'PYEOF'
    import anndata
    anndata.settings.allow_write_nullable_strings = True
    import scanpy as sc
    adata = sc.read("${h5ad}")
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=${params.n_top_genes})
    adata.write("${sample}_normalized.h5ad")
    PYEOF
    """
}

process SC_CLUSTER {
    tag "$sample"
    container 'quay.io/biocontainers/scanpy:1.9.8--pyhdfd78af_0'
    publishDir "${params.outdir}/${sample}", mode: 'copy'

    input:
        tuple val(sample), path(h5ad)
    output:
        path "${sample}_clustered.h5ad", emit: h5ad
        path "${sample}_umap.png", emit: plot

    """
    python - << 'PYEOF'
    import anndata
    anndata.settings.allow_write_nullable_strings = True
    import scanpy as sc
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    adata = sc.read("${h5ad}")
    adata = adata[:, adata.var.highly_variable]
    sc.tl.pca(adata, n_comps=${params.n_pcs})
    sc.pp.neighbors(adata, n_neighbors=${params.n_neighbors})
    sc.tl.umap(adata)
    sc.tl.leiden(adata, resolution=${params.leiden_resolution})
    adata.write("${sample}_clustered.h5ad")
    fig, ax = plt.subplots(figsize=(6, 5))
    sc.pl.umap(adata, color='leiden', ax=ax, show=False)
    fig.savefig("${sample}_umap.png", dpi=150, bbox_inches='tight')
    PYEOF
    """
}

workflow {
    Channel.fromPath(params.samplesheet)
        .splitCsv(header: true)
        .map { row -> tuple(row.sample, file(row.input_path)) }
        .set { inputs_ch }

    SC_QC(inputs_ch)
    SC_NORMALIZE(SC_QC.out.h5ad)
    SC_CLUSTER(SC_NORMALIZE.out.h5ad)
}
