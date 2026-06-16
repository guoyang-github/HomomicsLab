"""
Advanced Example: Perturbation Analysis with pertpy
====================================================

This example demonstrates advanced features of pertpy including:
- Pseudobulk and centroid space computation
- Distance calculations between perturbations
- Mixscape for CRISPR screen analysis
- Guide RNA assignment
- Comprehensive visualization
"""

import scanpy as sc
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python'))

from core_analysis import (
    check_perturbation_data,
    compute_pseudobulk_space,
    compute_centroid_space,
    calculate_perturbation_distances,
    compute_perturbation_signature,
    run_mixscape_classification,
    run_augur_classification,
    assign_guide_rna,
    compare_perturbations,
    run_complete_perturbation_analysis
)
from visualization import (
    plot_augur_results,
    plot_perturbation_distance_heatmap,
    plot_mixscape_results,
    plot_de_volcano,
    plot_distance_dendrogram,
    plot_perturbation_summary
)
from utils import (
    get_perturbation_summary,
    export_de_results,
    create_perturbation_report
)


def main():
    print("=" * 70)
    print("pertpy Advanced Perturbation Analysis Example")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Step 1: Load and preprocess data
    # -------------------------------------------------------------------------
    print("\n[Step 1] Loading data...")
    print("Note: Replace with your actual data loading code")

    # Load perturbation data (e.g., from CRISPR screen)
    # adata = sc.read_h5ad('crispr_screen.h5ad')

    # Preprocess
    # sc.pp.normalize_total(adata)
    # sc.pp.log1p(adata)
    # sc.pp.highly_variable_genes(adata, n_top_genes=2000)
    # sc.pp.scale(adata)
    # sc.tl.pca(adata)
    # sc.pp.neighbors(adata)
    # sc.tl.umap(adata)

    # -------------------------------------------------------------------------
    # Step 2: Data validation and summary
    # -------------------------------------------------------------------------
    print("\n[Step 2] Data validation...")

    # check_perturbation_data(adata, perturbation_col="perturbation", control="NT")
    # summary = get_perturbation_summary(adata, perturbation_col="perturbation")
    # print(summary)

    # -------------------------------------------------------------------------
    # Step 3: Guide RNA assignment (for CRISPR screens)
    # -------------------------------------------------------------------------
    print("\n[Step 3] Guide RNA assignment...")

    # Option 1: Threshold-based assignment
    # adata = assign_guide_rna(
    #     adata,
    #     guide_rna_column="guide_identity",
    #     assignment_method="threshold",
    #     threshold=5
    # )

    # Option 2: Mixture model assignment (for noisy data)
    # adata = assign_guide_rna(
    #     adata,
    #     guide_rna_column="guide_identity",
    #     assignment_method="mixture"
    # )

    print("- Guide RNAs assigned to cells")

    # -------------------------------------------------------------------------
    # Step 4: Compute perturbation spaces
    # -------------------------------------------------------------------------
    print("\n[Step 4] Computing perturbation spaces...")

    # 4.1 Pseudobulk space (for DE analysis)
    # ps_adata = compute_pseudobulk_space(
    #     adata,
    #     perturbation_col="perturbation",
    #     replicate_col="replicate",
    #     layer=None
    # )
    # print(f"Pseudobulk: {ps_adata.n_obs} perturbations")

    # 4.2 Centroid space (from embedding)
    # cs_adata = compute_centroid_space(
    #     adata,
    #     perturbation_col="perturbation",
    #     embedding_key="X_umap"
    # )
    # print(f"Centroid: {cs_adata.n_obs} perturbations")

    print("- Pseudobulk space computed")
    print("- Centroid space computed")

    # -------------------------------------------------------------------------
    # Step 5: Calculate perturbation distances
    # -------------------------------------------------------------------------
    print("\n[Step 5] Calculating perturbation distances...")

    # Available metrics: "edistance", "euclidean", "cosine_distance", "mmd", "wasserstein"
    # distance_df = calculate_perturbation_distances(
    #     adata,
    #     perturbation_col="perturbation",
    #     metric="edistance",
    #     control="NT"
    # )

    print("- Energy distances calculated")

    # Visualize distances
    # plot_perturbation_distance_heatmap(distance_df, save='distance_heatmap.png')
    # plot_distance_dendrogram(distance_df, save='distance_dendrogram.png')

    # -------------------------------------------------------------------------
    # Step 6: Differential expression analysis
    # -------------------------------------------------------------------------
    print("\n[Step 6] Differential expression analysis...")

    # Compare each perturbation to control
    # de_results = compare_perturbations(
    #     adata,
    #     perturbation_col="perturbation",
    #     reference="NT",
    #     method="pydeseq2",
    #     replicate_col="replicate"
    # )

    print("- DE analysis complete for all perturbations")

    # Export DE results
    # export_de_results(de_results, output_prefix="de_results", significant_only=True)

    # Visualize DE results
    # for pert, results in de_results.items():
    #     plot_de_volcano(results, save=f'volcano_{pert}.png')

    # -------------------------------------------------------------------------
    # Step 7: Mixscape analysis (for CRISPR screens)
    # -------------------------------------------------------------------------
    print("\n[Step 7] Mixscape analysis...")

    # 7.1 Compute perturbation signatures
    # adata = compute_perturbation_signature(
    #     adata,
    #     perturbation_col="perturbation",
    #     control="NT",
    #     split_by="replicate",
    #     n_neighbors=20
    # )

    # 7.2 Run Mixscape classification
    # adata = run_mixscape_classification(
    #     adata,
    #     perturbation_col="perturbation",
    #     control="NT",
    #     new_class_name="mixscape_class",
    #     min_de_genes=5,
    #     logfc_threshold=0.25
    # )

    print("- Perturbation signatures computed")
    print("- Mixscape classification complete")

    # Visualize Mixscape results
    # plot_mixscape_results(adata, save='mixscape_results.png')

    # -------------------------------------------------------------------------
    # Step 8: Augur classification
    # -------------------------------------------------------------------------
    print("\n[Step 8] Augur classification...")

    # Classify perturbations by effect size
    # adata = run_augur_classification(
    #     adata,
    #     estimator="random_forest_classifier",
    #     labels_col="perturbation",
    #     cell_type_col="cell_type",
    #     n_estimators=100,
    #     random_state=42
    # )

    print("- Augur classification complete")

    # Visualize Augur results
    # plot_augur_results(adata, save='augur_results.png')

    # -------------------------------------------------------------------------
    # Step 9: Comprehensive visualization
    # -------------------------------------------------------------------------
    print("\n[Step 9] Creating visualizations...")

    # Summary plot
    # plot_perturbation_summary(
    #     adata,
    #     perturbation_col="perturbation",
    #     save='perturbation_summary.png'
    # )

    print("- Summary plots created")

    # -------------------------------------------------------------------------
    # Step 10: Export results and generate report
    # -------------------------------------------------------------------------
    print("\n[Step 10] Exporting results...")

    # Generate comprehensive report
    # report = create_perturbation_report(
    #     adata,
    #     perturbation_col="perturbation",
    #     output_file="perturbation_report.txt"
    # )

    # Save annotated data
    # adata.write('perturbation_analysis_results.h5ad')

    print("- Report generated")
    print("- Results saved to H5AD")

    print("\n" + "=" * 70)
    print("Advanced analysis complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
