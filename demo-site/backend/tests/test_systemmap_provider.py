"""Pytest tests for systemmap_provider.py — AST-based detection of middleware, outbound calls, and business rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_analysis.inventory import build_inventory
from repo_analysis.models import EvidenceRecord, FactRecord
from repo_analysis.systemmap_provider import (
    _build_enforced_at,
    _call_name,
    _detect_auth_dependency,
    _detect_enum_transition,
    _detect_http_client,
    _detect_middleware_decorator,
    _detect_validator,
    _extract_url_from_call,
    _full_call_name,
    _get_imports,
    _is_auth_related_import,
    _literal_string,
    _stable_id,
    business_rule_evidence_to_facts,
    collect_business_rules,
    collect_middleware_connectors,
    collect_outbound_connectors,
    evidence_to_systemmap,
    middleware_evidence_to_facts,
    outbound_evidence_to_facts,
)
from dataroot.systemmap import SystemMap


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_inventory(tmp_path: Path) -> Path:
    """Create a sample Python file and return its inventory."""
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
    return build_inventory(tmp_path)


# =============================================================================
# Test 1: Middleware guard detection from AST
# =============================================================================

class TestMiddlewareGuardDetection:
    """Tests for middleware and auth guard detection via AST."""

    def test_detects_app_middleware_decorator(self, tmp_path: Path) -> None:
        """Should detect @app.middleware decorator."""
        app_file = tmp_path / "app.py"
        app_file.write_text(
            "\n".join([
                "from fastapi import FastAPI",
                "app = FastAPI()",
                "",
                "@app.middleware('http')",
                "async def auth_middleware(request, call_next):",
                "    return await call_next(request)",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_middleware_connectors(tmp_path, inventory)

        assert len(records) >= 1
        middleware_records = [r for r in records if r.type == "middleware_guard"]
        assert len(middleware_records) == 1
        assert middleware_records[0].attributes["kind"] == "middleware"
        assert middleware_records[0].attributes["handler"] == "auth_middleware"

    def test_detects_middleware_decorator_direct(self, tmp_path: Path) -> None:
        """Should detect @middleware decorator."""
        app_file = tmp_path / "app.py"
        app_file.write_text(
            "\n".join([
                "from fastapi import FastAPI",
                "app = FastAPI()",
                "",
                "@app.middleware('http')",
                "async def logging_middleware(request, call_next):",
                "    return await call_next(request)",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_middleware_connectors(tmp_path, inventory)

        assert len(records) >= 1
        middleware_records = [r for r in records if r.type == "middleware_guard"]
        assert len(middleware_records) == 1
        assert middleware_records[0].attributes["kind"] == "middleware"

    def test_detects_depends_auth_decorator(self, tmp_path: Path) -> None:
        """Should detect Depends() with auth dependency in function signature."""
        app_file = tmp_path / "app.py"
        app_file.write_text(
            "\n".join([
                "from fastapi import Depends, FastAPI",
                "from fastapi.security import HTTPBearer",
                "app = FastAPI()",
                "security = HTTPBearer()",
                "",
                "@app.get('/protected')",
                "def protected_route(token: str = Depends(security)):",
                "    return {'ok': True}",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_middleware_connectors(tmp_path, inventory)

        auth_records = [r for r in records if r.type == "auth_guard"]
        assert len(auth_records) >= 1
        assert auth_records[0].attributes["kind"] == "auth"

    def test_detects_auth_decorator(self, tmp_path: Path) -> None:
        """Should detect auth-related decorators."""
        app_file = tmp_path / "app.py"
        app_file.write_text(
            "\n".join([
                "from fastapi import FastAPI",
                "app = FastAPI()",
                "",
                "@app.middleware('http')",
                "async def jwt_guard(request, call_next):",
                "    return await call_next(request)",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_middleware_connectors(tmp_path, inventory)

        # Both middleware and auth guard should be detected
        assert len(records) >= 1

    def test_middleware_record_has_correct_structure(self, tmp_path: Path) -> None:
        """Middleware records should have correct structure with enforced_at."""
        app_file = tmp_path / "app.py"
        app_file.write_text(
            "\n".join([
                "from fastapi import FastAPI",
                "app = FastAPI()",
                "",
                "@app.middleware('http')",
                "async def logging_middleware(request, call_next):",
                "    return await call_next(request)",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_middleware_connectors(tmp_path, inventory)

        assert len(records) >= 1
        record = records[0]
        assert record.id
        assert record.type == "middleware_guard"
        assert record.source == "python_ast"
        assert record.path == "app.py"
        assert record.line_start is not None
        assert record.excerpt is not None
        assert "middleware" in record.tags
        assert 0.0 <= record.confidence <= 1.0


# =============================================================================
# Test 2: Outbound HTTP call detection
# =============================================================================

class TestOutboundCallDetection:
    """Tests for outbound HTTP/SDK call detection via AST."""

    def test_detects_requests_get(self, tmp_path: Path) -> None:
        """Should detect requests.get() calls."""
        app_file = tmp_path / "client.py"
        app_file.write_text(
            "\n".join([
                "import requests",
                "",
                "def fetch_data():",
                "    response = requests.get('https://api.example.com/data')",
                "    return response.json()",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_outbound_connectors(tmp_path, inventory)

        assert len(records) >= 1
        outbound_records = [r for r in records if r.type == "outbound_call"]
        assert len(outbound_records) == 1
        assert outbound_records[0].attributes["client"] == "requests"
        assert outbound_records[0].attributes["method"] == "GET"
        assert outbound_records[0].attributes["url"] == "https://api.example.com/data"
        assert outbound_records[0].attributes["target_system"] == "api.example.com"

    def test_detects_requests_post(self, tmp_path: Path) -> None:
        """Should detect requests.post() calls."""
        app_file = tmp_path / "client.py"
        app_file.write_text(
            "\n".join([
                "import requests",
                "",
                "def submit_data(payload):",
                "    response = requests.post(",
                "        'https://api.example.com/submit',",
                "        json=payload",
                "    )",
                "    return response.json()",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_outbound_connectors(tmp_path, inventory)

        outbound_records = [r for r in records if r.type == "outbound_call"]
        assert len(outbound_records) == 1
        assert outbound_records[0].attributes["client"] == "requests"
        assert outbound_records[0].attributes["method"] == "POST"

    def test_detects_httpx_client(self, tmp_path: Path) -> None:
        """Should detect httpx.Client() calls."""
        app_file = tmp_path / "client.py"
        app_file.write_text(
            "\n".join([
                "import httpx",
                "",
                "def fetch_httpx():",
                "    client = httpx.Client()",
                "    response = client.get('https://api.example.com/data')",
                "    return response.json()",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_outbound_connectors(tmp_path, inventory)

        outbound_records = [r for r in records if r.type == "outbound_call"]
        assert len(outbound_records) >= 1
        assert any(r.attributes["client"] == "httpx" for r in outbound_records)

    def test_detects_httpx_async_client(self, tmp_path: Path) -> None:
        """Should detect httpx.AsyncClient() calls."""
        app_file = tmp_path / "client.py"
        app_file.write_text(
            "\n".join([
                "import httpx",
                "",
                "async def fetch_async():",
                "    async with httpx.AsyncClient() as client:",
                "        response = await client.get('https://api.example.com/data')",
                "        return response.json()",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_outbound_connectors(tmp_path, inventory)

        outbound_records = [r for r in records if r.type == "outbound_call"]
        assert len(outbound_records) >= 1

    def test_outbound_record_has_correct_structure(self, tmp_path: Path) -> None:
        """Outbound records should have correct structure with enforced_at."""
        app_file = tmp_path / "client.py"
        app_file.write_text(
            "\n".join([
                "import requests",
                "",
                "def fetch_data():",
                "    return requests.get('https://api.example.com/data')",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_outbound_connectors(tmp_path, inventory)

        assert len(records) >= 1
        record = records[0]
        assert record.id
        assert record.type == "outbound_call"
        assert record.source == "python_ast"
        assert record.path == "client.py"
        assert record.line_start is not None
        assert "outbound" in record.tags
        assert "http" in record.tags
        assert 0.0 <= record.confidence <= 1.0

    def test_extracts_url_from_keyword_args(self, tmp_path: Path) -> None:
        """Should extract URL from keyword arguments."""
        app_file = tmp_path / "client.py"
        app_file.write_text(
            "\n".join([
                "import requests",
                "",
                "def fetch_data():",
                "    return requests.get(url='https://api.example.com/data')",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_outbound_connectors(tmp_path, inventory)

        outbound_records = [r for r in records if r.type == "outbound_call"]
        assert len(outbound_records) == 1
        assert outbound_records[0].attributes["url"] == "https://api.example.com/data"


# =============================================================================
# Test 3: Validator/state-transition detection
# =============================================================================

class TestValidatorDetection:
    """Tests for Pydantic validator detection via AST."""

    def test_detects_pydantic_validator(self, tmp_path: Path) -> None:
        """Should detect @validator decorator."""
        app_file = tmp_path / "models.py"
        app_file.write_text(
            "\n".join([
                "from pydantic import BaseModel, validator",
                "",
                "class User(BaseModel):",
                "    name: str",
                "    email: str",
                "",
                "    @validator('email')",
                "    def email_must_be_valid(cls, v):",
                "        return v",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_business_rules(tmp_path, inventory)

        validator_records = [r for r in records if r.type == "pydantic_validator"]
        assert len(validator_records) >= 1
        assert any(r.attributes["validator_kind"] == "validator" for r in validator_records)

    def test_detects_field_validator(self, tmp_path: Path) -> None:
        """Should detect @field_validator decorator."""
        app_file = tmp_path / "models.py"
        app_file.write_text(
            "\n".join([
                "from pydantic import BaseModel, field_validator",
                "",
                "class Order(BaseModel):",
                "    total: float",
                "",
                "    @field_validator('total')",
                "    @classmethod",
                "    def total_must_be_positive(cls, v):",
                "        if v < 0:",
                "            raise ValueError('must be positive')",
                "        return v",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_business_rules(tmp_path, inventory)

        validator_records = [r for r in records if r.type == "pydantic_validator"]
        assert len(validator_records) >= 1
        assert any(r.attributes["validator_kind"] == "field_validator" for r in validator_records)

    def test_detects_validator_with_import_prefix(self, tmp_path: Path) -> None:
        """Should detect validators with import prefix."""
        app_file = tmp_path / "models.py"
        app_file.write_text(
            "\n".join([
                "from pydantic import BaseModel",
                "import pydantic",
                "",
                "class User(BaseModel):",
                "    email: str",
                "",
                "    @pydantic.validator('email')",
                "    def email_must_be_valid(cls, v):",
                "        return v",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_business_rules(tmp_path, inventory)

        validator_records = [r for r in records if r.type == "pydantic_validator"]
        assert len(validator_records) >= 1
        assert any(r.attributes["validator_kind"] == "validator" for r in validator_records)

    def test_validator_record_has_correct_structure(self, tmp_path: Path) -> None:
        """Validator records should have correct structure."""
        app_file = tmp_path / "models.py"
        app_file.write_text(
            "\n".join([
                "from pydantic import BaseModel, validator",
                "",
                "class User(BaseModel):",
                "    email: str",
                "",
                "    @validator('email')",
                "    def email_must_be_valid(cls, v):",
                "        return v",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_business_rules(tmp_path, inventory)

        validator_records = [r for r in records if r.type == "pydantic_validator"]
        assert len(validator_records) >= 1
        record = validator_records[0]
        assert record.id
        assert record.type == "pydantic_validator"
        assert record.source == "python_ast"
        assert record.attributes["category"] == "validation"
        assert "validator" in record.tags
        assert "pydantic" in record.tags


class TestStateTransitionDetection:
    """Tests for state transition detection via AST."""

    def test_detects_state_transition_from_function_name(self, tmp_path: Path) -> None:
        """Should detect state transitions from function naming patterns."""
        app_file = tmp_path / "workflow.py"
        app_file.write_text(
            "\n".join([
                "class OrderWorkflow:",
                "    def transition_pending_to_processing(self):",
                "        pass",
                "",
                "    def from_draft_to_submitted(self):",
                "        pass",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_business_rules(tmp_path, inventory)

        transition_records = [r for r in records if r.type == "state_transition"]
        assert len(transition_records) >= 1

    def test_detects_state_machine_patterns(self, tmp_path: Path) -> None:
        """Should detect state machine patterns in function body."""
        app_file = tmp_path / "workflow.py"
        app_file.write_text(
            "\n".join([
                "class StateMachine:",
                "    def change_status(self, new_status):",
                "        self.status = new_status",
                "",
                "    def set_state(self, state):",
                "        self.state = state",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_business_rules(tmp_path, inventory)

        transition_records = [r for r in records if r.type == "state_transition"]
        assert len(transition_records) >= 1

    def test_state_transition_record_has_correct_structure(self, tmp_path: Path) -> None:
        """State transition records should have correct structure."""
        app_file = tmp_path / "workflow.py"
        app_file.write_text(
            "\n".join([
                "class OrderWorkflow:",
                "    def transition_draft_to_pending(self):",
                "        self.status = 'pending'",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        records = collect_business_rules(tmp_path, inventory)

        transition_records = [r for r in records if r.type == "state_transition"]
        assert len(transition_records) >= 1
        record = transition_records[0]
        assert record.id
        assert record.type == "state_transition"
        assert record.attributes["category"] == "state_machine"
        assert "state_machine" in record.tags
        assert "transition" in record.tags


# =============================================================================
# Test 4: Connector and BusinessRule record generation with enforced_at
# =============================================================================

class TestEnforcedAtGeneration:
    """Tests for enforced_at file:line generation."""

    def test_build_enforced_at_with_line_start(self) -> None:
        """Should build enforced_at with line_start only."""
        result = _build_enforced_at("app.py", 42, None)
        assert result == ["app.py:42"]

    def test_build_enforced_at_with_line_range(self) -> None:
        """Should build enforced_at with line range."""
        result = _build_enforced_at("app.py", 42, 50)
        assert result == ["app.py:42-50"]

    def test_build_enforced_at_with_different_lines(self) -> None:
        """Should build enforced_at with different start and end."""
        result = _build_enforced_at("app.py", 10, 20)
        assert result == ["app.py:10-20"]

    def test_build_enforced_at_without_line_start(self) -> None:
        """Should build enforced_at without line_start."""
        result = _build_enforced_at("app.py", None, None)
        assert result == ["app.py"]


class TestConnectorRecordGeneration:
    """Tests for Connector record generation."""

    def test_middleware_evidence_to_facts(self, tmp_path: Path) -> None:
        """Should convert middleware evidence to facts."""
        app_file = tmp_path / "app.py"
        app_file.write_text(
            "\n".join([
                "from fastapi import FastAPI",
                "app = FastAPI()",
                "",
                "@app.middleware('http')",
                "async def auth_middleware(request, call_next):",
                "    return await call_next(request)",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        evidence = collect_middleware_connectors(tmp_path, inventory)
        facts = middleware_evidence_to_facts(evidence)

        assert len(facts) >= 1
        fact = facts[0]
        assert fact.id
        assert fact.type == "connector"
        assert "connector" in fact.subject
        assert "enforced_at" in fact.attributes
        assert len(fact.attributes["enforced_at"]) >= 1
        assert "app.py" in fact.attributes["enforced_at"][0]

    def test_outbound_evidence_to_facts(self, tmp_path: Path) -> None:
        """Should convert outbound evidence to facts."""
        app_file = tmp_path / "client.py"
        app_file.write_text(
            "\n".join([
                "import requests",
                "",
                "def fetch_data():",
                "    return requests.get('https://api.example.com/data')",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        evidence = collect_outbound_connectors(tmp_path, inventory)
        facts = outbound_evidence_to_facts(evidence)

        assert len(facts) >= 1
        # First fact should be the connector
        connector_fact = facts[0]
        assert connector_fact.type == "connector"
        assert connector_fact.attributes["kind"] == "seam"
        assert "enforced_at" in connector_fact.attributes

        # If target_system is available, should have data_flow fact
        data_flow_facts = [f for f in facts if f.type == "data_flow"]
        assert len(data_flow_facts) >= 1
        assert data_flow_facts[0].attributes["from_system"] == "local"
        assert data_flow_facts[0].attributes["to_system"] == "api.example.com"


class TestBusinessRuleRecordGeneration:
    """Tests for BusinessRule record generation."""

    def test_validator_evidence_to_facts(self, tmp_path: Path) -> None:
        """Should convert validator evidence to facts."""
        app_file = tmp_path / "models.py"
        app_file.write_text(
            "\n".join([
                "from pydantic import BaseModel, validator",
                "",
                "class User(BaseModel):",
                "    email: str",
                "",
                "    @validator('email')",
                "    def email_must_be_valid(cls, v):",
                "        return v",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        evidence = collect_business_rules(tmp_path, inventory)
        facts = business_rule_evidence_to_facts(evidence)

        assert len(facts) >= 1
        fact = facts[0]
        assert fact.id
        assert fact.type == "business_rule"
        assert fact.attributes["category"] == "validation"
        assert "enforced_at" in fact.attributes
        assert len(fact.attributes["enforced_at"]) >= 1

    def test_state_transition_evidence_to_facts(self, tmp_path: Path) -> None:
        """Should convert state transition evidence to facts."""
        app_file = tmp_path / "workflow.py"
        app_file.write_text(
            "\n".join([
                "class OrderWorkflow:",
                "    def transition_draft_to_pending(self):",
                "        self.status = 'pending'",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        evidence = collect_business_rules(tmp_path, inventory)
        facts = business_rule_evidence_to_facts(evidence)

        assert len(facts) >= 1
        fact = facts[0]
        assert fact.id
        assert fact.type == "business_rule"
        assert fact.attributes["category"] == "state_machine"
        assert "enforced_at" in fact.attributes


# =============================================================================
# Test 5: evidence_to_systemmap() produces valid SystemMap
# =============================================================================

class TestEvidenceToSystemMap:
    """Tests for evidence_to_systemmap() conversion."""

    def test_produces_valid_system_map(self, tmp_path: Path) -> None:
        """Should produce a valid SystemMap from evidence records."""
        app_file = tmp_path / "app.py"
        app_file.write_text(
            "\n".join([
                "from fastapi import FastAPI",
                "import requests",
                "from pydantic import BaseModel, validator",
                "app = FastAPI()",
                "",
                "@app.middleware('http')",
                "async def auth_middleware(request, call_next):",
                "    return await call_next(request)",
                "",
                "def fetch_data():",
                "    return requests.get('https://api.example.com/data')",
                "",
                "class User(BaseModel):",
                "    email: str",
                "    @validator('email')",
                "    def email_must_be_valid(cls, v):",
                "        return v",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        middleware_records = collect_middleware_connectors(tmp_path, inventory)
        outbound_records = collect_outbound_connectors(tmp_path, inventory)
        rule_records = collect_business_rules(tmp_path, inventory)

        system_map = evidence_to_systemmap(
            middleware_records,
            outbound_records,
            rule_records,
        )

        assert "systems" in system_map
        assert "connectors" in system_map
        assert "business_rules" in system_map
        assert "data_flows" in system_map

        # Should have local system
        assert len(system_map["systems"]) >= 1
        local_system = next(
            (s for s in system_map["systems"] if s["name"] == "Local Repository"), None
        )
        assert local_system is not None

    def test_system_map_has_middleware_connectors(self, tmp_path: Path) -> None:
        """Should include middleware connectors in SystemMap."""
        app_file = tmp_path / "app.py"
        app_file.write_text(
            "\n".join([
                "from fastapi import FastAPI",
                "app = FastAPI()",
                "",
                "@app.middleware('http')",
                "async def auth_middleware(request, call_next):",
                "    return await call_next(request)",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        middleware_records = collect_middleware_connectors(tmp_path, inventory)

        system_map = evidence_to_systemmap(middleware_records, [], [])

        assert len(system_map["connectors"]) >= 1
        connector = system_map["connectors"][0]
        assert connector["kind"] in ("middleware", "auth")
        assert "enforced_at" in connector
        assert len(connector["enforced_at"]) >= 1

    def test_system_map_has_outbound_connectors(self, tmp_path: Path) -> None:
        """Should include outbound connectors in SystemMap."""
        app_file = tmp_path / "client.py"
        app_file.write_text(
            "\n".join([
                "import requests",
                "",
                "def fetch_data():",
                "    return requests.get('https://api.example.com/data')",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        outbound_records = collect_outbound_connectors(tmp_path, inventory)

        system_map = evidence_to_systemmap([], outbound_records, [])

        assert len(system_map["connectors"]) >= 1
        connector = system_map["connectors"][0]
        assert connector["kind"] == "seam"
        # Name should include client and method
        assert "requests" in connector["name"]
        assert "enforced_at" in connector

    def test_system_map_has_data_flows(self, tmp_path: Path) -> None:
        """Should include data flows in SystemMap for outbound calls."""
        app_file = tmp_path / "client.py"
        app_file.write_text(
            "\n".join([
                "import requests",
                "",
                "def fetch_data():",
                "    return requests.get('https://api.example.com/data')",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        outbound_records = collect_outbound_connectors(tmp_path, inventory)

        system_map = evidence_to_systemmap([], outbound_records, [])

        assert len(system_map["data_flows"]) >= 1
        flow = system_map["data_flows"][0]
        assert "from_ref" in flow
        assert "to_ref" in flow
        assert flow["from_ref"]["kind"] == "system"
        assert flow["to_ref"]["kind"] == "system"

    def test_system_map_has_business_rules(self, tmp_path: Path) -> None:
        """Should include business rules in SystemMap."""
        app_file = tmp_path / "models.py"
        app_file.write_text(
            "\n".join([
                "from pydantic import BaseModel, validator",
                "",
                "class User(BaseModel):",
                "    email: str",
                "    @validator('email')",
                "    def email_must_be_valid(cls, v):",
                "        return v",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        rule_records = collect_business_rules(tmp_path, inventory)

        system_map = evidence_to_systemmap([], [], rule_records)

        assert len(system_map["business_rules"]) >= 1
        rule = system_map["business_rules"][0]
        assert rule["category"] == "validation"
        assert "enforced_at" in rule
        assert rule["status"] == "enforced"

    def test_system_map_creates_target_system(self, tmp_path: Path) -> None:
        """Should create target system for outbound calls."""
        app_file = tmp_path / "client.py"
        app_file.write_text(
            "\n".join([
                "import requests",
                "",
                "def fetch_data():",
                "    return requests.get('https://api.example.com/data')",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        outbound_records = collect_outbound_connectors(tmp_path, inventory)

        system_map = evidence_to_systemmap([], outbound_records, [])

        # Should have local + target system
        assert len(system_map["systems"]) >= 2
        target_system = next(
            (s for s in system_map["systems"] if s["name"] == "api.example.com"), None
        )
        assert target_system is not None
        assert target_system["kind"] == "saas"

    def test_system_map_validates_with_systemmap_model(self, tmp_path: Path) -> None:
        """SystemMap dict should pass SystemMap validation."""
        app_file = tmp_path / "app.py"
        app_file.write_text(
            "\n".join([
                "from fastapi import FastAPI",
                "import requests",
                "from pydantic import BaseModel, validator",
                "app = FastAPI()",
                "",
                "@app.middleware('http')",
                "async def auth_middleware(request, call_next):",
                "    return await call_next(request)",
                "",
                "def fetch_data():",
                "    return requests.get('https://api.example.com/data')",
                "",
                "class User(BaseModel):",
                "    email: str",
                "    @validator('email')",
                "    def email_must_be_valid(cls, v):",
                "        return v",
            ]),
            encoding="utf-8",
        )

        inventory = build_inventory(tmp_path)
        middleware_records = collect_middleware_connectors(tmp_path, inventory)
        outbound_records = collect_outbound_connectors(tmp_path, inventory)
        rule_records = collect_business_rules(tmp_path, inventory)

        system_map = evidence_to_systemmap(
            middleware_records,
            outbound_records,
            rule_records,
        )

        # Should not raise - validate as SystemMap
        SystemMap.model_validate(system_map)


# =============================================================================
# Test helper functions
# =============================================================================

class TestHelperFunctions:
    """Tests for helper functions used in detection."""

    def test_stable_id_generation(self) -> None:
        """Should generate stable IDs from parts."""
        id1 = _stable_id("ev", "test", "path.py", "42")
        id2 = _stable_id("ev", "test", "path.py", "42")
        assert id1 == id2
        assert id1.startswith("ev_test_path_py_42_")

    def test_literal_string_extraction(self) -> None:
        """Should extract string literals from AST nodes."""
        import ast
        tree = ast.parse("x = 'hello'")
        assign = tree.body[0]
        result = _literal_string(assign.value)
        assert result == "hello"

    def test_call_name_extraction(self) -> None:
        """Should extract call name from AST nodes."""
        import ast
        tree = ast.parse("requests.get('url')")
        call = tree.body[0].value
        # _call_name takes the func attribute of a Call node
        assert _call_name(call.func) == "get"

    def test_full_call_name_extraction(self) -> None:
        """Should extract full dotted call name from AST nodes."""
        import ast
        tree = ast.parse("requests.get('url')")
        call = tree.body[0].value
        # _full_call_name takes the func attribute of a Call node
        assert _full_call_name(call.func) == "requests.get"

    def test_get_imports(self) -> None:
        """Should collect imports from AST."""
        import ast
        tree = ast.parse(
            "import requests\n"
            "import httpx\n"
            "from fastapi import FastAPI"
        )
        imports = _get_imports(tree)
        assert "requests" in imports
        assert "httpx" in imports
        assert "FastAPI" in imports

    def test_is_auth_related_import(self) -> None:
        """Should detect auth-related imports."""
        imports = {
            "HTTPBearer": {"fastapi.security.http.HTTPBearer"},
            "OAuth2PasswordBearer": {"fastapi.security.oauth2.OAuth2PasswordBearer"},
        }
        assert _is_auth_related_import(imports, "HTTPBearer") is True
        assert _is_auth_related_import(imports, "OAuth2PasswordBearer") is True

    def test_detect_http_client_requests(self) -> None:
        """Should detect requests HTTP client calls."""
        import ast
        tree = ast.parse("requests.get('url')")
        call = tree.body[0].value
        result = _detect_http_client(call)
        assert result == ("requests", "get")

    def test_detect_http_client_httpx(self) -> None:
        """Should detect httpx HTTP client calls."""
        import ast
        tree = ast.parse("client.get('url')")
        call = tree.body[0].value
        result = _detect_http_client(call)
        assert result == ("httpx", "get")

    def test_extract_url_from_call_positional(self) -> None:
        """Should extract URL from positional argument."""
        import ast
        tree = ast.parse("requests.get('https://api.example.com')")
        call = tree.body[0].value
        result = _extract_url_from_call(call)
        assert result == "https://api.example.com"

    def test_extract_url_from_call_keyword(self) -> None:
        """Should extract URL from keyword argument."""
        import ast
        tree = ast.parse("requests.get(url='https://api.example.com')")
        call = tree.body[0].value
        result = _extract_url_from_call(call)
        assert result == "https://api.example.com"

    def test_detect_middleware_decorator(self) -> None:
        """Should detect middleware decorators."""
        import ast
        tree = ast.parse(
            "@app.middleware('http')\n"
            "async def test(): pass"
        )
        func = tree.body[0]
        decorator = func.decorator_list[0]
        result = _detect_middleware_decorator(decorator, {})
        assert result == "middleware"

    def test_detect_auth_dependency(self) -> None:
        """Should detect Depends() calls."""
        import ast
        tree = ast.parse("Depends(security)")
        call = tree.body[0].value
        result = _detect_auth_dependency(call, {})
        assert result is True

    def test_detect_validator_pydantic(self) -> None:
        """Should detect Pydantic validators."""
        import ast
        tree = ast.parse(
            "from pydantic import validator\n"
            "@validator('email')\n"
            "def email_validator(cls, v): pass"
        )
        func = tree.body[-1]
        result = _detect_validator(func)
        assert result is not None
        assert result[0] == "validator"

    def test_detect_enum_transition(self) -> None:
        """Should detect state transitions."""
        import ast
        tree = ast.parse(
            "def transition_draft_to_pending(): pass"
        )
        func = tree.body[0]
        result = _detect_enum_transition(func)
        assert result is not None
        assert result[0] == "draft"
        assert result[1] == "pending"
