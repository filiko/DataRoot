# DataRoot

DataRoot turns a folder of heterogeneous research files into a searchable,
linked provenance graph.

The implementation keeps persistence behind a KBStore adapter. `GitKBStore`
is the backend for the application path. DataRoot now fails loudly when the
real `git-kb` CLI is unavailable; there is no silent local KB fallback.

On Windows, the current GitKB release artifacts are Linux/macOS only. Use WSL
for end-to-end validation:

```bash
curl -fsSL https://get.gitkb.com/install.sh | INSTALL_DIR="$HOME/.local/bin" bash
export PATH="$HOME/.local/bin:$PATH"
git kb --version
```

## Quick Start

```bash
export PYTHONPATH=src
git init
git config user.name "DataRoot"
git config user.email "dataroot@example.local"
python -m dataroot.cli init
python -m dataroot.cli profile ExampleData
python -m dataroot.cli link
python -m dataroot.cli search A-CUL-TOM-014
python -m dataroot.cli search B-RUN-FERM-033
python -m dataroot.cli graph relationships/a-cul-tom-014 --depth 1
```

## Miro App Panel

Run the panel locally:

```bash
python -m uvicorn dataroot.server.app:app --host 0.0.0.0 --port 8000
```

For a shared Miro app, deploy the same FastAPI service to Railway and set the
Miro Developer app SDK URL to:

```text
https://<railway-domain>/miro/sdk
```

The SDK page registers the Miro app icon and opens the panel at `/miro/` inside
the board. Configure Railway variables with a rotated `MIRO_ACCESS_TOKEN`,
`MIRO_BOARD_ID=uXjVHVqV-rs=`, and optionally `OPENAI_API_KEY` plus
`DATAROOT_USE_MODEL_ASK=0`.

The hosted panel uses the real GitKB CLI when `DATAROOT_SERVER_KB_BACKEND=gitkb`.
On the first render request it initializes `.kb`, profiles `ExampleData`, links
the workspace, and runs `git-kb code index --prune --branch main .`. Mount a
Railway volume at `/app/.kb` so the GitKB store persists across deploys. Set
`OPENAI_API_KEY` to let the data tidbit interpreter and Miro planner produce
human-readable board text. Set `DATAROOT_USE_TIDBIT_INTERPRETER=0` or
`DATAROOT_USE_MIRO_PLANNER=0` to force deterministic fallback for either layer.

Refresh the shared demo board while preserving the top provenance header:

```bash
dataroot miro-refresh-board --board-id uXjVHVqV-rs= --preserve-title "DataRoot Provenance" --dry-run
dataroot miro-refresh-board --board-id uXjVHVqV-rs= --preserve-title "DataRoot Provenance"
```

The dry run prints the preserved frame, deletion count, and frame titles that
would be removed. The live run deletes only content below the preserved frame
and recreates four demo sections:

- `CropProtectorAI - Standard Demo`
- `CropProtectorAI - Live Ask`
- `BioReactorAI - Standard Demo`
- `BioReactorAI - Live Ask`

Questions from the Miro app panel update the selected company's `Live Ask`
section in place. The stable top flow shapes and arrows remain on the board.
The evidence area below is refreshed as interpreted claim cards with citations
preserved. The default board stays readable and uses only the three process
arrows: `Question -> GitKB retrieval -> Evidence Path -> Final Answer`. The
panel checkbox `Include precise proof frame` adds a lower `Precise Proof` frame
with exact source rows, citation slugs, edge evidence, and render metadata.
