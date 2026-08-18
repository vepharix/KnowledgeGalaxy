from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .domain.io import load_knowledge_graph
from .export import snapshot_to_dict, write_diagnostic_data
from .graph_engine.build import build_graph


DEFAULT_FIELDS = Path("data/fields.json")
DEFAULT_RELATIONS = Path("data/relations.json")
DEFAULT_VIEWER_DATA = Path("apps/diagnostic-viewer/galaxy-data.js")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knowledge-galaxy",
        description="Knowledge Galaxy ResearchField 图构建与三维诊断",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="构建当前知识图和三维诊断输出")
    build.add_argument("--fields", type=Path, default=DEFAULT_FIELDS)
    build.add_argument("--relations", type=Path, default=DEFAULT_RELATIONS)
    build.add_argument("--viewer-data", type=Path, default=DEFAULT_VIEWER_DATA)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        graph = load_knowledge_graph(args.fields, args.relations)
        snapshot = build_graph(graph)
        result = snapshot_to_dict(snapshot)
        write_diagnostic_data(args.viewer_data, result)
        print(
            f"Knowledge Galaxy 图构建完成：{len(result['nodes'])} 个 ResearchField；"
            f"请打开 apps/diagnostic-viewer/index.html"
        )
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2
