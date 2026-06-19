"""Score a generated ERD against a textbook answer-key ERD.

Pure, deterministic, no LLM — so the scoring logic is unit-testable on its own
(feed the answer key as the "generated" model and every metric is perfect). The
generation eval (run_erd_eval.py) pairs this with the LLM generator.

Matching is name-based and structural, not id-based, because a generated model
invents its own ids:
  * entities  — matched by normalized name (snake + naive singularization);
  * relationships — matched by the unordered pair of entity names they connect;
  * cardinality — the matched relationship's shape (one_to_one / one_to_many /
    many_to_many), direction-insensitive.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from models.pen import Cardinality, PenFile


def _normalize(name: str) -> str:
    n = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    if n.endswith("ies"):
        n = n[:-3] + "y"
    elif n.endswith("ses"):
        n = n[:-2]
    elif n.endswith("s") and not n.endswith("ss"):
        n = n[:-1]
    return n


def _shape(card: Cardinality) -> str:
    many_from = card.from_max == "many"
    many_to = card.to_max == "many"
    if many_from and many_to:
        return "many_to_many"
    if many_from or many_to:
        return "one_to_many"
    return "one_to_one"


def _prf(matched: int, generated: int, expected: int) -> tuple[float, float, float]:
    precision = matched / generated if generated else 0.0
    recall = matched / expected if expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1


@dataclass
class ErdScore:
    entity_precision: float
    entity_recall: float
    entity_f1: float
    pk_accuracy: float                # matched entities whose generated form has a PK
    relationship_precision: float
    relationship_recall: float
    relationship_f1: float
    cardinality_accuracy: float       # matched relationships with the same shape
    missing_entities: list[str] = field(default_factory=list)
    extra_entities: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "entity_precision": round(self.entity_precision, 3),
            "entity_recall": round(self.entity_recall, 3),
            "entity_f1": round(self.entity_f1, 3),
            "pk_accuracy": round(self.pk_accuracy, 3),
            "relationship_precision": round(self.relationship_precision, 3),
            "relationship_recall": round(self.relationship_recall, 3),
            "relationship_f1": round(self.relationship_f1, 3),
            "cardinality_accuracy": round(self.cardinality_accuracy, 3),
            "missing_entities": self.missing_entities,
            "extra_entities": self.extra_entities,
        }


def _entity_norm_map(pen: PenFile) -> dict[str, str]:
    """entity_id → normalized name."""
    return {e.id: _normalize(e.display_name or e.name) for e in pen.erd.entities}


def _has_pk(pen: PenFile, norm_name: str) -> bool:
    for e in pen.erd.entities:
        if _normalize(e.display_name or e.name) == norm_name:
            return any(a.key_role == "primary" for a in e.attributes)
    return False


def _rel_pairs(pen: PenFile) -> list[tuple[frozenset[str], str]]:
    norm = _entity_norm_map(pen)
    out: list[tuple[frozenset[str], str]] = []
    for r in pen.erd.relationships:
        a = norm.get(r.from_.entity_id)
        b = norm.get(r.to.entity_id)
        if a and b:
            out.append((frozenset({a, b}), _shape(r.cardinality)))
    return out


def score_erd(generated: PenFile, answer: PenFile) -> ErdScore:
    gen_names = {_normalize(e.display_name or e.name) for e in generated.erd.entities}
    ans_names = {_normalize(e.display_name or e.name) for e in answer.erd.entities}
    gen_names.discard("")
    ans_names.discard("")

    matched_entities = gen_names & ans_names
    ep, er, ef = _prf(len(matched_entities), len(gen_names), len(ans_names))
    pk_hits = sum(1 for n in matched_entities if _has_pk(generated, n))
    pk_accuracy = pk_hits / len(matched_entities) if matched_entities else 0.0

    # Relationships: greedily match by unordered entity-name pair.
    gen_rels = _rel_pairs(generated)
    ans_rels = _rel_pairs(answer)
    remaining = list(gen_rels)
    matched_rels = 0
    shape_matches = 0
    for pair, ans_shape in ans_rels:
        for i, (gpair, gshape) in enumerate(remaining):
            if gpair == pair:
                matched_rels += 1
                if gshape == ans_shape:
                    shape_matches += 1
                remaining.pop(i)
                break
    rp, rr, rf = _prf(matched_rels, len(gen_rels), len(ans_rels))
    cardinality_accuracy = shape_matches / matched_rels if matched_rels else 0.0

    return ErdScore(
        entity_precision=ep, entity_recall=er, entity_f1=ef, pk_accuracy=pk_accuracy,
        relationship_precision=rp, relationship_recall=rr, relationship_f1=rf,
        cardinality_accuracy=cardinality_accuracy,
        missing_entities=sorted(ans_names - gen_names),
        extra_entities=sorted(gen_names - ans_names),
    )
