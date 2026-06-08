import pytest
from homomics_lab.skills.sandbox import LocalSandbox


@pytest.fixture
def sandbox(tmp_path):
    return LocalSandbox(working_dir=tmp_path)


@pytest.mark.asyncio
async def test_run_python_script(sandbox):
    code = """
result = {"sum": 1 + 2, "message": "hello"}
"""
    result = await sandbox.run_python(code, {"x": 10})
    assert result["sum"] == 3
    assert result["message"] == "hello"


@pytest.mark.asyncio
async def test_run_with_timeout(sandbox):
    code = """
import time
time.sleep(10)
"""
    with pytest.raises(TimeoutError):
        await sandbox.run_python(code, {}, timeout_seconds=0.1)


@pytest.mark.asyncio
async def test_run_captures_errors(sandbox):
    code = """
raise ValueError("test error")
"""
    with pytest.raises(RuntimeError) as exc_info:
        await sandbox.run_python(code, {})
    assert "test error" in str(exc_info.value)
