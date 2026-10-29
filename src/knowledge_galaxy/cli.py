from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import replace
from pathlib import Path

from .alignment import load_math_dataset, to_graph_input
from .alignment.adapter import alignment_report
from .alignment.export import alignment_to_dict
from .alignment.audit import audit_math_dataset
from .alignment.assessment import assess_layout_stability, assess_radius_scale_tradeoffs
from .alignment.sources import prepare_source_files
from .alignment.validation import verify_source_files
from .domain.io import load_knowledge_graph
from .export import snapshot_to_dict, write_diagnostic_data
from .graph_engine.build import build_graph
from .graph_engine.models import GraphConfiguration


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
    build_math.add_argument("--steps", type=int, default=3500, help="优化步数；小预算只用于诊断")
    build_math.add_argument("--radius-scale", type=float, default=1.0, help="相对于原径向跨度的比例；默认 1，受控对照可用 0.5")
    audit_math = subparsers.add_parser("audit-math", help="检查证据覆盖、关系分量、依赖冲突与可选布局结果")
    audit_math.add_argument("--dataset", type=Path, default=Path("data/mathematics"))
    audit_math.add_argument("--snapshot", type=Path, help="可选：当前图输入对应的数学布局 JSON")
    audit_math.add_argument("--report", type=Path, default=Path("outputs/math-audit.json"))
    assess_math = subparsers.add_parser("assess-math", help="用固定预算比较不同随机种子的布局敏感性")
    assess_math.add_argument("--dataset", type=Path, default=Path("data/mathematics"))
    assess_math.add_argument("--seeds", type=int, nargs="+", default=[20260816, 42, 7])
    assess_math.add_argument("--steps", type=int, default=600)
    assessment_mode = assess_math.add_mutually_exclusive_group()
    assessment_mode.add_argument("--radius-scales", type=float, nargs="+", help="可选：用一个种子比较径向跨度，替代多种子检查")
    assessment_mode.add_argument("--radius-scale", type=float, default=1.0, help="多种子检查使用的径向跨度比例")
    assess_math.add_argument("--report", type=Path)
    prepare_math = subparsers.add_parser("prepare-math-sources", help="并行准备映射所引用的固定版本源码并核对哈希")
    prepare_math.add_argument("--dataset", type=Path, default=Path("data/mathematics"))
    prepare_math.add_argument("--destination", type=Path, default=Path("work/formal-sources"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-math":
            dataset = load_math_dataset(args.dataset)
            report = alignment_report(dataset)
            report["knowledgeAudit"] = audit_math_dataset(dataset)
            report["sourceDeclarationsVerified"] = verify_source_files(dataset, args.source_root) if args.source_root else None
            if args.report:
                _write_json(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if args.command == "prepare-math-sources":
            report = prepare_source_files(load_math_dataset(args.dataset), args.destination)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if args.command in {"audit-math", "assess-math"}:
            dataset = load_math_dataset(args.dataset)
            if args.command == "audit-math":
                snapshot_payload = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else None
                report = audit_math_dataset(dataset, snapshot_payload)
            else:
                if args.radius_scales:
                    report = assess_radius_scale_tradeoffs(dataset, tuple(args.radius_scales), args.steps, args.seeds[0])
                else:
                    report = assess_layout_stability(dataset, tuple(args.seeds), args.steps, args.radius_scale)
            report_path = args.report or Path("outputs/math-radius-tradeoffs.json" if args.radius_scales else "outputs/math-stability.json")
            _write_json(report_path, report)
            print(f"数学检查报告已保存：{report_path}")
            return 0
        if args.command == "build-math":
            if args.steps <= 0 or not math.isfinite(args.radius_scale) or args.radius_scale <= 0:
                raise ValueError("optimization steps and radius scale must be positive and finite")
            dataset = load_math_dataset(args.dataset)
            graph = to_graph_input(dataset)
        else:
            graph = load_knowledge_graph(args.fields, args.relations)
        if args.command == "build-math":
            config = GraphConfiguration(optimization_steps=args.steps)
            config = replace(config, radius_max=config.radius_min + (config.radius_max - config.radius_min) * args.radius_scale)
            snapshot = build_graph(graph, config)
        else:
            snapshot = build_graph(graph)
        result = snapshot_to_dict(snapshot)
        if args.command == "build-math":
            result["formalAlignment"] = alignment_to_dict(dataset)
            result["knowledgeAudit"] = audit_math_dataset(dataset, result)
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
