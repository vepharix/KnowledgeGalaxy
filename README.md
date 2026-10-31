# 知识银河 / Knowledge Galaxy

Knowledge Galaxy 当前聚焦于一件更窄、也更可检验的工作：以 Lean/mathlib 的形式对象为证据来源，逐步建立数学知识星图。可见节点仍然是人能够理解的数学领域、概念与重要结果；Lean 声明不是直接显示的星体，而是节点及关系背后的形式锚点。原始知识关系仍只有层级 H、方向性依赖 D 和对称相关性 R。Scope、依赖深度、连接度与坐标均由输入推导；坐标只是视觉布局结果，不能反推出知识关系。

当前工作按三个阶段推进：先用少量节点检验“声明引用—概念映射—D/R 候选”是否成立，再扩大到能够显现局部结构的中型样本，最后才进入完整数学网络。图引擎只负责关系与坐标，Diagnostic Viewer 继续检查数据和几何行为；`apps/web/` 已开始建立独立的 WebGL 星图原型，颜色、光晕、背景和标签裁剪都留在应用层。

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
node --test tests/test_diagnostic_evidence.cjs tests/test_node_search.cjs tests/test_web_render_policy.cjs
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
  web/                           WebGL 星图与大规模渲染原型
tests/                            数学不变量与端到端测试
formal/lean/                      固定版本 Lean/mathlib 声明依赖提取器
```

仓库仍保留一套 150 个领域的跨学科人工数据，用于回归测试图引擎和查看器，但它不再是当前数据扩展方向。这套数据中的 H、D、R 都是附有 provenance 的策展输入，不是客观测量或专家共识。当前新增工作只进入 `data/mathematics/` 与 `formal/lean/`，先解决数学概念怎样从形式数据获得可追踪关系的问题。

## 数学概念与 Lean 映射

数学切片独立放在 `data/mathematics/`，不会改写或混入原来的 150 个领域。已有的 80 节点数据保留为概念目录与人工基线。第一阶段使用 13 个线性代数节点检验数据链；第二阶段已扩展到 30 个节点，范围包括数系、初等数论、群环域、线性代数以及 Filter/Tendsto 表达的极限基础。第二阶段只选择本机已有固定版本编译缓存的声明，使实验能够完整复现；微分、拓扑和测度模块等待相应缓存环境准备后再加入。

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

### G2：数学星图 v0.1 研究预览

G2 把现有 80 节点数学基线固定为一份可重复生成、可审计但不夸大其成熟度的研究预览。`data/mathematics/release-v0.1.json` 固定数据规模、Lean/mathlib 源码版本、布局种子、优化预算和多种子评估预算；发布命令同时生成星图快照、审计报告、稳定性报告摘要和诊断页面数据：

```powershell
python -m knowledge_galaxy prepare-math-sources --destination work/formal-sources

python -m knowledge_galaxy release-math `
  --source-root work/formal-sources `
  --lean-candidates outputs/phase2-derived-relations.json
