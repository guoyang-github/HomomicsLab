"""
Niche Comparison Example

Compare niche distributions across experimental groups or conditions.
Performs statistical testing for differential abundance and creates
visualizations for group comparisons.

Prerequisites:
    - Spatial data with niche annotations
    - Group/condition metadata in adata.obs
"""

import pandas as pd
import numpy as np
import scanpy as sc
from scipy.stats import chi2_contingency, fisher_exact


def compare_niches_by_group(adata, niche_key='niche_annotated', group_key='group'):
    """
    Compare niche distributions across experimental groups.

    Parameters
    ----------
    adata : AnnData
        Spatial data with niche annotations
    niche_key : str
        Column containing niche labels
    group_key : str
        Column for grouping (e.g., 'condition', 'sample')

    Returns
    -------
    DataFrame : Niche proportions per group
    DataFrame : Niche counts per group
    """
    # Count niches per group
    niche_counts = adata.obs.groupby([group_key, niche_key]).size().unstack(fill_value=0)

    # Convert to proportions
    niche_proportions = niche_counts.div(niche_counts.sum(axis=1), axis=0)

    print("Niche counts per group:")
    print(niche_counts)
    print("\nNiche proportions per group:")
    print(niche_proportions.round(3))

    return niche_proportions, niche_counts


def niche_differential_abundance(adata, niche_key='niche_annotated', group_key='group',
                                  test='chi2', correction='fdr_bh'):
    """
    Test for differential niche abundance between groups.

    Parameters
    ----------
    adata : AnnData
    niche_key : str
        Column with niche labels
    group_key : str
        Column with group assignments
    test : str
        'chi2' for chi-square test on full table
        'fisher' for Fisher's exact test per niche (2 groups only)
    correction : str
        Multiple testing correction method (None for no correction)

    Returns
    -------
    DataFrame : Differential abundance results per niche
    """
    from statsmodels.stats.multitest import multipletests

    groups = adata.obs[group_key].unique()
    niche_counts = adata.obs.groupby([group_key, niche_key]).size().unstack(fill_value=0)

    results = []

    if test == 'chi2':
        # Overall chi-square test on the full contingency table
        chi2, pval, dof, expected = chi2_contingency(niche_counts.values)
        print(f"Overall chi-square test: χ²={chi2:.3f}, p={pval:.2e}, df={dof}")

        # Per-niche comparisons (post-hoc)
        if len(groups) == 2:
            for niche in niche_counts.columns:
                # Build 2x2 table for this niche
                g0_count = niche_counts.loc[groups[0], niche]
                g1_count = niche_counts.loc[groups[1], niche]
                g0_total = niche_counts.loc[groups[0]].sum()
                g1_total = niche_counts.loc[groups[1]].sum()
                g0_other = g0_total - g0_count
                g1_other = g1_total - g1_count

                contingency = np.array([[g0_count, g0_other],
                                       [g1_count, g1_other]])

                _, pval_niche, _, _ = chi2_contingency(contingency)

                # Calculate proportions
                prop_g0 = g0_count / g0_total
                prop_g1 = g1_count / g1_total
                fold_change = prop_g1 / (prop_g0 + 1e-8)

                results.append({
                    'niche': niche,
                    'prop_group0': prop_g0,
                    'prop_group1': prop_g1,
                    'fold_change': fold_change,
                    'count_g0': g0_count,
                    'count_g1': g1_count,
                    'pval': pval_niche
                })

    elif test == 'fisher' and len(groups) == 2:
        for niche in niche_counts.columns:
            g0_count = niche_counts.loc[groups[0], niche]
            g1_count = niche_counts.loc[groups[1], niche]
            g0_total = niche_counts.loc[groups[0]].sum()
            g1_total = niche_counts.loc[groups[1]].sum()
            g0_other = g0_total - g0_count
            g1_other = g1_total - g1_count

            contingency = [[g0_count, g0_other],
                          [g1_count, g1_other]]

            _, pval_niche = fisher_exact(contingency)

            prop_g0 = g0_count / g0_total
            prop_g1 = g1_count / g1_total
            fold_change = prop_g1 / (prop_g0 + 1e-8)

            results.append({
                'niche': niche,
                'prop_group0': prop_g0,
                'prop_group1': prop_g1,
                'fold_change': fold_change,
                'count_g0': g0_count,
                'count_g1': g1_count,
                'pval': pval_niche
            })
    else:
        raise ValueError("For test='fisher', exactly 2 groups are required")

    results_df = pd.DataFrame(results)

    # Multiple testing correction
    if correction and len(results) > 0:
        _, qvals, _, _ = multipletests(results_df['pval'], method=correction)
        results_df['qval'] = qvals
        results_df['significant'] = results_df['qval'] < 0.05
    else:
        results_df['qval'] = results_df['pval']
        results_df['significant'] = results_df['pval'] < 0.05

    # Sort by significance
    results_df = results_df.sort_values('qval')

    print(f"\nDifferential abundance results (sorted by q-value):")
    print(results_df.round(4))

    n_sig = results_df['significant'].sum()
    print(f"\n{n_sig} niches significantly different (q < 0.05)")

    return results_df


