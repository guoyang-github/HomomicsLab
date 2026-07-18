"""Tests for the streaming line callback in ``Sandbox.run_command``.

The optional ``on_output_line`` callback reports every stdout/stderr line as
it arrives (used for real-time domain phase markers). Without the callback,
behavior is byte-identical to the original batch collection.
"""

import asyncio

import pytest

from homomics_lab.skills.sandbox import LocalSandbox


@pytest.fixture
def sandbox(tmp_path):
    return LocalSandbox(working_dir=tmp_path)


@pytest.mark.asyncio
async def test_line_callback_receives_lines_with_stream_tags(sandbox):
    lines = []
    output = await sandbox.run_command(
        "echo out1; echo err1 >&2; echo out2",
        on_output_line=lambda line, stream: lines.append((line, stream)),
    )
    # Ordering within each stream is preserved and streams are tagged.
    assert [line for line, stream in lines if stream == "stdout"] == ["out1", "out2"]
    assert [line for line, stream in lines if stream == "stderr"] == ["err1"]
    # The merged return text keeps the batch contract: stdout, then a "\n"
    # separator, then stderr (stdout's own trailing newline makes a blank line).
    assert output == "out1\nout2\n\nerr1"


@pytest.mark.asyncio
async def test_line_callback_arrives_incrementally(sandbox):
    arrivals = []

    def _cb(line, stream):
        arrivals.append((line, asyncio.get_event_loop().time()))

    output = await sandbox.run_command(
        "echo first; sleep 0.5; echo second",
        timeout_seconds=10.0,
        on_output_line=_cb,
    )
    assert output == "first\nsecond"
    assert [line for line, _ in arrivals] == ["first", "second"]
    # "first" was reported while the process was still sleeping, i.e. well
    # before "second" could exist — not batch-collected at process exit.
    assert arrivals[1][1] - arrivals[0][1] >= 0.2


@pytest.mark.asyncio
async def test_output_identical_with_and_without_callback(sandbox):
    command = "echo alpha; echo beta >&2; printf 'gamma'"
    batch = await sandbox.run_command(command)
    streamed = await sandbox.run_command(command, on_output_line=lambda *_: None)
    assert streamed == batch


@pytest.mark.asyncio
async def test_merge_contract_stderr_only(sandbox):
    lines = []
    output = await sandbox.run_command(
        "echo onlyerr >&2",
        on_output_line=lambda line, stream: lines.append((line, stream)),
    )
    assert output == "onlyerr"
    assert lines == [("onlyerr", "stderr")]


@pytest.mark.asyncio
async def test_timeout_semantics_unchanged(sandbox):
    # Batch path (pre-existing behavior).
    with pytest.raises(asyncio.TimeoutError):
        await sandbox.run_command("sleep 5", timeout_seconds=0.2)
    # Streaming path: same wait_for-based timeout, same exception type.
    with pytest.raises(asyncio.TimeoutError):
        await sandbox.run_command(
            "sleep 5", timeout_seconds=0.2, on_output_line=lambda *_: None
        )


@pytest.mark.asyncio
async def test_callback_exception_does_not_break_execution(sandbox):
    def _boom(line, stream):
        raise ValueError("callback exploded")

    output = await sandbox.run_command("echo hello", on_output_line=_boom)
    assert output == "hello"


@pytest.mark.asyncio
async def test_partial_final_line_reported(sandbox):
    lines = []
    output = await sandbox.run_command(
        "printf 'no-trailing-newline'",
        on_output_line=lambda line, stream: lines.append(line),
    )
    assert lines == ["no-trailing-newline"]
    assert output == "no-trailing-newline"
