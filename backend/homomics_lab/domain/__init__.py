"""Domain declaration system: single-file domain configuration for HomomicsLab.

A domain in HomomicsLab is a complete bioinformatics sub-discipline (e.g. single-cell,
metagenomics, proteomics) declared in a single domain.yaml file. The DomainLoader
reads this file and automatically registers skills, strategies, roles, intents,
and DAG seeds into the system.
"""

from homomics_lab.domain.models import (
    DomainDefinition,
    DomainPhase,
    DomainStateCheck,
    DomainIntent,
    DomainDAGSeed,
    DomainRole,
)
from homomics_lab.domain.loader import DomainLoader
from homomics_lab.domain.registry import DomainRegistry, get_domain_registry

__all__ = [
    "DomainDefinition",
    "DomainPhase",
    "DomainStateCheck",
    "DomainIntent",
    "DomainDAGSeed",
    "DomainRole",
    "DomainLoader",
    "DomainRegistry",
    "get_domain_registry",
]
