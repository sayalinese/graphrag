# 传统 RAG 检索  接口文档

**Base URL Prefix:** `/api/rag` 或 `/api/api/rag`

## 1. 检索接口

### 1.1 混合搜索 (Hybrid Search)
- **URL**: `/api/rag/search/hybrid`
- **方法**: `POST`
- **描述**: 结合向量搜索与传统文本搜索，提供多路召回排序结果。
- **请求范例 (JSON)**:
  ```json
  {
    "kb_id": 1,
    "query": "什么是腺癌的病理特征？",
    "top_k": 5
  }
  ```
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": [
      { "content": "...", "score": 0.92, "source": "文档A" }
    ]
  }
  ```

### 1.2 pgvector 混合/重排搜索
- **URL**: `/api/rag/search/query_pgvector`
- **方法**: `POST`
- **描述**: 基于 PostgreSQL pgvector 插件的高性能向量检索，支持重排模式。
- **请求范例 (JSON)**:
  ```json
  {
    "kb_id": 1,
    "query": "蛋白质折叠",
    "top_k": 5,
    "mode": "hybrid"
  }
  ```
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": [
      {
        "id": "chunk_123",
        "content": "蛋白质的三级结构...",
        "score": 0.89
      }
    ]
  }
  ```

### 1.3 纯向量搜索
- **URL**: `/api/rag/search/vector`
- **方法**: `POST`
- **描述**: 仅基于向量相似度的搜索，快速返回语义最相关的内容。
- **请求范例 (JSON)**:
  ```json
  {
    "kb_id": 1,
    "query": "上呼吸道感染症状",
    "top_k": 10
  }
  ```
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": [
      {
        "content": "上呼吸道感染常见症状：流鼻涕、打喷嚏...",
        "cosine_score": 0.87,
        "chunk_id": "doc_456_chunk_2"
      }
    ]
  }
  ```

### 1.4 BM25 全文搜索
- **URL**: `/api/rag/search/bm25`
- **方法**: `POST`
- **描述**: 基于传统 BM25 算法的全文关键词搜索，适合精确匹配场景。
- **请求范例 (JSON)**:
  ```json
  {
    "kb_id": 1,
    "query": "放疗 化疗",
    "top_k": 5
  }
  ```
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": [
      {
        "content": "放疗和化疗是癌症的主要治疗手段...",
        "bm25_score": 12.34,
        "matched_terms": ["放疗", "化疗"]
      }
    ]
  }
  ```

---

## 2. 索引与统计

### 2.1 获取检索统计
- **URL**: `/api/rag/search/stats`
- **方法**: `GET`
- **描述**: 查看当前知识库的分块总数、向量索引状态等统计信息。
- **Query 参数**: `kb_id` (可选)
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": {
      "total_chunks": 1500,
      "kb_id": 1,
      "indexed_chunks": 1500,
      "vector_dim": 384
    }
  }
  ```

### 2.2 重建索引
- **URL**: `/api/rag/search/rebuild-index`
- **方法**: `POST`
- **描述**: 触发所有知识库的向量索引重构（需逐个知识库或全量），耗时操作。
- **请求范例 (JSON)**:
  ```json
  {
    "kb_id": 1
  }
  ```

---

## 3. 服务配置与状态

### 3.1 获取 RAG 全局配置
- **URL**: `/api/api/rag/config`
- **方法**: `GET`
- **描述**: 查看当前系统的检索参数（如 top_k, 相似度阈值, 是否开启重排等）。
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": {
       "top_k": 5,
       "threshold": 0.5,
       "enable_rerank": true
    }
  }
  ```

### 3.2 更新 RAG 配置
- **URL**: `/api/api/rag/config`
- **方法**: `POST`
- **请求范例 (JSON)**:
  ```json
  {
    "top_k": 10,
    "threshold": 0.45
  }
  ```

### 3.3 执行直接 RAG 查询 (带 LLM)
- **URL**: `/api/api/rag/query`
- **方法**: `POST`
- **描述**: 针对单一问题，立即返回检索出的知识条目及系统处理建议（非流式）。
- **请求范例 (JSON)**:
  ```json
  {
    "kb_id": 1,
    "query": "肺癌的早期症状有哪些"
  }
  ```
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": {
      "query": "肺癌的早期症状有哪些",
      "answer": "肺癌早期症状包括...",
      "sources": [
        { "content": "...", "score": 0.95 }
      ]
    }
  }
  ```
