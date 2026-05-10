"""KBStore selection."""

from __future__ import annotations

from .gitkb_store import GitKBStore
from ..config import DataRootConfig


def make_store(config: DataRootConfig):
    if config.kb_backend != "gitkb":
        raise RuntimeError(
            "DataRoot no longer falls back to a local mock KB. "
            'Set kb_backend = "gitkb" and install git-kb.'
        )
    if not GitKBStore.is_available():
        raise RuntimeError(
            "git-kb is not available on PATH. Install the real GitKB CLI "
            "from https://github.com/gitkb/gitkb-releases before running DataRoot."
        )
    return GitKBStore(config.root)
