"""Single source of truth for the application version."""

from importlib.metadata import PackageNotFoundError, version as _package_version


def app_version() -> str:
    """Return the installed package version from pyproject.toml.

    Falls back to ``0.1.0`` when the package is not installed (e.g. during
    ad-hoc script execution).
    """
    try:
        return _package_version("homomics_lab")
    except PackageNotFoundError:
        return "0.1.0"
