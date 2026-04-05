import os
import logging
from typing import List, Dict, Any, Optional
import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from concurrent.futures import ThreadPoolExecutor, as_completed

from neo4j import GraphDatabase
from langchain_community.vectorstores import PGVector

try:
    import psycopg2
except Exception:
    psycopg2 = None

from app.utils.llm_utils import DeepSeekLLM
from app.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)

# ========== 实体抽取 Prompt 模板 ==========
ENTITY_EXTRACTION_PROMPT = """你是一个专业的知识图谱构建助手。请从以下文本中抽取实体和关系。

【抽取要求】
1. 实体类型包括：PERSON(人物)、ORGANIZATION(组织/门派)、LOCATION(地点)、ITEM(物品/法宝)、SKILL(技能/功法)、EVENT(事件)
2. 关系应该连接两个已抽取的实体
3. 每个实体需要简短描述
4. 如果文本中没有明确的实体或关系，返回空数组

【输出格式】
请严格按照以下JSON格式输出，不要添加任何其他内容：
{{
  "entities": [
    {{"name": "实体名称", "type": "PERSON", "description": "简短描述"}}
  ],
  "relations": [
    {{"source": "源实体名称", "target": "目标实体名称", "type": "关系类型", "description": "关系描述"}}
  ]
}}

【常见关系类型】
- BELONGS_TO: 属于/隶属
- LOCATED_IN: 位于
- KNOWS: 认识
- TEACHES: 教导
- LEARNS: 学习
- POSSESSES: 拥有
- PARTICIPATES_IN: 参与
- RELATED_TO: 相关

【待抽取文本】
{text}

请输出JSON："""


