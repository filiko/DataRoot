"""V1 business-rule verification: rule statement ↔ ERD cardinality.

For each BusinessRule whose English statement describes cardinality/optionality
(the may/must/one/many translation from docs/business-rule-verification.md §2),
resolve the ERD relationship it governs and check whether the relationship's
cardinality is consistent with the statement. Sets `status` (enforced/gap) and
`verified_by` on matched rules.

Deliberately conservative: it only changes a rule's status when it can (a) read a
cardinality claim from the statement AND (b) resolve a relationship to check it.
Behavioral rules (validators, state machines) carry no cardinality language, so
their statement parses to nothing and their status is left untouched.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from models.pen import BusinessRule, Cardinality, PenFile, Relationship


@dataclass
class CardinalityExpectation:
    """What a rule statement claims, coarsely. Fields are None when unstated."""
    m2m: bool = False                 # "many-to-many"
    one_to_many: bool = False         # two-sided "may have many … but each … only one"
    mandatory: bool | None = None     # must → True, may → False
    max_one: bool | None = None       # "exactly/only one" → True; "many"/"one or more" → False

    @property
    def mentions_cardinality(self) -> bool:
        # Require an explicit maximum claim (one / many / one-to-many / many-to-many).
        # Optionality alone ("must"/"may") is too weak — most behavioral rules say
        # "must" without describing a relationship's cardinality, and classifying
        # those would clobber their status. mandatory is only used as a secondary
        # check once a max claim has already qualified the statement.
        return self.m2m or self.one_to_many or self.max_one is not None


_M2M = re.compile(r"many[\s-]*to[\s-]*many", re.IGNORECASE)
_ONE_ONLY = re.compile(r"\b(exactly one|only one|one and only one|a single|at most one)\b", re.IGNORECASE)
_MANY = re.compile(r"\b(many|one or more|zero or more|multiple|several)\b", re.IGNORECASE)
_MUST = re.compile(r"\b(must|required|always|cannot exist without|has to)\b", re.IGNORECASE)
_MAY = re.compile(r"\b(may|optional|can have|might|zero or)\b", re.IGNORECASE)


def parse_cardinality_expectation(statement: str) -> CardinalityExpectation:
    text = statement or ""
    exp = CardinalityExpectation()
    if _M2M.search(text):
        exp.m2m = True
    has_one = bool(_ONE_ONLY.search(text))
    has_many = bool(_MANY.search(text))
    if exp.m2m:
        pass  # "many-to-many" is the strongest, most specific max claim
    elif has_one and has_many:
        # The canonical textbook sentence states both sides at once: "A salesperson
        # may sell many cars, but each car is sold by only one salesperson." That is
        # a one-to-many claim — verify the relationship has exactly one 'many' side.
        exp.one_to_many = True
    elif has_one:
        exp.max_one = True
    elif has_many:
        exp.max_one = False
    has_must = bool(_MUST.search(text))
    has_may = bool(_MAY.search(text))
    if has_must and not has_may:
        exp.mandatory = True
    elif has_may and not has_must:
        exp.mandatory = False
    return exp


def _is_m2m(card: Cardinality) -> bool:
    return card.from_max == "many" and card.to_max == "many"


def _has_one_side(card: Cardinality) -> bool:
    return card.from_max == 1 or card.to_max == 1


def _has_many_side(card: Cardinality) -> bool:
    return card.from_max == "many" or card.to_max == "many"


def _has_mandatory_side(card: Cardinality) -> bool:
    return card.from_min >= 1 or card.to_min >= 1


def _has_optional_side(card: Cardinality) -> bool:
    return card.from_min == 0 or card.to_min == 0


def _check(exp: CardinalityExpectation, card: Cardinality) -> str | None:
    """Return a contradiction reason, or None if consistent with what's stated."""
    if exp.m2m and not _is_m2m(card):
        return "statement says many-to-many but the relationship is not"
    if exp.one_to_many:
        if _is_m2m(card):
            return "statement says one-to-many but the relationship is many-to-many"
        if not _has_many_side(card):
            return "statement says one-to-many but neither side is many (looks one-to-one)"
    if exp.max_one is True and not _has_one_side(card):
        return "statement says exactly one but neither side is a single reference"
    if exp.max_one is False and not _has_many_side(card):
        return "statement says many but neither side is many"
    if exp.mandatory is True and not _has_mandatory_side(card):
        return "statement says mandatory but the relationship is optional on both sides"
    if exp.mandatory is False and not _has_optional_side(card):
        return "statement says optional but the relationship is mandatory on both sides"
    return None


