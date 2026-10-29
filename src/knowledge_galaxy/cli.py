from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .alignment import load_math_dataset, to_graph_input
from .alignment.adapter import alignment_report
from .alignment.export import alignment_to_dict
from .alignment.validation import verify_source_files
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
    validate_math = subparsers.add_parser("validate-math", help="校验数学概念与 Lean 映射，不运行布局")
    validate_math.add_argument("--dataset", type=Path, default=Path("data/mathematics"))
    validate_math.add_argument("--source-root", type=Path, help="可选：与固定提交一致的 mathlib 本地源码，用于逐字节核对")
    validate_math.add_argument("--report", type=Path, help="可选：保存 JSON 校验报告")
    build_math = subparsers.add_parser("build-math", help="把策展数学关系适配至图引擎和诊断页面")
    build_math.add_argument("--dataset", type=Path, default=Path("data/mathematics"))
    build_math.add_argument("--viewer-data", type=Path, default=DEFAULT_VIEWER_DATA)
    build_math.add_argument("--snapshot", type=Path, default=Path("outputs/math-galaxy.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-math":
            dataset = load_math_dataset(args.dataset)
            report = alignment_report(dataset)
            report["sourceDeclarationsVerified"] = verify_source_files(dataset, args.source_root) if args.source_root else None
            if args.report:
                _write_json(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if args.command == "build-math":
            dataset = load_math_dataset(args.dataset)
            graph = to_graph_input(dataset)
        else:
            graph = load_knowledge_graph(args.fields, args.relations)
        snapshot = build_graph(graph)
        result = snapshot_to_dict(snapshot)
        if args.command == "build-math":
            result["formalAlignment"] = alignment_to_dict(dataset)
        write_diagnostic_data(args.viewer_data, result)
        if args.command == "build-math":
            _write_json(args.snapshot, result)
        print(
            f"Knowledge Galaxy 图构建完成：{len(result['nodes'])} 个节点；"
            f"诊断数据：{args.viewer_data}；请打开 apps/diagnostic-viewer/index.html"
        )
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