```

结果写入 `outputs/mathematics-galaxy-v0.1.json` 和 `outputs/mathematics-galaxy-v0.1-report.json`，同时让两个查看器读取同一份 80 节点快照。输出目录仍属于本地生成物，不提交到仓库；任何人都应从固定清单重新生成它。发布报告目前通过数据契约、非领域节点映射覆盖、R 图连通、有限坐标以及 71 个声明的源码字节与定位核对。30 节点 Lean 实验被附加为部分候选证据，但不会替换 84 条 H、78 条直接 D 和 209 条 R 的策展基线。

这里需要明确当前自动化边界：80 个节点和主要概念—Lean 锚点仍来自版本化 JSON，程序负责校验和重复生成；Lean 程序已经能从真实声明引用批量生成 D/R 候选，但尚不能从整个 mathlib 自动发现适合人类阅读的概念节点。报告因此固定标记为 `research_preview`，并把 68 对径向—距离目标冲突、个别节点的跨种子近邻不稳定、独立数学专家复核和真实浏览器视觉验收分别列为 warning 或 pending。G2 完成的是可追踪的研究基线，不是自动生成的最终数学知识图。

Linux/macOS 可在命令前加 `PYTHONPATH=src`。数学构建会更新同一诊断页面的数据，并额外保存中立快照 `outputs/math-galaxy.json`；重新运行 `build` 可切回原领域数据。诊断页面支持中文、英文和稳定 ID 搜索，回车或选择结果后定位节点并暂停自动旋转；选择节点后可展开正式声明、适用条件、源码链接及相关的策展/候选/间接关系。图引擎不读取映射数量或源码路径，形式证据在布局完成后才附加到导出结果。

`audit-math` 报告映射覆盖、R 未评估对、关系连通分量、缺少 D 的节点、直接依赖的旁路与深度残差，也在三个正则强度下做诊断扫描。提供布局快照时会检查输入是否匹配，并报告没有正 R 证据的近邻；它不自动补边或修改参数。`assess-math` 默认对三个种子各运行 600 步，比较旋转/镜像不变的距离及五近邻集合，列出最不稳定的节点。报告包含图输入摘要，避免将旧输入的结果误用于当前图。600 步结果是固定预算探索，不是收敛证明。

### 从 Lean 声明依赖生成关系候选

数学关系的下一条数据路径已经建立到“声明依赖导入与概念聚合”这一层。输入文件必须来自与 `manifest.json` 完全一致的 Lean 工具链和源码提交，并记录声明类型或定义/证明体中的常量引用。引用方向统一为“被引用声明 → 使用它的声明”。程序通过现有概念—声明映射，把声明级引用聚合为方向性 D 候选，并根据直接形式连接、共享前置、共享后继和共享声明锚点生成对称 R 候选：

```powershell
python -m knowledge_galaxy derive-math-relations `
  --formal-dependencies work/lean-dependencies.json `
  --output outputs/math-derived-relations.json
```

输入中的单条边采用下面的最小形式；文件顶层还必须保存 `schema_version`、`extractor`、`toolchain`、`source_revisions` 和 `extraction_scope`：

```json
{
  "source": "Module",
  "target": "LinearMap",
  "reference_kind": "type_reference",
  "occurrences": 1
}
```

该命令会核对工具链与 mathlib/Lean 固定提交，拒绝混用不同版本。输出中的关系全部标为 `candidate`，不会写回 `assertions.json`。H 不从声明引用推导；类型引用、定义体引用等只作为 H/D/R 之下的证据种类，不是新增的知识关系。当前人工 assertions 暂时保留为比较基线，而不是被宣称为自动结果。

第一阶段的真实提取器位于 `formal/lean/`。它已经在固定的 Lean `v4.36.0-rc2` 和 mathlib 提交上编译、运行，从 12 个声明锚点取得 116 条声明引用；经 13 节点筛选后生成 22 条 D 候选和 28 条 R 候选。D 与现有人工基线重合 8 条，覆盖人工基线 14 条中的约 57%；R 重合 12 条，覆盖 23 条中的约 52%。这些数字只描述两套关系的一致程度，人工基线尚未成为专家 gold set，因而不能把它们直接解释为科学意义上的准确率。

第二阶段由 `run-extraction.ps1` 根据节点集、映射和声明表自动收集锚点，不再在脚本中逐个维护声明名。30 个节点对应 28 个去重声明锚点，真实提取取得 160 条声明引用，生成 31 条 D 与 39 条 R 候选。D 与当前人工基线重合 11/32，R 重合 16/44；重合率没有随节点数自然提高，说明声明引用、概念语境和教学依赖之间仍需桥接与审核。

要复现候选聚合和小型三维诊断图，可运行：

```powershell
./formal/lean/run-phase2.ps1

