"""Explicit source preparation, outside the graph engine and normal builds."""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

from .models import MathDataset
from .validation import validate_math_dataset, verify_source_files


def prepare_source_files(dataset: MathDataset, destination: Path) -> dict:
    validate_math_dataset(dataset)
    sources = {s.id: s for s in dataset.sources}
    files = {}
    for declaration in dataset.declarations:
        key = (declaration.source_id, declaration.path)
        if key in files and files[key] != declaration.blob_sha:
            raise ValueError("inconsistent source blobs for path")
        files[key] = declaration.blob_sha

    def prepare(item):
        (source_id, relative), expected = item
        source = sources[source_id]
        base = destination if source.repository.endswith("/mathlib4") else destination / source_id
        target = (base / relative).resolve()
        if not target.is_relative_to(destination.resolve()):
            raise ValueError("source destination escapes root")
        raw = target.read_bytes() if target.exists() else None
        digest = lambda data: hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if raw is not None and digest(raw) == expected:
            return False
        repository = source.repository.removeprefix("https://github.com/")
        with urlopen(f"https://raw.githubusercontent.com/{repository}/{source.revision}/{relative}", timeout=30) as response:
            raw = response.read(8_000_001)
        if len(raw) > 8_000_000 or digest(raw) != expected:
            raise ValueError(f"downloaded source blob mismatch: {source_id}/{relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return True

    # Individual immutable byte transfers are independent; one failure aborts the report.
    with ThreadPoolExecutor(max_workers=6) as pool:
        downloaded = sum(pool.map(prepare, files.items()))
    checked = verify_source_files(dataset, destination)
    return {"files": len(files), "downloadedFiles": downloaded, "declarationsVerified": checked,
            "formalVerification": "not_run"}