def find_enriched_niches(results_df, group_name='group1', qval_threshold=0.05,
                         fc_threshold=1.5):
    """
    Identify niches enriched in a specific group.

    Parameters
    ----------
    results_df : DataFrame
        Output from niche_differential_abundance()
    group_name : str
        Name of group to check enrichment for
    qval_threshold : float
        FDR threshold for significance
    fc_threshold : float
        Minimum fold change for enrichment

    Returns
    -------
    DataFrame : Enriched niches
    """
    enriched = results_df[
        (results_df['qval'] < qval_threshold) &
        (results_df['fold_change'] > fc_threshold)
    ].sort_values('fold_change', ascending=False)

    print(f"Niches enriched in {group_name} (q < {qval_threshold}, FC > {fc_threshold}):")
    if len(enriched) > 0:
        print(enriched[['niche', 'prop_group0', 'prop_group1', 'fold_change', 'qval']])
    else:
        print("No enriched niches found")

    return enriched


def plot_niche_comparison(niche_proportions, title='Niche Distribution Comparison'):
    """
    Create grouped bar plot of niche proportions.

    Parameters
    ----------
    niche_proportions : DataFrame
        Output from compare_niches_by_group()
    title : str
        Plot title

    Returns
    -------
    fig : matplotlib Figure
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 6))

    niche_proportions.T.plot(kind='bar', ax=ax, width=0.8)
    ax.set_xlabel('Niche')
    ax.set_ylabel('Proportion')
    ax.set_title(title)
    ax.legend(title='Group', bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    return fig


def plot_niche_stacked(niche_proportions, title='Niche Composition by Group'):
    """
    Create stacked bar plot of niche distributions.

    Parameters
    ----------
    niche_proportions : DataFrame
        Output from compare_niches_by_group()
    title : str
        Plot title

    Returns
    -------
    fig : matplotlib Figure
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))

    niche_proportions.T.plot(kind='bar', stacked=True, ax=ax, colormap='tab20')
    ax.set_xlabel('Group')
    ax.set_ylabel('Proportion')
    ax.set_title(title)
    ax.legend(title='Niche', bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.tick_params(axis='x', rotation=0)

    plt.tight_layout()
    return fig


def export_comparison_results(results_df, niche_proportions, output_prefix='niche_comparison'):
    """
    Export comparison results to CSV files.

    Parameters
    ----------
    results_df : DataFrame
        Differential abundance results
    niche_proportions : DataFrame
        Niche proportions per group
    output_prefix : str
        Prefix for output files
    """
    results_file = f"{output_prefix}_statistics.csv"
    proportions_file = f"{output_prefix}_proportions.csv"

    results_df.to_csv(results_file, index=False)
    niche_proportions.to_csv(proportions_file)

    print(f"Results exported to:")
    print(f"  - {results_file}")
    print(f"  - {proportions_file}")


# Example usage
if __name__ == "__main__":
    # Example workflow:

    # 1. Load data with niche annotations
    # adata = sc.read_h5ad('spatial_data_annotated.h5ad')

    # 2. Compare niches between groups
    # niche_props, niche_counts = compare_niches_by_group(
    #     adata,
    #     niche_key='niche_annotated',
    #     group_key='condition'  # e.g., 'NI+', 'NI-'
    # )

    # 3. Statistical testing
    # da_results = niche_differential_abundance(
    #     adata,
    #     niche_key='niche_annotated',
    #     group_key='condition',
    #     test='chi2'
    # )

    # 4. Find enriched niches
    # enriched = find_enriched_niches(
    #     da_results,
    #     group_name='NI+',
    #     qval_threshold=0.05,
    #     fc_threshold=1.5
    # )

    # 5. Visualize
    # fig1 = plot_niche_comparison(niche_props, title='Niche Distribution by Condition')
    # fig1.savefig('niche_comparison_bar.png', dpi=300, bbox_inches='tight')

    # fig2 = plot_niche_stacked(niche_props, title='Niche Composition')
    # fig2.savefig('niche_comparison_stacked.png', dpi=300, bbox_inches='tight')

    # 6. Export results
    # export_comparison_results(da_results, niche_props, output_prefix='niche_comparison')

    print("Niche comparison example loaded successfully!")
    print("\nTo use:")
    print("1. Load your data with niche annotations")
    print("2. Compare groups with compare_niches_by_group()")
    print("3. Test significance with niche_differential_abundance()")
    print("4. Find enriched niches with find_enriched_niches()")
    print("5. Visualize with plot_niche_comparison() or plot_niche_stacked()")
    print("6. Export results with export_comparison_results()")
