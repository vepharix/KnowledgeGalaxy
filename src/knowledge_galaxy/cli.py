from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import replace
from pathlib import Path

from .alignment import (
    compare_with_curated_baseline,
    derive_relation_candidates,
    derived_candidates_to_graph_input,
    load_dependency_extraction,
    load_math_dataset,
    load_node_selection,
    create_math_release,
    load_release_manifest,
    to_graph_input,
)
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
    derive_math = subparsers.add_parser("derive-math-relations", help="将 Lean 声明依赖聚合为待审核的 D/R 候选")
    derive_math.add_argument("--dataset", type=Path, default=Path("data/mathematics"))
    derive_math.add_argument("--formal-dependencies", type=Path, required=True, help="固定版本 Lean 提取器生成的声明依赖 JSON")
    derive_math.add_argument("--node-set", type=Path, help="可选：限制候选关系的数学节点实验集")
    derive_math.add_argument("--output", type=Path, default=Path("outputs/math-derived-relations.json"))
    build_derived = subparsers.add_parser("build-math-derived", help="用待审核 Lean D/R 候选构建小型诊断图")
    build_derived.add_argument("--dataset", type=Path, default=Path("data/mathematics"))
    build_derived.add_argument("--candidates", type=Path, required=True)
    build_derived.add_argument("--node-set", type=Path, required=True)
    build_derived.add_argument("--viewer-data", type=Path, default=DEFAULT_VIEWER_DATA)
    build_derived.add_argument("--snapshot", type=Path, default=Path("outputs/math-derived-galaxy.json"))
    build_derived.add_argument("--steps", type=int, default=3500)
    release_math = subparsers.add_parser("release-math", help="生成固定版本的数学星图研究预览、审计和稳定性报告")
    release_math.add_argument("--dataset", type=Path, default=Path("data/mathematics"))
    release_math.add_argument("--manifest", type=Path, default=Path("data/mathematics/release-v0.1.json"))
    release_math.add_argument("--lean-candidates", type=Path, help="可选：附加真实 Lean 引用生成的候选关系报告")
    release_math.add_argument("--source-root", type=Path, help="可选：核对固定版本源码字节和声明定位")
    release_math.add_argument("--viewer-data", type=Path, default=DEFAULT_VIEWER_DATA)
    release_math.add_argument("--snapshot", type=Path, default=Path("outputs/mathematics-galaxy-v0.1.json"))
    release_math.add_argument("--report", type=Path, default=Path("outputs/mathematics-galaxy-v0.1-report.json"))
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
        if args.command == "derive-math-relations":
            dataset = load_math_dataset(args.dataset)
            extraction = load_dependency_extraction(args.formal_dependencies, dataset)
            experiment, selected = load_node_selection(args.node_set, dataset) if args.node_set else (None, None)
            report = derive_relation_candidates(dataset, extraction, selected_node_ids=selected)
            if selected is not None:
                report["experiment"] = experiment
                report["baselineComparison"] = compare_with_curated_baseline(dataset, report, selected)
            _write_json(args.output, report)
            print(
                f"Lean 关系候选已保存：{args.output}；"
                f"D={len(report['relations']['D'])}，R={len(report['relations']['R'])}；尚未进入布局"
            )
            return 0
        if args.command == "build-math-derived":
            if args.steps <= 0:
                raise ValueError("optimization steps must be positive")
            dataset = load_math_dataset(args.dataset)
            experiment, selected = load_node_selection(args.node_set, dataset)
            report = json.loads(args.candidates.read_text(encoding="utf-8"))
            if report.get("experiment") != experiment:
                raise ValueError("candidate report and node-set experiment do not match")
            graph = derived_candidates_to_graph_input(dataset, report, selected)
            snapshot = build_graph(graph, GraphConfiguration(optimization_steps=args.steps))
            result = snapshot_to_dict(snapshot)
            result["formalAlignment"] = alignment_to_dict(dataset)
            result["derivedRelationExperiment"] = report
            write_diagnostic_data(args.viewer_data, result)
            _write_json(args.snapshot, result)
            print(
                f"Lean 数学候选诊断图完成：{len(result['nodes'])} 个节点；"
                f"快照：{args.snapshot}；候选关系尚未审核"
            )
            return 0
        if args.command == "release-math":
            dataset = load_math_dataset(args.dataset)
            manifest = load_release_manifest(args.manifest)
            candidates = json.loads(args.lean_candidates.read_text(encoding="utf-8")) if args.lean_candidates else None
            verified = verify_source_files(dataset, args.source_root) if args.source_root else None
            result, report = create_math_release(
                dataset,
                manifest,
                lean_candidates=candidates,
                source_declarations_verified=verified,
            )
            write_diagnostic_data(args.viewer_data, result)
            _write_json(args.snapshot, result)
            _write_json(args.report, report)
            summary = result["release"]["gateSummary"]
            print(
                f"数学星图研究预览已生成：{len(result['nodes'])} 个节点；"
                f"门槛 pass={summary['pass']}、warning={summary['warning']}、"
                f"pending={summary['pending']}；快照：{args.snapshot}；报告：{args.report}"
            )
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
