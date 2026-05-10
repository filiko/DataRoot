---
purpose: Key terms and definitions for DataRoot.
prerequisites: none
read-when: Reading the spec, clarifying terminology.
---

# Glossary — docs/glossary.md

Key terms and definitions used throughout the DataRoot project.

← Back to [CONTEXT.md](../CONTEXT.md)

**GitKB**: distributed knowledge graph protocol with sparse sync, MCP server, FTS5 + vector search, tree-sitter code intelligence. See https://gitkb.com/.

**KBStore**: DataRoot's abstraction over the document store. Two implementations: GitKBStore (wraps GitKB CLI) and LocalMarkdownStore (pure Markdown fallback).

**MCP**: Model Context Protocol. Standardized way for agents to call tools. DataRoot uses GitKB's MCP server as a subprocess.

**Provenance trace**: the structured record of what artifacts informed an agent's answer. In DataRoot, it's a JSON object with nodes, edges, and stages.

**Lineage edge**: an inferred relationship between two artifacts (e.g., harvest log row references cultivar ID).

**Domain Spec**: a YAML file (`.dataroot/domain_spec.yaml`) produced by Role A that defines entities, relationships, aliases, units, and traversal hints for a workspace.

**Cultivar**: a plant line with specific genetic and phenotypic traits (lab demo domain).

**Terpene synthase (TPS)**: a class of enzymes that produce terpenoid compounds. The genes encoding these are what we trace through FASTAs (lab demo domain).

**Titer**: the concentration of a compound in a sample (typical units: % w/w or mg/g).

**Station**: a monitoring location in the water quality domain (smoke-test domain).

**Wikilink**: `[[slug]]` syntax that GitKB indexes as a graph edge between documents.

**Role A / Role B / Role C**: the three agent roles — Domain Spec Generator, Domain Spec Applier, Query Agent.

**FK (foreign key)**: a column whose values reference rows in another table. The linker infers FK relationships from column names and value overlap.

**PK (primary key)**: a column with unique values that identify rows in a table. The linker marks likely PKs from unique_count ≈ row_count.

← Back to [CONTEXT.md](../CONTEXT.md)