"""
Test module imports for spatial transcriptomics statistics package.

Run with: python -m pytest tests/test_imports.py -v
"""

import sys
import os

# Add scripts/python to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python'))


def test_import_core_stats():
    """Test core_stats module imports."""
    from core_stats import (
        compute_morans_i,
        compute_gearys_c,
        compute_lisa,
        compute_bivariate_moran,
        compare_morans_geary,
        run_autocorrelation_analysis
    )
    assert callable(compute_morans_i)
    assert callable(compute_lisa)


def test_import_hotspot():
    """Test hotspot module imports."""
    from hotspot import (
        compute_getis_ord_gi,
        compute_getis_ord_gi_batch,
        extract_hotspots,
        plot_hotspots,
        comprehensive_hotspot_analysis
    )
    assert callable(compute_getis_ord_gi)
    assert callable(comprehensive_hotspot_analysis)


def test_import_pattern():
    """Test pattern module imports."""
    from pattern import (
        compute_cooccurrence,
        compute_cooccurrence_probability,
        compute_join_counts,
        interpret_join_counts,
        compute_neighborhood_enrichment,
        compute_ripley_k,
        compute_ripley_l,
        plot_ripley
    )
    assert callable(compute_cooccurrence)
    assert callable(compute_ripley_k)


def test_import_network():
    """Test network module imports."""
    from network import (
        compute_centrality_scores,
        compute_spatial_centrality,
        compute_network_properties,
        compute_interaction_matrix,
        analyze_network_structure
    )
    assert callable(compute_centrality_scores)
    assert callable(analyze_network_structure)


def test_import_zones():
    """Test zones module imports."""
    from zones import (
        define_anchor_zones,
        define_neural_zones,
        compute_roe,
        interpret_roe_results,
        plot_roe_heatmap,
        analyze_spatial_zones
    )
    assert callable(define_anchor_zones)
    assert callable(compute_roe)


def test_import_utils():
    """Test utils module imports."""
    from utils import (
        validate_spatial_data,
        check_spatial_neighbors,
        infer_spatial_platform,
        suggest_neighbors
    )
    assert callable(validate_spatial_data)
    assert callable(infer_spatial_platform)


def test_import_all_from_init():
    """Test that __init__.py file exists and has correct exports."""
    init_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python', '__init__.py')

    # Verify the __init__.py file exists and has content
    assert os.path.exists(init_path), f"__init__.py not found at {init_path}"
    with open(init_path) as f:
        content = f.read()
        assert 'compute_morans_i' in content
        assert 'compute_getis_ord_gi' in content
        assert 'compute_roe' in content
        assert '__all__' in content


if __name__ == '__main__':
    print("Testing imports...")
    test_import_core_stats()
    print("✓ core_stats imports OK")
    test_import_hotspot()
    print("✓ hotspot imports OK")
    test_import_pattern()
    print("✓ pattern imports OK")
    test_import_network()
    print("✓ network imports OK")
    test_import_zones()
    print("✓ zones imports OK")
    test_import_utils()
    print("✓ utils imports OK")
    test_import_all_from_init()
    print("✓ __init__.py structure OK")
    print("\nAll import tests passed!")
