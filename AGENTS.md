# AGENTS.md

## 当前模型边界

- 开始修改前阅读 README.md、docs/model-paper.md 和 docs/first-experiment-analysis.md。
- 每个节点都是 ResearchField；不要为学科、子学科、主题或研究方向增加不同实体类。
- 原始关系只保留层级 H、方向性依赖 D 和对称相关性 R；几何亲和 G、Scope、依赖深度与坐标均为派生量。
- H、D、R、G 必须分别保存，不得从坐标或层级密度区域反推 H。
- H 不进入当前坐标优化，只用于传递成员关系、Scope 和布局后的层级密度。
- emergence_time 只作为元数据保存，不影响空间位置。
- 不增加 center_bonus、basicness、importance、discipline_position 或手工径向坐标来修饰结果。
- fixture 中的人工值必须有 provenance，并明确为实验假设而非客观测量。
- 自动相关性数据、体积云和交互式前端仍是未实现边界，不得在文档中写成既有功能。
- 修改后运行全部测试和当前实验，并说明未验证的部分。

## 目录

- 模型构建论文放在 docs/model-paper.md。
- 第一次结果分析放在 docs/first-experiment-analysis.md。
- fixture 放在 data/first_experiment/。
- Python 实现放在 src/knowledge_galaxy/。
- 测试放在 tests/。
- 本地机器结果放在 work/，诊断图放在 outputs/；二者都不提交。