def _resolve_relationship(
    rule: BusinessRule,
    rels: list[Relationship],
    rel_by_id: dict[str, Relationship],
    entity_names: dict[str, str],
) -> Relationship | None:
    """Find the relationship a cardinality rule governs.

    Precedence: explicit relationship_id → the single relationship on entity_id →
    the relationship between two entities named in the statement. Ambiguous cases
    return None (we then leave the rule's status untouched rather than guess)."""
    if rule.relationship_id and rule.relationship_id in rel_by_id:
        return rel_by_id[rule.relationship_id]

    if rule.entity_id:
        touching = [r for r in rels if rule.entity_id in (r.from_.entity_id, r.to.entity_id)]
        if len(touching) == 1:
            return touching[0]
        if len(touching) > 1:
            # Disambiguate by a second entity named in the statement.
            text = (rule.statement or "").lower()
            for r in touching:
                other = r.to.entity_id if r.from_.entity_id == rule.entity_id else r.from_.entity_id
                name = entity_names.get(other, "").lower()
                if name and name in text:
                    return r
        return None

    # No entity link: match two entity names mentioned in the statement.
    text = (rule.statement or "").lower()
    mentioned = [eid for eid, name in entity_names.items() if name and name.lower() in text]
    if len(mentioned) >= 2:
        for r in rels:
            if r.from_.entity_id in mentioned and r.to.entity_id in mentioned:
                return r
    return None


def verify_business_rules(pen: PenFile) -> PenFile:
    """Annotate cardinality-bearing business rules with enforced/gap status by
    checking them against the ERD. Idempotent; leaves non-cardinality rules alone."""
    rels = [r for r in pen.erd.relationships if r.review_status != "rejected"]
    rel_by_id = {r.id: r for r in rels}
    entity_names: dict[str, str] = {}
    for e in pen.erd.entities:
        entity_names[e.id] = e.display_name or e.name

    for rule in pen.dfd.business_rules:
        if rule.review_status == "rejected":
            continue
        exp = parse_cardinality_expectation(rule.statement)
        if not exp.mentions_cardinality:
            continue  # behavioral/non-structural rule — don't touch its status

        rel = _resolve_relationship(rule, rels, rel_by_id, entity_names)
        if rel is None:
            # No relationship resolves. Only call this a gap when the rule explicitly
            # claims a structural link (relationship_id / entity_id) — a stated
            # cardinality the ERD doesn't carry. A rule with no link whose wording
            # merely contains "a single"/"multiple"/"many" is almost always a
            # validation/behavioral rule, so leave its status and provenance
            # untouched (this module's contract: only mutate when a relationship is
            # actually checkable).
            if rule.relationship_id or rule.entity_id:
                rule.status = "gap"
                rule.verified_by = "rule↔ERD: cardinality stated but no matching relationship found"
            continue

        reason = _check(exp, rel.cardinality)
        label = rel.name or rel.id
        if reason is None:
            rule.status = "enforced"
            rule.verified_by = f"rule↔ERD: consistent with relationship '{label}' cardinality"
        else:
            rule.status = "gap"
            rule.verified_by = f"rule↔ERD: contradicts relationship '{label}' — {reason}"
    return pen
