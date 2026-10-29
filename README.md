# 知识银河 / Knowledge Galaxy

Knowledge Galaxy 1.0 研究知识关系如何生成可检查的三维空间。原领域数据的节点都是 `ResearchField`；独立数学切片进一步保存领域、概念与重要结果的语义标签，并通过适配器接入同一图引擎。原始知识输入只有层级 H、方向性依赖 D 和对称相关性 R。Scope、依赖深度、连接度与坐标均由输入推导；坐标只是视觉布局结果，不能反推出知识关系。

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

打开 `apps/diagnostic-viewer/index.html` 后，可以拖动旋转，使用 Shift 或鼠标右键拖动平移，滚轮缩放。页面允许分别显示 D 方向边、R 无向边和 H 色彩家族，可以切换中英文领域名称，并在选择节点后显示真实 x/y/z 坐标、依赖深度、目标与实际半径以及连接度。名称语言只属于显示层，不参与图计算。

## 测试

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
node --test tests/test_diagnostic_evidence.cjs tests/test_node_search.cjs
```

测试覆盖关系方向、H 环校验、最大乘积层级传递、Scope、依赖深度、R 距离、D/R 职责隔离、连接度去重、H 与坐标隔离、出现时间及本地化名称隔离、固定种子复现、坐标有限性和诊断查看器的数据边界。

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

当前 `data/` 中包含 150 个领域、205 条 H、314 条 D 和 492 条 R。第二次扩展补入 Graph Theory、Measure Theory、Distributed Systems、Particle Physics、Organic Chemistry、Genomics、Oncology、Archaeology、Finance 等数学、计算机系统、自然科学、生命医学、工程与人文学科。每个领域保存英文名称及中文显示名。所有关系数值均为附有 provenance 的人工策展输入，用于检查模型行为，不是客观测量或专家共识。未列出的 R 只表示当前没有提供相关性值，不能解释为两个领域已经被证明无关。

## 数学概念与 Lean 映射

数学切片独立放在 `data/mathematics/`，不会改写或混入原来的 150 个领域。当前有 80 个节点（9 个领域、66 个概念、5 个结果），71 个固定版本声明与 80 条带条件、角色和审核状态的映射。范围包括集合与数系、初等数论、代数、线性代数、分析、拓扑、测度与概率，以及秩—零度、中值定理、微积分基本定理和柯西—施瓦茨不等式等结果。

已核对的 mathlib 版本是 [`9bb5e306206014ecee5f033738bb5a6a8490d5c9`](https://github.com/leanprover-community/mathlib4/tree/9bb5e306206014ecee5f033738bb5a6a8490d5c9)。`manifest.json` 保存版本和工具链，`declarations.json` 保存声明、源码路径、Git blob SHA 与准确行号，`nodes.json` 保存我们自己的定义范围，`mappings.json` 保存多对多映射，`assertions.json` 保存 H/D/R 判断。映射审核状态不代替 D 的可信强度，也不等于 Lean 形式验证。

自然数、整数和有理数的定义等来自 Lean 核心，因此另行固定 [`lean4@b35cb10cf2ced51a2fd1880cfdbf75c71ab7a35a`](https://github.com/leanprover/lean4/tree/b35cb10cf2ced51a2fd1880cfdbf75c71ab7a35a)，对应 mathlib 所需的 `v4.36.0-rc2`。来源不会被强行改写为 Mathlib。由 `to_additive` 生成的 `Summable` 保存生成来源，并明确还未经过本项目的 Lean 编译核验。

在已经设置好 `PYTHONPATH` 的 PowerShell 中运行：

```powershell
python -m knowledge_galaxy validate-math
python -m knowledge_galaxy build-math
python -m knowledge_galaxy audit-math --snapshot outputs/math-galaxy.json
python -m knowledge_galaxy assess-math --steps 600
python -m knowledge_galaxy assess-math --radius-scales 0.25 0.5 1 --steps 600
```

Linux/macOS 可在命令前加 `PYTHONPATH=src`。数学构建会更新同一诊断页面的数据，并额外保存中立快照 `outputs/math-galaxy.json`；重新运行 `build` 可切回原领域数据。诊断页面支持中文、英文和稳定 ID 搜索，回车或选择结果后定位节点并暂停自动旋转；选择节点后可展开正式声明、适用条件、源码链接及相关的策展/候选/间接关系。图引擎不读取映射数量或源码路径，形式证据在布局完成后才附加到导出结果。

`audit-math` 报告映射覆盖、R 未评估对、关系连通分量、缺少 D 的节点、直接依赖的旁路与深度残差，也在三个正则强度下做诊断扫描。提供布局快照时会检查输入是否匹配，并报告没有正 R 证据的近邻；它不自动补边或修改参数。`assess-math` 默认对三个种子各运行 600 步，比较旋转/镜像不变的距离及五近邻集合，列出最不稳定的节点。报告包含图输入摘要，避免将旧输入的结果误用于当前图。600 步结果是固定预算探索，不是收敛证明。

审计还检查必要的几何条件：节点对的目标距离不能小于两目标半径之差，否则两个目标无法同时精确满足。当前原尺度有 68 对这样的目标冲突。`--radius-scales` 单独比较径向跨度，报告关系距离误差、径向误差和拥挤程度，保存到 `outputs/math-radius-tradeoffs.json`。减半尺度改善了距离拟合，但三种子试跑中的局部近邻更不稳定，因此原尺度继续作为默认对照。候选可通过 `build-math --radius-scale 0.5` 重现，并用 `assess-math --radius-scale 0.5 --report outputs/math-half-stability.json` 检查。所有实际配置都保存在输出中。

可以先准备所需的 58 个固定版本源码文件，再做离线核对；该准备只下载声明引用到的文件，并行进行字节传输，不能代替完整的 Lean/mathlib 编译环境：

```powershell
python -m knowledge_galaxy prepare-math-sources --destination work/formal-sources
python -m knowledge_galaxy validate-math --source-root work/formal-sources --report outputs/math-alignment-report.json
```

mathlib 文件位于源码根目录的 `Mathlib/`，Lean 核心文件位于其 `lean-core/src/` 子目录。核对检查完整源文件的 Git blob SHA 和声明摘录，不安装或运行 Lean。当前 80 条映射经过辅助策展和源码核对，尚未通过独立数学专家复核，也未将记录的表达式编译成 Lean 定理。函数、二元关系和概率空间明确保留组合表达或上下文锚点，不伪造与之严格等价的单个声明。

数学关系中，84 条 H、78 条直接 D 和 209 条 R 进入图构建；另有 8 条间接、候选或未知断言保留在证据层。所有数值都是显式策展假设；候选、未知和间接依赖不成为布局约束。当前 R 覆盖全部 3160 个节点对中的约 6.6%，其余不表示无关。直接 D 出现循环时会报错；即便无环，也可能存在目标层差冲突，审计保留并报告这些冲突。扩展规则、困难与先后安排见[模型论文](docs/model-paper.md)第五节。
