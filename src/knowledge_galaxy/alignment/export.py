from __future__ import annotations

from dataclasses import asdict

from .models import MathDataset


def alignment_to_dict(dataset: MathDataset) -> dict:
    """Attach auditable formal evidence at the export boundary, after layout."""
    sources = {s.id: s for s in dataset.sources}
    declarations = []
    for declaration in dataset.declarations:
        source = sources[declaration.source_id]
        declarations.append({
            **asdict(declaration),
            "url": f"{source.repository}/blob/{source.revision}/{declaration.path}#L{declaration.line_start}-L{declaration.line_end}",
        })
    return {
        "schema_version": dataset.schema_version,
        "sources": [asdict(s) for s in dataset.sources],
        "nodes": [asdict(n) for n in dataset.nodes],
        "declarations": declarations,
        "mappings": [asdict(m) for m in dataset.mappings],
        "assertions": [asdict(a) for a in dataset.assertions],
        "formal_verification": "not_run",
    }
