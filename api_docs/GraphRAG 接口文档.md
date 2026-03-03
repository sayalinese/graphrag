# GraphRAG 接口文档

**Base URL Prefix:** `/api/kg`

## 1. GraphRAG 核心查询

### 1.1 图谱智能问答 (QA)
- **URL**: `/api/kg/graph_rag_qa`
- **方法**: `POST`
- **描述**: 基于知识图谱的结构化信息进行检索，适合处理复杂关系、全局性问题及跨文档的知识关联。
- **请求范例 (JSON)**:
  ```json
  {
    "question": "阿尔茨海默症与哪些蛋白质变异有关？",
    "top_k": 5
  }
  ```
- **输出范例**:
  ```json
  {
    "success": true,
    "data": {
      "answer": "阿尔茨海默症主要与 APP、PSEN1 和 PSEN2 基因突变有关...",
      "context": "检索到的图谱子图节点与关系描述...",
      "nodes": [ { "id": "APP", "label": "Protein" }, ... ],
      "links": [ { "source": "Alzheimer", "target": "APP", "type": "ASSOCIATED_WITH" } ]
    }
  }
  ```

---

## 2. 数据入库与图谱构建 (Graph Construction)

### 2.1 文本增量入库
- **URL**: `/api/kg/ingest`
- **方法**: `POST`
- **描述**: 提取给定文本中的实体与关系，同时将其向量化存入 pgvector 并结构化存入 Neo4j。
- **请求范例 (JSON)**:
  ```json
  {
    "text": "研究发现药物A可以抑制蛋白B的表达。",
    "doc_id": "paper_001",
    "kb_id": 1,
    "filename": "research_report.txt"
  }
  ```
- **输出范例**:
  ```json
  {
    "success": true,
    "data": {
       "nodes_added": 2,
       "relationships_added": 1,
       "chunks": 1
    }
  }
  ```

### 2.2 Excel/CSV 批量导入映射
- **URL**: `/api/kg/excel/import`
- **方法**: `POST`
- **描述**: 根据预设的 Schema 映射关系，将结构化表格数据批量导入图谱。

---

## 3. 图谱分析与高级特性

### 3.1 社区检测列表 (Community Discovery)
- **URL**: `/api/kg/communities`
- **方法**: `GET`
- **描述**: 获取图谱中自动划分的社区标识，常用于 GraphRAG 的全局摘要生成。

### 3.2 图谱可视化预览
- **URL**: `/api/kg/visualize`
- **方法**: `GET`
- **描述**: 获取适合前端（如 D3.js, Cytoscape）展示的图谱 JSON 数据。
- **Query 参数**: `limit=100`, `doc_id=xxx`
- **输出范例**:
  ```json
  {
    "nodes": [ {"id": "1", "name": "A", "group": 1} ],
    "links": [ {"source": "1", "target": "2", "value": 1} ]
  }
  ```
