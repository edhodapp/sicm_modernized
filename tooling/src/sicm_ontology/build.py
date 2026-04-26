"""Build the sicm_modernized ontology snapshot from the YAML authoring surface.

Flow:
  YAML source  ->  pydantic validation  ->  JSON snapshot + .sha256 sidecar

Idempotent: re-running with unchanged content produces the same
snapshot byte-for-byte (sorted keys, canonical hash). Wired into the
pre-push gate later (Day 3+).

Usage::

    python -m sicm_ontology.build
    python -m sicm_ontology.build --source other.yaml --out other.json
    build-sicm-ontology    # console-script alias
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from sicm_ontology.dag import canonical_hash, load_ontology, save_ontology
from sicm_ontology.models import Ontology

# tooling/src/sicm_ontology/build.py
# parents[0]=sicm_ontology, [1]=src, [2]=tooling, [3]=<repo-root>.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SOURCE = _REPO_ROOT / "tooling" / "sicm-ontology.yaml"
_DEFAULT_OUT = _REPO_ROOT / "tooling" / "sicm-ontology.json"


def _load_yaml_source(path: Path) -> dict[str, Any]:
    """Read the YAML source and return its top-level mapping.

    Rejects non-dict top-levels at this layer so the pydantic
    validator downstream gets the shape it expects.
    """
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: YAML root must be a mapping, got "
            f"{type(data).__name__}",
        )
    return data


def build_ontology_from_yaml(source_path: Path) -> Ontology:
    """Load + validate the YAML source into an Ontology.

    Pydantic does the heavy lifting: literal checks, status discipline,
    cross-reference resolution, prerequisite cycle detection. A
    ValidationError points at a schema mismatch or dangling reference
    in the YAML.
    """
    raw = _load_yaml_source(source_path)
    return Ontology.model_validate(raw)


def build(
    source_path: Path = _DEFAULT_SOURCE,
    out_path: Path = _DEFAULT_OUT,
) -> tuple[Ontology, str, bool]:
    """Run the build. Returns (ontology, digest, changed).

    `changed` is True when the new snapshot differs from the on-disk
    one (or when no on-disk snapshot exists yet); False when the
    rebuild is a no-op against the prior content.
    """
    ontology = build_ontology_from_yaml(source_path)
    new_digest = canonical_hash(ontology)
    if _is_snapshot_unchanged(out_path, new_digest):
        return ontology, new_digest, False
    save_ontology(ontology, out_path)
    return ontology, new_digest, True


def _is_snapshot_unchanged(out_path: Path, new_digest: str) -> bool:
    """True iff the on-disk snapshot's content hash matches new_digest.

    Returns False on missing file or corrupted JSON, so the caller
    rewrites in either case rather than skipping silently.
    """
    if not out_path.exists():
        return False
    try:
        current = load_ontology(out_path)
    except (json.JSONDecodeError, ValueError):
        return False
    return canonical_hash(current) == new_digest


def _summarize(ontology: Ontology) -> str:
    """One-line count-by-kind summary for stdout."""
    return (
        f"{len(ontology.mathematical_objects)} math_obj, "
        f"{len(ontology.mathematical_relations)} math_rel, "
        f"{len(ontology.numerical_methods)} method, "
        f"{len(ontology.invariants)} invariant, "
        f"{len(ontology.code_modules)} code, "
        f"{len(ontology.pedagogical_units)} ped, "
        f"{len(ontology.verification_cases)} verif, "
        f"{len(ontology.decisions)} decision"
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the sicm_modernized ontology snapshot from YAML."
        ),
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=_DEFAULT_SOURCE,
        help=f"YAML source path (default: {_DEFAULT_SOURCE}).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUT,
        help=f"JSON snapshot output path (default: {_DEFAULT_OUT}).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Called both directly and via the ``build-sicm-ontology`` console-
    script entry in pyproject.toml. Returns exit code 0 on success.
    """
    argv_list = sys.argv[1:] if argv is None else list(argv)
    args = _parse_args(argv_list)
    ontology, digest, changed = build(args.source, args.out)
    status = "rebuilt" if changed else "unchanged"
    print(f"{status}: {args.out}  sha256={digest[:12]}...")
    print(f"  {_summarize(ontology)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
