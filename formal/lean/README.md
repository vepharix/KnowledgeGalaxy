# Lean 形式关系提取器

这里保存 Knowledge Galaxy 数学星图的 Lean 侧程序。它不把每条 theorem 直接变成可见星体，而是在固定版本的 Lean/mathlib 环境中读取声明的类型与定义或证明体，输出“被引用声明 → 使用声明”的形式引用。Python 侧再通过 `data/mathematics/mappings.json` 把声明级引用聚合成待审核的 D、R 候选。

依赖由 `lean-toolchain` 和 `lake-manifest.json` 固定。当前版本为 Lean `v4.36.0-rc2`、Lean 核心提交 `b35cb10cf2ced51a2fd1880cfdbf75c71ab7a35a`、mathlib 提交 `9bb5e306206014ecee5f033738bb5a6a8490d5c9`。`.lake/`、编译产物以及提取结果均是本地文件，不提交到仓库。

第一阶段加载一小组线性代数声明，第二阶段在本机已有固定版本缓存的范围内加入数系、数论、代数和极限基础。`PhaseOneImports.lean` 与 `PhaseTwoImports.lean` 控制可用环境，`ExtractDependencies.lean` 负责遍历 `Environment`，`Main.lean` 提供命令行入口。首次准备依赖后，可在本目录运行：

```powershell
lake update
lake exe cache get
./run-phase1.ps1
./run-phase2.ps1
```

两个入口都调用 `run-extraction.ps1`。通用脚本读取节点集、`mappings.json` 与 `declarations.json`，自动去重声明锚点，然后只编译本项目的 Lean 文件并复用 mathlib 缓存。若新增节点所需模块没有缓存，不应强行完整原生编译 mathlib；第二阶段曾验证这会牵出数千个模块，因此当前先保持可复现的小步扩展。

提取成功只能说明 Lean 找到了这些声明以及它们的形式引用。它不能自动证明“声明引用等于人类学习前置关系”，也不能消除概念映射中的条件。例如 mathlib 的 `Module` 比“域上的向量空间”更一般，因此仅靠 `Module` 的原始引用无法恢复 `Field → Vector Space`。这类差异需要下一阶段用明确的项目内桥接声明表达条件，再重新比较候选关系。
