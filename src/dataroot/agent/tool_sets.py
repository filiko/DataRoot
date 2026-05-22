"""
Tool set definitions for DataRoot's three agent roles.

Each role has a list of tool schemas it is allowed to call.
Tools are defined once and referenced by each role's tool list.
"""

from typing import Literal

RoleName = Literal["domain_spec_generator", "domain_spec_applier", "query_agent"]

TOOLS: dict[RoleName, list[dict]] = {
    "domain_spec_generator": [
        {
            "type": "function",
            "function": {
                "name": "kb_search",
                "description": "Full-text search over all KB documents. Returns doc slugs and snippets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kb_show",
                "description": "Get full content of a KB document by slug.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string", "description": "Document slug"},
                    },
                    "required": ["slug"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kb_list",
                "description": "List KB documents filtered by type, status, tags, or path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "Document type filter"},
                        "status": {"type": "string", "description": "Status filter"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Tag filter"},
                        "path": {"type": "string", "description": "Path prefix filter"},
                    },
                },
            },
        },
    ],
    "domain_spec_applier": [
        {
            "type": "function",
            "function": {
                "name": "kb_show",
                "description": "Get full content of a KB document by slug.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string", "description": "Document slug"},
                    },
                    "required": ["slug"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kb_update",
                "description": "Update a KB document with enriched content, tags, and wikilinks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string", "description": "Document slug to update"},
                        "content": {"type": "string", "description": "Updated Markdown content with frontmatter"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Domain tags to add"},
                        "wikilinks": {"type": "array", "items": {"type": "string"}, "description": "Wikilinks to add in format [[slug|label]]"},
                    },
                    "required": ["slug", "content"],
                },
            },
        },
    ],
    "query_agent": [
        {
            "type": "function",
            "function": {
                "name": "kb_search",
                "description": "Full-text search over all KB documents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kb_semantic",
                "description": "Semantic search over KB documents. Falls back to FTS if vector search unavailable.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Semantic query"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kb_show",
                "description": "Get full content of a KB document.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string", "description": "Document slug"},
                    },
                    "required": ["slug"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kb_list",
                "description": "List KB documents filtered by type, status, tags, or path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "Document type filter"},
                        "status": {"type": "string", "description": "Status filter"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Tag filter"},
                        "path": {"type": "string", "description": "Path prefix filter"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kb_graph",
                "description": "Graph traversal from a document. Returns linked documents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string", "description": "Starting document slug"},
                        "direction": {"type": "string", "enum": ["outbound", "inbound", "both"], "description": "Traversal direction"},
                        "depth": {"type": "integer", "description": "Max depth", "default": 2},
                    },
                    "required": ["slug"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find_candidate_paths",
                "description": "Find paths between documents in the graph matching start and target terms.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_terms": {"type": "array", "items": {"type": "string"}, "description": "Starting entity terms"},
                        "target_terms": {"type": "array", "items": {"type": "string"}, "description": "Target entity terms"},
                        "constraints": {"type": "object", "description": "Additional constraints"},
                    },
                    "required": ["start_terms", "target_terms"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_table",
                "description": "Query rows from a table document with filters and aggregations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_slug": {"type": "string", "description": "Table document slug"},
                        "filters": {"type": "array", "description": "Filter conditions"},
                        "aggregations": {"type": "object", "description": "Aggregation spec"},
                        "limit": {"type": "integer", "description": "Max rows", "default": 50},
                    },
                    "required": ["table_slug"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "log_inquiry",
                "description": "Write the customer question, answer, and provenance trace as an inquiry KB doc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Original question"},
                        "answer": {"type": "string", "description": "Agent's answer"},
                        "provenance_trace": {"type": "object", "description": "Provenance JSON block"},
                    },
                    "required": ["question", "answer", "provenance_trace"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "render_provenance",
                "description": "Render a provenance trace to Miro or HTML.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace": {"type": "object", "description": "Provenance trace object"},
                        "mode": {"type": "string", "enum": ["miro", "html"], "description": "Render mode"},
                        "answer": {"type": "string", "description": "Optional answer text to show in the final answer card"},
                    },
                    "required": ["trace", "mode"],
                },
            },
        },
    ],
}


def get_tools(role: RoleName) -> list[dict]:
    """Return the tool schemas for a given role."""
    return TOOLS[role]
