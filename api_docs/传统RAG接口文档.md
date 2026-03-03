# 老知识库与文档管理接口文档

**Base URL Prefix:** `/api/api` (由底层蓝图确定)

## 1. 知识库管理

### 1.1 获取知识库列表
- **URL**: `/api/api/kb/list`
- **方法**: `GET`
- **描述**: 列出所有知识库，支持根据 `user_id` 过滤。
- **Query 参数**: `limit=20`, `offset=0`
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": {
      "knowledge_bases": [
        { "id": 1, "name": "医疗百科", "description": "xxx", "created_at": "..." }
      ],
      "total": 1
    }
  }
  ```

### 1.2 创建知识库
- **URL**: `/api/api/kb/create`
- **方法**: `POST`
- **请求范例 (JSON)**:
  ```json
  {
    "name": "肺癌病理库",
    "description": "存储肺癌相关的科研报告",
    "user_id": 1
  }
  ```
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": { "knowledge_base": { "id": 1, "name": "肺癌病理库" } },
    "message": "success"
  }
  ```

### 1.3 获取知识库详情
- **URL**: `/api/api/kb/<kb_id>`
- **方法**: `GET`
- **描述**: 获取特定知识库的详细信息及其下所有文档列表。
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": {
      "knowledge_base": {
        "id": 1,
        "name": "肺癌病理库",
        "description": "...",
        "documents": [
          { "id": "uuid-1", "title": "报告1.pdf" }
        ]
      }
    }
  }
  ```

### 1.4 更新知识库信息
- **URL**: `/api/api/kb/<kb_id>`
- **方法**: `PUT`
- **描述**: 修改知识库的基本信息。
- **请求范例 (JSON)**:
  ```json
  {
    "name": "更新后的名称",
    "description": "更新后的描述"
  }
  ```

### 1.5 删除知识库
- **URL**: `/api/api/kb/<kb_id>`
- **方法**: `DELETE`
- **描述**: 删除知识库及其所有文档和分块。
- **输出范例**:
  ```json
  {
    "code": 0,
    "message": "success"
  }
  ```

### 1.6 获取知识库统计信息
- **URL**: `/api/api/kb/<kb_id>/stats`
- **方法**: `GET`
- **描述**: 获取知识库的统计数据（文档数、总分块数等）。
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": {
      "stats": {
        "document_count": 3,
        "total_chunks": 150,
        "total_size_mb": 25.5
      }
    }
  }
  ```

### 1.7 列出知识库下的文档
- **URL**: `/api/api/kb/<kb_id>/documents`
- **方法**: `GET`
- **描述**: 分页列出指定知识库下的所有文档。
- **Query 参数**: `limit=20`, `offset=0`
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": {
      "items": [
        { "id": "uuid-1", "title": "报告.pdf", "status": "success", "chunk_count": 50 }
      ],
      "total": 5
    }
  }
  ```

---

## 2. 文档操作

### 2.1 上传并处理文档
- **URL**: `/api/api/kb/<kb_id>/upload`
- **方法**: `POST`
- **描述**: 上传文件（PDF/Word/TXT）至指定知识库，系统将自动进行文本提取、解析、切分合向量化入库。
- **请求参数**: `multipart/form-data`
  - `file`: 文件流
  - `split_mode`: 切分模式 (如 `smart`, `fixed`)
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": {
      "document": {
        "id": "uuid-xxx",
        "title": "报告1.pdf",
        "status": "processing"
      }
    }
  }
  ```

### 2.2 获取文档分块 (Chunks)
- **URL**: `/api/api/document/<doc_id>/chunks`
- **方法**: `GET`
- **描述**: 分页查看该文档下被切分后的具体内容。
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": {
      "items": [
        { "id": 101, "content": "切片内容文本...", "metadata": { ... } }
      ],
      "total": 50
    }
  }
  ```

### 2.3 预览文档切分效果
- **URL**: `/api/api/documents/preview`
- **方法**: `POST`
- **描述**: 不保存数据，仅模拟切分处理。
- **请求参数**: `multipart/form-data` 包含 `file`
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": {
      "chunks": ["段落A", "段落B"],
      "total_count": 2
    }
  }
  ```

### 2.4 获取文档原始内容 (Text)
- **URL**: `/api/api/kb/<kb_id>/document/<doc_id>/content`
- **方法**: `GET`
- **描述**: 获取经过解析后的文档全文文本，便于前端展示或二次分析。
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": {
      "content": "这是文档的全文内容，已经过 OCR/文本提取..."
    }
  }
  ```

### 2.5 下载原始文件
- **URL**: `/api/api/kb/<kb_id>/document/<doc_id>/file`
- **方法**: `GET`
- **描述**: 下载该文档的原始二进制文件（PDF、Word 等）。
- **返回**: 二进制流 (如 `application/pdf`, `application/msword`)

### 2.6 删除文档
- **URL**: `/api/api/kb/<kb_id>/document/<doc_id>`
- **方法**: `DELETE`
- **描述**: 从知识库中彻底删除指定文档及其所有分块。
- **输出范例**:
  ```json
  {
    "code": 0,
    "message": "success"
  }
  ```

### 2.7 语义去重 (Deduplication)
- **URL**: `/api/api/document/<doc_id>/dedupe`
- **方法**: `POST`
- **描述**: 对指定文档的切片进行语义相似度检测，移除冗余或极度相似的知识点。
- **输出范例**:
  ```json
  {
    "code": 0,
    "data": { "removed": 5, "remaining": 15 },
    "message": "success"
  }
  ```
