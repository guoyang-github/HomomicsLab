"""Semantic versioning helpers for skills.

Provides version parsing, compatibility checks, and breaking-change detection
between two skill definitions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from homomics_lab.skills.models import SkillDefinition


_VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-(?P<pre>[a-zA-Z0-9.]+))?$")


@dataclass(frozen=True)
class SkillVersion:
    major: int
    minor: int
    patch: int
    prerelease: str = ""

    @classmethod
    def parse(cls, version: str) -> "SkillVersion":
        """Parse a semver string into a SkillVersion."""
        match = _VERSION_RE.match(version.strip())
        if not match:
            raise ValueError(f"Invalid semantic version: {version!r}")
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=match.group("pre") or "",
        )

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        return f"{base}-{self.prerelease}" if self.prerelease else base

    def is_compatible_with(self, other: "SkillVersion") -> bool:
        """Return True if `other` is backwards-compatible with this version.

        In semver, versions with the same major are compatible unless a
        prerelease is involved.
        """
        if self.major == 0 or other.major == 0:
            # 0.x.y does not promise backwards compatibility.
            return self.major == other.major and self.minor == other.minor
        if self.major != other.major:
            return False
        if self.prerelease or other.prerelease:
            return str(self) == str(other)
        return True


def detect_breaking_changes(
    old: SkillDefinition,
    new: SkillDefinition,
) -> List[str]:
    """Compare two skill definitions and report breaking changes.

    Breaking changes include:
    - Removing a previously required input parameter.
    - Adding a new required input parameter.
    - Removing a previously guaranteed output field.
    - Changing the runtime language.
    """
    changes: List[str] = []

    old_required = set(old.input_schema.required)
    new_required = set(new.input_schema.required)
    old_inputs = set(old.input_schema.properties.keys())
    new_inputs = set(new.input_schema.properties.keys())

    removed_required = old_required - new_inputs
    if removed_required:
        changes.append(f"Removed required inputs: {sorted(removed_required)}")

    added_required = new_required - old_inputs
    if added_required:
        changes.append(f"Added new required inputs: {sorted(added_required)}")

    old_outputs = set(old.output_schema.properties.keys())
    new_outputs = set(new.output_schema.properties.keys())
    removed_outputs = old_outputs - new_outputs
    if removed_outputs:
        changes.append(f"Removed guaranteed outputs: {sorted(removed_outputs)}")

    if old.runtime.type != new.runtime.type:
        changes.append(f"Runtime changed from {old.runtime.type} to {new.runtime.type}")

    return changes


def bump_version(old_version: str, changes: List[str]) -> str:
    """Suggest a new semver based on detected breaking changes."""
    version = SkillVersion.parse(old_version)
    if changes:
        return str(SkillVersion(major=version.major + 1, minor=0, patch=0))
    return str(SkillVersion(major=version.major, minor=version.minor + 1, patch=0))
