# 知识银河 / Knowledge Galaxy

Knowledge Galaxy 研究领域关系如何生成可检查的三维知识空间。所有可见节点都是 `ResearchField`，原始知识输入只有层级 H、方向性依赖 D 和对称相关性 R。Scope、依赖深度、连接度与坐标均由输入推导；坐标只是视觉布局结果，不能反推出知识关系。

当前版本已经把领域计算与演示逻辑分开。图引擎只负责验证输入、计算 H 的层级闭包、用 D 计算依赖深度、用 R 约束局部距离、计算 D/R 连接度并优化三维坐标。Diagnostic Viewer 位于 `apps/diagnostic-viewer/`，运行图构建后直接打开其中的 `index.html`；它不是最终星图。

## 文档

- [模型构建论文](docs/model-paper.md)：实体、关系、派生量、三维损失和渲染边界。
- [研究碎记](docs/research-log.md)：模型变更、历史运行观察、疑问与暂缓事项。

## 运行

项目要求 Python 3.11+，当前图计算只使用 Python 标准库。在 PowerShell 中运行：

```powershell
cd D:\Gabriel\Documents\KnowledgeGalaxy
$env:PYTHONPATH = "$PWD\src"
python -m knowledge_galaxy build
```

如果当前终端不能直接识别 Python：

```powershell
$env:PYTHONPATH = "$PWD\src"
& "C:\Users\Gabriel\AppData\Local\Programs\Python\Python312\python.exe" -m knowledge_galaxy build
```

每次构建更新演示所读取的数据：

```text
apps/diagnostic-viewer/galaxy-data.js   节点、坐标、H、D、R 与派生指标
```

打开 `apps/diagnostic-viewer/index.html` 后，可以拖动旋转，使用 Shift 或鼠标右键拖动平移，滚轮缩放。页面允许分别显示 D 方向边、R 无向边和 H 色彩家族，并在选择节点后显示真实 x/y/z 坐标、依赖深度、目标与实际半径以及连接度。

## 测试

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```

测试覆盖关系方向、H 环校验、最大乘积层级传递、Scope、依赖深度、R 距离、D/R 职责隔离、连接度去重、H 与坐标隔离、出现时间隔离、固定种子复现、坐标有限性和诊断查看器的数据边界。

## 目录

```text
data/
  fields.json                    当前 ResearchField 输入
  relations.json                 当前 H、D、R 与 provenance
docs/
  model-paper.md                 模型构建论文
  research-log.md                研究碎记与运行记录
src/knowledge_galaxy/
  domain/                        输入类型、JSON 边界与校验
  graph_engine/                  H、D、R、连接度、布局、区域与诊断计算
  export.py                      稳定输出契约与诊断页面生成
  cli.py                         Knowledge Galaxy 命令行入口
apps/
  diagnostic-viewer/             可直接打开的三维诊断演示及其当前数据
  web/                           最终 Galaxy Explorer 的保留边界
tests/                            数学不变量与端到端测试
```

当前 `data/` 中的 55 个领域以及 H、D、R 数值是附有 provenance 的人工策展输入，用于检查模型行为，不是客观测量或专家共识。未列出的 R 只表示当前没有提供相关性值，不能解释为两个领域已经被证明无关。
