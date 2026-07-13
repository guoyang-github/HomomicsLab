"""Verify bubblewrap sandbox resolves python to the project venv."""

import asyncio
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("HOMOMICS_FORCE_SANDBOX", "true")
os.environ.setdefault("HOMOMICS_SKILL_SANDBOX_BACKEND", "bubblewrap")

from homomics_lab.skills.sandbox import BubblewrapSandbox


async def main():
    work = Path("/tmp/homomics_bwrap_test")
    work.mkdir(parents=True, exist_ok=True)
    sandbox = BubblewrapSandbox(work)
    output = await sandbox.run_command("which python && python -c 'import sys; print(sys.executable); import celltypist; print(\"celltypist ok\", celltypist.__version__)'", timeout_seconds=60)
    print(output)


if __name__ == "__main__":
    asyncio.run(main())