python -m knowledge_galaxy derive-math-relations `
  --formal-dependencies work/phase2-lean-dependencies.json `
  --node-set data/mathematics/phase2-nodes.json `
  --output outputs/phase2-derived-relations.json

python -m knowledge_galaxy build-math-derived `
  --candidates outputs/phase2-derived-relations.json `
  --node-set data/mathematics/phase2-nodes.json `
  --snapshot outputs/phase2-galaxy.json
```

当前第二阶段图有 30 个节点，H 被有意留空；D、R 全部标记为未审核候选。一次 3500 步固定种子运行中，坐标均为有限值，依赖深度与实际半径的 Pearson 相关系数约为 0.9996，最小节点距离约为 1.48，平均目标半径误差约为 0.028。它说明布局程序能够处理这批候选，并不说明候选在数学语义上已经正确。`Module` 同时锚定一般模与向量空间、原始声明缺少教学语境等问题仍然存在，下一轮仍需加入明确条件的项目内 Lean 桥接声明。

构建完成后，可以分别打开 `apps/diagnostic-viewer/index.html` 检查关系和数值，或打开 `apps/web/index.html` 查看星体光晕、深度颜色、关系线裁剪和分级标签。WebGL 页面使用 point sprites 将全部节点放在一个 GPU draw call 中；在地址后附加 `?benchmark=20000` 会显示明确标注的两万合成点渲染测试。这只能检查已有坐标的浏览器显示能力。当前 Python 优化器仍对全部节点对计算排斥，时间与内存复杂度为二次量级，因此尚不能生成数万真实节点布局；后续需要稀疏 R 邻接、空间树近似排斥、分块布局与增量坐标更新。

Lean 侧的依赖准备、编译与提取方法见 [`formal/lean/README.md`](formal/lean/README.md)。本机工具链、mathlib 工作副本、缓存、提取结果和三维输出都位于被忽略的 `work/`、`formal/lean/.lake/` 与 `outputs/`，不会随提交上传。

审计还检查必要的几何条件：节点对的目标距离不能小于两目标半径之差，否则两个目标无法同时精确满足。当前原尺度有 68 对这样的目标冲突。`--radius-scales` 单独比较径向跨度，报告关系距离误差、径向误差和拥挤程度，保存到 `outputs/math-radius-tradeoffs.json`。减半尺度改善了距离拟合，但三种子试跑中的局部近邻更不稳定，因此原尺度继续作为默认对照。候选可通过 `build-math --radius-scale 0.5` 重现，并用 `assess-math --radius-scale 0.5 --report outputs/math-half-stability.json` 检查。所有实际配置都保存在输出中。

可以先准备所需的 58 个固定版本源码文件，再做离线核对；该准备只下载声明引用到的文件，并行进行字节传输，不能代替完整的 Lean/mathlib 编译环境：

```powershell
python -m knowledge_galaxy prepare-math-sources --destination work/formal-sources
python -m knowledge_galaxy validate-math --source-root work/formal-sources --report outputs/math-alignment-report.json
```

mathlib 文件位于源码根目录的 `Mathlib/`，Lean 核心文件位于其 `lean-core/src/` 子目录。核对检查完整源文件的 Git blob SHA 和声明摘录，不安装或运行 Lean。当前 80 条映射经过辅助策展和源码核对，尚未通过独立数学专家复核，也未将记录的表达式编译成 Lean 定理。函数、二元关系和概率空间明确保留组合表达或上下文锚点，不伪造与之严格等价的单个声明。

数学关系中，84 条 H、78 条直接 D 和 209 条 R 进入当前基线图构建；另有 8 条间接、候选或未知断言保留在证据层。这些数值仍是显式策展假设，不能与新管线生成的候选混称为形式结论；候选、未知和间接依赖不成为布局约束。当前 R 覆盖全部 3160 个节点对中的约 6.6%，其余不表示无关。直接 D 出现循环时会报错；即便无环，也可能存在目标层差冲突，审计保留并报告这些冲突。关系来源、扩展规则、困难与先后安排见[模型论文](docs/model-paper.md)第四、五节。
