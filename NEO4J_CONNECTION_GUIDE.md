# Neo4j 连接详解

## 一、连接配置

### 1.1 配置来源（优先级从高到低）

#### 环境变量（`.env` 文件）
位置: `C:\Users\16960\Desktop\项目\.env`

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=weiwenhan1110
```

#### 默认配置（`app/config.py`）
位置: `C:\Users\16960\Desktop\项目\app\config.py`

```python
class Config:
    # Neo4j 配置
    NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USERNAME = os.getenv('NEO4J_USERNAME', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'weiwenhan1110')
```

### 1.2 当前连接参数

| 参数 | 值 | 说明 |
|------|----|------|
| **URI** | `bolt://localhost:7687` | Neo4j Bolt 协议，本地 7687 端口 |
| **用户名** | `neo4j` | 默认管理员账户 |
| **密码** | `weiwenhan1110` | 连接密码 |
| **协议** | `bolt://` | 二进制协议（比 HTTP 更快） |

---

## 二、连接初始化流程

### 2.1 应用启动时的初始化

```
app/__init__.py (应用工厂)
    ↓
1. load_dotenv() - 加载 .env 文件
2. init_neo4j(app) - 初始化 Neo4j 驱动
3. GraphRAGService() - 初始化 GraphRAG 服务
    ↓
extensions.py (驱动管理)
```

### 2.2 详细初始化步骤（`app/extensions.py`）

```python
def init_neo4j(app):
    """初始化 Neo4j 驱动"""
    global neo4j_driver
    try:
        # 创建驱动实例
        neo4j_driver = GraphDatabase.driver(
            app.config['NEO4J_URI'],                    # bolt://localhost:7687
            auth=(
                app.config['NEO4J_USERNAME'],            # neo4j
                app.config['NEO4J_PASSWORD']             # weiwenhan1110
            ),
            encrypted=False                             # 不加密（本地开发）
        )
        
        # 验证连接
        neo4j_driver.verify_connectivity()
        logger.info("✓ Neo4j 连接成功")
        
    except Exception as e:
        logger.warning(f"✗ Neo4j 连接失败: {e}，将在需要时尝试重连")
        neo4j_driver = None
```

### 2.3 驱动获取（健康检查）

```python
def get_neo4j_driver():
    """获取 Neo4j 驱动，若失效则尝试重连"""
    global neo4j_driver
    
    if not neo4j_driver:
        # 延迟初始化
        init_neo4j(current_app)
    else:
        try:
            # 验证驱动健康状态
            neo4j_driver.verify_connectivity()
        except Exception:
            # 重新建立连接
            neo4j_driver = None
            init_neo4j(current_app)
    
    return neo4j_driver
```

---

## 三、核心服务架构

### 3.1 层级关系

```
┌─────────────────────────────────────┐
│  GraphRAGService                    │
│  (高级业务逻辑：融合向量+图检索)     │
├─────────────────────────────────────┤
│  KGManager / KGBuilder / KGQuery    │
│  (实体抽取、图构建、图查询)          │
├─────────────────────────────────────┤
│  GraphService                       │
│  (Neo4j 基础操作：执行 Cypher)      │
├─────────────────────────────────────┤
│  Neo4j Driver (neo4j-python)        │
│  (连接池、会话管理、事务处理)        │
├─────────────────────────────────────┤
│  Neo4j Server (bolt://localhost)   │
└─────────────────────────────────────┘
```

### 3.2 关键服务文件

| 文件 | 职责 |
|------|------|
| `app/services/neo/graph_service.py` | **基础操作层** - CRUD / Cypher 执行 |
| `app/services/neo/kg_builder.py` | 实体关系抽取、节点创建、关系建立 |
| `app/services/neo/kg_query.py` | 节点搜索、路径查询、子图提取 |
| `app/services/neo/graphrag_service.py` | **高级查询层** - Local/Global Search |

---

## 四、数据模型和查询

### 4.1 Neo4j 数据结构

