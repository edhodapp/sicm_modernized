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
    return _canonical_hash_from_payload(ontology.model_dump(mode="json"))


def _canonical_hash_from_payload(payload: Any) -> str:
    """SHA-256 over an already-dumped pydantic payload.

    Split out so `save_ontology` can dump once and reuse the same
    payload for both the on-disk pretty JSON and the compact-
    canonical hash form, instead of dumping the model twice. The
    public `canonical_hash(ontology)` entry point preserves the
    one-call API for callers (e.g., `verify_snapshot`) that don't
    already hold a payload.
    """
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_ontology(path: Path) -> Ontology:
    """Load an Ontology from the JSON snapshot file.

    Loud failures by design. The snapshot is the project's
    formal-knowledge artifact, so:

    - A missing file raises `FileNotFoundError` (from
      `path.open`). Earlier versions silently returned an
      empty `Ontology()` here for a hypothetical bootstrap path,
      but no actual call site relied on that — silent empties
      would make a typo'd `path` argument indistinguishable from
      a freshly-initialized project, which is debug-hostile. If
      a caller genuinely needs the bootstrap behavior they should
      construct `Ontology()` explicitly at the call site.
    - JSON parse errors (`json.JSONDecodeError`) and Pydantic
      validation errors (`ValidationError`) propagate.
    """
    with path.open("r", encoding="utf-8") as fh:
        data: Any = json.load(fh)
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
    digest = _canonical_hash_from_payload(payload)
    sidecar = path.with_suffix(path.suffix + ".sha256")

    _atomic_write_text(path, text)
    _atomic_write_text(sidecar, digest + "\n")
    return digest


def _atomic_write_text(path: Path, content: str) -> None:
    """Write `content` to `path` atomically via tempfile + os.replace.

    `flush` + `os.fsync` on the file fd before close + replace so
    the file's data blocks are durable before the rename publishes
    the new path. Without the file fsync, POSIX permits the kernel
    to re-order data and metadata commits — the directory entry
    could update to point at the tempfile's inode while the inode's
    data blocks remain unwritten, leaving a zero-length file at
    `path` after a power-loss recovery. The data fsync forecloses
    that window.

    Scope of the durability claim: this routine guarantees the
    file's CONTENT is durable before the rename runs, and that the
    rename is atomic against torn writes (in-flight POSIX
    semantics). It does NOT fsync the parent directory after the
    rename, so a power loss between `os.replace` returning and the
    directory inode hitting disk can still lose the rename itself
    — recovery would see the old file at `path` (or no entry, if
    this was the first write). For a build-snapshot artifact that
    is regenerated from YAML on demand, this trade-off is
    acceptable; if a future caller needs full crash-durability of
    the publication step, add `os.fsync(os.open(parent,
    O_DIRECTORY))` after the replace, with platform-portability
    handling (Windows does not allow fsync on a directory).

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
        fd.flush()
        os.fsync(fd.fileno())
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

    By design, the hash is computed via `canonical_hash(load_ontology(
    path))` — a full Pydantic validate-then-canonicalize round-trip,
    not a raw byte hash of the on-disk JSON. This is deliberate: the
    round-trip catches semantic drift on a hand-edited snapshot that
    still parses (e.g., status discipline broken, dangling refs)
    *in addition to* byte-level tampering. The cost is microseconds
    at any plausible ontology size; the stronger contract is worth
    it because Day 3 audit tooling treats this snapshot as
    trustable in both senses.
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
    """Best-effort close + unlink for `_atomic_write_text`'s except branch.

    Runs during exception propagation: an earlier write/fsync/
    replace raised, the caller is about to re-raise. We swallow
    secondary failures here so they do not mask the original
    exception — that is the helper's whole reason to exist. The
    swallows cover the realistic OS-layer failure modes from the
    cleanup operations themselves:

    - `fd.close()` may raise `OSError` (broken pipe, ENOSPC, fd
      already gone) or `ValueError` (close on a corrupted file
      object state). `fd.close()` is idempotent on success in
      CPython's `_TemporaryFileWrapper`, so the no-op second close
      in the post-write failure path is harmless.
    - `os.unlink(name)` may raise any `OSError` subclass:
      `FileNotFoundError` for concurrent removal,
      `PermissionError` if the directory mode changed mid-flight,
      EBUSY on some filesystems. All swallow into the same
      best-effort path.

    Pulled out of `_atomic_write_text` so each side stays under the
    project complexity ceiling (max-complexity = 5); inlining would
    re-collapse the split.
    """
    try:
        fd.close()
    except (OSError, ValueError):
        pass
    try:
        os.unlink(name)
    except OSError:
        pass
