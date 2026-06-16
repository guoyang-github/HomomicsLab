"""CLI entry point for invoking a registered tool from a sandbox subprocess.

This module allows generated CodeAct code running inside bubblewrap/container
sandboxes to call back into HomomicsLab's ToolRegistry without sharing the
parent process's memory space.

Usage:
    python -m homomics_lab.tools.invoke_tool <tool_name> --args-json '{"key":"value"}'
"""

import argparse
import json
import sys


def _register_builtin_tools(registry):
    """Register builtin tools into a fresh registry.

    Mirrors the registration logic in bootstrap.register_all_builtin_tools so
    that sandboxed generated code sees the same tools as the parent process.
    """
    from homomics_lab.tools.builtin import register_all_builtin_tools

    register_all_builtin_tools(registry)


def main() -> int:
    parser = argparse.ArgumentParser(description="Invoke a HomomicsLab tool by name")
    parser.add_argument("tool_name", help="Name of the registered tool")
    parser.add_argument(
        "--args-json",
        default="{}",
        help="JSON-encoded arguments object for the tool",
    )
    parser.add_argument(
        "--async",
        dest="is_async",
        action="store_true",
        help="Use async invocation if the tool handler is async",
    )
    args = parser.parse_args()

    from homomics_lab.tools.registry import ToolRegistry

    registry = ToolRegistry()
    _register_builtin_tools(registry)

    try:
        inputs = json.loads(args.args_json)
    except json.JSONDecodeError as exc:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {exc}"}))
        return 1

    try:
        if args.is_async:
            import asyncio

            result = asyncio.run(registry.invoke_async(args.tool_name, inputs))
        else:
            result = registry.invoke(args.tool_name, inputs)
        print(
            json.dumps(
                {
                    "success": result.success,
                    "output": result.output,
                    "error": result.error_message,
                }
            )
        )
        return 0 if result.success else 1
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
