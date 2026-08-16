from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .spatial_experiment import render_spatial_svg, run_spatial_experiment


DEFAULT_FIXTURE = Path("data/first_experiment/fixture.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="new-synapse",
        description="新突触 ResearchField 三维空间实验",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    spatial = subparsers.add_parser("run", help="运行当前模型的第一次三维空间实验")
    spatial.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    spatial.add_argument("--output", type=Path, default=Path("work/first-experiment.json"))
    spatial.add_argument("--svg", type=Path, default=Path("outputs/first-experiment.svg"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_spatial_experiment(args.fixture)
        _write_json(args.output, result)
        render_spatial_svg(result, args.svg)
        print(
            f"空间实验完成：{len(result['nodes'])} 个 ResearchField；"
            f"结果 {args.output}；三维诊断图 {args.svg}"
        )
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
