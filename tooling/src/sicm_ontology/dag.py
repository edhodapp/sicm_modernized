"""Persistence and content-hash utilities for the sicm_modernized ontology.

DAG-history machinery (parent/child snapshots, Decision records on
edges, advisory-locked transactions) is intentionally NOT implemented
in this initial cut. Iomoments has it; we may port the principle back
when there is real cross-edit traceability demand. For now the
on-disk artifact is the single canonical Ontology snapshot plus its
SHA-256 sidecar.

Re-derived 2026-04-25 per DECISIONS.md D002 from iomoments / fireasm
patterns; trimmed to current-state-only persistence per the same
phasing iomoments used (their Phase 1 was baseline persistence; their
Phase 3 added the history/transaction layer).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from sicm_ontology.models import Ontology


def canonical_hash(ontology: Ontology) -> str:
    """SHA-256 hex digest over a canonicalized Ontology snapshot.

    Canonicalization sorts keys recursively and uses pydantic's
    json-mode dump so two semantically-identical Ontology instances
    hash identically across schema-field-order refactors.

    List order is treated as semantic. The builder controls list
    order deterministically (YAML-source order is preserved); two
    ontologies with the same items in different order hash
    differently, which doubles as a "did someone reshuffle the list"
    signal.
    """
    canonical = json.dumps(
        ontology.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_ontology(path: Path) -> Ontology:
    """Load an Ontology from the JSON snapshot file.

    Validation failures are raised, not swallowed: the snapshot is
    the project's formal-knowledge artifact, and a corrupted file
    must surface loudly. FileNotFoundError is the only silent path
    (returns an empty Ontology so the bootstrap build can run).
    """
    if not path.exists():
        return Ontology()
    text = path.read_text(encoding="utf-8")
    data: Any = json.loads(text)
    return Ontology.model_validate(data)


def save_ontology(ontology: Ontology, path: Path) -> str:
    """Persist an Ontology to JSON via atomic tempfile + rename.

    Writes a sibling ``<path>.sha256`` containing the canonical hash
    of the saved snapshot for integrity checking by consumers.
    Returns the hash hex digest.
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    payload = ontology.model_dump(mode="json")
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    digest = canonical_hash(ontology)

    fd = tempfile.NamedTemporaryFile(
        mode="w",
        dir=str(parent),
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    )
    try:
        fd.write(text)
        fd.close()
        os.replace(fd.name, str(path))
    except BaseException:
        _cleanup_tempfile(fd, fd.name)
        raise

    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_text(digest + "\n", encoding="utf-8")
    return digest


def verify_snapshot(path: Path) -> bool:
    """Verify the on-disk snapshot's hash matches its sidecar.

    Returns True when the snapshot is valid and the hashes match,
    False when there is no sidecar to compare against, raises
    ValueError when the hashes disagree.

    The loud failure on mismatch is intentional — silent acceptance
    of a tampered or stale snapshot would defeat the purpose.
    """
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not sidecar.exists():
        return False
    expected = sidecar.read_text(encoding="utf-8").strip()
    actual = canonical_hash(load_ontology(path))
    if expected != actual:
        raise ValueError(
            f"snapshot hash mismatch at {path}: "
            f"expected {expected[:12]}..., got {actual[:12]}...",
        )
    return True


def _cleanup_tempfile(fd: Any, name: str) -> None:
    """Best-effort close + unlink; swallow everything so the caller's
    original exception is the one that propagates."""
    try:
        fd.close()
    except Exception:  # pylint: disable=broad-except
        pass
    try:
        os.unlink(name)
    except FileNotFoundError:
        pass
