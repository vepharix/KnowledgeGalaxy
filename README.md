# 新突触 / New Synapse

新突触是一个研究“领域关系如何生成三维知识空间”的实验项目。当前模型把所有节点统一表示为 ResearchField，以层级 H、方向性知识依赖 D 和对称相关性 R 作为原始关系，再由这些关系推导依赖深度、几何亲和、三维坐标和层级密度区域。坐标是可重复计算的布局结果，不是知识事实；几何重叠也不会生成层级关系。

## 文档

- [模型构建论文](docs/model-paper.md)：模型的实体、关系、数学定义、三维布局与渲染边界。
- [第一次实验分析](docs/first-experiment-analysis.md)：24 个领域的运行结果、成功表现、冲突和下一步检验。

## 运行

项目要求 Python 3.11+，当前实现只使用 Python 标准库。在 PowerShell 中运行：

    cd D:\Gabriel\Documents\KnowledgeGalaxy
    $env:PYTHONPATH = "$PWD\src"
    python -m knowledge_galaxy run

如果当前终端还不能直接识别 Python：

    $env:PYTHONPATH = "$PWD\src"
    & "C:\Users\Gabriel\AppData\Local\Programs\Python\Python312\python.exe" -m knowledge_galaxy run

运行后会生成：

    work/first-experiment.json       H、D、R、G、Scope、依赖深度、三维坐标和诊断指标
    outputs/first-experiment.svg     三维坐标的静态二维诊断投影

work 和 outputs 是本地实验产物，不提交 Git。

## 测试

    $env:PYTHONPATH = "$PWD\src"
    python -m unittest discover -s tests -v

测试覆盖关系方向、R 对称性、层级传递、Scope、依赖深度、目标距离、层级与坐标隔离、出现时间隔离、固定种子复现以及坐标有限性。

## 目录

    data/first_experiment/             第一次实验的人工 fixture 与来源说明
    docs/model-paper.md                模型构建论文
    docs/first-experiment-analysis.md  第一次实验分析
    src/knowledge_galaxy/              数据结构、数学计算、优化与输出代码
    tests/                             数学不变量与端到端测试
    work/                              本地机器可读结果，不提交
    outputs/                           本地诊断图，不提交

fixture 中的 H、D、R 数值是为了观察几何行为而人工策展的实验假设，不是客观科学测量或专家共识。
