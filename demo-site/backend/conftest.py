"""Ensures the backend directory is importable as the module root during tests,
so bare imports (`from models...`, `from repo_cli import ...`) resolve the same
way they do when Railway runs `uvicorn main:app` from this directory."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
