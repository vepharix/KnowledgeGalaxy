from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .data import DataValidationError, load_json, validate_dataset
from .experiment import write_json


def request_external_embeddings(
    dataset_path: Path,
    output_path: Path,
    endpoint: str,
    model: str,
    api_key_env: str,
    allow_external: bool,
) -> dict[str, Any]:
    if not allow_external:
        raise ValueError("external sending requires the explicit --allow-external flag")
    dataset = load_json(dataset_path)
    errors = validate_dataset(dataset)
    if errors:
        raise DataValidationError("\n".join(f"- {error}" for error in errors))
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise ValueError(f"environment variable {api_key_env!r} is not set")

    eligible = [
        entity
        for entity in dataset["entities"]
        if entity["definitionMayBeSentExternally"]
        and entity["sampleRole"] != "theoretical_physics_boundary"
    ]
    if not eligible:
        raise ValueError("dataset has no externally eligible mathematical definitions")
    inputs = [entity["publicDefinitionEn"] for entity in eligible]
    body = json.dumps({"model": model, "input": inputs, "encoding_format": "float"}).encode()
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        response_payload = json.load(response)
    ordered = sorted(response_payload.get("data", []), key=lambda item: item["index"])
    embeddings = [item["embedding"] for item in ordered]
    if len(embeddings) != len(eligible):
        raise ValueError("external API returned a different number of embeddings")

    result = {
        "schemaVersion": "0.1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "providerVersion": response_payload.get("model", "unspecified"),
        "entityIds": [entity["id"] for entity in eligible],
        "embeddings": embeddings,
        "sendingPolicy": {
            "fieldsSent": ["publicDefinitionEn"],
            "excludedSampleRole": "theoretical_physics_boundary",
            "explicitlyAllowed": True,
            "endpoint": endpoint,
        },
    }
    write_json(output_path, result)
    return result
