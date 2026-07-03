import pytest
from homomics_lab.skills.sandbox import LocalSandbox


@pytest.fixture
def sandbox(tmp_path):
    return LocalSandbox(working_dir=tmp_path)


@pytest.mark.asyncio
async def test_blocks_os_import(sandbox):
    code = '''
import os
result = {"status": "should not reach here"}
'''
    with pytest.raises(RuntimeError) as exc_info:
        await sandbox.run_python(code, {})
    assert "failed" in str(exc_info.value).lower() or "restricted" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_blocks_subprocess(sandbox):
    code = '''
import subprocess
result = {"status": "should not reach here"}
'''
    with pytest.raises(RuntimeError):
        await sandbox.run_python(code, {})


@pytest.mark.asyncio
async def test_allows_safe_imports(sandbox):
    code = '''
import json
import math
result = {"sum": math.sqrt(16)}
'''
    result = await sandbox.run_python(code, {})
    assert result["sum"] == 4.0


@pytest.mark.asyncio
async def test_blocks_builtins_import_attribute(sandbox):
    """Regression: __builtins__['__import__']('os') must also be blocked."""
    code = '''
__builtins__["__import__"]("os")
result = {"status": "should not reach here"}
'''
    with pytest.raises(RuntimeError) as exc_info:
        await sandbox.run_python(code, {})
    assert "failed" in str(exc_info.value).lower() or "restricted" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_blocks_builtin_help_system(sandbox):
    """Regression: builtins.__import__ must be the patched version."""
    code = '''
import builtins
builtins.__import__("os")
result = {"status": "should not reach here"}
'''
    with pytest.raises(RuntimeError) as exc_info:
        await sandbox.run_python(code, {})
    assert "failed" in str(exc_info.value).lower() or "restricted" in str(exc_info.value).lower()
