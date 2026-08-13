from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def render_report(result: dict[str, Any], output_path: Path) -> None:
    names = result["entityNames"]
    models = result["modelRuns"]
    role_labels = {
        "math_concept": "数学概念",
        "theorem_structure_method": "定理／结构／方法",
        "theoretical_physics_boundary": "理论物理边界对象",
    }
    role_rows = "".join(
        f"<tr><td>{_e(role_labels.get(role, role))}</td><td>{count}</td>"
        f"<td>{count / result['entityCount']:.1%}</td></tr>"
        for role, count in result["samplingRoles"].items()
    )
    model_sections = "".join(_model_section(name, run, names) for name, run in models.items())
    disagreement_rows = "".join(
        "<tr>"
        f"<td>{_entity(row['left'], names)}</td>"
        f"<td>{_entity(row['right'], names)}</td>"
        f"<td>{row['spread']:.3f}</td>"
        f"<td>{'<br>'.join(f'{_e(model)}: {value:.3f}' for model, value in row['scores'].items())}</td>"
        "</tr>"
        for row in result["largestDisagreements"]
    ) or '<tr><td colspan="4">至少需要两个具有共同实体对的模型。</td></tr>'

    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>新突触 Phase 1 语义模型实验报告</title>
  <style>
    :root {{ color-scheme: light; --ink:#162126; --muted:#647176; --line:#dbe2e1; --paper:#fff; --wash:#f3f6f5; --accent:#176b62; --bad:#a43d35; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; background:var(--wash); color:var(--ink); font:16px/1.65 system-ui,-apple-system,"Noto Sans SC",sans-serif; }}
    main {{ width:min(1100px,calc(100% - 32px)); margin:36px auto 80px; }}
    header,section {{ background:var(--paper); border:1px solid var(--line); border-radius:12px; padding:24px 28px; margin:16px 0; }}
    h1 {{ margin:0 0 6px; font-size:30px; }} h2 {{ margin:0 0 14px; font-size:22px; }} h3 {{ margin:24px 0 10px; font-size:17px; }}
    p {{ max-width:78ch; }} .meta {{ color:var(--muted); }} .metric {{ font-size:28px; color:var(--accent); font-weight:650; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }} th,td {{ padding:9px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }} th {{ background:#f8faf9; }}
    .pass {{ color:var(--accent); }} .fail {{ color:var(--bad); }} code {{ overflow-wrap:anywhere; }}
    details {{ margin-top:12px; }} @media (max-width:700px) {{ header,section {{ padding:18px; overflow-x:auto; }} }}
  </style>
</head>
<body><main>
  <header>
    <h1>新突触 Phase 1：语义相似模型实验</h1>
    <div class="meta">数据集 {_e(result['dataset']['datasetId'])} · {result['entityCount']} 个实体 · 生成于 {_e(result['generatedAt'])}</div>
    <p>本报告比较英文名称与公开定义上的文本模型。它不使用学科元数据或图关系，也不把结果解释为先修、图连接性、知识基础性、径向位置或未来视觉距离。</p>
  </header>
  <section>
    <h2>样本构成与解释边界</h2>
    <table><thead><tr><th>抽样角色</th><th>数量</th><th>比例</th></tr></thead><tbody>{role_rows}</tbody></table>
    <p>{_e(result['interpretationBoundary']['noteZh'])} 当前 19 个对象只是管线薄切片，尚未达到 Phase 1 的 30–100 个实体范围。</p>
  </section>
  {model_sections}
  <section>
    <h2>最大模型分歧</h2>
    <p>这里按同一实体对在各模型中的最高分与最低分之差排序。分歧只用于选择人工复核案例，不表示分差较大的模型一定错误。</p>
    <table><thead><tr><th>对象 A</th><th>对象 B</th><th>分差</th><th>各模型分数</th></tr></thead><tbody>{disagreement_rows}</tbody></table>
  </section>
  <section>
    <h2>可重复性</h2>
    <p>数据 SHA-256：<code>{_e(result['inputDigests']['datasetSha256'])}</code><br>锚点 SHA-256：<code>{_e(result['inputDigests']['anchorsSha256'])}</code></p>
    <details><summary>机器可读运行参数</summary><pre>{_e(json.dumps({name: {k:v for k,v in run.items() if k in ('version','parameters','execution','inputTrack')} for name,run in models.items()}, ensure_ascii=False, indent=2))}</pre></details>
  </section>
</main></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")


def _model_section(name: str, run: dict[str, Any], names: dict[str, Any]) -> str:
    evaluation = run["anchorEvaluation"]
    anchor_rows = "".join(
        "<tr>"
        f"<td>{_entity(case['query'], names)}</td>"
        f"<td>{_entity(case['closer'], names)} ({case['closerScore']:.3f})</td>"
        f"<td>{_entity(case['farther'], names)} ({case['fartherScore']:.3f})</td>"
        f"<td class={'pass' if case['passed'] else 'fail'}>{'通过' if case['passed'] else '未通过'} · {case['margin']:+.3f}</td>"
        f"<td>{_e(case['rationaleZh'])}</td></tr>"
        for case in evaluation["cases"]
    )
    neighbor_rows = "".join(
        f"<tr><td>{_entity(entity_id, names)}</td><td>"
        + "；".join(f"{_entity(item['id'], names)} {item['score']:.3f}" for item in neighbors)
        + "</td></tr>"
        for entity_id, neighbors in run["nearestNeighbors"].items()
    )
    return f"""<section>
      <h2>模型：{_e(name)}</h2>
      <div class="metric">{evaluation['passed']} / {evaluation['total']} 锚点通过</div>
      <p class="meta">运行位置：{_e(run['execution'])}；覆盖 {len(run['coveredEntityIds'])} 个实体；参数：<code>{_e(json.dumps(run['parameters'], ensure_ascii=False, sort_keys=True))}</code></p>
      <h3>锚点预期</h3>
      <table><thead><tr><th>查询</th><th>预期更近</th><th>预期更远</th><th>结果／边际</th><th>人工理由</th></tr></thead><tbody>{anchor_rows}</tbody></table>
      <details><summary>查看每个对象的前三近邻</summary><table><thead><tr><th>对象</th><th>近邻</th></tr></thead><tbody>{neighbor_rows}</tbody></table></details>
    </section>"""


def _entity(entity_id: str, names: dict[str, Any]) -> str:
    item = names.get(entity_id, {"zh": entity_id, "en": entity_id})
    return f"{_e(item['zh'])}<br><span class=\"meta\">{_e(item['en'])}</span>"


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)