#### 节点标签（Label）
```
Entity     - 知识图谱实体（人物、地点、组织等）
Chunk      - 文档分块
Document   - 原始文档
Community  - 社区（由 Leiden 算法检测）
```

#### 关系类型（Relationship）
```
HAS_RELATION    - 实体间的自定义关系（类型由 LLM 识别）
BELONGS_TO      - 属于
LOCATED_IN      - 位于
KNOWS           - 认识
TEACHES         - 教导
LEARNS          - 学习
...更多（见提示词模板）
```

### 4.2 典型查询示例

#### 搜索节点
```python
# 文件: app/services/neo/kg_query.py
def search_nodes(self, query: str, node_type: Optional[str] = None, limit: int = 20):
    cypher = """
    MATCH (n:{node_type})
    WHERE toLower(n.name) CONTAINS toLower($query)
    RETURN n
    LIMIT $limit
    """
```

#### 获取节点上下文（邻居节点）
```python
def get_node_context(self, node_id: str, depth: int = 2):
    cypher = """
    MATCH (center {id: $id})-[r*1..{depth}]-(related)
    RETURN center, r, related
    LIMIT 100
    """
```

#### 查找最短路径
```python
def find_shortest_path(self, start_id: str, end_id: str):
    cypher = """
    MATCH path = shortestPath((a {id: $start})-[*]-(b {id: $end}))
    RETURN path, length(path) as path_length
    """
```

---

## 五、GraphRAG 混合搜索流程

### 5.1 操作流程

```
用户问题
    ↓
hybrid_search()
    ├─ Local Search （基于向量的邻近实体搜索）
    │   ├─ 问题向量化（embedding）
    │   ├─ pgvector 检索相似文本块
    │   └─ 扩展到 Neo4j 邻近节点
    │
    ├─ Global Search （基于社区的全局搜索）
    │   ├─ LDA 主题建模或关键词提取
    │   └─ 查询 Neo4j 社区节点
    │
    └─ 答案生成
        ├─ 收集实体、关系、文本块
        ├─ 格式化为 LLM 上下文
        └─ DeepSeek LLM 生成最终答案

返回结果
{
    "success": bool,
    "strategy_used": "local|global|both",
    "answer": "生成的答案文本",
    "local_result": {      # Local Search 结果
        "entities": [...],
        "relations": [...],
        "chunks": [...]
    },
    "global_result": {     # Global Search 结果
        "communities": [...],
        "answer": "..."
    }
}
```

### 5.2 返回数据结构（前端使用）

当调用 `hybridSearch()` API 时，返回的数据中包含：

```python
{
    "entities": [
        {
            "name": "肺炎",
            "type": "DISEASE",
            "id": "disease_123",
            "neo_id": 12345,  # Neo4j 节点 ID
            "description": "..."
        }
    ],
    "relations": [
        {
            "source": "肺炎",
            "target": "咳嗽",
            "type": "SYMPTOMS",
            "id": "rel_456",
            "description": "肺炎导致咳嗽症状"
        }
    ]
}
```

这些数据由 `KgChatWindow.vue` 通过 `@kg-highlight` 事件发送给 `KgGraph2D.vue` 进行可视化。

---

## 六、前端-后端数据流（知识图谱解释视图）

### 6.1 完整数据流

```
前端 (kg_explain)
    ↓
1. 用户输入问题
2. KgChatWindow 调用 hybridSearch API
    ↓
后端 (FastAPI/Flask)
    ↓
3. RAG 服务执行混合搜索
   - pgvector 向量检索
   - Neo4j 图检索
   - 实体/关系提取
    ↓
4. 返回结果
{
    "entities": [...],      // Neo4j 节点数据
    "relations": [...],     // Neo4j 关系数据
    "answer": "..."
}
    ↓
前端 (kg_explain)
    ↓
5. KgChatWindow 发出 @kg-highlight 事件
   payload: {
       seedNodeIds: ["肺炎", ...],
       nodeIds: ["肺炎", "咳嗽", ...],
       linkIds: ["rel_1", ...],
       maxDepth: 3,
       graph: {
           nodes: [...Neo4j entities],
           edges: [...Neo4j relations],
           links: [...Neo4j relations]  // 别名
       }
   }
    ↓
6. kg_explain/index.vue 接收
   handleKgHighlight(payload)
    ↓
7. KgGraph2D.vue 渲染
   - normalizeGraphPayload() 规范化数据结构
   - buildPathSubgraph() 过滤路径
   - highlightByWaves() 触发动画
   - Canvas 2D 绘制节点和边
```

