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
import sys
from pathlib import Path
from typing import Any

import yaml

from sicm_ontology.dag import canonical_hash, save_ontology
from sicm_ontology.models import Ontology

# tooling/src/sicm_ontology/build.py
# parents[0]=sicm_ontology, [1]=src, [2]=tooling, [3]=<repo-root>.
#
# Default paths assume editable install (`pip install -e ".[dev]"`),
# which is the only supported install mode for this project (we
# never publish to PyPI). Editable install keeps __file__ pointing
# to the in-tree source location, so parents[3] correctly resolves
# to the repo root. For non-editable installs (a hypothetical
# package consumer) use --source and --out to specify paths
# explicitly; the defaults will not be meaningful.
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
    """True iff the on-disk sidecar's recorded hash matches new_digest.

    Compares against the .sha256 sidecar text directly rather than
    re-hashing the snapshot. This makes the check self-healing on
    partial-failure states: if save_ontology updated the JSON but
    failed before updating the sidecar (or vice versa), the recorded
    hash diverges from new_digest and we trigger a full rewrite.

    Returns False whenever either file is missing or unreadable, so
    the caller rewrites in any ambiguous state rather than skipping
    silently.
    """
    sidecar = out_path.with_suffix(out_path.suffix + ".sha256")
    if not (out_path.exists() and sidecar.exists()):
        return False
    try:
        recorded = sidecar.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return recorded == new_digest


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
