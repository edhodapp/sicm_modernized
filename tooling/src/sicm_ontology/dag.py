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
    """Persist an Ontology to JSON plus a SHA-256 sidecar.

    Both files are written via tempfile + ``os.replace``, so each
    individually is atomic against torn writes. POSIX provides no
    cross-file atomicity, so a crash between the two replaces would
    leave a stale sidecar (mismatch surfaces loudly on the next
    ``verify_snapshot`` — recovery is rerunning the build, which
    rewrites both). Returns the hash hex digest.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = ontology.model_dump(mode="json")
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    digest = canonical_hash(ontology)
    sidecar = path.with_suffix(path.suffix + ".sha256")

    _atomic_write_text(path, text)
    _atomic_write_text(sidecar, digest + "\n")
    return digest


def _atomic_write_text(path: Path, content: str) -> None:
    """Write `content` to `path` atomically via tempfile + os.replace.

    On any failure the tempfile is cleaned up and the original
    exception re-raises (cleanup errors are swallowed so they can't
    mask the root cause).
    """
    parent = path.parent
    fd = tempfile.NamedTemporaryFile(
        mode="w",
        dir=str(parent),
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    )
    try:
        fd.write(content)
        fd.close()
        os.replace(fd.name, str(path))
    except BaseException:
        _cleanup_tempfile(fd, fd.name)
        raise


def verify_snapshot(path: Path) -> bool:
    """Verify the on-disk snapshot's hash matches its sidecar.

    Returns True when the snapshot is valid and the hashes match,
    False when there is no sidecar to compare against. Raises
    FileNotFoundError when the snapshot file itself is absent
    (distinguishing "missing snapshot" from "tampered snapshot"),
    and raises ValueError when the file is present but its hash
    disagrees with the sidecar.

    The loud failures on mismatch are intentional — silent acceptance
    of a tampered or missing snapshot would defeat the purpose.
    """
    if not path.exists():
        raise FileNotFoundError(f"snapshot file not found: {path}")
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