---

## 七、连接故障排除

### 7.1 常见问题

| 问题 | 症状 | 解决方案 |
|------|------|--------|
| Neo4j 服务未启动 | "Connection refused" | 启动 Neo4j 服务：`neo4j start` |
| 认证失败 | "Authentication failed" | 检查 .env 中用户名密码是否正确 |
| 驱动断开 | 查询返回空结果 | 驱动会自动重连，检查日志 |
| URI 格式错误 | 连接异常 | 确保为 `bolt://host:port` 格式 |

### 7.2 调试方法

```python
# 1. 检查驱动连接
from app.extensions import get_neo4j_driver
driver = get_neo4j_driver()
driver.verify_connectivity()  # 如果无异常则连接正常

# 2. 执行测试查询
with driver.session() as session:
    result = session.run("RETURN 1")
    print(result.single())  # 输出 1

# 3. 查看活跃连接
with driver.session() as session:
    result = session.run("SHOW CONNECTIONS")
```

---

## 八、性能优化建议

### 8.1 连接池配置

```python
# 目前使用默认配置，可根据负载调整
GraphDatabase.driver(
    uri,
    auth=(...),
    encrypted=False,
    # 可选性能调参：
    # connection_pool_size=50,      # 连接池大小
    # trust=Trust.TRUST_ALL_CERTIFICATES,
    # resolver=...,
)
```

### 8.2 查询优化

1. **使用索引**
   ```cypher
   CREATE INDEX ON :Entity(name)
   CREATE INDEX ON :Chunk(doc_id)
   ```

2. **避免全表扫描**
   ```cypher
   // ✗ 不好
   MATCH (n) WHERE n.name = "value"
   
   // ✓ 更好
   MATCH (n:Entity {name: "value"})
   ```

3. **限制返回结果**
   ```cypher
   MATCH (...) RETURN ... LIMIT 100
   ```

---

## 九、关键文件位置速查

```
Neo4j 连接相关
├── C:\Users\16960\Desktop\项目\.env                   (配置)
├── C:\Users\16960\Desktop\项目\app\config.py          (默认值)
├── C:\Users\16960\Desktop\项目\app\extensions.py      (驱动初始化)
│
核心服务
├── C:\Users\16960\Desktop\项目\app\services\neo\
│   ├── graph_service.py        (基础 CRUD)
│   ├── kg_builder.py           (图构建)
│   ├── kg_query.py             (图查询)
│   └── graphrag_service.py     (混合搜索)
│
API 接口
├── C:\Users\16960\Desktop\项目\app\api\rag_api.py     (RAG 接口)
├── C:\Users\16960\Desktop\项目\app\api\kg_api.py      (知识图谱 API)
│
前端
├── C:\Users\16960\Desktop\项目\vben-web\apps\web-ele\src\views\kg\kg_preview\
│   └── components\KgChatWindow.vue          (调用 hybridSearch)
├── C:\Users\16960\Desktop\项目\vben-web\apps\web-ele\src\views\kg\kg_explain\
│   ├── index.vue                            (事件接收)
│   └── components\KgGraph2D.vue             (图渲染)
```

---

## 十、总结

Neo4j 在这个系统中扮演的角色：

1. **存储层** - 存储实体、关系、社区等结构化知识
2. **检索层** - 支持快速的图遍历和模式匹配查询
3. **融合层** - 与 pgvector（向量检索）结合进行混合搜索
4. **可视化** - Neo4j 数据经过规范化后在前端 Canvas 上绘制

连接方式简洁稳定：**Python neo4j 驱动** → **Bolt 协议** → **Neo4j 服务器**

