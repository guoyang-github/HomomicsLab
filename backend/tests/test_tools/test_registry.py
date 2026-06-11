"""Tests for ToolRegistry."""

from pathlib import Path

import pytest

from homomics_lab.models.common import AgentType
from homomics_lab.tools.models import ToolDefinition
from homomics_lab.tools.registry import ToolRegistry


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"},
            handler=lambda x: x,
        )
        reg.register(tool)
        assert reg.get("test_tool") is tool

    def test_get_unknown_tool(self):
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_register_builtin_convenience(self):
        reg = ToolRegistry()
        reg.register_builtin(
            name="adder",
            description="Adds two numbers",
            handler=lambda a, b: a + b,
            input_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        )
        tool = reg.get("adder")
        assert tool is not None
        assert tool.source == "builtin"

    def test_invoke_builtin_sync(self):
        reg = ToolRegistry()
        reg.register_builtin(
            name="greet",
            description="Greets someone",
            handler=lambda name: f"Hello, {name}!",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        )
        result = reg.invoke("greet", {"name": "World"})
        assert result.success is True
        assert result.output == "Hello, World!"

    def test_invoke_missing_required_input(self):
        reg = ToolRegistry()
        reg.register_builtin(
            name="needs_name",
            description="Needs a name",
            handler=lambda name: name,
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        )
        result = reg.invoke("needs_name", {})
        assert result.success is False
        assert "Missing required input" in result.error_message

    def test_invoke_unknown_tool_raises(self):
        reg = ToolRegistry()
        with pytest.raises(ValueError, match="not found"):
            reg.invoke("unknown", {})

    def test_invoke_tool_without_handler(self):
        reg = ToolRegistry()
        reg.register(
            ToolDefinition(
                name="no_handler",
                description="No handler",
                input_schema={"type": "object"},
                handler=None,
                source="mcp",
            )
        )
        with pytest.raises(RuntimeError, match="no handler"):
            reg.invoke("no_handler", {})

    def test_list_by_source(self):
        reg = ToolRegistry()
        reg.register_builtin("t1", "test1", lambda: None)
        reg.register(
            ToolDefinition(name="t2", description="test2", input_schema={}, source="mcp")
        )
        builtins = reg.list_by_source("builtin")
        mcps = reg.list_by_source("mcp")
        assert len(builtins) == 1
        assert len(mcps) == 1

    def test_get_for_role(self):
        reg = ToolRegistry()
        reg.register_builtin("file_read", "Read file", lambda path: path)
        reg.register_builtin("web_search", "Search web", lambda query: [])
        reg.register_builtin("shell_exec", "Run shell", lambda command: command)

        planner_tools = reg.get_for_role(AgentType.PLANNER)
        bioinfo_tools = reg.get_for_role(AgentType.BIOINFO)

        assert len(planner_tools) >= 2
        assert len(bioinfo_tools) >= 3

    def test_reset(self):
        reg = ToolRegistry()
        reg.register_builtin("t1", "test", lambda: None)
        assert len(reg.list_all()) == 1
        reg.reset()
        assert len(reg.list_all()) == 0


class TestBuiltinTools:
    def test_file_read(self, tmp_path: Path):
        from homomics_lab.tools.builtin import file_read

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        content = file_read(str(test_file))
        assert content == "hello world"

    def test_file_read_not_found(self, tmp_path: Path):
        from homomics_lab.tools.builtin import file_read

        with pytest.raises(FileNotFoundError):
            file_read(str(tmp_path / "nonexistent.txt"))

    def test_file_write(self, tmp_path: Path):
        from homomics_lab.tools.builtin import file_write

        result = file_write(str(tmp_path / "output.txt"), "test content")
        assert result["bytes_written"] == 12
        assert (tmp_path / "output.txt").read_text() == "test content"

    def test_file_list(self, tmp_path: Path):
        from homomics_lab.tools.builtin import file_list

        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "sub").mkdir()
        files = file_list(str(tmp_path))
        assert len(files) == 2

    def test_shell_exec_echo(self):
        from homomics_lab.tools.builtin import shell_exec

        result = shell_exec("echo hello")
        assert result["returncode"] == 0
        assert "hello" in result["stdout"]
