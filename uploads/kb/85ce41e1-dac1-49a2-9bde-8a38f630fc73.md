# Neo4j

## 范例

```sql
//1. 创建所有实体 (Nodes)
CREATE (b:Brand {name: "华为"})
CREATE (m:Model {name: "Huawei Band 5 Pro", release_date: "2025-10-01"})
CREATE (s:Store {name: "官方旗舰店", platform: "天猫"})
CREATE (pr:PriceRange {range: "300-400元"})
CREATE (r:Review {user_id: "user_123", rating: 5, content: "续航很给力，防水效果好！"})

// 2. 创建所有关系 (Relationships)
// (我们给关系命名为 rel1, rel2...)
CREATE (b)-[rel1:PRODUCES]->(m)
CREATE (s)-[rel2:SELLS]->(m)
CREATE (m)-[rel3:FALLS_IN_RANGE]->(pr)
CREATE (r)-[rel4:IS_ABOUT]->(m)

// 3. 返回所有创建的节点 和 关系 [!!]
RETURN b, m, s, pr, r, rel1, rel2, rel3, rel4
```

## 查询

```sql
MATCH (n)-[r]-(m)
RETURN n, r, m
```

# 删除

```sql
MATCH (n)
DETACH DELETE n
```

