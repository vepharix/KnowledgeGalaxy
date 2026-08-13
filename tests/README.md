# 测试

这里放数据契约校验、来源引用完整性检查和模型运行的可重复性测试。本阶段没有界面交互测试；验收要求以 `docs/prototype-scope.md` 为准。

从仓库根目录运行：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

测试覆盖样本配额与引用完整性、两种本地模型、锚点评价、最大分歧、外部嵌入子集导入、外发显式授权门槛和 HTML 生成。真实外部服务调用不进入自动化测试。
