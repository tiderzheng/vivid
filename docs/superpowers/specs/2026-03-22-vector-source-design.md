# 向量化预留目录设计

## 背景

当前每个工作目录下只有 `artifacts/`，主要面向人类阅读与排障。后续如果要把已解析内容送入向量数据库，还需要再从 Markdown 或混合产物里反解析一次，成本高且不稳定。

## 目标

在每个工作目录下新增一个与 `artifacts/` 平行的程序消费目录，用于存放后续向量化入库所需的干净源数据。

目录名固定为：

- `vector_source/`

## 目录内容

`vector_source/` 至少包含 3 个文件：

1. `document.json`
2. `chunks.jsonl`
3. `manifest.json`

### `document.json`

整条内容的主文档，保存：

- 来源信息：`source`、`platform`、`title`
- 获取信息：`acquisition_method`
- 摘要结构：`title`、`overview`、`core_points`、`controversies`、`action_suggestions`、`playful_comment`
- 原始文本：完整逐字稿
- 运行元数据：`workdir`、`artifacts_dir`、生成时间、schema 版本

### `chunks.jsonl`

每行一个可直接向量化的 chunk，字段固定：

- `chunk_id`
- `section`
- `text`
- `source_type`
- `order`
- `metadata`

首版只切两类来源：

- 摘要 section chunks
- 逐字稿 chunks

### `manifest.json`

记录：

- `schema_version`
- `generated_at_utc`
- `workdir`
- `files`
- `chunk_count`
- `chunk_sections`

## 设计原则

- `artifacts/` 继续面向人类
- `vector_source/` 明确面向程序和后续 embedding
- 不直接接向量数据库；当前只做“为未来入库准备干净语料”
- skill 文档必须明确：涉及向量化 / embedding / RAG / 知识库入库时，优先读取 `vector_source/`
