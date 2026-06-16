# bio-single-cell-doublet-scrublet Python module
# Scrublet wrapper for doublet detection

from .core_analysis import (
    run_scrublet,
    filter_doublets,
    calculate_doublet_rate
)

__all__ = [
    'run_scrublet',
    'filter_doublets',
    'calculate_doublet_rate'
]
