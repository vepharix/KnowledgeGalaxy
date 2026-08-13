# Phase 1 研究代码

这里放数据校验、候选模型运行和结果比较代码。本阶段不加入三维渲染或前端框架。所有模型输出应可从 `data/sample/` 和带版本的参数重复生成。

## 运行

当前实现只使用 Python 3.11 标准库。无需安装即可从仓库根目录运行：

```bash
PYTHONPATH=src python3 -m knowledge_galaxy validate
PYTHONPATH=src python3 -m knowledge_galaxy all
```

第二条命令将机器可读结果写入 `work/semantic-run.json`，将中文静态报告写入 `outputs/semantic-report.html`。这两个目录不提交。也可以用 `pip install -e .` 安装 `new-synapse` 命令。

本地默认比较词级 TF-IDF 与字符 3–5 gram TF-IDF。它们是检验实验管线和评价方法的透明基线，不是已经胜出的语义模型。模型只读取英文名称与公开定义，不读取 `sampleRole`、学科归属或来源元数据。

## 可选外部嵌入对照

外部调用必须同时提供完整 endpoint、模型名、密钥环境变量，并显式加入 `--allow-external`：

```bash
EMBEDDING_API_KEY=... PYTHONPATH=src python3 -m knowledge_galaxy external-embed \
  --endpoint https://provider.example/v1/embeddings \
  --model provider-model \
  --allow-external
PYTHONPATH=src python3 -m knowledge_galaxy all \
  --external-embeddings work/external-embeddings.json
```

命令采用常见的 OpenAI-compatible embeddings JSON 形状，但不绑定特定供应商。它只发送 `definitionMayBeSentExternally=true` 且不属于理论物理边界角色的 `publicDefinitionEn`，不发送名称、中文报告、元数据、人工锚点或图结构。密钥不会写入结果文件。不同供应商若不兼容这一请求或响应形状，需要另写适配器；当前未在真实外部服务上验证。
