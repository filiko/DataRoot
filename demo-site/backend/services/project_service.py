"""
ProjectService — filesystem persistence for DfdProject (formerly PenFile).

Provides durable open/save of project.dfd.json files.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

from models.pen import PenFile


class ProjectService:
    @staticmethod
    def _resolve_path(path: str | None, default_name: str) -> Path:
        """Resolve a path, defaulting to a sensible location."""
        if path:
            return Path(path)
        documents = Path.home() / "Documents"
        dfd_projects = documents / "DFDMaker"
        dfd_projects.mkdir(parents=True, exist_ok=True)
        return dfd_projects / f"{default_name}.dfd.json"

    @staticmethod
    def open(path: str) -> tuple[PenFile, str]:
        """
        Load a project from a .dfd.json file.
        Returns (PenFile, resolved_path).
        Raises FileNotFoundError if path does not exist.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Project file not found: {path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        pen = PenFile.model_validate(data)
        return pen, str(file_path.resolve())

    @staticmethod
    def save(pen: PenFile, path: str | None = None) -> tuple[PenFile, str]:
        """
        Save a project to a .dfd.json file.
        Creates directories if needed.
        Returns (PenFile, resolved_path).
        """
        file_path = ProjectService._resolve_path(path, pen.project.name)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        pen.project.revision += 1
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(pen.model_dump_json(by_alias=True, indent=2))

        return pen, str(file_path)

    @staticmethod
    def delete(path: str) -> None:
        """Delete a project file."""
        file_path = Path(path)
        if file_path.exists():
            file_path.unlink()
