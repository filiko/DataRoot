"""Generic System Map fixtures used by tests and examples."""

from __future__ import annotations

from dataroot.systemmap.models import (
    AccessSurface,
    AuthConfig,
    BusinessRule,
    Connector,
    DataField,
    DataFlow,
    DataObject,
    EnterpriseSystem,
    Evidence,
    Ref,
    SystemMap,
)

CAPTURED_AT = "2026-01-01T00:00:00Z"


def _evidence(record_id: str, kind: str, locator: str, excerpt: str, confidence: float = 0.9) -> Evidence:
    return Evidence(
        id=f"ev_{record_id}",
        kind=kind,  # type: ignore[arg-type]
        locator=locator,
        excerpt=excerpt,
        confidence=confidence,
        captured_at=CAPTURED_AT,
    )


def generic_saas_abc_map() -> SystemMap:
    """Return a Nexus-free System Map for SaaS A/B/C data-access examples."""

    ev_a = _evidence("saas_a", "mcp_descriptor", "mcp://saas_a/tools/list", "SaaS A exposes get_theta and get_iota.")
    ev_b = _evidence("saas_b", "openapi_spec", "https://api.saas-b.example/openapi.json", "SaaS B devices API.")
    ev_c = _evidence("saas_c", "openapi_spec", "https://api.saas-c.example/openapi.json", "SaaS C orders API.")
    ev_rule = _evidence(
        "n9102_status_rule",
        "openapi_spec",
        "https://api.saas-b.example/openapi.json#/components/schemas/Device/properties/n9102_status",
        "n9102_status enum values: pass, fail, pending.",
    )
    ev_seam = _evidence("order_device_seam", "manual", "manual://workshop/saas-abc", "Order.device_id maps to Device.device_id.")

    systems = [
        EnterpriseSystem(id="saas_a", name="SaaS A", kind="mcp_server", owner="operations", evidence=[ev_a], confidence=0.9, review_status="accepted"),
        EnterpriseSystem(id="saas_b", name="SaaS B", kind="saas", owner="compliance", evidence=[ev_b], confidence=0.9, review_status="accepted"),
        EnterpriseSystem(id="saas_c", name="SaaS C", kind="saas", owner="fulfillment", evidence=[ev_c], confidence=0.9, review_status="accepted"),
    ]

    surfaces = [
        AccessSurface(
            id="surface_saas_a_get_theta",
            system_id="saas_a",
            kind="mcp_tool",
            operation="read",
            name="get_theta",
            address="mcp://saas_a/get_theta",
            auth=AuthConfig(method="oauth2", scopes=["theta:read"]),
            response_schema_ref="object_theta_reading",
            evidence=[ev_a],
            confidence=0.9,
            review_status="accepted",
        ),
        AccessSurface(
            id="surface_saas_a_get_iota",
            system_id="saas_a",
            kind="mcp_tool",
            operation="read",
            name="get_iota",
            address="mcp://saas_a/get_iota",
            auth=AuthConfig(method="oauth2", scopes=["iota:read"]),
            evidence=[ev_a],
            confidence=0.86,
            review_status="accepted",
        ),
        AccessSurface(
            id="surface_saas_b_get_device",
            system_id="saas_b",
            kind="openapi_endpoint",
            operation="read",
            name="GET /devices/{id}",
            address="GET https://api.saas-b.example/devices/{id}",
            auth=AuthConfig(method="bearer", scopes=["devices:read"]),
            response_schema_ref="object_device",
            evidence=[ev_b],
            confidence=0.92,
            review_status="accepted",
        ),
        AccessSurface(
            id="surface_saas_c_get_orders",
            system_id="saas_c",
            kind="openapi_endpoint",
            operation="read",
            name="GET /orders",
            address="GET https://api.saas-c.example/orders",
            auth=AuthConfig(method="bearer", scopes=["orders:read"]),
            response_schema_ref="object_order",
            evidence=[ev_c],
            confidence=0.92,
            review_status="accepted",
        ),
    ]

    objects = [
        DataObject(id="object_theta_reading", system_id="saas_a", surface_ids=["surface_saas_a_get_theta"], name="ThetaReading", evidence=[ev_a], confidence=0.9, review_status="accepted"),
        DataObject(id="object_device", system_id="saas_b", surface_ids=["surface_saas_b_get_device"], name="Device", evidence=[ev_b], confidence=0.92, review_status="accepted"),
        DataObject(id="object_order", system_id="saas_c", surface_ids=["surface_saas_c_get_orders"], name="Order", evidence=[ev_c], confidence=0.92, review_status="accepted"),
    ]

    fields = [
        DataField(id="field_theta_id", object_id="object_theta_reading", name="id", type="string", nullable=False, sensitivity="internal", source_path="$.id", evidence=[ev_a], confidence=0.9, review_status="accepted"),
        DataField(id="field_theta_value", object_id="object_theta_reading", name="value", type="number", nullable=False, sensitivity="internal", source_path="$.value", evidence=[ev_a], confidence=0.9, review_status="accepted"),
        DataField(id="field_theta_subject_ref", object_id="object_theta_reading", name="subject_ref", type="string", nullable=True, sensitivity="internal", source_path="$.subject_ref", evidence=[ev_a], confidence=0.8, review_status="needs_review"),
        DataField(id="field_device_device_id", object_id="object_device", name="device_id", type="string", nullable=False, sensitivity="internal", source_path="$.device_id", evidence=[ev_b], confidence=0.92, review_status="accepted"),
        DataField(id="field_device_n9102_status", object_id="object_device", name="n9102_status", type="enum", nullable=False, sensitivity="internal", source_path="$.n9102_status", evidence=[ev_rule], confidence=0.92, review_status="accepted"),
        DataField(id="field_device_owner_email", object_id="object_device", name="owner_email", type="string", nullable=True, sensitivity="pii", source_path="$.owner_email", evidence=[ev_b], confidence=0.72, review_status="needs_review"),
        DataField(id="field_order_order_id", object_id="object_order", name="order_id", type="string", nullable=False, sensitivity="internal", source_path="$.order_id", evidence=[ev_c], confidence=0.92, review_status="accepted"),
        DataField(id="field_order_customer_id", object_id="object_order", name="customer_id", type="string", nullable=False, sensitivity="pii", source_path="$.customer_id", evidence=[ev_c], confidence=0.8, review_status="needs_review"),
        DataField(id="field_order_device_id", object_id="object_order", name="device_id", type="string", nullable=True, sensitivity="internal", source_path="$.device_id", evidence=[ev_c], confidence=0.92, review_status="accepted"),
        DataField(id="field_order_status", object_id="object_order", name="status", type="enum", nullable=False, sensitivity="internal", source_path="$.status", evidence=[ev_c], confidence=0.92, review_status="accepted"),
    ]

    rules = [
        BusinessRule(
            id="rule_n9102_status_values",
            scope=Ref(kind="object", id="object_device"),
            title="N9102 status values are constrained",
            statement="Device compliance status must be one of pass, fail, or pending.",
            category="validation",
            condition="n9102_status in {'pass', 'fail', 'pending'}",
            enforced_at=["https://api.saas-b.example/openapi.json#/components/schemas/Device/properties/n9102_status"],
            evidence=[ev_rule],
            confidence=0.9,
            review_status="accepted",
        ),
        # A cross-system rule: it governs Order (SaaS C) but references Device
        # (SaaS B). Verifiable only because a connector/seam bridges the systems.
        BusinessRule(
            id="rule_order_requires_compliant_device",
            scope=Ref(kind="object", id="object_order"),
            title="Fulfilled orders reference a compliant device",
            statement="Every fulfilled order must reference a Device that passed n9102 compliance.",
            category="gate",
            evidence=[ev_seam],
            confidence=0.8,
            review_status="needs_review",
        ),
    ]

    connectors = [
        Connector(
            id="connector_order_device_id",
            name="Order fulfillment references device compliance",
            kind="seam",
            trigger="SaaS C order includes device_id",
            effect="SaaS B device/compliance record can be joined for fulfillment checks",
            from_system="saas_c",
            to_systems=["saas_b"],
            contract="Order.device_id -> Device.device_id",
            evidence=[ev_seam],
            confidence=0.82,
            review_status="needs_review",
        )
    ]

    flows = [
        DataFlow(
            id="flow_order_to_device_compliance",
            from_ref=Ref(kind="object", id="object_order"),
            to_ref=Ref(kind="object", id="object_device"),
            via="connector_order_device_id",
            data_object_ids=["object_order", "object_device"],
            trigger="Order references a device",
            evidence=[ev_seam],
            confidence=0.82,
        )
    ]

    return SystemMap(
        systems=systems,
        access_surfaces=surfaces,
        data_objects=objects,
        data_fields=fields,
        business_rules=rules,
        connectors=connectors,
        data_flows=flows,
    )
