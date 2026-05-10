---
purpose: Everything about the Miro rendering layer.
prerequisites: CONTEXT.md, docs/architecture.md §6
read-when: Building the Miro renderer or the Cytoscape fallback.
---

# Miro renderer — docs/miro-renderer.md

Miro REST API renderer, swimlane layout math, OAuth, rendering
pseudocode, and Cytoscape fallback.

← Back to [CONTEXT.md](../CONTEXT.md)

## 6.1 Why Miro

Researchers already use whiteboards for experiment planning. The
provenance graph becomes the input artifact for the next experiment —
they can drag, annotate, add stickies. Miro boards are also the
sponsor track submission angle.

The official Miro MCP server exists and supports board access and
diagram generation, but we use REST for deterministic rendering.

## 6.2 Implementation path

Use Miro REST API v2 directly (not MCP) as the implementation path.

Reasons:
- Fewer moving parts than launching another MCP subprocess.
- Bulk endpoints handle 20 items per call.
- Precise positioning (swimlane layout) is straightforward via REST.
- Deterministic behavior is critical for live demo reliability.

Miro MCP is optional sponsor-track polish — use REST first, add MCP
only if time permits after the full demo path works.

## 6.3 Supported item types

The renderer supports only boring primitives. Not all Miro item types
are supported programmatically. Stick to these four:

- **frames** — stage containers
- **shapes** — entities (rectangles for tables, circles for measurements, etc.)
- **sticky notes** — citations and labels
- **connectors** — relationships between entities

## 6.4 Layout

Swimlanes left-to-right, one per stage:

```
│ Query     │ Tables     │ Columns    │ Measurements   │ Answer    │
│           │            │            │                │           │
│ "nitrate  │ water_     │ station_id │ STATION_001    │ "3 of 42  │
│  exceed   │ quality    │ nitrate    │ exceeds limit │ stations  │
│  2024"    │            │ mg_l       │ by 2.7 mg/L"  │ exceed    │
│           │            │            │                │           │
└───────────┴────────────┴────────────┴────────────────┴───────────┘
```

Each stage is a Miro frame (800×1200px, spaced 900px apart horizontally).
Each entity is a shape.
Each shape has a sticky note attached with the citation (file + row).
Connectors run between stages with labels ("has_column", "measured_at").
Color-code by stage.

## 6.5 Rendering pseudocode

```python
def render_provenance_to_miro(trace: ProvenanceTrace, board_id: str) -> str:
    """Returns the Miro board URL."""
    miro = MiroClient(token=os.environ["MIRO_ACCESS_TOKEN"])

    # 1. Create stage frames
    frames = {}
    for i, stage in enumerate(trace.stages):
        frame = miro.create_frame(
            board_id,
            title=stage,
            x=i * 900,
            y=0,
            w=800,
            h=1200
        )
        frames[stage] = frame

    # 2. Create shapes for each node (bulk)
    shape_ids = {}
    by_stage = group_by_stage(trace.nodes)
    for stage, nodes in by_stage.items():
        items = [build_shape_payload(n, frames[stage], idx) for idx, n in enumerate(nodes)]
        created = miro.bulk_create_items(board_id, items)
        for n, c in zip(nodes, created):
            shape_ids[n.id] = c.id

    # 3. Create connectors (bulk)
    connectors = [
        {
            "start_item_id": shape_ids[e.from_],
            "end_item_id": shape_ids[e.to],
            "caption": e.label
        }
        for e in trace.edges
    ]
    miro.bulk_create_connectors(board_id, connectors)

    # 4. Attach citation stickies near each shape
    stickies = [
        {
            "text": f"[{n.slug}]\n{n.citation}",
            "x": pos.x + 200,
            "y": pos.y,
            "color": "yellow"
        }
        for n in trace.nodes if n.citation
    ]
    miro.bulk_create_items(board_id, stickies)

    return f"https://miro.com/app/board/{board_id}/"
```

## 6.6 OAuth

Use a personal OAuth token in .env. No multi-tenant Miro app.

```
MIRO_ACCESS_TOKEN=your_miro_oauth_access_token_here
MIRO_BOARD_ID=optional_existing_board_id
```

Authorization header: `Authorization: Bearer {MIRO_ACCESS_TOKEN}`

## 6.7 Fallback

If Miro fails (rate limit, auth error, network), fall back to
Cytoscape.js renderer in the web UI. The provenance trace JSON is
the same; only the rendering target changes.

The fallback must work cleanly in the demo so a Miro outage doesn't
kill the presentation.

← Back to [CONTEXT.md](../CONTEXT.md)