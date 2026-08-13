from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .data import DataValidationError, validate_files
from .experiment import run_experiment, write_json
from .external import request_external_embeddings
from .report import render_report


DEFAULT_DATASET = Path("data/sample/entities.json")
DEFAULT_ANCHORS = Path("data/sample/anchors.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="new-synapse",
        description="新突触 Phase 1 知识模型研究命令行工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="校验研究数据和锚点")
    _add_inputs(validate)

    run = subparsers.add_parser("run", help="运行本地语义模型实验")
    _add_inputs(run)
    run.add_argument("--external-embeddings", type=Path)
    run.add_argument("--output", type=Path, default=Path("work/semantic-run.json"))

    report = subparsers.add_parser("report", help="从机器可读结果生成静态 HTML")
    report.add_argument("--input", type=Path, default=Path("work/semantic-run.json"))
    report.add_argument("--output", type=Path, default=Path("outputs/semantic-report.html"))

    all_command = subparsers.add_parser("all", help="依次校验、运行并生成报告")
    _add_inputs(all_command)
    all_command.add_argument("--external-embeddings", type=Path)
    all_command.add_argument("--run-output", type=Path, default=Path("work/semantic-run.json"))
    all_command.add_argument("--report-output", type=Path, default=Path("outputs/semantic-report.html"))

    external = subparsers.add_parser("external-embed", help="显式发送可外发的数学定义到兼容嵌入 API")
    external.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    external.add_argument("--endpoint", required=True, help="完整的嵌入 API endpoint URL")
    external.add_argument("--model", required=True)
    external.add_argument("--api-key-env", default="EMBEDDING_API_KEY")
    external.add_argument("--allow-external", action="store_true", help="确认只发送标记可外发的数学定义")
    external.add_argument("--output", type=Path, default=Path("work/external-embeddings.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            dataset, anchors = validate_files(args.dataset, args.anchors)
            print(f"校验通过：{len(dataset['entities'])} 个实体，{len(anchors['triplets'])} 个锚点。")
        elif args.command == "run":
            result = run_experiment(args.dataset, args.anchors, args.external_embeddings)
            write_json(args.output, result)
            print(f"实验完成：{len(result['modelRuns'])} 个模型；结果写入 {args.output}")
        elif args.command == "report":
            result = json.loads(args.input.read_text(encoding="utf-8"))
            render_report(result, args.output)
            print(f"报告写入 {args.output}")
        elif args.command == "all":
            result = run_experiment(args.dataset, args.anchors, args.external_embeddings)
            write_json(args.run_output, result)
            render_report(result, args.report_output)
            print(f"完成：结果 {args.run_output}；报告 {args.report_output}")
        elif args.command == "external-embed":
            result = request_external_embeddings(
                args.dataset,
                args.output,
                args.endpoint,
                args.model,
                args.api_key_env,
                args.allow_external,
            )
            print(f"外部对照完成：{len(result['entityIds'])} 个数学定义；结果写入 {args.output}")
        return 0
    except (DataValidationError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2


def _add_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
