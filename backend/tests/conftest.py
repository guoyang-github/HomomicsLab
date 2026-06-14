"""Global pytest configuration for the HomomicsLab backend."""

import os


# Run Hugging Face hubs in offline mode during tests. This prevents network
# timeouts when sentence-transformers tries to reach the remote model hub,
# while still allowing locally cached models to load.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
