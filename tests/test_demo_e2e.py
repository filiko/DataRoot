from __future__ import annotations

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from dataroot.cli import main
from dataroot.kb.gitkb_store import GitKBStore


ROOT = Path(__file__).resolve().parents[1]
WATER_QUALITY_RAW = ROOT / "ExampleData" / "water_quality" / "raw"


class DemoE2ETests(unittest.TestCase):
    @unittest.skipUnless(GitKBStore.is_available(), "real git-kb CLI is required for CLI E2E")
    def test_water_quality_cli_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            _configure_git_author(workdir)
            with _cwd(workdir):
                self.assertEqual(_run_cli(["init"]), 0)
                self.assertEqual(_run_cli(["profile", str(WATER_QUALITY_RAW)]), 0)
                self.assertEqual(_run_cli(["link"]), 0)
                self.assertEqual(_run_cli(["infer-domain-spec"]), 0)
                _, generated_specs = _run_cli_with_output(["list", "--type", "domain_spec"])
                self.assertEqual(_run_cli(["apply-domain-spec"]), 0)
                _, accepted_specs = _run_cli_with_output(["list", "--type", "domain_spec"])
                code, output = _run_cli_with_output(
                    ["ask", "Which stations exceeded nitrate limits in 2024?"]
                )
                _, provenance_docs = _run_cli_with_output(["list", "--type", "provenance_trace"])
                _, inquiry_docs = _run_cli_with_output(["list", "--type", "inquiry"])

            self.assertEqual(code, 0)
            self.assertIn("STATION_001", output)
            self.assertIn("STATION_002", output)
            self.assertIn("[citation: row_groups/water_quality_measurements_2024.csv/samp-2024-002]", output)
            self.assertIn("[citation: row_groups/water_quality_measurements_2024.csv/samp-2024-004]", output)
            self.assertIn("<provenance>", output)
            self.assertIn("provenance_traces/", provenance_docs)
            self.assertIn("inquiries/", inquiry_docs)
            self.assertIn("domain_specs/generated", generated_specs)
            self.assertIn("domain_specs/accepted", accepted_specs)


def _run_cli(args: list[str]) -> int:
    return _run_cli_with_output(args)[0]


def _run_cli_with_output(args: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(args)
    return code, buffer.getvalue()


def _configure_git_author(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "DataRoot Tests"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "dataroot-tests@example.local"], cwd=path, check=True)


@contextlib.contextmanager
def _cwd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
