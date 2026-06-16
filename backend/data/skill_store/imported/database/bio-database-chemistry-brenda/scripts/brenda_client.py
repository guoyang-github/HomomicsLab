"""
BRENDA SOAP API Client

Minimal client for BRENDA enzyme database SOAP API.
Requires BRENDA account (free registration at https://www.brenda-enzymes.org/).

Environment variables:
    BRENDA_EMAIL: Your BRENDA account email
    BRENDA_PASSWORD: Your BRENDA account password (hashed with SHA-256 before transmission)

Usage:
    from brenda_client import get_km_values, get_reactions

    km_data = get_km_values("1.1.1.1", organism="*", substrate="*")
    reactions = get_reactions("1.1.1.1")
"""

import os
import hashlib
from typing import List, Optional

try:
    from zeep import Client, Settings
    from zeep.exceptions import Fault, TransportError
    ZEEP_AVAILABLE = True
except ImportError:
    ZEEP_AVAILABLE = False


WSDL_URL = "https://www.brenda-enzymes.org/soap/brenda_zeep.wsdl"


def _get_credentials() -> tuple:
    """Get BRENDA credentials from environment."""
    email = os.getenv("BRENDA_EMAIL", "")
    password = os.getenv("BRENDA_PASSWORD", "")
    return email, password


def _hash_password(password: str) -> str:
    """Hash password with SHA-256 for BRENDA API."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def call_brenda(method_name: str, *args) -> list:
    """
    Call a BRENDA SOAP method.

    Args:
        method_name: SOAP method name (e.g., 'getKmValue', 'getReaction')
        *args: Method-specific arguments (after email and passwordHash)

    Returns:
        List of result strings
    """
    if not ZEEP_AVAILABLE:
        raise ImportError("zeep library required. Install: uv pip install zeep")

    email, password = _get_credentials()
    if not email or not password:
        raise ValueError(
            "BRENDA credentials required. Set BRENDA_EMAIL and BRENDA_PASSWORD "
            "environment variables. Register at https://www.brenda-enzymes.org/"
        )

    password_hash = _hash_password(password)

    settings = Settings(strict=False, xml_huge_tree=True)
    client = Client(WSDL_URL, settings=settings)
    method = getattr(client.service, method_name)

    try:
        result = method(email, password_hash, *args)
        if result is None:
            return []
        if isinstance(result, str):
            return [result] if result else []
        return list(result)
    except Fault as e:
        raise RuntimeError(f"BRENDA SOAP error: {e}")
    except TransportError as e:
        raise RuntimeError(f"BRENDA transport error: {e}")


def get_km_values(
    ec_number: str = "*",
    organism: str = "*",
    substrate: str = "*",
    km_value: str = "*",
    km_value_maximum: str = "*",
) -> List[str]:
    """
    Retrieve Km values for an enzyme.

    Args:
        ec_number: EC number (wildcards allowed, e.g., "1.1.1.1")
        organism: Organism name (wildcards allowed, default "*")
        substrate: Substrate name (wildcards allowed, default "*")
        km_value: Km value filter (default "*")
        km_value_maximum: Maximum Km value filter (default "*")

    Returns:
        List of Km value entry strings
    """
    return call_brenda(
        "getKmValue",
        ec_number,
        organism,
        km_value,
        km_value_maximum,
        substrate,
    )


def get_reactions(
    ec_number: str = "*",
    organism: str = "*",
    reaction: str = "*",
) -> List[str]:
    """
    Retrieve reaction entries for an enzyme.

    Args:
        ec_number: EC number (wildcards allowed, e.g., "1.1.1.1")
        organism: Organism name (wildcards allowed, default "*")
        reaction: Reaction filter (wildcards allowed, default "*")

    Returns:
        List of reaction entry strings
    """
    return call_brenda(
        "getReaction",
        ec_number,
        organism,
        reaction,
    )
