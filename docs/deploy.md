# Hosted deploy and Miro app setup

This document covers everything needed to run DataRoot as a hosted service
(Railway), wire it into a real Miro Developer app, and refresh the shared
demo board. For a local-only walkthrough, the top-level `README.md` is
enough; come here when you are ready to put the service behind a domain.

## Local backend

Run the backend locally for development:

```bash
python -m uvicorn dataroot.server.app:app --host 0.0.0.0 --port 8000
```

This is sufficient for any of the three Live Ask workspaces
(`company_a`, `company_b`, `austin_permits`) when you point Miro at
`http://localhost:8000` via a tunnel like `ngrok` or `cloudflared`.

## Railway deploy

For a shared Miro app, deploy the same FastAPI service to Railway and set
the Miro Developer app SDK URL to:

```text
https://<railway-domain>/miro/sdk
```

The SDK page registers the Miro app icon and a board-item custom action.
Clicking the icon, or the `Run DataRoot` custom action, reads the question
from the board-side `Live Ask` text item and submits it directly — no app
panel is opened.

Configure Railway variables with:

| Variable                                | Purpose                                                |
|-----------------------------------------|--------------------------------------------------------|
| `MIRO_ACCESS_TOKEN`                     | Rotated Miro REST token                                 |
| `MIRO_BOARD_ID`                         | Default board id, e.g. `uXjVHVqV-rs=`                   |
| `OPENAI_API_KEY`                        | Enables the data-tidbit interpreter and Miro planner    |
| `DATAROOT_SERVER_KB_BACKEND=gitkb`      | Forces real GitKB — no LocalMarkdownStore fallback      |
| `DATAROOT_USE_TIDBIT_INTERPRETER=0`     | Optional: force deterministic interpreter               |
| `DATAROOT_USE_MIRO_PLANNER=0`           | Optional: force deterministic board planner             |
| `DATAROOT_LINK_ADDRESS_JOIN=1`          | Required for the Austin workspace cross-table links     |
| `MIRO_COMPANY_A_ASK_BOARD_ID`           | Board id for the CropProtectorAI Live Ask section       |
| `MIRO_COMPANY_B_ASK_BOARD_ID`           | Board id for the BioReactorAI Live Ask section          |
| `MIRO_AUSTIN_PERMITS_BOARD_ID`          | Board id for the Austin Permits Live Ask section        |

Mount a Railway volume at `/app/.kb` so the GitKB store persists across
deploys.

## Bootstrap behavior

The hosted backend uses the real `git-kb` CLI when
`DATAROOT_SERVER_KB_BACKEND=gitkb`. On the first render request it:

1. initializes `.kb`,
2. profiles `ExampleData`,
3. links the workspace,
4. runs `git-kb code index --prune --branch main .`.

If `git-kb` is not on `PATH`, the server fails fast with a clear error.

## Miro Developer app icons

To make the toolbar button visible, configure the Miro Developer app
display settings with the bundled DataRoot root/tree icon assets:

- `assets/miro/dataroot-outline.svg` → `Outline icon`
- `assets/miro/dataroot-color.svg` → `Color icon`

Then install or refresh the app on the demo board. The icon artwork is
controlled by Miro Developer app settings; `/miro/sdk` only handles what
happens after the icon is clicked.

## Optional board visuals

Each company can override its evidence-card visuals by setting any of:

```text
DATAROOT_MIRO_FIELD_IMAGE_URL
DATAROOT_MIRO_BIOREACTOR_IMAGE_URL
DATAROOT_MIRO_LAB_IMAGE_URL
DATAROOT_MIRO_IMAGE_URL              # generic fallback
```

If none are set, the renderer uses large Miro-native visual badges instead.

## Refreshing the shared demo board

```bash
dataroot miro-refresh-board --board-id uXjVHVqV-rs= \
    --preserve-title "DataRoot Provenance" --dry-run

dataroot miro-refresh-board --board-id uXjVHVqV-rs= \
    --preserve-title "DataRoot Provenance"
```

The dry run prints the preserved frame, deletion count, and frame titles
that would be removed. The live run deletes only content below the
preserved frame and recreates the demo sections:

- `CropProtectorAI - Standard Demo`
- `CropProtectorAI - Live Ask`
- `BioReactorAI - Standard Demo`
- `BioReactorAI - Live Ask`
- `Austin Permits Explorer - Live Ask` (when the Austin workspace is configured)

Each `Live Ask` section includes an editable board-side text item labeled
`Type your question here:`. Type the live question directly on the Miro
board, then click the DataRoot app icon or select the green
`DataRoot Run Live Ask` root marker and choose `Run DataRoot`. The hosted
endpoint reads that board text, runs the query agent, persists the inquiry
and provenance trace, then updates the selected workspace's `Live Ask`
section in place.

## Renderer behavior contract

The stable top flow shapes and arrows remain on the board. The evidence
area below is refreshed as interpreted claim cards with citations
preserved. The default board keeps:

- a direct `Question -> Final Answer` arrow,
- the process chain
  `Question -> DataRoot Parsing & Retrieval -> Evidence Path -> Final Answer`,
- and up to two evidence-card arrows into `Final Answer`.

Evidence cards use compact `S1`/`S2` source badges; the final answer
carries the source strip. The full contract is in
`docs/miro-fundamental-functionality.md`.
