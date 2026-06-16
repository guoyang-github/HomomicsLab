"""Parse nf-core ``nextflow_schema.json`` into user-friendly parameter forms.

nf-core pipelines ship with a JSON Schema describing all accepted ``--params``.
This module flattens that schema into a form definition that the frontend can
render, and validates user input against it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ParameterField:
    """A single user-facing parameter field."""

    name: str
    type: str  # "string" | "integer" | "number" | "boolean" | "array" | "object"
    title: str
    description: str
    required: bool
    default: Any = None
    enum: Optional[List[Any]] = None
    enum_names: Optional[List[str]] = None
    help_text: str = ""
    format: Optional[str] = None  # e.g. "file-path", "directory-path"
    hidden: bool = False
    group: str = "General"


@dataclass
class ParameterForm:
    """A flattened form definition for a pipeline."""

    pipeline: str
    version: Optional[str]
    groups: List[str] = field(default_factory=list)
    fields: List[ParameterField] = field(default_factory=list)
    required_global: List[str] = field(default_factory=list)


def load_schema(pipeline_dir: Path) -> Dict[str, Any]:
    """Load ``nextflow_schema.json`` from a pipeline directory."""
    schema_path = pipeline_dir / "nextflow_schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"No nextflow_schema.json found in {pipeline_dir}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _extract_enum_names(property_def: Dict[str, Any]) -> Optional[List[str]]:
    """Extract human-readable enum names if provided by nf-core."""
    enum = property_def.get("enum")
    if not enum:
        return None
    # nf-core sometimes uses a parallel "enumNames" array.
    names = property_def.get("enumNames")
    if names and len(names) == len(enum):
        return names
    return None


def _map_type(json_schema_type: str, property_def: Dict[str, Any]) -> str:
    """Map JSON Schema type to a simpler frontend type."""
    if json_schema_type == "array":
        return "array"
    if json_schema_type == "boolean":
        return "boolean"
    if json_schema_type == "integer":
        return "integer"
    if json_schema_type == "number":
        return "number"
    if json_schema_type == "object":
        return "object"
    # Default to string; nf-core often uses string with format hints.
    return "string"


def _format_from_def(property_def: Dict[str, Any]) -> Optional[str]:
    """Infer field format from nf-core schema hints."""
    fmt = property_def.get("format", "")
    if fmt:
        return fmt
    # nf-core often encodes path types via pattern or mimetype.
    mimetype = property_def.get("mimetype", "")
    if "csv" in mimetype or "tsv" in mimetype:
        return "file-path"
    return None


def parse_schema(
    schema: Dict[str, Any],
    pipeline_name: str,
    version: Optional[str] = None,
) -> ParameterForm:
    """Parse an nf-core nextflow_schema.json into a ParameterForm."""
    form = ParameterForm(pipeline=pipeline_name, version=version)

    top_required = set(schema.get("required", []))
    form.required_global = list(top_required)

    properties = schema.get("properties", {})
    definitions = schema.get("definitions", schema.get("$defs", {}))

    # Top-level properties.
    for name, prop in properties.items():
        if name.startswith("_"):
            continue
        field = ParameterField(
            name=name,
            type=_map_type(prop.get("type", "string"), prop),
            title=prop.get("title", name),
            description=prop.get("description", ""),
            required=name in top_required,
            default=prop.get("default"),
            enum=prop.get("enum"),
            enum_names=_extract_enum_names(prop),
            help_text=prop.get("help_text", "") or prop.get("description", ""),
            format=_format_from_def(prop),
            hidden=prop.get("hidden", False),
            group="General",
        )
        form.fields.append(field)

    # Definitions become groups.
    for group_name, group_def in definitions.items():
        group_title = group_def.get("title", group_name)
        form.groups.append(group_title)
        group_required = set(group_def.get("required", []))
        for name, prop in group_def.get("properties", {}).items():
            if name.startswith("_"):
                continue
            field = ParameterField(
                name=name,
                type=_map_type(prop.get("type", "string"), prop),
                title=prop.get("title", name),
                description=prop.get("description", ""),
                required=name in group_required,
                default=prop.get("default"),
                enum=prop.get("enum"),
                enum_names=_extract_enum_names(prop),
                help_text=prop.get("help_text", "") or prop.get("description", ""),
                format=_format_from_def(prop),
                hidden=prop.get("hidden", False),
                group=group_title,
            )
            form.fields.append(field)

    if "General" not in form.groups:
        form.groups.insert(0, "General")

    return form


def form_to_dict(form: ParameterForm) -> Dict[str, Any]:
    """Serialize a ParameterForm to a JSON-safe dict."""
    return {
        "pipeline": form.pipeline,
        "version": form.version,
        "groups": form.groups,
        "required_global": form.required_global,
        "fields": [
            {
                "name": f.name,
                "type": f.type,
                "title": f.title,
                "description": f.description,
                "required": f.required,
                "default": f.default,
                "enum": f.enum,
                "enum_names": f.enum_names,
                "help_text": f.help_text,
                "format": f.format,
                "hidden": f.hidden,
                "group": f.group,
            }
            for f in form.fields
        ],
    }


def validate_params(
    schema: Dict[str, Any],
    params: Dict[str, Any],
) -> List[str]:
    """Basic validation of user-provided params against the schema.

    Returns a list of human-readable error messages (empty if valid).
    """
    errors: List[str] = []
    required = set(schema.get("required", []))
    properties = schema.get("properties", {})
    definitions = schema.get("definitions", schema.get("$defs", {}))

    for name in required:
        if name not in params or params[name] in (None, ""):
            errors.append(f"Missing required parameter: {name}")

    all_props = dict(properties)
    for group in definitions.values():
        all_props.update(group.get("properties", {}))

    for name, value in params.items():
        prop = all_props.get(name)
        if prop is None:
            continue
        ptype = prop.get("type", "string")
        if ptype == "boolean" and not isinstance(value, bool):
            errors.append(f"Parameter {name} must be a boolean")
        elif ptype == "integer" and not isinstance(value, int):
            errors.append(f"Parameter {name} must be an integer")
        elif ptype == "number" and not isinstance(value, (int, float)):
            errors.append(f"Parameter {name} must be a number")
        elif ptype == "array" and not isinstance(value, list):
            errors.append(f"Parameter {name} must be a list")
        enum = prop.get("enum")
        if enum is not None and value not in enum:
            errors.append(f"Parameter {name} must be one of {enum}")

    return errors


def build_params_file(
    pipeline_dir: Path,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate and prepare a params dict for an nf-core run.

    Returns the validated params dict. Raises ValueError on validation errors.
    """
    schema = load_schema(pipeline_dir)
    errors = validate_params(schema, params)
    if errors:
        raise ValueError("; ".join(errors))
    return params
