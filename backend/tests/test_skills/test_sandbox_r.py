import pytest
from pathlib import Path

from homomics_lab.skills.sandbox import LocalSandbox


@pytest.fixture
def sandbox(tmp_path):
    return LocalSandbox(working_dir=tmp_path)


class TestSandboxR:
    @pytest.mark.asyncio
    async def test_run_r_simple_math(self, sandbox, tmp_path):
        """Test basic R execution with simple math."""
        code = """
result <- list(sum = a + b, product = a * b)
"""
        inputs = {"a": 3, "b": 4}

        result = await sandbox.run_r(code, inputs, timeout_seconds=30.0)

        assert result["sum"] == 7
        assert result["product"] == 12

    @pytest.mark.asyncio
    async def test_run_r_with_string_input(self, sandbox, tmp_path):
        """Test R execution with string inputs."""
        code = """
result <- list(greeting = paste0("Hello, ", name))
"""
        inputs = {"name": "HomomicsLab"}

        result = await sandbox.run_r(code, inputs, timeout_seconds=30.0)

        assert result["greeting"] == "Hello, HomomicsLab"

    @pytest.mark.asyncio
    async def test_run_r_with_list_input(self, sandbox, tmp_path):
        """Test R execution with list/vector inputs."""
        code = """
result <- list(total = sum(values), mean = mean(values))
"""
        inputs = {"values": [1, 2, 3, 4, 5]}

        result = await sandbox.run_r(code, inputs, timeout_seconds=30.0)

        assert result["total"] == 15
        assert result["mean"] == 3.0

    @pytest.mark.asyncio
    async def test_run_r_timeout(self, sandbox, tmp_path):
        """Test R execution timeout."""
        code = """
Sys.sleep(10)
result <- list()
"""

        with pytest.raises(TimeoutError):
            await sandbox.run_r(code, {}, timeout_seconds=1.0)

    @pytest.mark.asyncio
    async def test_run_r_error_handling(self, sandbox, tmp_path):
        """Test R execution error handling."""
        code = """
stop("Intentional error for testing")
"""

        with pytest.raises(RuntimeError) as exc_info:
            await sandbox.run_r(code, {}, timeout_seconds=30.0)
        assert "Intentional error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_r_no_result_variable(self, sandbox, tmp_path):
        """Test R execution when result is not explicitly set."""
        code = """
x <- 42
# result not set
"""
        inputs = {}

        result = await sandbox.run_r(code, inputs, timeout_seconds=30.0)

        # Should return empty list or raw output
        assert isinstance(result, (dict, list))

    def test_build_r_script_structure(self, sandbox, tmp_path):
        """Test that R script wrapper has correct structure."""
        code = "result <- list(x = 1)"
        inputs = {"foo": "bar"}

        script = sandbox._build_r_script(code, inputs)

        # Should contain input reading
        assert "fromJSON" in script
        # Should contain user code
        assert "result <- list(x = 1)" in script
        # Should contain result serialization
        assert "write_json" in script

    @pytest.mark.skipif(
        not Path("/usr/bin/Rscript").exists() and not Path("/usr/local/bin/Rscript").exists(),
        reason="Rscript not available on this system",
    )
    @pytest.mark.asyncio
    async def test_run_r_integration(self, sandbox, tmp_path):
        """Full integration test requiring R installation."""
        code = """
result <- list(
    doubled = a * 2,
    r_version = paste0(R.version$major, ".", R.version$minor)
)
"""
        inputs = {"a": 21}

        result = await sandbox.run_r(code, inputs, timeout_seconds=30.0)

        assert result["doubled"] == 42
        assert "r_version" in result
