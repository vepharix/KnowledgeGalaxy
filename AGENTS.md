# AGENTS.md

## 当前模型边界

- 开始修改前阅读 README.md、docs/model-paper.md 和 docs/research-log.md。
- 原始领域数据继续使用 ResearchField。数学切片在独立 alignment 层保存 field/concept/result 语义，以显式适配器投影至现有传输类型，不为每种数学对象增加实体类。
- 原始知识关系只有 H、D、R。彻底移除几何亲和及其别名、配置和输出，不重新引入第四种关系变量。
- H 不进入坐标优化，只计算层级闭包、归属、Scope 和布局后的区域；类型类继承不自动生成 H。
- D 只控制依赖深度和目标半径，R 独立控制节点对距离；连接度按 D/R 概念邻居计算，不计声明或辅助 lemma 数量。
- 数学输入保留未知、候选、直接与间接依赖；适配器只输出 curated H/R 与 curated direct D。遇到直接 D 环报告错误，不能静默删除边。
- 映射保存固定源码版本、声明角色、条件和审核状态；源码核对不能写成 Lean 编译或自然语言语义已获形式验证。
- emergence_time 只作为元数据保存，不影响空间位置。
- 不增加 center_bonus、basicness、importance、discipline_position 或手工径向坐标来修饰结果。
- 人工关系值必须附出处和判断理由，并明确为策展假设，不是客观测量或专家共识。
- 调色板、颜色、材质、大小映射只属于各自应用。诊断页面与未来 apps/web 不共享视觉配置。
- 修改后运行全部测试、原领域构建和数学构建，并说明未验证部分。数学源码可用 validate-math --source-root 做离线字节与定位核对；这不运行 Lean。

## 目录

- docs/ 只保留 model-paper.md 和 research-log.md，说明当前实现及其边界。
- 原领域输入放在 data/fields.json 与 data/relations.json；数学映射切片放在 data/mathematics/。
- Python 实现放在 src/knowledge_galaxy/，映射与图计算分别在 alignment/ 与 graph_engine/。
- 测试放在 tests/；work/、outputs/ 与诊断生成数据不提交。
