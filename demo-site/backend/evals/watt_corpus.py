"""Textbook ERD corpus — answer-key PenFiles + verbatim business rules.

Source (the standard we measure against):

    Watt, A. & Eng, N. (2014). *Database Design – 2nd Edition.*
    BCcampus / OpenTextBC. Appendix B: "Sample ERD Exercises".
    Licensed CC BY 4.0.
    https://opentextbc.ca/dbdesign01/back-matter/appendix-b-erd-exercises/

Each exercise gives an English business-rule paragraph WITH a published answer
key (entities, primary keys, relationships, cardinality, optionality, and the
associative/junction entities that resolve many-to-many relationships). We encode
the answer key as a `PenFile` and the rules as `BusinessRule`s linked to the
relationship they govern, so the verification layers (V0 structural integrity,
V1 rule↔cardinality) can be checked against a known-correct reference — and so
the generation eval can score an LLM's ERD against the same key.

This module holds only the CLEAN answer keys + verbatim rule text. The corrupted
variants that exercise the negative paths live in the conformance test.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from models.pen import (
    Attribute,
    BusinessRule,
    Cardinality,
    Entity,
    PenFile,
    Relationship,
    RelationshipEndpoint,
)

CITATION = (
    "Watt & Eng, Database Design – 2nd Ed., Appendix B (Sample ERD Exercises), "
    "BCcampus/OpenTextBC, CC BY 4.0"
)


def _attr(attr_id: str, name: str, *, key_role: str = "none", nullable: bool = True,
          pg_type: str = "text") -> Attribute:
    return Attribute(id=attr_id, name=name, pg_type=pg_type, key_role=key_role, nullable=nullable)


def _entity(eid: str, name: str, display: str, attrs: list[Attribute]) -> Entity:
    return Entity(id=eid, name=name, display_name=display, attributes=attrs, review_status="accepted")


def _rel(rid: str, name: str, from_ent: str, from_attr: str, to_ent: str, to_attr: str,
         card: Cardinality) -> Relationship:
    return Relationship(
        id=rid, name=name,
        from_=RelationshipEndpoint(entity_id=from_ent, attribute_id=from_attr),
        to=RelationshipEndpoint(entity_id=to_ent, attribute_id=to_attr),
        # Copy so each relationship owns its Cardinality — never share a mutable
        # instance across relationships (in-place edits would leak to siblings).
        cardinality=card.model_copy(deep=True), review_status="accepted",
    )


def _many_to_one_mandatory() -> Cardinality:
    """A junction/associative row references exactly one parent (mandatory, max
    one); each parent has zero-or-many such rows — the classic many-to-one."""
    return Cardinality(from_min=0, from_max="many", to_min=1, to_max=1)


# ─────────────────────────────────────────────────────────────────────────────
# Exercise 1 — Manufacturer (many-to-many resolved with junction entities)
# ─────────────────────────────────────────────────────────────────────────────

MANUFACTURER_PARAGRAPH = (
    "A manufacturing company produces products. The following information is "
    "tracked for each product: product name, product ID, and quantity on hand. "
    "These products are made up of many components. Each component can be supplied "
    "by one or more suppliers. The following information is kept for each "
    "component: component ID, name, description, the suppliers who supply them, and "
    "the products in which they are used. Assume the following: a supplier can "
    "exist without providing components; a component does not have to be associated "
    "with a supplier; a component does not have to be associated with a product; a "
    "product cannot exist without components."
)


def manufacturer_pen() -> PenFile:
    """Answer key: Component, Product, Supplier + CompSupp & Build junction
    entities resolving the two many-to-many relationships."""
    component = _entity("ent_component", "component", "Component", [
        _attr("comp_pk", "comp_id", key_role="primary", nullable=False),
        _attr("comp_name", "comp_name"),
        _attr("comp_desc", "description"),
    ])
    product = _entity("ent_product", "product", "Product", [
        _attr("prod_pk", "prod_id", key_role="primary", nullable=False),
        _attr("prod_name", "prod_name"),
        _attr("prod_qoh", "qty_on_hand", pg_type="integer"),
    ])
    supplier = _entity("ent_supplier", "supplier", "Supplier", [
        _attr("supp_pk", "supp_id", key_role="primary", nullable=False),
        _attr("supp_name", "supp_name"),
    ])
    # Associative entities. Composite primary keys; the key columns double as the
    # references back to the parents (the textbook's CompSupp and Build tables).
    comp_supp = _entity("ent_comp_supp", "comp_supp", "CompSupp", [
        _attr("cs_comp", "comp_id", key_role="primary", nullable=False),
        _attr("cs_supp", "supp_id", key_role="primary", nullable=False),
    ])
    build = _entity("ent_build", "build", "Build", [
        _attr("bd_comp", "comp_id", key_role="primary", nullable=False),
        _attr("bd_prod", "prod_id", key_role="primary", nullable=False),
        _attr("bd_qty", "qty_of_comp", pg_type="integer"),
    ])

    rels = [
        _rel("rel_cs_component", "links", "ent_comp_supp", "cs_comp", "ent_component", "comp_pk", _many_to_one_mandatory()),
        _rel("rel_cs_supplier", "links", "ent_comp_supp", "cs_supp", "ent_supplier", "supp_pk", _many_to_one_mandatory()),
        _rel("rel_build_component", "uses", "ent_build", "bd_comp", "ent_component", "comp_pk", _many_to_one_mandatory()),
        _rel("rel_build_product", "in", "ent_build", "bd_prod", "ent_product", "prod_pk", _many_to_one_mandatory()),
    ]

    rules = [
        # Optionality/participation narrative — mandatory-only, no max claim. The
        # verifier must LEAVE these untouched (they are not relationship-cardinality
        # rules). Initial status is preserved as a regression guard for the
        # mentions_cardinality clobber fix.
        BusinessRule(id="rule_mfr_product_needs_components", entity_id="ent_product",
                     title="A product cannot exist without components",
                     statement="A product cannot exist without components.",
                     category="invariant", status="deferred"),
        BusinessRule(id="rule_mfr_supplier_optional", entity_id="ent_supplier",
                     title="A supplier can exist without providing components",
                     statement="A supplier can exist without providing components.",
                     category="invariant", status="deferred"),
    ]

    pen = PenFile()
    pen.project.name = "Watt Appendix B — Exercise 1: Manufacturer"
    pen.erd.entities = [component, product, supplier, comp_supp, build]
    pen.erd.relationships = rels
    pen.dfd.business_rules = rules
    return pen


# ─────────────────────────────────────────────────────────────────────────────
# Exercise 2 — Car Dealership (1:M sales + M:N service)
# ─────────────────────────────────────────────────────────────────────────────

CAR_DEALERSHIP_PARAGRAPH = (
    "A car dealership needs to track its sales and its service work. A salesperson "
    "may sell many cars, but each car is sold by only one salesperson. A customer "
    "may buy many cars, but each car is bought by only one customer. A car brought "
    "in for service can be worked on by many mechanics, and each mechanic may work "
    "on many cars. A car that is serviced may or may not need parts."
)

# The two sales rules use the canonical two-sided textbook phrasing.
RULE_SELLS = "A salesperson may sell many cars, but each car is sold by only one salesperson."
RULE_BUYS = "A customer may buy many cars, but each car is bought by only one customer."
RULE_SERVICE_M2M = (
    "A car brought in for service can be worked on by many mechanics, and each "
    "mechanic may work on many cars."
)
RULE_PARTS_OPTIONAL = "A car that is serviced may or may not need parts."


def car_dealership_pen() -> PenFile:
    """Answer key: Salesperson, Customer, Car, Mechanic, Part + WorkOn & PartUsage
    associative entities. Mechanic↔Car many-to-many is resolved by WorkOn."""
    salesperson = _entity("ent_salesperson", "salesperson", "Salesperson", [
        _attr("sp_pk", "salesperson_id", key_role="primary", nullable=False),
        _attr("sp_name", "name"),
    ])
    customer = _entity("ent_customer", "customer", "Customer", [
        _attr("cu_pk", "customer_id", key_role="primary", nullable=False),
        _attr("cu_name", "name"),
    ])
    car = _entity("ent_car", "car", "Car", [
        _attr("car_pk", "car_id", key_role="primary", nullable=False),
        _attr("car_vin", "vin", key_role="unique", nullable=False),
        _attr("car_sp_fk", "salesperson_id", key_role="foreign", nullable=False),
        _attr("car_cu_fk", "customer_id", key_role="foreign", nullable=False),
    ])
    mechanic = _entity("ent_mechanic", "mechanic", "Mechanic", [
        _attr("me_pk", "mechanic_id", key_role="primary", nullable=False),
        _attr("me_name", "name"),
    ])
    part = _entity("ent_part", "part", "Part", [
        _attr("pt_pk", "part_id", key_role="primary", nullable=False),
        _attr("pt_name", "name"),
    ])
    work_on = _entity("ent_work_on", "work_on", "WorkOn", [
        _attr("wo_pk", "work_id", key_role="primary", nullable=False),
        _attr("wo_car_fk", "car_id", key_role="foreign", nullable=False),
        _attr("wo_me_fk", "mechanic_id", key_role="foreign", nullable=False),
    ])
    part_usage = _entity("ent_part_usage", "part_usage", "PartUsage", [
        _attr("pu_pk", "usage_id", key_role="primary", nullable=False),
        _attr("pu_wo_fk", "work_id", key_role="foreign", nullable=False),
        _attr("pu_pt_fk", "part_id", key_role="foreign", nullable=False),
    ])

    rels = [
        _rel("rel_sells", "sells", "ent_car", "car_sp_fk", "ent_salesperson", "sp_pk", _many_to_one_mandatory()),
        _rel("rel_buys", "buys", "ent_car", "car_cu_fk", "ent_customer", "cu_pk", _many_to_one_mandatory()),
        _rel("rel_workon_car", "on", "ent_work_on", "wo_car_fk", "ent_car", "car_pk", _many_to_one_mandatory()),
        _rel("rel_workon_mechanic", "by", "ent_work_on", "wo_me_fk", "ent_mechanic", "me_pk", _many_to_one_mandatory()),
        # PartUsage participation is optional: a serviced car may need no parts.
        _rel("rel_partusage_workon", "for", "ent_part_usage", "pu_wo_fk", "ent_work_on", "wo_pk",
             Cardinality(from_min=0, from_max="many", to_min=1, to_max=1)),
        _rel("rel_partusage_part", "of", "ent_part_usage", "pu_pt_fk", "ent_part", "pt_pk", _many_to_one_mandatory()),
    ]

    rules = [
        BusinessRule(id="rule_sells", relationship_id="rel_sells",
                     title="Salesperson sells cars", statement=RULE_SELLS,
                     category="invariant", status="deferred"),
        BusinessRule(id="rule_buys", relationship_id="rel_buys",
                     title="Customer buys cars", statement=RULE_BUYS,
                     category="invariant", status="deferred"),
        BusinessRule(id="rule_service", relationship_id="rel_workon_car",
                     title="Mechanics service cars", statement=RULE_SERVICE_M2M,
                     category="invariant", status="deferred"),
        BusinessRule(id="rule_parts", relationship_id="rel_partusage_part",
                     title="Service may need parts", statement=RULE_PARTS_OPTIONAL,
                     category="invariant", status="deferred"),
    ]

    pen = PenFile()
    pen.project.name = "Watt Appendix B — Exercise 2: Car Dealership"
    pen.erd.entities = [salesperson, customer, car, mechanic, part, work_on, part_usage]
    pen.erd.relationships = rels
    pen.dfd.business_rules = rules
    return pen


# ─────────────────────────────────────────────────────────────────────────────
# Corpus index
# ─────────────────────────────────────────────────────────────────────────────

# The textbook's PUBLISHED answer key, authored independently of our PenFile, so
# the reference view's left panel is genuine ground truth (not a readout of our
# own model). Used to verify the rendered diagram matches the textbook by eye.
MANUFACTURER_ANSWER_KEY = [
    "Component(CompID, CompName, Description)     PK = CompID",
    "Product(ProdID, ProdName, QtyOnHand)         PK = ProdID",
    "Supplier(SuppID, SuppName)                   PK = SuppID",
    "CompSupp(CompID, SuppID)                     PK = CompID, SuppID   [junction: Component ↔ Supplier]",
    "Build(CompID, ProdID, QtyOfComp)             PK = CompID, ProdID   [junction: Component ↔ Product]",
]

# Watt references an answer diagram for Ex.2 but the published page does not fully
# transcribe it; this is the standard/canonical solution to the verbatim rules.
CAR_DEALERSHIP_ANSWER_KEY = [
    "Salesperson(SalespersonID, Name)             PK = SalespersonID",
    "Customer(CustomerID, Name)                   PK = CustomerID",
    "Car(CarID, VIN, SalespersonID, CustomerID)   PK = CarID; FK SalespersonID, CustomerID (each mandatory)",
    "Mechanic(MechanicID, Name)                   PK = MechanicID",
    "Part(PartID, Name)                           PK = PartID",
    "WorkOn(CarID, MechanicID)                    PK = CarID, MechanicID   [junction: Car ↔ Mechanic, the M:N service]",
    "PartUsage(WorkID, PartID)                    optional — a serviced car may need no parts",
    "(standard solution — Watt's printed Ex.2 diagram is not transcribed verbatim)",
]


@dataclass(frozen=True)
class ErdExercise:
    key: str
    title: str
    source: str
    paragraph: str          # verbatim business rules → input for the generation eval
    build: Callable[[], PenFile]  # the answer-key PenFile
    reference_answer_key: list[str]  # textbook's printed key (independent ground truth)


EXERCISES: list[ErdExercise] = [
    ErdExercise(
        key="watt_b_ex1_manufacturer",
        title="Manufacturer (M:N via junctions)",
        source=CITATION,
        paragraph=MANUFACTURER_PARAGRAPH,
        build=manufacturer_pen,
        reference_answer_key=MANUFACTURER_ANSWER_KEY,
    ),
    ErdExercise(
        key="watt_b_ex2_car_dealership",
        title="Car Dealership (1:M sales, M:N service)",
        source=CITATION,
        paragraph=CAR_DEALERSHIP_PARAGRAPH,
        build=car_dealership_pen,
        reference_answer_key=CAR_DEALERSHIP_ANSWER_KEY,
    ),
]