class GraphRAGService:
    """GraphRAG service with entity extraction and community detection

    - Extracts entities and relations using LLM
    - Stores Entity/Chunk nodes in Neo4j with relationships
    - Stores embeddings in pgvector
    - Supports Leiden community detection (requires Neo4j GDS plugin)
    - Query: embed question -> pgvector search -> expand Neo4j subgraph -> format context -> call LLM
    """

    def __init__(
        self,
        neo_uri: str,
        neo_user: str,
        neo_pwd: str,
        pg_conn: str,
        pg_collection: str = "graphrag_collection",
        embed_model_name: str = "all-MiniLM-L6-v2",
        deepseek_api_key: str = "",
        deepseek_model: str = "deepseek-chat",
        deepseek_api_base: str = "https://api.deepseek.com/v1",
    ) -> None:
        self.driver = GraphDatabase.driver(neo_uri, auth=(neo_user, neo_pwd))
        self.default_database = os.getenv('NEO4J_DATABASE', '').strip() or None
        self._database_ctx: ContextVar[Optional[str]] = ContextVar('neo4j_database_ctx', default=None)
        self.pg_conn = pg_conn
        self.pg_collection = pg_collection
        self._vector_stores: Dict[str, Any] = {}
        
        # 使用 EmbeddingService（支持 OpenAI 兼容 API，如 BAAI/bge-m3）
        try:
            self._embedding_service = EmbeddingService()
            self._embedding_wrapper = self._embedding_service.embeddings
            logger.info(
                "GraphRAG 使用 EmbeddingService: provider=%s model=%s base_url=%s wrapper=%s",
                getattr(self._embedding_service, 'provider', 'unknown'),
                self._embedding_service.model_name,
                getattr(self._embedding_service, 'base_url', None),
                type(getattr(self._embedding_service, 'embeddings', None)).__name__,
            )
        except Exception as e:
            logger.warning(f"初始化 EmbeddingService 失败: {e}，回退到 SentenceTransformer")
            self._embedding_service = None
            self._embedding_wrapper = None
            # 回退到本地 SentenceTransformer
            try:
                from sentence_transformers import SentenceTransformer
                self.embed_model = SentenceTransformer(embed_model_name)
                
                class SentenceTransformerEmbeddings:
                    """LangChain 兼容的 Embeddings 接口包装"""
                    def __init__(self, model):
                        self.model = model
                    
                    def embed_documents(self, texts: List[str]) -> List[List[float]]:
                        if self.model is None:
                            raise RuntimeError("embed model not available")
                        emb = self.model.encode(texts)
                        return emb.tolist() if hasattr(emb, 'tolist') else [list(map(float, e)) for e in emb]
                    
                    def embed_query(self, text: str) -> List[float]:
                        if self.model is None:
                            raise RuntimeError("embed model not available")
                        emb = self.model.encode([text])[0]
                        return emb.tolist() if hasattr(emb, 'tolist') else list(map(float, emb))
                
                self._embedding_wrapper = SentenceTransformerEmbeddings(self.embed_model)
            except Exception as e2:
                logger.warning(f"加载 SentenceTransformer 也失败: {e2}")
                self.embed_model = None

        try:
            self.vector_store = self._build_vector_store(pg_collection)
            if self.vector_store is not None:
                self._vector_stores[pg_collection] = self.vector_store
        except Exception as e:  # fallback
            logger.warning(f"初始化 PGVector 失败: {e}")
            self.vector_store = None

        # DeepSeek LLM 用于生成答案
        try:
            self.llm = DeepSeekLLM(api_key=deepseek_api_key, model=deepseek_model, api_base=deepseek_api_base)
        except Exception as e:
            logger.warning(f"初始化 DeepSeekLLM 失败: {e}")
            self.llm = None

    def close(self):
        try:
            self.driver.close()
        except Exception:
            pass

    @contextmanager
    def _use_database(self, database: Optional[str]):
        db_name = (database or '').strip() or None
        token = None
        if db_name is not None:
            token = self._database_ctx.set(db_name)
        try:
            yield
        finally:
            if token is not None:
                self._database_ctx.reset(token)

    def _session(self):
        db_name = self._database_ctx.get() or self.default_database
        if db_name:
            return self.driver.session(database=db_name)
        return self.driver.session()

    def _normalize_database_name(self, database: str) -> str:
        safe = re.sub(r'[^0-9a-zA-Z_]+', '_', (database or '').strip().lower())
        return safe.strip('_') or 'default'

    def get_vector_collection_name(self, database: Optional[str] = None) -> str:
        db_name = (database or self._database_ctx.get() or '').strip()
        if not db_name:
            return self.pg_collection
        return f"{self.pg_collection}__{self._normalize_database_name(db_name)}"

    def _build_vector_store(self, collection_name: str):
        return PGVector(
            connection_string=self.pg_conn,
            collection_name=collection_name,
            embedding_function=self._embedding_wrapper,
        )

    def _get_vector_store(self, database: Optional[str] = None):
        collection_name = self.get_vector_collection_name(database=database)
        if collection_name in self._vector_stores:
            return self._vector_stores[collection_name], collection_name
        try:
            store = self._build_vector_store(collection_name)
            self._vector_stores[collection_name] = store
            return store, collection_name
        except Exception as e:
            logger.warning(f"初始化数据库向量集合失败({collection_name}): {e}")
            return None, collection_name

    def embed_text(self, text: str) -> Optional[List[float]]:
        """使用 EmbeddingService 生成文本向量"""
        # 优先使用 EmbeddingService
        if self._embedding_service:
            try:
                return self._embedding_service.embed_query(text)
            except Exception as e:
                logger.error(f"EmbeddingService embed_text failed: {e}")
                return None
        
        # 回退到本地 SentenceTransformer
        if hasattr(self, 'embed_model') and self.embed_model:
            try:
                emb = self.embed_model.encode(text)
                return emb.tolist() if hasattr(emb, 'tolist') else list(map(float, emb))
            except Exception as e:
                logger.error(f"embed_text failed: {e}")
                return None
        
        logger.error("No embed model available")
        return None

    # ========== Phase 1: 实体/关系抽取 ==========
    
    def extract_entities_relations(self, text: str) -> Dict[str, Any]:
        """使用 LLM 从文本中抽取实体和关系
        
        Returns:
            {
                "entities": [{"name": str, "type": str, "description": str}],
                "relations": [{"source": str, "target": str, "type": str, "description": str}]
            }
        """
        if not self.llm:
            logger.warning("LLM not available, skipping entity extraction")
            return {"entities": [], "relations": []}
        
        try:
            prompt = ENTITY_EXTRACTION_PROMPT.format(text=text[:2000])  # 限制长度避免超token
            
            # 使用 LangChain 的 ChatOpenAI 接口调用
            from langchain_core.messages import HumanMessage
            
            response = self.llm.llm.invoke([HumanMessage(content=prompt)])
            result_text = response.content.strip()
            
            logger.debug(f"LLM raw response: {result_text[:500]}")
            
            # 解析 JSON（处理可能的 markdown 代码块）
            # 尝试多种模式匹配
            json_str = None
            
            # 模式1: ```json ... ```
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', result_text)
            if json_match:
                json_str = json_match.group(1).strip()
            
            # 模式2: ``` ... ``` (无语言标记)
            if not json_str:
                json_match = re.search(r'```\s*([\s\S]*?)\s*```', result_text)
                if json_match:
                    json_str = json_match.group(1).strip()
            
            # 模式3: 直接找 JSON 对象
            if not json_str:
                # 找到第一个 { 和最后一个 }
                brace_start = result_text.find('{')
                brace_end = result_text.rfind('}')
                if brace_start >= 0 and brace_end > brace_start:
                    json_str = result_text[brace_start:brace_end + 1]
            
            if not json_str:
                logger.warning(f"No JSON found in LLM response: {result_text[:200]}")
                return {"entities": [], "relations": []}
            
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error: {e}, raw: {json_str[:200]}")
                return {"entities": [], "relations": []}
            
            entities = result.get("entities", [])
            relations = result.get("relations", [])
            
            # 验证数据格式
            valid_entities = []
            for e in entities:
                if isinstance(e, dict) and e.get("name"):
                    valid_entities.append({
                        "name": str(e.get("name", "")).strip(),
                        "type": str(e.get("type", "UNKNOWN")).upper(),
                        "description": str(e.get("description", ""))
                    })
            
            valid_relations = []
            for r in relations:
                if isinstance(r, dict) and r.get("source") and r.get("target"):
                    valid_relations.append({
                        "source": str(r.get("source", "")).strip(),
                        "target": str(r.get("target", "")).strip(),
                        "type": str(r.get("type", "RELATED_TO")).upper(),
                        "description": str(r.get("description", ""))
                    })
            
            logger.info(f"Extracted {len(valid_entities)} entities and {len(valid_relations)} relations")
            return {"entities": valid_entities, "relations": valid_relations}
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return {"entities": [], "relations": []}

    def _create_entity_node(self, sess, entity: Dict, doc_id: str) -> Optional[int]:
        """在 Neo4j 中创建 Entity 节点"""
        try:
            name = entity.get("name", "").strip()
            etype = entity.get("type", "UNKNOWN").upper()
            desc = entity.get("description", "")
            
            if not name:
                return None
            
            # MERGE 避免重复创建同名实体
            result = sess.run(
                """
                MERGE (e:Entity {name: $name})
                ON CREATE SET e.type = $type, e.description = $desc, e.doc_id = $doc_id, e.created_at = datetime()
                ON MATCH SET e.description = CASE WHEN e.description IS NULL OR e.description = '' THEN $desc ELSE e.description END
                RETURN elementId(e) as eid, elementId(e) as nid
                """,
                {"name": name, "type": etype, "desc": desc, "doc_id": doc_id}
            )
            row = result.single()
            return row["nid"] if row else None
        except Exception as e:
            logger.error(f"Failed to create entity node: {e}")
            return None

    def _create_relation_edge(self, sess, relation: Dict, doc_id: str) -> bool:
        """在 Neo4j 中创建关系边"""
        try:
            source = relation.get("source", "").strip()
            target = relation.get("target", "").strip()
            rel_type = relation.get("type", "RELATED_TO").upper().replace(" ", "_")
            desc = relation.get("description", "")
            
            if not source or not target:
                return False
            
            # 动态关系类型需要用 APOC 或拼接 Cypher
            # 这里使用通用 RELATES_TO 关系，type 存为属性
            result = sess.run(
                """
                MATCH (s:Entity {name: $source})
                MATCH (t:Entity {name: $target})
                MERGE (s)-[r:RELATES_TO {type: $rel_type}]->(t)
                ON CREATE SET r.description = $desc, r.doc_id = $doc_id, r.created_at = datetime()
                RETURN type(r) as rtype
                """,
                {"source": source, "target": target, "rel_type": rel_type, "desc": desc, "doc_id": doc_id}
            )
            return result.single() is not None
        except Exception as e:
            logger.error(f"Failed to create relation edge: {e}")
            return False

    def ingest_text(self, doc_id: str, text: str, kb_id: Optional[int] = None, filename: Optional[str] = None, 
                    extract_entities: bool = True) -> Dict[str, Any]:
        """Split text into chunks, extract entities/relations, create Neo4j nodes and upsert embeddings.

        Args:
            doc_id: 文档唯一标识
            text: 待处理文本
            kb_id: 知识库ID（可选）
            filename: 文件名（可选）
            extract_entities: 是否启用 LLM 实体抽取（默认 True）

        Returns:
            包含创建的 chunks、entities、relations 信息
        """
        chunks = [p.strip() for p in text.split("\n\n") if p.strip()]
        created_chunks = []
        created_entities = []
        created_relations = []
        all_entities = []  # 收集所有实体用于后续社区检测
        active_db = (self._database_ctx.get() or '').strip() or None
        vector_store, vector_collection = self._get_vector_store(database=active_db)

        with self._session() as sess:
            # create Document node
            doc_res = sess.run(
                "CREATE (d:Document {doc_id:$doc_id, filename:$filename}) RETURN elementId(d) as eid, elementId(d) as id",
                {"doc_id": doc_id, "filename": filename},
            )
            doc_row = doc_res.single()
            doc_node_id = doc_row["id"] if doc_row else None

            for idx, chunk in enumerate(chunks):
                # 1. 创建 Chunk 节点
                try:
                    res = sess.run(
                        "CREATE (c:Chunk {doc_id:$doc_id, idx:$idx, text:$text}) RETURN elementId(c) as nid",
                        {"doc_id": doc_id, "idx": idx, "text": chunk},
                    )
                    nid = res.single()["nid"]
                except Exception as e:
                    logger.error(f"创建 chunk 节点失败: {e}")
                    continue

                # 2. 关联 Document -> Chunk
                if doc_node_id:
                    try:
                        sess.run(
                            "MATCH (d:Document), (c:Chunk) WHERE elementId(d)=$did AND elementId(c)=$cid CREATE (d)-[:CONTAINS]->(c)",
                            {"did": doc_node_id, "cid": nid}
                        )
                    except Exception as e:
                        logger.warning(f"创建 Document-Chunk 关系失败: {e}")

                # 3. LLM 实体/关系抽取
                chunk_entities = []
                chunk_relations = []
                if extract_entities and self.llm:
                    extraction = self.extract_entities_relations(chunk)
                    
                    # 创建 Entity 节点
                    for entity in extraction.get("entities", []):
                        entity_nid = self._create_entity_node(sess, entity, doc_id)
                        if entity_nid:
                            chunk_entities.append({"name": entity["name"], "type": entity.get("type"), "neo_id": entity_nid})
                            all_entities.append(entity["name"])
                            
                            # 关联 Chunk -> Entity (MENTIONS)
                            try:
                                sess.run(
                                    "MATCH (c:Chunk), (e:Entity) WHERE elementId(c)=$cid AND elementId(e)=$eid CREATE (c)-[:MENTIONS]->(e)",
                                    {"cid": nid, "eid": entity_nid}
                                )
                            except Exception:
                                pass
                    
                    # 创建关系边
                    for relation in extraction.get("relations", []):
                        if self._create_relation_edge(sess, relation, doc_id):
                            chunk_relations.append(relation)
                    
                    created_entities.extend(chunk_entities)
                    created_relations.extend(chunk_relations)

                # 4. 生成向量并存储到 pgvector
                emb = self.embed_text(chunk)
                vec_id = f"chunk_{nid}"

                if vector_store and emb is not None:
                    try:
                        if hasattr(vector_store, 'add_texts'):
                            res = vector_store.add_texts(
                                [chunk], 
                                metadatas=[{
                                    "neo_node_id": str(nid), 
                                    "doc_id": doc_id, 
                                    "kb_id": kb_id, 
                                    "filename": filename,
                                    "database": active_db,
                                    "vector_collection": vector_collection,
                                    "entities": json.dumps([e["name"] for e in chunk_entities], ensure_ascii=False)
                                }], 
                                ids=[vec_id]
                            )
                            logger.info(f"PGVector.add_texts returned: {res}")
                    except Exception as e:
                        logger.warning(f"向量上载失败: {e}")

                # 5. 写回 vec_id 到 Neo4j Chunk 节点
                try:
                    sess.run("MATCH (c) WHERE elementId(c)=$nid SET c.vec_id=$vec", {"nid": nid, "vec": vec_id})
                except Exception:
                    pass

                created_chunks.append({
                    "neo_id": nid, 
                    "vec_id": vec_id, 
                    "idx": idx,
                    "entities_count": len(chunk_entities),
                    "relations_count": len(chunk_relations)
                })

        return {
            "success": True, 
            "created_chunks": created_chunks, 
            "created_entities": created_entities,
            "created_relations": created_relations,
            "doc_node_id": doc_node_id,
            "summary": {
                "chunks": len(created_chunks),
                "entities": len(created_entities),
                "relations": len(created_relations)
            }
        }

    def query(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """Query pipeline: embed question -> pgvector search -> expand neo4j subgraph -> return candidates and LLM answer"""
        q_emb = self.embed_text(question)
        if q_emb is None:
            return {"success": False, "error": "Embedding failed"}

        # vector search - robust parsing for different PGVector interfaces
        neo_ids: List[int] = []
        docs = []
        logger.debug("Starting vector search for question")
        def _parse_vector_results(results):
            parsed_docs = []
            parsed_neo_ids = []
            if not results:
                return parsed_docs, parsed_neo_ids
            logger.debug(f"Raw vector results type: {type(results)}, len: {len(results) if hasattr(results, '__len__') else 'n/a'}")
            for item in results:
                try:
                    # item may be (doc, score) or a dict/object
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        doc_part, score = item[0], item[1]
                    else:
                        doc_part, score = item, None

                    text = None
                    metadata = {}

                    # langchain.Document style
                    if hasattr(doc_part, 'page_content'):
                        text = getattr(doc_part, 'page_content', None)
                    elif hasattr(doc_part, 'text'):
                        text = getattr(doc_part, 'text', None)

                    # metadata may be attribute or dict
                    if hasattr(doc_part, 'metadata'):
                        try:
                            metadata = getattr(doc_part, 'metadata') or {}
                        except Exception:
                            metadata = {}
                    elif isinstance(doc_part, dict):
                        metadata = doc_part.get('metadata') or doc_part.get('meta') or {}
                        if not text:
                            text = doc_part.get('page_content') or doc_part.get('text') or doc_part.get('content')

                    # fallback to string
                    if text is None:
                        try:
                            text = str(doc_part)
                        except Exception:
                            text = ''

                    # find neo node id from various metadata keys
                    neo_node = None
                    for k in ('neo_node_id', 'neo_id', 'neo', 'node_id', 'id'):
                        if isinstance(metadata, dict) and k in metadata and metadata[k] is not None:
                            neo_node = metadata[k]
                            break

                    if neo_node is None and isinstance(doc_part, dict):
                        # try nested patterns
                        neo_node = doc_part.get('neo_node_id') or doc_part.get('neo_id')

                    if neo_node is not None:
                        try:
                            parsed_neo_ids.append(int(neo_node))
                        except Exception:
                            parsed_neo_ids.append(neo_node)

                    parsed_docs.append({"text": text, "score": score, "metadata": metadata})
                except Exception as e:
                    logger.warning(f"parse vector item failed: {e}")
                    continue
            return parsed_docs, parsed_neo_ids

        active_db = (self._database_ctx.get() or '').strip() or None
        vector_store, _ = self._get_vector_store(database=active_db)
        if vector_store:
            try:
                # try common search names used by different implementations
                results = None
                for fn in ("similarity_search_with_score_by_vector", "similarity_search_by_vector", "similarity_search_with_score", "similarity_search"):
                    if hasattr(vector_store, fn):
                        try:
                            results = getattr(vector_store, fn)(q_emb, k=top_k)
                            break
                        except TypeError:
                            # some APIs expect named args
                            try:
                                results = getattr(vector_store, fn)(q_emb, k=top_k)
                                break
                            except Exception:
                                results = None
                # if still None, try a generic 'search' or 'client' usage
                if results is None and hasattr(vector_store, 'client'):
                    try:
                        # many clients expose a query/upsert API; leave as best-effort
                        results = getattr(vector_store, 'client').query(q_emb, top_k)
                    except Exception:
                        results = None

                # log a short summary of raw results at INFO level so it's visible in default logs
                try:
                    logger.info(f"Vector search raw results sample: {str(results)[:1000]}")
                except Exception:
                    logger.info("Vector search raw results present (not shown)")
                parsed_docs, parsed_neo_ids = _parse_vector_results(results)
                docs.extend(parsed_docs)
                neo_ids.extend(parsed_neo_ids)
                # fallback strategies: if no neo_ids found, try to extract from metadata vec_id or match text
                if not neo_ids and docs:
                    logger.debug("No neo_ids from metadata, attempting fallback resolution via vec_id/text")
                    # try vec_id in metadata
                    for d in docs:
                        md = d.get('metadata') or {}
                        vec = None
                        if isinstance(md, dict):
                            vec = md.get('vec_id') or md.get('id') or md.get('vector_id')
                        if not vec:
                            # sometimes metadata stored under other keys
                            for k in ('neo_node_id', 'neo_id', 'id'):
                                if k in md:
                                    vec = md.get(k)
                                    break
                        # if vec looks like 'chunk_7', extract numeric suffix
                        if isinstance(vec, str) and vec.startswith('chunk_'):
                            try:
                                neo_ids.append(int(vec.split('_', 1)[1]))
                            except Exception:
                                pass
                    # if still empty, try matching text to Neo4j Chunk.text
                    if not neo_ids:
                        try:
                            with self._session() as sess2:
                                for d in docs:
                                    txt = (d.get('text') or '').strip()
                                    if not txt:
                                        continue
                                    q = sess2.run('MATCH (c:Chunk) WHERE c.text = $txt RETURN elementId(c) as nid LIMIT 1', {'txt': txt})
                                    r = q.single()
                                    if r and r.get('nid') is not None:
                                        neo_ids.append(r.get('nid'))
                        except Exception as e:
                            logger.debug(f"fallback text->neo lookup failed: {e}")
            except Exception as e:
                logger.warning(f"pgvector search failed: {e}")

        # remove duplicates and limit
        neo_ids = list(dict.fromkeys(neo_ids))[: max(1, top_k)]

        candidates = []
        if neo_ids:
            with self._session() as sess:
                try:
                    rows = sess.run(
                        "MATCH (c) WHERE elementId(c) IN $ids OPTIONAL MATCH (c)-[r]-(m) RETURN c, collect(r) as rels, collect(m) as mats",
                        {"ids": neo_ids},
                    )
                    for row in rows:
                        node = row.get("c")
                        rels = row.get("rels") or []
                        mats = row.get("mats") if "mats" in row.keys() else row.get("m")
                        # serialize node
                        try:
                            node_dict = dict(node)
                        except Exception:
                            node_dict = {k: getattr(node, k) for k in dir(node) if not k.startswith("_")}
                        candidates.append({"node": node_dict, "rels": [dict(r) for r in rels]})
                except Exception as e:
                    logger.error(f"Neo4j expand failed: {e}")

        # format context
        context_parts = []
        for c in candidates:
            txt = c["node"].get("text") or c["node"].get("name") or c["node"].get("doc_id")
            context_parts.append(f"节点ID:{c['node'].get('doc_id') or c['node'].get('id') or ''} 内容: {str(txt)[:400]}")
        context = "\n\n".join(context_parts)

        answer = ""
        if self.llm:
            try:
                answer = self.llm.generate_answer(question, context)
            except Exception as e:
                logger.error(f"LLM generate failed: {e}")
                answer = ""

        return {"success": True, "answer": answer, "candidates": candidates, "raw_docs": docs}

    # ========== Phase 3: Local Search (混合搜索) ==========
    
    def local_search(self, question: str, top_k: int = 20, include_community: bool = True, doc_id: str = None, database: str = None, return_context_only: bool = False) -> Dict[str, Any]:
        """Local Search: 结合实体、关系和向量检索的混合搜索
        
        搜索流程:
        1. 向量检索: 找到相关的 Chunk 节点
        2. 实体匹配: 从问题中提取关键词，匹配 Entity 节点
        3. 关系展开: 获取匹配实体的关系网络
        4. 上下文构建: 整合 Chunk 文本 + 实体信息 + 关系信息
        5. LLM 生成: 基于丰富上下文生成答案
        
        Args:
            question: 用户问题
            top_k: 返回的候选数量
            include_community: 是否包含社区信息
            doc_id: 文档 ID，用于限定检索范围（可选）
            
        Returns:
            包含 answer, entities, relations, chunks 的结果
        """
        result = {
            "success": True,
            "answer": "",
            "entities": [],
            "relations": [],
            "chunks": [],
            "community_context": [],
            "evidence": {
                "top_chunks": [],
                "top_entities": [],
                "top_relations": []
            }
        }

        # 1. 第一阶段召回：并行执行向量检索和实体匹配（两者相互独立）
        candidate_k = max(top_k * 3, 30)
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_chunks = executor.submit(
                self._vector_search_chunks, question, candidate_k,
                doc_id=doc_id, database=database
            )
            future_entities = executor.submit(
                self._match_entities_from_question, question, doc_id=doc_id
            )
        vector_candidates = future_chunks.result()
        matched_entities = future_entities.result()
        
        # 2. 从向量命中节点展开实体
        #    路径 A（文本语料库）：Chunk -[:MENTIONS]-> Entity
        #    路径 B（纯知识图谱）：向量命中节点本身即为 Disease/Drug/Symptom 域节点
        chunk_entity_ids = set()
        if vector_candidates:
            chunk_neo_ids = [c.get("neo_id") for c in vector_candidates if c.get("neo_id")]
            if chunk_neo_ids:
                with self._session() as sess:
                    # 路径 A：Chunk-MENTIONS（文本语料库）
                    try:
                        res = sess.run("""
                            MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
                            WHERE elementId(c) IN $chunk_ids
                            RETURN DISTINCT e.name AS name, labels(e)[0] AS type,
                                   elementId(e) AS neo_id,
                                   coalesce(e.description, e.intro, '') AS description,
                                   e.community_id AS community_id
                        """, {"chunk_ids": chunk_neo_ids})
                        for row in res:
                            entity_info = {
                                "name": row["name"], "type": row["type"],
                                "neo_id": row["neo_id"], "description": row["description"] or "",
                                "community_id": row["community_id"], "source": "chunk_mention"
                            }
                            chunk_entity_ids.add(row["neo_id"])
                            if not any(e["name"] == entity_info["name"] for e in matched_entities):
                                matched_entities.append(entity_info)
                    except Exception as e:
                        logger.warning(f"Chunk-MENTIONS path failed: {e}")

                    # 路径 B：向量命中节点本身就是域节点（纯知识图谱）
                    try:
                        res2 = sess.run("""
                            MATCH (n)
                            WHERE elementId(n) IN $node_ids
                              AND NOT n:Chunk AND NOT n:Document AND NOT n:Community
                            RETURN coalesce(n.name, n.id) AS name,
                                   labels(n)[0] AS type, elementId(n) AS neo_id,
                                   coalesce(n.description, n.intro, '') AS description,
                                   n.community_id AS community_id
                        """, {"node_ids": chunk_neo_ids})
                        for row in res2:
                            if not row["name"]:
                                continue
                            entity_info = {
                                "name": row["name"], "type": row["type"],
                                "neo_id": row["neo_id"], "description": row["description"] or "",
                                "community_id": row["community_id"], "source": "vector_entity"
                            }
                            chunk_entity_ids.add(row["neo_id"])
                            if not any(e["name"] == entity_info["name"] for e in matched_entities):
                                matched_entities.append(entity_info)
                    except Exception as e:
                        logger.warning(f"Vector entity path failed: {e}")

        # 4. 第二阶段重排：chunks + entities
        reranked_entities = self._rerank_entities(question, matched_entities, vector_candidates, top_n=max(12, top_k * 2))
        reranked_chunks = self._rerank_chunks(question, vector_candidates, reranked_entities, top_n=top_k)

        result["entities"] = reranked_entities
        result["chunks"] = reranked_chunks
        
        # 5. 获取实体之间的关系并进行证据打分（带疾病锚点约束）
        entity_names = [e["name"] for e in reranked_entities]
        intent = self._infer_medical_intent(question)
        anchors = self._select_anchor_entities(question, reranked_entities, intent)
        if entity_names:
            anchor_relations = self._get_anchor_relations(anchors, intent, limit=max(80, top_k * 10))
            base_relations = self._get_entity_relations(entity_names)
            if anchor_relations:
                seen = set()
                relations = []
                for r in (anchor_relations + base_relations):
                    key = (r.get('source'), r.get('type'), r.get('target'))
                    if key in seen:
                        continue
                    seen.add(key)
                    relations.append(r)
            else:
                relations = base_relations
            result["relations"] = self._score_relations(
                question,
                relations,
                reranked_entities,
                top_n=max(60, top_k * 8),
                anchors=anchors,
                intent=intent,
            )
        
        # 6. 如果启用社区信息，获取相关社区上下文（包含社区报告正文）
        if include_community and reranked_entities:
            community_ids = set()
            for e in reranked_entities:
                if e.get("community_id") is not None:
                    community_ids.add(e["community_id"])

            for cid in list(community_ids)[:3]:  # 最多3个社区
                community_entities = self.get_community_entities(cid)
                # 尝试获取该社区的 LLM 报告节点
                report_text = ""
                try:
                    active_db = (database or self._database_ctx.get() or '').strip() or None
                    with self._session() as sess:
                        row = sess.run(
                            "MATCH (c:Community {community_id: $cid, database: $database}) RETURN c.report AS report LIMIT 1",
                            {"cid": cid, "database": active_db or "default"}
                        ).single()
                        if row and row.get("report"):
                            report_text = row["report"]
                except Exception:
                    pass
                entry = {
                    "community_id": cid,
                    "report": report_text,
                    "members": [e["name"] for e in (community_entities or [])[:12]],
                }
                result["community_context"].append(entry)

        # 输出可解释证据（前端可直接展示）
        result["evidence"] = {
            "top_chunks": [{"neo_id": c.get("neo_id"), "score": c.get("evidence_score", 0.0)} for c in reranked_chunks[:10]],
            "top_entities": [{"name": e.get("name"), "score": e.get("evidence_score", 0.0), "source": e.get("source")} for e in reranked_entities[:15]],
            "top_relations": [{"source": r.get("source"), "target": r.get("target"), "type": r.get("type"), "score": r.get("evidence_score", 0.0)} for r in result["relations"][:20]]
        }

        # 7. 构建丰富的上下文
        context = self._build_local_search_context(
            chunks=reranked_chunks,
            entities=reranked_entities,
            relations=result["relations"],
            community_context=result["community_context"]
        )

        # 9. 结构化证据答案（当 LLM 回答过于保守或空时，使用关系证据兜底）
        structured_answer = self._build_medical_structured_answer(
            intent=intent,
            anchors=anchors,
            relations=result.get("relations", []),
        )

        # 支持流式调用：return_context_only=True 时不调用 LLM，返回检索中间结果
        if return_context_only:
            result['_context'] = context
            result['_structured_fallback'] = structured_answer
            return result

        # 8. LLM 生成答案
        if self.llm and context:
            try:
                answer = self.llm.generate_answer(question, context)
                result["answer"] = answer
            except Exception as e:
                logger.error(f"LLM generate failed: {e}")
                result["answer"] = ""

        low_conf_phrases = ("没有找到", "无法", "未能", "无相关", "信息不足")
        current_answer = result.get("answer") or ""
        if structured_answer and (not current_answer or any(p in current_answer for p in low_conf_phrases)):
            result["answer"] = structured_answer
        
        return result
    
    def _vector_search_chunks(self, question: str, top_k: int = 20, doc_id: str = None, database: str = None) -> List[Dict]:
        """向量检索相关的 Chunk
        
        Args:
            question: 用户问题
            top_k: 返回的候选数量
            doc_id: 文档 ID，用于限定检索范围（可选）
        """
        chunks = []
        q_emb = self.embed_text(question)
        active_db = (database or self._database_ctx.get() or '').strip() or None
        vector_store, _ = self._get_vector_store(database=active_db)
        if q_emb is None or not vector_store:
            return chunks
        
        try:
            # 如果指定了 doc_id，使用过滤条件
            filter_dict = None
            if doc_id or active_db:
                filter_dict = {}
                if doc_id:
                    filter_dict["doc_id"] = doc_id
                if active_db:
                    filter_dict["database"] = active_db
            
            results = None
            for fn in ("similarity_search_with_score_by_vector", "similarity_search_by_vector"):
                if hasattr(vector_store, fn):
                    try:
                        if filter_dict:
                            # 尝试带过滤条件的搜索
                            results = getattr(vector_store, fn)(q_emb, k=top_k * 3, filter=filter_dict)
                        else:
                            # 多取 2x 再截断，避免重复 neo_id 导致有效结果不足
                            results = getattr(vector_store, fn)(q_emb, k=top_k * 2)
                        break
                    except TypeError:
                        # 如果向量库不支持 filter 参数，回退到无过滤搜索
                        results = getattr(vector_store, fn)(q_emb, k=top_k * 3 if (doc_id or active_db) else top_k * 2)
                    except Exception:
                        continue
            
            if results:
                filtered_count = 0
                for item in results:
                    try:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            doc, score = item[0], item[1]
                        else:
                            doc, score = item, None
                        
                        text = getattr(doc, 'page_content', '') if hasattr(doc, 'page_content') else str(doc)
                        metadata = getattr(doc, 'metadata', {}) if hasattr(doc, 'metadata') else {}
                        
                        # 如果指定了 doc_id，进行后过滤
                        if doc_id:
                            chunk_doc_id = metadata.get('doc_id')
                            if chunk_doc_id and chunk_doc_id != doc_id:
                                continue  # 跳过不匹配的文档
                        if active_db:
                            chunk_db = metadata.get('database')
                            if chunk_db and str(chunk_db).strip() != active_db:
                                continue
                        
                        neo_id = None
                        for k in ('neo_node_id', 'neo_id', 'id'):
                            if k in metadata:
                                try:
                                    neo_id = int(metadata[k])
                                    break
                                except:
                                    neo_id = metadata[k]
                                    break
                        
                        chunks.append({
                            "text": text,
                            "score": score,
                            "neo_id": neo_id,
                            "metadata": metadata
                        })
                        filtered_count += 1
                        if filtered_count >= top_k:
                            break  # 已收集足够的结果
                    except Exception as e:
                        logger.warning(f"Parse chunk failed: {e}")
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
        
        return chunks
    
    def _match_entities_from_question(self, question: str, doc_id: str = None) -> List[Dict]:
        """从问题中匹配领域节点

        兼容两种模式：
        - 文本语料库模式：:Entity 节点（GraphRAG 文本摄入产生）
        - 纯知识图谱模式：:Disease/:Drug/:Symptom 等医疗域节点

        策略：提取问题中 2-6 字的连续子串作为候选词，让 Neo4j 用 CONTAINS 做匹配，
        避免将全部 5 万节点传回 Python 端做比对。
        """
        matched = []
        if not question:
            return matched

        # 提取候选词（2-6 字连续子串，去重）
        # 优先保留较长子串（更精确），限制总数以减少 Neo4j 全表扫描压力
        raw_tokens = {
            question[i:j]
            for i in range(len(question))
            for j in range(i + 2, min(i + 7, len(question) + 1))
        }
        tokens = sorted(raw_tokens, key=len, reverse=True)[:30]
        if not tokens:
            return matched

        with self._session() as sess:
            try:
                # 让 Neo4j CONTAINS 做匹配，兼容所有非基础设施节点
                res = sess.run("""
                    UNWIND $tokens AS tok
                    MATCH (n)
                    WHERE NOT n:Chunk AND NOT n:Document AND NOT n:Community
                      AND n.name IS NOT NULL
                      AND (n.name = tok OR n.name CONTAINS tok)
                    RETURN DISTINCT
                           n.name AS name,
                           labels(n)[0] AS type,
                           elementId(n) AS neo_id,
                           coalesce(n.description, n.intro, n.text, '') AS description,
                           n.community_id AS community_id
                    LIMIT 80
                """, {"tokens": tokens})
                for row in res:
                    entity_name = row["name"]
                    if entity_name:
                        matched.append({
                            "name": entity_name,
                            "type": row["type"],
                            "neo_id": row["neo_id"],
                            "description": row["description"] or "",
                            "community_id": row["community_id"],
                            "source": "question_match"
                        })
            except Exception as e:
                logger.warning(f"Entity matching failed: {e}")

        return matched
    
    def _get_entity_relations(self, entity_names: List[str]) -> List[Dict]:
        """获取实体的关系

        兼容任意边类型（不再局限于 RELATES_TO），适用于医疗知识图谱的
        has_symptom / recommand_drug / do_eat / no_eat / need_check 等真实边类型。
        同时返回邻居节点的简短描述，供上下文组装使用。
        """
        relations = []
        if not entity_names:
            return relations

        with self._session() as sess:
            try:
                res = sess.run("""
                    MATCH (n)
                    WHERE (n.name IN $names OR n.id IN $names)
                      AND NOT n:Chunk AND NOT n:Document
                    MATCH (n)-[r]->(m)
                    WHERE NOT m:Chunk AND NOT m:Document AND NOT m:Community
                    RETURN coalesce(n.name, n.id) AS source,
                           type(r)                AS rel_type,
                           coalesce(m.name, m.id) AS target,
                           labels(m)[0]           AS target_type,
                           coalesce(m.description, m.intro, '') AS target_desc,
                           r.description          AS rel_desc
                    LIMIT 200
                """, {"names": entity_names})
                for row in res:
                    relations.append({
                        "source":      row["source"],
                        "target":      row["target"],
                        "type":        row["rel_type"],
                        "target_type": row["target_type"],
                        "description": row.get("rel_desc") or "",
                        "target_desc": (row.get("target_desc") or "")[:120],
                    })
            except Exception as e:
                logger.warning(f"Get relations failed: {e}")

        return relations

    def _extract_query_terms(self, text: str) -> List[str]:
        """提取查询关键词（中英文混合），用于轻量级证据打分。"""
        if not text:
            return []
        terms = re.findall(r'[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{2,}', text)
        # 去重并保序
        seen = set()
        ordered = []
        for t in terms:
            key = t.lower()
            if key not in seen:
                seen.add(key)
                ordered.append(t)
        return ordered[:40]

    def _infer_medical_intent(self, question: str) -> Dict[str, bool]:
        """识别医疗问句意图，供关系重排加权使用。"""
        q = (question or '').lower()
        return {
            'ask_drug': any(k in q for k in ('用药', '药', '治疗', 'recommand_drug', 'common_drug')),
            'ask_check': any(k in q for k in ('检查', '检验', '化验', 'need_check')),
            'ask_symptom': any(k in q for k in ('症状', '表现', '体征', 'has_symptom')),
            'ask_diet': any(k in q for k in ('饮食', '吃', '忌口', 'do_eat', 'no_eat')),
        }

    def _select_anchor_entities(self, question: str, entities: List[Dict], intent: Dict[str, bool]) -> List[str]:
        """选择问题锚点实体（优先 Disease 且名称出现在问题中）。"""
        anchors: List[str] = []
        for e in entities or []:
            name = str(e.get('name') or '')
            etype = str(e.get('type') or '')
            if not name:
                continue
            if name in question and etype in ('Disease', '疾病'):
                anchors.append(name)

        # 如果没有 Disease 锚点，回退到名称直接命中的高分实体
        if not anchors:
            for e in entities or []:
                name = str(e.get('name') or '')
                if name and name in question and float(e.get('evidence_score') or 0.0) >= 0.55:
                    anchors.append(name)

        # 仍无锚点则取 top1 实体，避免完全失焦
        if not anchors and entities:
            anchors.append(str(entities[0].get('name') or ''))

        # 去重保序
        dedup = []
        seen = set()
        for a in anchors:
            if a and a not in seen:
                seen.add(a)
                dedup.append(a)
        return dedup[:3]

    def _get_anchor_relations(self, anchors: List[str], intent: Dict[str, bool], limit: int = 120) -> List[Dict]:
        """从锚点实体定向抓取关系，优先问题意图相关边类型。"""
        if not anchors:
            return []

        rel_types: List[str] = []
        if intent.get('ask_drug'):
            rel_types.extend(['recommand_drug', 'common_drug'])
        if intent.get('ask_check'):
            rel_types.append('need_check')
        if intent.get('ask_symptom'):
            rel_types.append('has_symptom')
        if intent.get('ask_diet'):
            rel_types.extend(['do_eat', 'no_eat'])
        rel_types = list(dict.fromkeys(rel_types))

        with self._session() as sess:
            try:
                if rel_types:
                    res = sess.run("""
                        MATCH (d)-[r]->(m)
                        WHERE coalesce(d.name, d.id) IN $anchors
                          AND type(r) IN $rel_types
                          AND NOT m:Chunk AND NOT m:Document AND NOT m:Community
                        RETURN coalesce(d.name, d.id) AS source,
                               type(r)                AS rel_type,
                               coalesce(m.name, m.id) AS target,
                               labels(m)[0]           AS target_type,
                               coalesce(m.description, m.intro, '') AS target_desc,
                               r.description          AS rel_desc
                        LIMIT $limit
                    """, {"anchors": anchors, "rel_types": rel_types, "limit": limit})
                else:
                    res = sess.run("""
                        MATCH (d)-[r]->(m)
                        WHERE coalesce(d.name, d.id) IN $anchors
                          AND NOT m:Chunk AND NOT m:Document AND NOT m:Community
                        RETURN coalesce(d.name, d.id) AS source,
                               type(r)                AS rel_type,
                               coalesce(m.name, m.id) AS target,
                               labels(m)[0]           AS target_type,
                               coalesce(m.description, m.intro, '') AS target_desc,
                               r.description          AS rel_desc
                        LIMIT $limit
                    """, {"anchors": anchors, "limit": limit})

                rows: List[Dict] = []
                for row in res:
                    rows.append({
                        "source": row["source"],
                        "target": row["target"],
                        "type": row["rel_type"],
                        "target_type": row["target_type"],
                        "description": row.get("rel_desc") or "",
                        "target_desc": (row.get("target_desc") or "")[:120],
                    })
                return rows
            except Exception as e:
                logger.warning(f"Get anchor relations failed: {e}")
                return []

    def _rerank_chunks(self, question: str, chunk_candidates: List[Dict], entities: List[Dict], top_n: int = 20) -> List[Dict]:
        """基于关键词命中+实体命中+向量得分对 chunk 候选重排。"""
        if not chunk_candidates:
            return []

        q_terms = [t.lower() for t in self._extract_query_terms(question)]
        entity_names = [str(e.get('name') or '').strip() for e in (entities or []) if e.get('name')]

        ranked = []
        for c in chunk_candidates:
            text = str(c.get('text') or '')
            meta = c.get('metadata') or {}
            searchable = (text + ' ' + json.dumps(meta, ensure_ascii=False)).lower()

            kw_hit = 0.0
            if q_terms:
                hit_cnt = sum(1 for t in q_terms if t and t in searchable)
                kw_hit = min(hit_cnt / max(len(q_terms), 1), 1.0)

            ent_hit = 0.0
            if entity_names:
                ent_cnt = sum(1 for n in entity_names if n and n.lower() in searchable)
                ent_hit = min(ent_cnt / max(min(len(entity_names), 8), 1), 1.0)

            raw_score = c.get('score')
            semantic = 0.0
            if isinstance(raw_score, (int, float)):
                # 兼容距离分数和相似度分数：统一映射到 (0,1]
                semantic = 1.0 / (1.0 + abs(float(raw_score)))

            evidence_score = 0.45 * kw_hit + 0.35 * ent_hit + 0.20 * semantic
            new_c = dict(c)
            new_c['evidence_score'] = round(float(evidence_score), 4)
            ranked.append(new_c)

        ranked.sort(key=lambda x: x.get('evidence_score', 0.0), reverse=True)
        return ranked[:max(1, top_n)]

    def _rerank_entities(self, question: str, entities: List[Dict], chunk_candidates: List[Dict], top_n: int = 30) -> List[Dict]:
        """为实体打证据分并重排。"""
        if not entities:
            return []

        q_terms = [t.lower() for t in self._extract_query_terms(question)]
        chunk_text = ' '.join(str(c.get('text') or '') for c in (chunk_candidates or [])).lower()

        source_weight = {
            'question_match': 0.45,
            'vector_entity': 0.35,
            'chunk_mention': 0.30,
        }

        ranked = []
        for e in entities:
            name = str(e.get('name') or '')
            desc = str(e.get('description') or '')
            source = str(e.get('source') or '')
            searchable = (name + ' ' + desc).lower()

            score = source_weight.get(source, 0.20)

            # 名称直接命中问题
            if name and name in question:
                score += 0.30

            # 描述与问题关键词重叠
            if q_terms:
                overlap = sum(1 for t in q_terms if t in searchable)
                score += min(overlap / max(len(q_terms), 1), 1.0) * 0.20

            # 是否在召回 chunk 中被提及
            if name and name.lower() in chunk_text:
                score += 0.20

            if e.get('community_id') is not None:
                score += 0.05

            new_e = dict(e)
            new_e['evidence_score'] = round(float(score), 4)
            ranked.append(new_e)

        ranked.sort(key=lambda x: x.get('evidence_score', 0.0), reverse=True)

        # 去重（按 name）
        dedup = []
        seen = set()
        for e in ranked:
            n = str(e.get('name') or '')
            if not n or n in seen:
                continue
            seen.add(n)
            dedup.append(e)
            if len(dedup) >= max(1, top_n):
                break
        return dedup

    def _score_relations(
        self,
        question: str,
        relations: List[Dict],
        entities: List[Dict],
        top_n: int = 120,
        anchors: Optional[List[str]] = None,
        intent: Optional[Dict[str, bool]] = None,
    ) -> List[Dict]:
        """为关系边打证据分并排序。"""
        if not relations:
            return []

        q_terms = [t.lower() for t in self._extract_query_terms(question)]
        ent_score_map = {str(e.get('name') or ''): float(e.get('evidence_score') or 0.0) for e in (entities or [])}
        anchor_set = set(anchors or [])
        intent = intent or {}

        rel_type_boost = {
            'ask_drug': {'recommand_drug', 'common_drug'},
            'ask_check': {'need_check'},
            'ask_symptom': {'has_symptom'},
            'ask_diet': {'do_eat', 'no_eat'},
        }

        scored = []
        for r in relations:
            src = str(r.get('source') or '')
            tgt = str(r.get('target') or '')
            rel_type = str(r.get('type') or '')
            rel_desc = str(r.get('description') or '')
            tgt_desc = str(r.get('target_desc') or '')

            score = 0.10
            score += min(ent_score_map.get(src, 0.0), 1.0) * 0.35
            score += min(ent_score_map.get(tgt, 0.0), 1.0) * 0.25

            # 锚点约束：优先展示锚点实体发出的关系
            if anchor_set:
                if src in anchor_set:
                    score += 0.35
                elif tgt in anchor_set:
                    score += 0.08
                else:
                    score -= 0.18

            searchable = (rel_type + ' ' + rel_desc + ' ' + tgt_desc).lower()
            if q_terms:
                overlap = sum(1 for t in q_terms if t in searchable)
                score += min(overlap / max(len(q_terms), 1), 1.0) * 0.30

            # 意图约束：问题问什么就优先对应关系类型
            rel_type_l = rel_type.lower()
            for key, rel_set in rel_type_boost.items():
                if intent.get(key):
                    if rel_type_l in rel_set:
                        score += 0.30
                    else:
                        score -= 0.04

            new_r = dict(r)
            new_r['evidence_score'] = round(float(score), 4)
            scored.append(new_r)

        scored.sort(key=lambda x: x.get('evidence_score', 0.0), reverse=True)
        return scored[:max(1, top_n)]

    def _build_medical_structured_answer(self, intent: Dict[str, bool], anchors: List[str], relations: List[Dict]) -> str:
        """基于锚点关系生成结构化答案，减少无关链路对最终回答的干扰。"""
        if not anchors or not relations:
            return ""

        anchor_set = set(anchors)
        rels = [r for r in relations if str(r.get('source') or '') in anchor_set]
        if not rels:
            return ""

        def collect_by_types(type_set: set, limit: int = 12) -> List[str]:
            vals = []
            seen = set()
            for r in rels:
                rt = str(r.get('type') or '').lower()
                tgt = str(r.get('target') or '').strip()
                if rt in type_set and tgt and tgt not in seen:
                    seen.add(tgt)
                    vals.append(tgt)
                    if len(vals) >= limit:
                        break
            return vals

        anchor_name = anchors[0]
        drugs = collect_by_types({'recommand_drug', 'common_drug'}, limit=15)
        checks = collect_by_types({'need_check'}, limit=10)
        symptoms = collect_by_types({'has_symptom'}, limit=10)
        do_eat = collect_by_types({'do_eat'}, limit=10)
        no_eat = collect_by_types({'no_eat'}, limit=10)

        lines = [f"基于知识图谱中与“{anchor_name}”直接相关的证据："]

        # 根据问题意图优先展示对应信息
        if intent.get('ask_drug') and drugs:
            lines.append("推荐用药：" + "、".join(drugs))
        if intent.get('ask_check') and checks:
            lines.append("建议检查：" + "、".join(checks))
        if intent.get('ask_symptom') and symptoms:
            lines.append("常见症状：" + "、".join(symptoms))
        if intent.get('ask_diet'):
            if do_eat:
                lines.append("宜食：" + "、".join(do_eat))
            if no_eat:
                lines.append("忌食：" + "、".join(no_eat))

        # 如果问题意图不明确，给出综合摘要
        if len(lines) == 1:
            if drugs:
                lines.append("相关用药：" + "、".join(drugs[:10]))
            if checks:
                lines.append("相关检查：" + "、".join(checks[:8]))
            if symptoms:
                lines.append("相关症状：" + "、".join(symptoms[:8]))

        if len(lines) == 1:
            return ""

        lines.append("以上结果来自图谱关系证据，仅供医学参考。")
        return "\n".join(lines)
    
    def _build_local_search_context(self, chunks: List[Dict], entities: List[Dict],
                                     relations: List[Dict], community_context: List[Dict]) -> str:
        """构建 Local Search 的上下文

        优先级：实体信息 → 实体关系（含邻居描述） → 社区报告 → 原文片段
        关系信息按源实体分组展示，便于 LLM 理解医疗知识图谱结构。
        """
        context_parts = []

        # 1. 实体信息
        if entities:
            entity_lines = ["【相关实体】"]
            for e in entities[:12]:
                desc = f"：{e['description'][:120]}" if e.get('description') else ""
                entity_lines.append(f"• [{e.get('type', '?')}] {e['name']}{desc}")
            context_parts.append("\n".join(entity_lines))

        # 2. 关系信息（按源实体分组，每组列出所有连出的关系+邻居简介）
        if relations:
            from collections import defaultdict
            grouped: dict = defaultdict(list)
            for r in relations[:200]:
                grouped[r['source']].append(r)
            rel_lines = ["【知识图谱关系】"]
            for src, rels in list(grouped.items())[:10]:
                rel_lines.append(f"▶ {src}")
                for r in rels[:15]:
                    target_info = r['target']
                    if r.get('target_desc'):
                        target_info += f"（{r['target_desc'][:80]}）"
                    rel_lines.append(f"   -{r['type']}→ {target_info}")
            context_parts.append("\n".join(rel_lines))

        # 3. 社区上下文（包含报告文本，如有）
        if community_context:
            comm_lines = ["【社区概览】"]
            for c in community_context:
                report = c.get("report", "")
                if report:
                    comm_lines.append(f"• 社区 {c['community_id']} 摘要：{report[:300]}")
                else:
                    members = "、".join(c.get("members", [])[:10])
                    comm_lines.append(f"• 社区 {c['community_id']} 成员：{members}")
            context_parts.append("\n".join(comm_lines))

        # 4. 原文片段（有 :Chunk 节点时才有内容）
        if chunks:
            chunk_lines = ["【原文片段】"]
            for idx, c in enumerate(chunks[:5], 1):
                text = c.get("text", "")[:500]
                score_info = f" (相似度: {c['score']:.3f})" if c.get('score') else ""
                chunk_lines.append(f"[{idx}]{score_info}: {text}")
            context_parts.append("\n".join(chunk_lines))

        return "\n\n".join(context_parts)

    # ========== Phase 2: 社区检测 (Leiden Algorithm) ==========
    
    def detect_communities(self, write_property: bool = True, mode: str = 'auto') -> Dict[str, Any]:
        """使用 Leiden 算法检测节点社区

        需要安装 Neo4j Graph Data Science (GDS) 插件

        Args:
            write_property: 是否将 community_id 写回节点属性
            mode: 检测模式
                'entity' — 仅对 :Entity 节点（GraphRAG 文档摄入产生的实体）
                'full'   — 对全图所有领域节点（排除 Chunk/Document），适合医疗/知识图谱等领域数据库
                'auto'   — 自动判断：若 Entity < 50 则回退到 full 模式

        Returns:
            {"success": bool, "communities": [...], "total_communities": int, "total_nodes": int, "mode_used": str}
        """
        with self._session() as sess:
            try:
                GRAPH_NAME = 'kgCommunityGraph'

                # ── 自动选择模式 ──
                entity_count = sess.run("MATCH (e:Entity) RETURN count(e) as cnt").single()["cnt"]
                if mode == 'auto':
                    mode = 'entity' if entity_count >= 50 else 'full'
                    logger.info(f"社区检测模式自动选择: {mode}（Entity 节点数={entity_count}）")

                # ── 删除旧投影 ──
                try:
                    sess.run(f"CALL gds.graph.drop('{GRAPH_NAME}', false)")
                except Exception:
                    pass

                if mode == 'entity':
                    # ────── Entity 模式（原有逻辑）──────
                    if entity_count < 2:
                        return {"success": False, "error": f"Entity 节点不足 2 个（当前 {entity_count}），无法检测社区"}

                    # 补充共现关系
                    rel_count = sess.run("MATCH (:Entity)-[r:RELATES_TO|CO_OCCURS]->(:Entity) RETURN count(r) as cnt").single()["cnt"]
                    if rel_count == 0:
                        logger.warning("Entity 间无关系，基于 Chunk 共现建立隐式关系")
                        sess.run("""
                            MATCH (c:Chunk)-[:MENTIONS]->(e1:Entity)
                            MATCH (c)-[:MENTIONS]->(e2:Entity)
                            WHERE elementId(e1) < elementId(e2)
                            MERGE (e1)-[r:CO_OCCURS]->(e2)
                            ON CREATE SET r.weight = 1
                            ON MATCH SET r.weight = r.weight + 1
                        """)

                    has_relates  = sess.run("MATCH (:Entity)-[:RELATES_TO]->(:Entity)  RETURN count(*) > 0 as has").single()["has"]
                    has_co_occurs = sess.run("MATCH (:Entity)-[:CO_OCCURS]->(:Entity)  RETURN count(*) > 0 as has").single()["has"]
                    rel_configs = []
                    if has_relates:   rel_configs.append("RELATES_TO: {orientation: 'UNDIRECTED'}")
                    if has_co_occurs: rel_configs.append("CO_OCCURS:  {orientation: 'UNDIRECTED'}")
                    if not rel_configs:
                        return {"success": False, "error": "Entity 节点之间无可用关系，无法检测社区"}

                    project_query = f"CALL gds.graph.project('{GRAPH_NAME}', 'Entity', {{{', '.join(rel_configs)}}})"
                    sess.run(project_query)
                    node_where = "n:Entity"

                else:
                    # ────── Full 模式（领域知识图谱） ──────
                    # 获取所有非 Chunk/Document 标签
                    all_labels_raw = sess.run(
                        "CALL db.labels() YIELD label "
                        "WITH label "
                        "WHERE NOT label IN ['Chunk','Document','Community'] "
                        "RETURN label"
                    ).data()
                    domain_labels = [r['label'] for r in all_labels_raw]
                    if not domain_labels:
                        return {"success": False, "error": "没有找到可用的领域节点标签"}

                    total_nodes = sess.run(
                        "MATCH (n) WHERE NOT n:Chunk AND NOT n:Document AND NOT n:Community "
                        "RETURN COUNT(n) as cnt"
                    ).single()["cnt"]
                    if total_nodes < 2:
                        return {"success": False, "error": f"可用节点不足 2 个（当前 {total_nodes}）"}

                    # 获取这些节点之间的所有关系类型
                    all_rel_raw = sess.run(
                        "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
                    ).data()
                    all_rels = [r['relationshipType'] for r in all_rel_raw
                                if r['relationshipType'] not in ('HAS_CHUNK', 'CONTAINS', 'MENTIONS')]

                    # 使用 Cypher 投影以排除 Chunk/Document 节点
                    node_query = (
                        "MATCH (n) WHERE NOT n:Chunk AND NOT n:Document AND NOT n:Community "
                        "RETURN id(n) AS id"
                    )
                    edge_query = (
                        "MATCH (a)-[r]->(b) "
                        "WHERE NOT a:Chunk AND NOT a:Document AND NOT b:Chunk AND NOT b:Document "
                        "  AND NOT a:Community AND NOT b:Community "
                        "RETURN id(a) AS source, id(b) AS target"
                    )
                    project_query = (
                        f"CALL gds.graph.project.cypher("
                        f"  '{GRAPH_NAME}', "
                        f"  '{node_query}', "
                        f"  '{edge_query}'"
                        f")"
                    )
                    logger.info(f"Full 模式 GDS 投影: {len(domain_labels)} 个标签, {len(all_rels)} 种关系类型")
                    sess.run(project_query)
                    node_where = "NOT n:Chunk AND NOT n:Document AND NOT n:Community"

                # ── 运行 Leiden ──
                if write_property:
                    algorithm_used = None
                    community_count = 0
                    modularity = None

                    # 优先 Leiden；若插件版本/图方向不兼容，自动回退 Louvain，再回退 LabelPropagation。
                    algo_attempts = [
                        (
                            "leiden",
                            f"""
                            CALL gds.leiden.write('{GRAPH_NAME}', {{writeProperty: 'community_id'}})
                            YIELD communityCount, modularity
                            RETURN communityCount, modularity
                            """,
                        ),
                        (
                            "louvain",
                            f"""
                            CALL gds.louvain.write('{GRAPH_NAME}', {{writeProperty: 'community_id'}})
                            YIELD communityCount, modularity
                            RETURN communityCount, modularity
                            """,
                        ),
                        (
                            "label_propagation",
                            f"""
                            CALL gds.labelPropagation.write('{GRAPH_NAME}', {{writeProperty: 'community_id'}})
                            YIELD communityCount
                            RETURN communityCount, null AS modularity
                            """,
                        ),
                    ]

                    last_err = None
                    for algo_name, algo_query in algo_attempts:
                        try:
                            algo_result = sess.run(algo_query)
                            stats = algo_result.single()
                            community_count = stats["communityCount"] or 0
                            modularity = stats.get("modularity") if hasattr(stats, "get") else stats["modularity"]
                            algorithm_used = algo_name
                            logger.info(f"社区检测算法 {algo_name} 完成: {community_count} 个社区, modularity={modularity}")
                            break
                        except Exception as algo_err:
                            last_err = str(algo_err)
                            logger.warning(f"社区检测算法 {algo_name} 失败，将尝试回退算法: {algo_err}")

                    if algorithm_used is None:
                        return {
                            "success": False,
                            "error": "社区检测失败：Leiden/Louvain/LabelPropagation 均不可用，请检查 Neo4j GDS 插件版本与配置。",
                            "detail": last_err,
                        }

                # ── 获取社区概览 ──
                communities_result = sess.run(f"""
                    MATCH (n)
                    WHERE {node_where} AND n.community_id IS NOT NULL
                    RETURN n.community_id AS community_id,
                           collect(coalesce(n.name, n.id, elementId(n)))[..10] AS members,
                           count(n) AS size
                    ORDER BY size DESC
                    LIMIT 200
                """)
                communities = [
                    {"community_id": row["community_id"], "members": row["members"], "size": row["size"]}
                    for row in communities_result
                ]

                # ── 清理投影 ──
                try:
                    sess.run(f"CALL gds.graph.drop('{GRAPH_NAME}', false)")
                except Exception:
                    pass

                return {
                    "success": True,
                    "communities": communities,
                    "total_communities": len(communities),
                    "total_nodes": entity_count if mode == 'entity' else total_nodes,
                    "mode_used": mode,
                    "algorithm_used": algorithm_used if write_property else None,
                    "modularity": modularity if write_property else None,
                }

            except Exception as e:
                error_msg = str(e)
                try:
                    sess.run(f"CALL gds.graph.drop('kgCommunityGraph', false)")
                except Exception:
                    pass
                if "Unknown function" in error_msg or "gds" in error_msg.lower() or "No value present" in error_msg:
                    return {
                        "success": False,
                        "error": "Neo4j GDS 插件未安装、版本不兼容或图投影配置不满足算法要求。请检查 Graph Data Science 插件和关系方向配置。",
                        "detail": error_msg,
                    }
                logger.error(f"Community detection failed: {e}")
                import traceback; traceback.print_exc()
                return {"success": False, "error": error_msg}

    def get_community_entities(self, community_id: int) -> List[Dict[str, Any]]:
        """获取指定社区的所有节点（支持 Entity 节点或领域节点）"""
        with self._session() as sess:
            result = sess.run("""
                MATCH (n)
                WHERE n.community_id = $cid AND NOT n:Chunk AND NOT n:Document AND NOT n:Community
                OPTIONAL MATCH (n)-[r]-(other)
                WHERE other.community_id = $cid AND NOT other:Chunk AND NOT other:Document
                RETURN
                    coalesce(n.name, n.id, elementId(n)) AS name,
                    labels(n)[0] AS type,
                    coalesce(n.description, n.intro, n.content, '') AS description,
                    collect(DISTINCT {
                        target: coalesce(other.name, other.id, elementId(other)),
                        rel_type: type(r)
                    })[..8] AS relations
                LIMIT 200
            """, {"cid": community_id})

            entities = []
            for row in result:
                entities.append({
                    "name": row["name"],
                    "type": row["type"],
                    "description": row["description"],
                    "relations": [r for r in row["relations"] if r and r.get("target")],
                })
            return entities

    def generate_community_report(self, community_id: int) -> Dict[str, Any]:
        """为指定社区生成 LLM 摘要报告（支持 Entity 节点和领域节点）"""
        if not self.llm:
            return {"success": False, "error": "LLM not available"}

        active_db = (self._database_ctx.get() or '').strip() or None

        entities = self.get_community_entities(community_id)
        if not entities:
            return {"success": False, "error": f"Community {community_id} has no nodes"}

        entity_info = []
        for e in entities:
            info = f"- {e['name']} ({e['type']}): {e['description'] or '无描述'}"
            if e['relations']:
                rels = ", ".join([
                    f"{r['rel_type']}->{r['target']}"
                    for r in e['relations'][:5]
                    if r.get('target')
                ])
                if rels:
                    info += f" [关系: {rels}]"
            entity_info.append(info)

        prompt = f"""请为以下知识社区生成一份简洁的摘要报告。

【社区节点】
{chr(10).join(entity_info[:60])}

【要求】
1. 总结这个社区的核心主题（1-2句话）
2. 列出关键节点及其重要性
3. 描述节点之间的主要关系模式
4. 总字数不超过300字

请输出摘要报告："""

        try:
            from langchain_core.messages import HumanMessage
            response = self.llm.llm.invoke([HumanMessage(content=prompt)])
            report = response.content.strip()

            with self._session() as sess:
                sess.run("""
                    MERGE (c:Community {community_id: $cid, database: $database})
                    SET c.report = $report,
                        c.updated_at = datetime(),
                        c.entity_count = $count,
                        c.node_count = $count
                """, {
                    "cid": community_id,
                    "database": active_db or "default",
                    "report": report,
                    "count": len(entities)
                })

            return {
                "success": True,
                "community_id": community_id,
                "report": report,
                "entity_count": len(entities),
            }
        except Exception as e:
            logger.error(f"Generate community report failed: {e}")
            return {"success": False, "error": str(e)}

    def generate_all_community_reports(self) -> Dict[str, Any]:
        """为所有社区生成报告（支持 Entity 节点和领域节点）"""
        with self._session() as sess:
            result = sess.run("""
                MATCH (n)
                WHERE n.community_id IS NOT NULL AND NOT n:Chunk AND NOT n:Document
                RETURN DISTINCT n.community_id AS cid
                ORDER BY cid
            """)
            community_ids = [row["cid"] for row in result]
        
        reports = []
        for cid in community_ids:
            report_result = self.generate_community_report(cid)
            if report_result.get("success"):
                reports.append(report_result)
        
        return {
            "success": True,
            "total_communities": len(community_ids),
            "generated_reports": len(reports),
            "reports": reports
        }

    # ========== Phase 3: Global Search (Map-Reduce 汇总搜索) ==========
    
    def global_search(self, question: str, max_communities: int = 10, 
                      include_intermediate: bool = False, doc_id: str = None, database: str = None) -> Dict[str, Any]:
        """Global Search: 基于社区报告的 Map-Reduce 汇总搜索
        
        适用于宏观性、总结性问题，如：
        - "这个故事的主要人物有哪些？"
        - "文档中涉及哪些主要组织？"
        - "整体来看，这些内容讲述了什么？"
        
        搜索流程:
        1. 获取所有社区及其报告
        2. Map 阶段：让 LLM 基于每个社区报告独立回答问题
        3. Reduce 阶段：汇总所有社区的回答，生成最终全局答案
        
        Args:
            question: 用户问题
            max_communities: 最多处理的社区数量（按大小排序）
            include_intermediate: 是否在结果中包含中间 Map 结果
            doc_id: 文档 ID，用于限定检索范围（可选）
            
        Returns:
            {
                "success": bool,
                "answer": str,  # 最终汇总答案
                "communities_used": int,
                "map_results": List[Dict],  # 如果 include_intermediate=True
                "coverage": Dict  # 覆盖统计
            }
        """
        result = {
            "success": True,
            "answer": "",
            "communities_used": 0,
            "map_results": [],
            "coverage": {},
            "fallback_used": None
        }
        
        if not self.llm:
            return {"success": False, "error": "LLM not available for Global Search"}
        
        # 1. 获取所有社区报告（可选：按 doc_id 过滤）
        communities = self._get_all_community_reports(max_communities, doc_id=doc_id)
        
        if not communities:
            # 如果没有社区报告，尝试先生成
            logger.info("No community reports found, attempting to generate...")
            gen_result = self.generate_all_community_reports()
            if gen_result.get("success") and gen_result.get("generated_reports", 0) > 0:
                communities = self._get_all_community_reports(max_communities, doc_id=doc_id)
        
        if not communities:
            fallback_payload = self._global_no_communities_fallback(question, doc_id)
            if fallback_payload:
                return fallback_payload
            return {
                "success": False, 
                "error": "没有可用的社区报告。请先运行社区检测 (detect_communities) 和报告生成 (generate_all_community_reports)。",
                "communities_used": 0,
                "map_results": [],
                "coverage": {},
                "fallback_used": "none"
            }
        
        result["communities_used"] = len(communities)
        result["coverage"] = {
            "total_communities": len(communities),
            "total_entities": sum(c.get("entity_count", 0) for c in communities)
        }
        
        # 2. Map 阶段：每个社区独立回答
        map_results = []
        for community in communities:
            map_answer = self._map_community_answer(question, community)
            map_results.append({
                "community_id": community["community_id"],
                "entity_count": community.get("entity_count", 0),
                "answer": map_answer,
                "has_relevant_info": self._has_relevant_info(map_answer)
            })
        
        if include_intermediate:
            result["map_results"] = map_results
        
        # 3. 过滤有相关信息的回答
        relevant_answers = [m for m in map_results if m["has_relevant_info"]]
        
        if not relevant_answers:
            # 优先尝试直接基于社区报告生成总结
            fallback_answer = self._summarize_communities(question, communities)
            if fallback_answer:
                result["answer"] = fallback_answer
                result["fallback_used"] = "community_summary"
                return result

            # 若社区报告不足，再回退到一次局部检索，确保至少提供片段级答案
            local_fallback = self.local_search(question, top_k=20, doc_id=doc_id)
            if local_fallback:
                answer_text = local_fallback.get("answer")
                if not answer_text:
                    answer_text = self._build_fallback_answer(
                        local_fallback.get("entities", []),
                        local_fallback.get("relations", []),
                        local_fallback.get("chunks", []),
                        question
                    )

                if answer_text:
                    result["answer"] = answer_text
                    result["fallback_used"] = "local_search"
                    result["local_context"] = {
                        "entities": local_fallback.get("entities", []),
                        "relations": local_fallback.get("relations", []),
                        "chunks": local_fallback.get("chunks", [])
                    }
                    return result

            result["answer"] = "根据现有的知识图谱社区信息，未能找到与问题直接相关的内容。"
            result["fallback_used"] = "none"
            return result
        
        # 4. Reduce 阶段：汇总生成最终答案
        final_answer = self._reduce_answers(question, relevant_answers)
        result["answer"] = final_answer
        
        return result
    
    def _get_all_community_reports(self, max_communities: int = 10, doc_id: str = None) -> List[Dict]:
        """获取所有社区及其报告，按实体数量降序排列
        
        Args:
            max_communities: 最多处理的社区数量
            doc_id: 文档 ID，用于过滤只包含该文档实体的社区（可选）
        """
        communities = []
        active_db = (self._database_ctx.get() or '').strip() or None
        
        with self._session() as sess:
            try:
                if doc_id:
                    # 如果指定了 doc_id，只获取包含该文档实体的社区
                    res = sess.run("""
                        MATCH (e:Entity)
                        WHERE e.doc_id = $doc_id AND e.community_id IS NOT NULL
                        WITH DISTINCT e.community_id AS cid
                        MATCH (c:Community {community_id: cid})
                        WHERE c.report IS NOT NULL AND c.database = $database
                        RETURN c.community_id AS community_id, c.report AS report, 
                               c.entity_count AS entity_count, c.updated_at AS updated_at
                        ORDER BY c.entity_count DESC
                        LIMIT $limit
                    """, {"doc_id": doc_id, "limit": max_communities, "database": active_db or "default"})
                else:
                    # 获取有报告的社区
                    res = sess.run("""
                        MATCH (c:Community)
                        WHERE c.report IS NOT NULL AND c.database = $database
                        RETURN c.community_id AS community_id, c.report AS report, 
                               c.entity_count AS entity_count, c.updated_at AS updated_at
                        ORDER BY c.entity_count DESC
                        LIMIT $limit
                    """, {"limit": max_communities, "database": active_db or "default"})
                
                for row in res:
                    communities.append({
                        "community_id": row["community_id"],
                        "report": row["report"],
                        "entity_count": row["entity_count"] or 0
                    })
                
                # 如果没有 Community 节点但有带 community_id 的实体（Entity 或领域节点），也尝试获取
                if not communities:
                    if doc_id:
                        res = sess.run("""
                            MATCH (e:Entity)
                            WHERE e.community_id IS NOT NULL AND e.doc_id = $doc_id
                            WITH e.community_id AS cid, collect(e) AS entities
                            RETURN cid AS community_id, size(entities) AS entity_count,
                                   [e IN entities | e.name + ': ' + coalesce(e.description, '')] AS entity_info
                            ORDER BY entity_count DESC
                            LIMIT $limit
                        """, {"doc_id": doc_id, "limit": max_communities})
                    else:
                        res = sess.run("""
                            MATCH (e:Entity)
                            WHERE e.community_id IS NOT NULL
                            WITH e.community_id AS cid, collect(e) AS entities
                            RETURN cid AS community_id, size(entities) AS entity_count,
                                   [e IN entities | e.name + ': ' + coalesce(e.description, '')] AS entity_info
                            ORDER BY entity_count DESC
                            LIMIT $limit
                        """, {"limit": max_communities})
                    
                    for row in res:
                        # 构建简单的实体列表作为报告
                        entity_info = row["entity_info"][:20]  # 限制数量
                        report = "社区成员: " + "; ".join(entity_info)
                        communities.append({
                            "community_id": row["community_id"],
                            "report": report,
                            "entity_count": row["entity_count"]
                        })

                # 第三级 fallback：查询领域节点（Disease/Drug 等，非 Entity/Chunk/Document/Community）
                if not communities:
                    res = sess.run("""
                        MATCH (n)
                        WHERE n.community_id IS NOT NULL
                          AND NOT n:Chunk AND NOT n:Document AND NOT n:Community
                        WITH n.community_id AS cid,
                             collect(n)[..30] AS members,
                             count(n) AS cnt
                        RETURN cid AS community_id, cnt AS entity_count,
                               [m IN members |
                                   coalesce(labels(m)[0], '') + '|' +
                                   coalesce(m.name, m.id, '') +
                                   CASE WHEN m.description IS NOT NULL
                                        THEN ': ' + substring(m.description, 0, 80)
                                        ELSE '' END
                               ] AS entity_info
                        ORDER BY cnt DESC
                        LIMIT $limit
                    """, {"limit": max_communities})
                    for row in res:
                        entity_info_list = [x for x in (row["entity_info"] or []) if x][:20]
                        report = "社区成员（领域节点）: " + "; ".join(entity_info_list)
                        communities.append({
                            "community_id": row["community_id"],
                            "report": report,
                            "entity_count": row["entity_count"] or 0
                        })
                        
            except Exception as e:
                logger.error(f"Failed to get community reports: {e}")
        
        return communities
    
    def _map_community_answer(self, question: str, community: Dict) -> str:
        """Map 阶段：基于单个社区报告回答问题"""
        if not self.llm:
            return ""
        
        community_report = community.get("report", "")
        community_id = community.get("community_id", "未知")
        
        prompt = f"""基于以下社区知识，回答用户问题。如果社区知识与问题无关，请回答"该社区信息与问题无关"。

【社区 {community_id} 的知识摘要】
{community_report}

【用户问题】
{question}

【要求】
1. 仅基于上述社区知识回答
2. 如果信息不足或无关，明确说明
3. 回答简洁，不超过100字

请回答："""
        
        try:
            from langchain_core.messages import HumanMessage
            response = self.llm.llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.error(f"Map phase failed for community {community_id}: {e}")
            return ""
    
    def _has_relevant_info(self, answer: str) -> bool:
        """判断 Map 阶段的回答是否包含相关信息"""
        if not answer:
            return False
        
        # 检查是否包含"无关"、"不相关"等关键词
        irrelevant_keywords = [
            "无关", "不相关", "没有相关", "未提及", "没有提到",
            "信息不足", "无法回答", "不确定", "没有发现"
        ]
        
        answer_lower = answer.lower()
        for kw in irrelevant_keywords:
            if kw in answer_lower:
                return False
        
        # 回答太短也认为无关
        if len(answer) < 10:
            return False
        
        return True
    
    def _reduce_answers(self, question: str, map_results: List[Dict]) -> str:
        """Reduce 阶段：汇总所有社区的回答，生成最终答案"""
        if not self.llm:
            return ""
        
        # 构建所有社区回答的汇总
        answers_text = []
        for idx, m in enumerate(map_results, 1):
            answers_text.append(f"[社区 {m['community_id']}] ({m['entity_count']} 个实体)\n{m['answer']}")
        
        combined_answers = "\n\n".join(answers_text)
        
        prompt = f"""请综合以下多个知识社区的回答，生成一个完整、连贯的最终答案。

【用户问题】
{question}

【各社区的回答】
{combined_answers}

【要求】
1. 整合各社区的相关信息
2. 去除重复内容
3. 保持答案的完整性和连贯性
4. 如果各社区信息有冲突，指出差异
5. 回答应该全面但简洁

请输出最终答案："""
        
        try:
            from langchain_core.messages import HumanMessage
            response = self.llm.llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.error(f"Reduce phase failed: {e}")
            # 如果 Reduce 失败，返回拼接的结果
            return f"（汇总失败，以下是各社区回答）\n\n{combined_answers}"
    
    def _summarize_communities(self, question: str, communities: List[Dict]) -> str:
        """当 Map 阶段无相关回答时，直接基于社区摘要生成答案"""
        if not self.llm or not communities:
            return ""

        summaries = []
        for community in communities:
            report = (community.get("report") or "").strip()
            if not report:
                continue
            truncated_report = report if len(report) <= 800 else report[:800] + "..."
            summaries.append(
                f"社区 {community.get('community_id', '未知')} (包含 {community.get('entity_count', 0)} 个实体)\n"
                f"{truncated_report}"
            )
            if len(summaries) >= 8:  # 控制 prompt 长度
                break

        if not summaries:
            return ""

        combined_reports = "\n\n".join(summaries)
        prompt = f"""以下是若干知识社区的摘要。请综合这些信息回答用户的问题，即便部分社区未直接覆盖问题要点，也请给出最可能的总结。\n\n【用户问题】\n{question}\n\n【社区摘要】\n{combined_reports}\n\n【要求】\n1. 结合所有社区的关键信息进行总结\n2. 如果信息不足，明确说明缺失内容并提供可能的方向\n3. 回答保持在 200 字以内，突出主要实体或主题\n\n请输出最终答案："""

        try:
            from langchain_core.messages import HumanMessage
            response = self.llm.llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.error(f"Community summary fallback failed: {e}")
            return ""

    def _global_no_communities_fallback(self, question: str, doc_id: str = None) -> Optional[Dict[str, Any]]:
        """Global Search fallback when no communities/reports exist"""
        try:
            active_db = (self._database_ctx.get() or '').strip() or None
            local_result = self.local_search(question, top_k=20, doc_id=doc_id, database=active_db)
        except Exception as exc:
            logger.warning(f"Local search fallback during global search failed: {exc}")
            return None

        if not isinstance(local_result, dict):
            return None

        answer_text = local_result.get("answer", "") or self._build_fallback_answer(
            local_result.get("entities", []) or [],
            local_result.get("relations", []) or [],
            local_result.get("chunks", []) or [],
            question
        )

        if not answer_text:
            return None

        return {
            "success": True,
            "answer": answer_text,
            "communities_used": 0,
            "map_results": [],
            "coverage": {"total_communities": 0, "total_entities": 0},
            "fallback_used": "local_search_no_community",
            "local_context": {
                "entities": local_result.get("entities", []),
                "relations": local_result.get("relations", []),
                "chunks": local_result.get("chunks", [])
            }
        }
    
    def hybrid_search(self, question: str, top_k: int = 20, 
                      strategy: str = "auto", chat_history: list = None, doc_id: str = None, database: str = None) -> Dict[str, Any]:
        """混合搜索：自动选择或组合 Local Search 和 Global Search
        
        Args:
            question: 用户问题
            top_k: Local Search 的候选数量
            strategy: 搜索策略
                - "auto": 自动判断使用哪种搜索
                - "local": 只使用 Local Search
                - "global": 只使用 Global Search
                - "both": 同时使用两种，合并结果
            chat_history: 对话历史 [{"role": "user"|"assistant", "content": str}, ...]
            doc_id: 文档 ID，用于限定检索范围（可选）
                
        Returns:
            {
                "success": bool,
                "strategy_used": str,
                "answer": str,
                "local_result": Dict,  # 如果使用了 Local Search
                "global_result": Dict  # 如果使用了 Global Search
            }
        """
        result = {
            "success": True,
            "strategy_used": strategy,
            "answer": ""
        }
        
        # 构建带上下文的问题
        enhanced_question = self._build_question_with_history(question, chat_history)
        
        # 自动判断策略
        if strategy == "auto":
            strategy = self._determine_search_strategy(question)
            result["strategy_used"] = strategy
        
        local_result = None
        global_result = None
        active_db = (database or self._database_ctx.get() or '').strip() or None
        
        if strategy in ("local", "both"):
            local_result = self.local_search(enhanced_question, top_k=top_k, doc_id=doc_id, database=active_db)
            result["local_result"] = local_result
        
        if strategy in ("global", "both"):
            global_result = self.global_search(enhanced_question, doc_id=doc_id, database=active_db)
            result["global_result"] = global_result
        
        # 生成最终答案
        if strategy == "local" and local_result:
            answer = local_result.get("answer", "")
            if answer:  # 只有有效答案才使用
                result["answer"] = answer
            else:
                # Local Search 返回空答案，尝试使用附加信息
                result["answer"] = self._build_fallback_answer(
                    local_result.get("entities", []),
                    local_result.get("relations", []),
                    local_result.get("chunks", []),
                    question
                )
        elif strategy == "global" and global_result:
            answer = global_result.get("answer", "")
            if answer:
                result["answer"] = answer
            else:
                result["answer"] = "根据全局搜索，未能从社区知识中找到相关信息。"
        elif strategy == "both" and local_result and global_result:
            local_answer = local_result.get("answer", "")
            global_answer = global_result.get("answer", "")
            
            # 如果两个答案都为空，使用回退方案
            if not local_answer and not global_answer:
                result["answer"] = self._build_fallback_answer(
                    local_result.get("entities", []),
                    local_result.get("relations", []),
                    local_result.get("chunks", []),
                    question
                )
            # 如果其中一个为空，使用非空的
            elif not local_answer:
                result["answer"] = global_answer
            elif not global_answer:
                result["answer"] = local_answer
            # 两个都有，合并
            else:
                result["answer"] = self._merge_search_answers(
                    question,
                    local_answer,
                    global_answer
                )
        
        # 最终检查：如果答案仍为空，返回友好提示
        if not result["answer"]:
            result["answer"] = "抱歉，未能为您的问题生成答案。请尝试换个问题或调整搜索策略。"
        
        return result
    
    def _build_question_with_history(self, question: str, chat_history: list = None) -> str:
        """将对话历史整合到问题中，使用 LangChain ConversationSummaryBufferMemory 进行优化
        
        Args:
            question: 当前用户问题
            chat_history: 对话历史列表
            
        Returns:
            增强后的问题（包含对话上下文）
        """
        if not chat_history or len(chat_history) == 0:
            return question
            
        try:
            from langchain.memory import ConversationSummaryBufferMemory
            from langchain_community.chat_message_histories import ChatMessageHistory
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
            
            # 1. Populate ChatMessageHistory
            history = ChatMessageHistory()
            for msg in chat_history:
                role = msg.get("role")
                content = msg.get("content")
                if role == "user":
                    history.add_user_message(content)
                elif role == "assistant":
                    history.add_ai_message(content)
            
            # 2. Initialize Memory with LLM
            # max_token_limit: 当历史记录超过此 token 数时触发摘要
            # 这里的 llm 使用 self.llm.llm (ChatOpenAI 实例)
            if not self.llm or not hasattr(self.llm, 'llm'):
                raise ValueError("LLM not initialized")
                
            memory = ConversationSummaryBufferMemory(
                llm=self.llm.llm,
                chat_memory=history,
                max_token_limit=10000,  # 设置为 10000 token，可根据需求调整
                return_messages=True
            )
            
            # 3. Prune memory (Trigger summarization if needed)
            # 这会修改 history.messages 并更新 memory.moving_summary_buffer
            memory.prune()
            
            # 4. Get processed messages
            buffer_messages = memory.load_memory_variables({})["history"]
            
            # 5. Format messages
            history_parts = []
            for msg in buffer_messages:
                if isinstance(msg, SystemMessage):
                    history_parts.append(f"【之前的对话摘要】: {msg.content}")
                elif isinstance(msg, HumanMessage):
                    history_parts.append(f"用户: {msg.content}")
                elif isinstance(msg, AIMessage):
                    history_parts.append(f"助手: {msg.content}")
            
            if not history_parts:
                return question
                
            history_text = "\n".join(history_parts)
            
            enhanced_question = f"""以下是之前的对话历史（可能包含摘要）：
{history_text}

基于以上对话上下文，用户现在的问题是：{question}

请结合对话历史来理解和回答这个问题。如果问题中有代词或省略（如"他"、"这个"、"上面提到的"等），请根据对话历史来解析其具体指代。"""
            
            return enhanced_question

        except Exception as e:
            logger.warning(f"ConversationSummaryBufferMemory failed, falling back to simple truncation: {e}")
            return self._build_question_with_history_fallback(question, chat_history)

    def _build_question_with_history_fallback(self, question: str, chat_history: list = None) -> str:
        """(Fallback) 将对话历史整合到问题中，用于更好的上下文理解
        
        Args:
            question: 当前用户问题
            chat_history: 对话历史列表
            
        Returns:
            增强后的问题（包含对话上下文）
        """
        if not chat_history or len(chat_history) == 0:
            return question
        
        # 限制历史长度，避免上下文过长
        max_history = 6  # 最多保留最近 6 轮对话
        recent_history = chat_history[-max_history:]
        
        # 构建对话历史字符串
        history_parts = []
        for msg in recent_history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                history_parts.append(f"用户: {content}")
            elif role == "assistant":
                # 截取助手回答的前200个字符，避免上下文过长
                truncated = content[:200] + "..." if len(content) > 200 else content
                history_parts.append(f"助手: {truncated}")
        
        if not history_parts:
            return question
        
        # 组合成带上下文的问题
        history_text = "\n".join(history_parts)
        enhanced_question = f"""以下是之前的对话历史：
{history_text}

基于以上对话上下文，用户现在的问题是：{question}

请结合对话历史来理解和回答这个问题。如果问题中有代词或省略（如"他"、"这个"、"上面提到的"等），请根据对话历史来解析其具体指代。"""
        
        return enhanced_question
    
    def _determine_search_strategy(self, question: str) -> str:
        """根据问题类型自动判断搜索策略
        
        Local Search 适合: 具体实体查询、关系查询、细节问题
        Global Search 适合: 总结性、宏观性、全局性问题
        """
        # 全局性问题的关键词
        global_keywords = [
            "所有", "全部", "总共", "一共", "多少",
            "总结", "概述", "整体", "全局", "宏观",
            "主要", "核心", "关键", "重要",
            "有哪些", "包括什么", "涉及哪些",
            "整个", "完整", "全面"
        ]
        
        # 局部性问题的关键词
        local_keywords = [
            "是谁", "是什么", "在哪", "什么时候",
            "为什么", "怎么", "如何",
            "之间", "关系", "相关"
        ]
        
        question_lower = question.lower()
        
        global_score = sum(1 for kw in global_keywords if kw in question_lower)
        local_score = sum(1 for kw in local_keywords if kw in question_lower)
        
        # 如果问题很短且包含实体名，倾向 Local
        if len(question) < 20:
            local_score += 1
        
        if global_score > local_score:
            return "global"
        elif local_score > global_score:
            return "local"
        else:
            # 默认使用 Local，因为它通常更精确
            return "local"
    
    def _build_fallback_answer(self, entities: List[Dict], relations: List[Dict], chunks: List[Dict], question: str) -> str:
        """当 LLM 生成失败时，基于原始数据构建回退答案"""
        answer_parts = []
        
        if entities:
            entity_names = [e.get('name', '未知') for e in entities[:10]]
            answer_parts.append(f"相关实体：{', '.join(entity_names)}")
        
        if relations:
            rel_desc = [f"{r.get('source', '')}-{r.get('type', '')}->{r.get('target', '')}" for r in relations[:5]]
            answer_parts.append(f"实体关系：{'; '.join(rel_desc)}")
        
        if chunks:
            chunk_text = chunks[0].get('text', '').strip()
            if len(chunk_text) > 200:
                chunk_text = chunk_text[:200] + "..."
            answer_parts.append(f"相关文本：{chunk_text}")
        
        if answer_parts:
            return "\n\n".join(answer_parts)
        else:
            return "抱歉，未能找到与您的问题相关的信息。"
    
    def _merge_search_answers(self, question: str, local_answer: str, global_answer: str) -> str:
        """合并 Local 和 Global 搜索的答案"""
        if not self.llm:
            return f"【Local Search 答案】\n{local_answer}\n\n【Global Search 答案】\n{global_answer}"
        
        prompt = f"""请综合以下两种搜索方式的答案，生成一个更完整的最终答案。

【用户问题】
{question}

【精确搜索答案】(基于具体实体和关系)
{local_answer}

【全局搜索答案】(基于社区知识汇总)
{global_answer}

【要求】
1. 整合两种答案的信息
2. 精确搜索的具体细节优先
3. 全局搜索的宏观信息作为补充
4. 保持答案简洁、完整

请输出最终答案："""
        
        try:
            from langchain_core.messages import HumanMessage
            response = self.llm.llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.error(f"Merge answers failed: {e}")
            return f"【Local Search 答案】\n{local_answer}\n\n【Global Search 答案】\n{global_answer}"

    def hybrid_search_stream(
        self,
        question: str,
        top_k: int = 20,
        strategy: str = "auto",
        chat_history: list = None,
        doc_id: str = None,
        database: str = None,
    ):
        """混合搜索流式版本 - 生成 SSE 事件字符串序列

        先产出一个 metadata 事件（包含实体/关系/chunk），
        再逐 token 产出 LLM 生成内容，最后产出 done 事件。

        每个 yield 都是完整的 SSE 行，格式为:
            data: <json>\\n\\n
        """
        import json as _json

        enhanced_question = self._build_question_with_history(question, chat_history or [])

        if strategy == "auto":
            strategy = self._determine_search_strategy(question)

        # --- 检索阶段（不调 LLM）---
        try:
            local_result = self.local_search(
                enhanced_question, top_k=top_k, doc_id=doc_id, database=database,
                return_context_only=True,
            )
        except Exception as e:
            logger.error(f"hybrid_search_stream retrieval failed: {e}")
            yield f"data: {_json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
            return

        context = local_result.pop('_context', '') or ''
        structured_fallback = local_result.pop('_structured_fallback', '') or ''

        # 1. 先推送元数据（实体 / 关系 / chunks / strategy_used）
        metadata_payload = {
            "type": "metadata",
            "strategy_used": strategy,
            "entities": local_result.get("entities", []),
            "relations": local_result.get("relations", []),
            "chunks": local_result.get("chunks", []),
            "communities_used": len(local_result.get("community_context", [])),
            "evidence": local_result.get("evidence", {}),
        }
        yield f"data: {_json.dumps(metadata_payload, ensure_ascii=False)}\n\n"

        # 2. 流式 LLM 生成
        if self.llm and context:
            total_tokens = 0
            try:
                for token in self.llm.generate_answer_stream(enhanced_question, context):
                    total_tokens += 1
                    yield f"data: {_json.dumps({'type': 'token', 'token': token}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"hybrid_search_stream LLM failed: {e}")
                # 用结构化兜底
                if structured_fallback:
                    yield f"data: {_json.dumps({'type': 'token', 'token': structured_fallback}, ensure_ascii=False)}\n\n"

            # 如果 LLM 没给出内容，用结构化答案补充
            if total_tokens == 0 and structured_fallback:
                yield f"data: {_json.dumps({'type': 'token', 'token': structured_fallback}, ensure_ascii=False)}\n\n"
        elif structured_fallback:
            yield f"data: {_json.dumps({'type': 'token', 'token': structured_fallback}, ensure_ascii=False)}\n\n"
        else:
            yield f"data: {_json.dumps({'type': 'token', 'token': '未能从知识库中找到相关信息。'}, ensure_ascii=False)}\n\n"

        yield f"data: {_json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    def delete_document(self, doc_id: str) -> Dict[str, Any]:
        """删除文档及其关联的图数据和向量数据"""
        try:
            # 1. 获取该文档所有 Chunk 的 vec_id
            vec_ids = []
            with self._session() as sess:
                result = sess.run("""
                    MATCH (c:Chunk)
                    WHERE c.doc_id = $doc_id
                    RETURN c.vec_id as vec_id
                """, {"doc_id": doc_id})
                vec_ids = [row["vec_id"] for row in result if row["vec_id"]]
            
            # 2. 从 PGVector 删除向量
            active_db = (self._database_ctx.get() or '').strip() or None
            vector_store, _ = self._get_vector_store(database=active_db)
            if vector_store and vec_ids:
                try:
                    if hasattr(vector_store, 'delete'):
                        vector_store.delete(vec_ids)
                        logger.info(f"Deleted {len(vec_ids)} vectors for doc {doc_id}")
                    else:
                        logger.warning("PGVector store does not support delete method")
                except Exception as e:
                    logger.error(f"Failed to delete vectors: {e}")

            # 3. 从 Neo4j 删除节点和关系
            with self._session() as sess:
                sess.run("""
                    MATCH (n)
                    WHERE n.doc_id = $doc_id OR n.source = $doc_id
                    DETACH DELETE n
                """, {"doc_id": doc_id})
            
            return {"success": True, "deleted_vectors": len(vec_ids)}
        except Exception as e:
            logger.error(f"Delete document failed: {e}")
            return {"success": False, "error": str(e)}

    def _sql_upsert_vector(self, table: str, vec_id: str, embedding: List[float], metadata: Dict[str, Any]):
        """Direct SQL upsert into an existing pgvector table.

        Expects table to have columns: id (text primary key), embedding (vector), metadata (jsonb)
        """
        if psycopg2 is None:
            raise RuntimeError('psycopg2 is required for SQL upsert fallback')
        db_url = os.environ.get('DATABASE_URL') or self.pg_conn
        if not db_url:
            raise RuntimeError('No DATABASE_URL available for SQL upsert')

        emb_str = '[' + ','.join(map(str, embedding)) + ']'
        meta_json = json.dumps(metadata, ensure_ascii=False)
        # allow configurable column names to support different schemas (e.g., langchain_pg_embedding)
        id_col = os.environ.get('PG_VECTOR_ID_COLUMN') or 'id'
        emb_col = os.environ.get('PG_VECTOR_EMBEDDING_COLUMN') or 'embedding'
        meta_col = os.environ.get('PG_VECTOR_METADATA_COLUMN') or 'metadata'

        # Build SQL with the chosen column names. Use ON CONFLICT on id_col — ensure the column has UNIQUE/PK in your table.
        sql = (
            f'INSERT INTO "{table}" ({id_col}, {emb_col}, {meta_col}) '
            f"VALUES (%s, %s::vector, %s::jsonb) ON CONFLICT ({id_col}) DO UPDATE SET {emb_col} = EXCLUDED.{emb_col}, {meta_col} = EXCLUDED.{meta_col};"
        )
        conn = None
        try:
            conn = psycopg2.connect(db_url)
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (vec_id, emb_str, meta_json))
        finally:
            if conn:
                conn.close()

    def cleanup_isolated_vectors(self, database: Optional[str] = None) -> Dict[str, Any]:
        """清理孤立向量：删除 PGVector 中存在但 Neo4j 中不存在的向量"""
        if not psycopg2:
            return {"success": False, "error": "psycopg2 module not found"}
        
        try:
            # 1. 获取 Neo4j 中所有有效的 vec_id
            valid_vec_ids = set()
            with self._use_database(database):
                with self._session() as sess:
                    result = sess.run("MATCH (c:Chunk) WHERE c.vec_id IS NOT NULL RETURN c.vec_id as vec_id")
                    for row in result:
                        valid_vec_ids.add(row["vec_id"])
            
            logger.info(f"Found {len(valid_vec_ids)} valid vector IDs in Neo4j")

            # 2. 连接 Postgres
            active_db = (database or self._database_ctx.get() or '').strip() or None
            active_collection = self.get_vector_collection_name(database=active_db)
            conn = psycopg2.connect(self.pg_conn)
            deleted_count = 0
            total_pg_vectors = 0
            
            try:
                with conn:
                    with conn.cursor() as cur:
                        # 获取 collection_id
                        cur.execute(
                            "SELECT uuid FROM kg_pg_collection WHERE name = %s", 
                            (active_collection,)
                        )
                        row = cur.fetchone()
                        if not row:
                            return {"success": True, "total_vectors": 0, "valid_vectors": len(valid_vec_ids), "deleted_isolated_vectors": 0}
                        collection_uuid = row[0]
                        
                        # 确定 ID 列名
                        cur.execute(
                            "SELECT column_name FROM information_schema.columns WHERE table_name = 'kg_pg_embedding'"
                        )
                        columns = [r[0] for r in cur.fetchall()]
                        
                        id_col = None
                        if 'custom_id' in columns:
                            id_col = 'custom_id'
                        elif 'id' in columns:
                            id_col = 'id'
                        
                        if not id_col:
                                return {"success": False, "error": f"Could not find ID column in kg_pg_embedding. Available columns: {columns}"}

                        logger.info(f"Using ID column: {id_col}")

                        # 获取该 collection 下所有向量 ID
                        cur.execute(
                            f"SELECT {id_col} FROM kg_pg_embedding WHERE collection_id = %s",
                            (collection_uuid,)
                        )
                        pg_vec_ids = [r[0] for r in cur.fetchall() if r[0] is not None]
                        total_pg_vectors = len(pg_vec_ids)
                        
                        # 找出孤立向量
                        isolated_ids = [vid for vid in pg_vec_ids if vid not in valid_vec_ids]
                        
                        if isolated_ids:
                            logger.info(f"Found {len(isolated_ids)} isolated vectors to delete")
                            # 批量删除
                            chunk_size = 1000
                            for i in range(0, len(isolated_ids), chunk_size):
                                batch = isolated_ids[i:i+chunk_size]
                                cur.execute(
                                    f"DELETE FROM kg_pg_embedding WHERE collection_id = %s AND {id_col} = ANY(%s)",
                                    (collection_uuid, batch)
                                )
                                deleted_count += cur.rowcount
                        else:
                            logger.info("No isolated vectors found")
                            
            finally:
                conn.close()
                
            return {
                "success": True, 
                "total_vectors": total_pg_vectors,
                "valid_vectors": len(valid_vec_ids),
                "deleted_isolated_vectors": deleted_count
            }
            
        except Exception as e:
            logger.error(f"Cleanup isolated vectors failed: {e}")
            return {"success": False, "error": str(e)}

    def cleanup_orphaned_chunks(self, database: Optional[str] = None) -> Dict[str, Any]:
        """清理孤立Chunk：删除 Neo4j 中没有对应向量的 Chunk 节点"""
        try:
            deleted_chunks = 0
            deleted_mentions = 0
            deleted_contains = 0
            
            with self._use_database(database):
                with self._session() as sess:
                    # 合并两条件：获取所有孤立Chunk
                    # 条件1: 没有 vec_id 或 vec_id 为空
                    # 条件2: 没有对应Document（CONTAINS关系）
                    result = sess.run("""
                        MATCH (c:Chunk)
                        WHERE (c.vec_id IS NULL OR c.vec_id = '')
                           OR NOT EXISTS { MATCH (d:Document)-[:CONTAINS]->(c) }
                        RETURN elementId(c) as chunk_id, c.doc_id as doc_id, c.idx as idx, c.vec_id as vec_id
                        LIMIT 10000
                    """)
                    orphaned = [row for row in result]
                
                if not orphaned:
                    logger.info("No orphaned chunks found")
                    return {
                        "success": True,
                        "deleted_chunks": 0,
                        "deleted_mentions": 0,
                        "deleted_contains": 0,
                        "total_checked": 0
                    }

                logger.info(f"Found {len(orphaned)} orphaned chunks to delete")

                # 删除这些 Chunk 的关系和节点
                for chunk in orphaned:
                    chunk_id = chunk["chunk_id"]

                    # 删除 MENTIONS 关系
                    result = sess.run("MATCH (c)-[r:MENTIONS]->() WHERE elementId(c)=$cid DELETE r", {"cid": chunk_id})
                    deleted_mentions += result.delete_relationships_deleted

                    # 删除 CONTAINS 关系
                    result = sess.run("MATCH ()-[r:CONTAINS]->(c) WHERE elementId(c)=$cid DELETE r", {"cid": chunk_id})
                    deleted_contains += result.delete_relationships_deleted

                    # 删除 Chunk 节点本身
                    result = sess.run("MATCH (c:Chunk) WHERE elementId(c)=$cid DELETE c", {"cid": chunk_id})
                    deleted_chunks += result.nodes_deleted
                
            return {
                "success": True,
                "deleted_chunks": deleted_chunks,
                "deleted_mentions": deleted_mentions,
                "deleted_contains": deleted_contains,
                "total_checked": len(orphaned),
                "summary": f"删除了 {deleted_chunks} 个孤立Chunk，以及 {deleted_mentions} 个MENTIONS关系和 {deleted_contains} 个CONTAINS关系"
            }
            
        except Exception as e:
            logger.error(f"Cleanup orphaned chunks failed: {e}")
            return {"success": False, "error": str(e)}

    def cleanup_chunks_without_vectors(self, database: Optional[str] = None) -> Dict[str, Any]:
        """更新元数据：统计没有向量的Chunk数量"""
        try:
            with self._use_database(database):
                with self._session() as sess:
                    # 获取所有没有vec_id的Chunk
                    result = sess.run("""
                        MATCH (c:Chunk)
                        WHERE c.vec_id IS NULL OR c.vec_id = ''
                        RETURN count(c) as count
                    """)
                    orphaned_count = result.single()["count"]
                    
                    # 获取所有有vec_id的Chunk
                    result = sess.run("""
                        MATCH (c:Chunk)
                        WHERE c.vec_id IS NOT NULL AND c.vec_id <> ''
                        RETURN count(c) as count
                    """)
                    vectorized_count = result.single()["count"]
                
            return {
                "success": True,
                "orphaned_chunks": orphaned_count,
                "vectorized_chunks": vectorized_count,
                "summary": f"找到 {orphaned_count} 个没有向量的Chunk，{vectorized_count} 个有向量的Chunk"
            }
            
        except Exception as e:
            logger.error(f"Failed to check chunks without vectors: {e}")
            return {"success": False, "error": str(e)}

    def cleanup_all_orphaned_data(self, database: Optional[str] = None) -> Dict[str, Any]:
        """统一清理函数：同时清理孤立向量和孤立Chunk"""
        try:
            result = {
                "success": True,
                "vectors": {"deleted": 0, "total": 0, "valid": 0, "error": None},
                "chunks": {"deleted": 0, "mentions": 0, "contains": 0, "error": None},
                "summary": ""
            }
            
            # 1. 清理孤立向量
            try:
                vector_result = self.cleanup_isolated_vectors(database=database)
                if vector_result.get("success"):
                    result["vectors"]["deleted"] = vector_result.get("deleted_isolated_vectors", 0)
                    result["vectors"]["total"] = vector_result.get("total_vectors", 0)
                    result["vectors"]["valid"] = vector_result.get("valid_vectors", 0)
                else:
                    result["vectors"]["error"] = vector_result.get("error", "Unknown error")
            except Exception as e:
                logger.warning(f"Cleanup isolated vectors failed: {e}")
                result["vectors"]["error"] = str(e)
            
            # 2. 清理孤立Chunk
            try:
                chunk_result = self.cleanup_orphaned_chunks(database=database)
                if chunk_result.get("success"):
                    result["chunks"]["deleted"] = chunk_result.get("deleted_chunks", 0)
                    result["chunks"]["mentions"] = chunk_result.get("deleted_mentions", 0)
                    result["chunks"]["contains"] = chunk_result.get("deleted_contains", 0)
                else:
                    result["chunks"]["error"] = chunk_result.get("error", "Unknown error")
            except Exception as e:
                logger.warning(f"Cleanup orphaned chunks failed: {e}")
                result["chunks"]["error"] = str(e)
            
            # 生成摘要
            summary_parts = []
            if result["vectors"]["deleted"] > 0:
                summary_parts.append(f"删除了 {result['vectors']['deleted']} 个孤立向量")
            if result["chunks"]["deleted"] > 0:
                summary_parts.append(f"删除了 {result['chunks']['deleted']} 个孤立Chunk")
                if result["chunks"]["mentions"] > 0:
                    summary_parts.append(f"{result['chunks']['mentions']} 个MENTIONS关系")
                if result["chunks"]["contains"] > 0:
                    summary_parts.append(f"{result['chunks']['contains']} 个CONTAINS关系")
            
            if summary_parts:
                result["summary"] = "清理完成: " + ", ".join(summary_parts)
            else:
                result["summary"] = "未发现需要清理的数据"
            
            return result
            
        except Exception as e:
            logger.error(f"Cleanup all orphaned data failed: {e}")
            return {"success": False, "error": str(e)}

    def reconcile_legacy_vectors(
        self,
        database: str,
        strategy: str = "migrate",
        source_collection: Optional[str] = None,
    ) -> Dict[str, Any]:
        """收口历史全局向量到分库集合。

        strategy:
          - keep: 仅统计，不做修改
          - migrate: 将确认属于当前database的向量迁移到分库collection，并从source移除对应项
          - delete: 删除source中确认属于当前database的向量
        """
        if not psycopg2:
            return {"success": False, "error": "psycopg2 module not found"}

        db_name = (database or "").strip()
        if not db_name:
            return {"success": False, "error": "database is required"}

        mode = (strategy or "migrate").strip().lower()
        if mode not in ("keep", "migrate", "delete"):
            return {"success": False, "error": f"invalid strategy: {strategy}"}

        src_collection = (source_collection or self.pg_collection or "").strip()
        target_collection = self.get_vector_collection_name(database=db_name)

        # 仅用于确保 target collection 被创建
        self._get_vector_store(database=db_name)

        valid_vec_ids = set()
        with self._use_database(db_name):
            with self._session() as sess:
                rows = sess.run(
                    """
                    MATCH (c:Chunk)
                    WHERE c.vec_id IS NOT NULL AND c.vec_id <> ''
                    RETURN c.vec_id AS vec_id
                    """
                )
                for row in rows:
                    vid = row.get("vec_id") if hasattr(row, "get") else row["vec_id"]
                    if vid:
                        valid_vec_ids.add(str(vid))

        conn = psycopg2.connect(self.pg_conn)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT uuid FROM kg_pg_collection WHERE name = %s",
                        (src_collection,),
                    )
                    src_row = cur.fetchone()
                    if not src_row:
                        return {
                            "success": True,
                            "database": db_name,
                            "strategy": mode,
                            "source_collection": src_collection,
                            "target_collection": target_collection,
                            "source_total": 0,
                            "target_total": 0,
                            "matched_with_database": 0,
                            "moved": 0,
                            "deleted_from_source": 0,
                            "target_deduplicated": 0,
                            "orphan_in_source": 0,
                            "note": "source collection not found",
                        }
                    src_uuid = src_row[0]

                    cur.execute(
                        "SELECT uuid FROM kg_pg_collection WHERE name = %s",
                        (target_collection,),
                    )
                    tgt_row = cur.fetchone()
                    if not tgt_row:
                        return {"success": False, "error": f"target collection not found: {target_collection}"}
                    tgt_uuid = tgt_row[0]

                    cur.execute(
                        "SELECT custom_id FROM kg_pg_embedding WHERE collection_id = %s AND custom_id IS NOT NULL",
                        (src_uuid,),
                    )
                    source_ids = [str(r[0]) for r in cur.fetchall() if r[0]]
                    source_set = set(source_ids)

                    cur.execute(
                        "SELECT custom_id FROM kg_pg_embedding WHERE collection_id = %s AND custom_id IS NOT NULL",
                        (tgt_uuid,),
                    )
                    target_set = {str(r[0]) for r in cur.fetchall() if r[0]}

                    matched_ids = source_set.intersection(valid_vec_ids)
                    orphan_ids = source_set.difference(valid_vec_ids)
                    already_in_target = matched_ids.intersection(target_set)
                    move_ids = matched_ids.difference(target_set)

                    moved = 0
                    deleted_from_source = 0

                    if mode == "migrate" and src_uuid != tgt_uuid:
                        if move_ids:
                            cur.execute(
                                """
                                                                UPDATE kg_pg_embedding
                                SET collection_id = %s
                                WHERE collection_id = %s
                                  AND custom_id = ANY(%s)
                                """,
                                (tgt_uuid, src_uuid, list(move_ids)),
                            )
                            moved = int(cur.rowcount or 0)

                        # 已存在于目标集合的重复项，直接从source删除
                        if already_in_target:
                            cur.execute(
                                "DELETE FROM kg_pg_embedding WHERE collection_id = %s AND custom_id = ANY(%s)",
                                (src_uuid, list(already_in_target)),
                            )
                            deleted_from_source += int(cur.rowcount or 0)

                    elif mode == "delete":
                        if matched_ids:
                            cur.execute(
                                "DELETE FROM kg_pg_embedding WHERE collection_id = %s AND custom_id = ANY(%s)",
                                (src_uuid, list(matched_ids)),
                            )
                            deleted_from_source += int(cur.rowcount or 0)

                    # 对 target 做一次去重（同 custom_id 保留1条）
                    cur.execute(
                        """
                        WITH dupes AS (
                            SELECT uuid,
                                   ROW_NUMBER() OVER (PARTITION BY custom_id ORDER BY uuid) AS rn
                                                        FROM kg_pg_embedding
                            WHERE collection_id = %s
                              AND custom_id IS NOT NULL
                        )
                                                DELETE FROM kg_pg_embedding e
                        USING dupes d
                        WHERE e.uuid = d.uuid
                          AND d.rn > 1
                        """,
                        (tgt_uuid,),
                    )
                    target_deduplicated = int(cur.rowcount or 0)

                    cur.execute(
                        "SELECT COUNT(*) FROM kg_pg_embedding WHERE collection_id = %s",
                        (src_uuid,),
                    )
                    source_total_after = int((cur.fetchone() or [0])[0])

                    cur.execute(
                        "SELECT COUNT(*) FROM kg_pg_embedding WHERE collection_id = %s",
                        (tgt_uuid,),
                    )
                    target_total_after = int((cur.fetchone() or [0])[0])

                    return {
                        "success": True,
                        "database": db_name,
                        "strategy": mode,
                        "source_collection": src_collection,
                        "target_collection": target_collection,
                        "source_total": len(source_ids),
                        "source_total_after": source_total_after,
                        "target_total": len(target_set),
                        "target_total_after": target_total_after,
                        "matched_with_database": len(matched_ids),
                        "moved": moved,
                        "deleted_from_source": deleted_from_source,
                        "target_deduplicated": target_deduplicated,
                        "orphan_in_source": len(orphan_ids),
                    }
        except Exception as e:
            logger.error(f"Reconcile legacy vectors failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

