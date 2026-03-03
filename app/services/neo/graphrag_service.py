import os
import logging
from typing import List, Dict, Any, Optional
import json
import re
from contextlib import contextmanager
from contextvars import ContextVar

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
        
        # 使用 EmbeddingService（支持 OpenAI 兼容 API，如 BAAI/bge-m3）
        try:
            self._embedding_service = EmbeddingService()
            self._embedding_wrapper = self._embedding_service.embeddings
            logger.info(f"GraphRAG 使用 EmbeddingService: {self._embedding_service.model_name}")
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
            self.vector_store = PGVector(
                connection_string=pg_conn,
                collection_name=pg_collection,
                embedding_function=self._embedding_wrapper,
            )
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
                RETURN elementId(e) as eid, id(e) as nid
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

        with self._session() as sess:
            # create Document node
            doc_res = sess.run(
                "CREATE (d:Document {doc_id:$doc_id, filename:$filename}) RETURN elementId(d) as eid, id(d) as id",
                {"doc_id": doc_id, "filename": filename},
            )
            doc_row = doc_res.single()
            doc_node_id = doc_row["id"] if doc_row else None

            for idx, chunk in enumerate(chunks):
                # 1. 创建 Chunk 节点
                try:
                    res = sess.run(
                        "CREATE (c:Chunk {doc_id:$doc_id, idx:$idx, text:$text}) RETURN id(c) as nid",
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
                            "MATCH (d:Document), (c:Chunk) WHERE id(d)=$did AND id(c)=$cid CREATE (d)-[:CONTAINS]->(c)",
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
                                    "MATCH (c:Chunk), (e:Entity) WHERE id(c)=$cid AND id(e)=$eid CREATE (c)-[:MENTIONS]->(e)",
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

                if self.vector_store and emb is not None:
                    try:
                        if hasattr(self.vector_store, 'add_texts'):
                            res = self.vector_store.add_texts(
                                [chunk], 
                                metadatas=[{
                                    "neo_node_id": str(nid), 
                                    "doc_id": doc_id, 
                                    "kb_id": kb_id, 
                                    "filename": filename,
                                    "entities": json.dumps([e["name"] for e in chunk_entities], ensure_ascii=False)
                                }], 
                                ids=[vec_id]
                            )
                            logger.info(f"PGVector.add_texts returned: {res}")
                    except Exception as e:
                        logger.warning(f"向量上载失败: {e}")

                # 5. 写回 vec_id 到 Neo4j Chunk 节点
                try:
                    sess.run("MATCH (c) WHERE id(c)=$nid SET c.vec_id=$vec", {"nid": nid, "vec": vec_id})
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

        if self.vector_store:
            try:
                # try common search names used by different implementations
                results = None
                for fn in ("similarity_search_with_score_by_vector", "similarity_search_by_vector", "similarity_search_with_score", "similarity_search"):
                    if hasattr(self.vector_store, fn):
                        try:
                            results = getattr(self.vector_store, fn)(q_emb, k=top_k)
                            break
                        except TypeError:
                            # some APIs expect named args
                            try:
                                results = getattr(self.vector_store, fn)(q_emb, k=top_k)
                                break
                            except Exception:
                                results = None
                # if still None, try a generic 'search' or 'client' usage
                if results is None and hasattr(self.vector_store, 'client'):
                    try:
                        # many clients expose a query/upsert API; leave as best-effort
                        results = getattr(self.vector_store, 'client').query(q_emb, top_k)
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
                                    q = sess2.run('MATCH (c:Chunk) WHERE c.text = $txt RETURN id(c) as nid LIMIT 1', {'txt': txt})
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
                        "MATCH (c) WHERE id(c) IN $ids OPTIONAL MATCH (c)-[r]-(m) RETURN c, collect(r) as rels, collect(m) as mats",
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
    
    def local_search(self, question: str, top_k: int = 5, include_community: bool = True, doc_id: str = None, database: str = None) -> Dict[str, Any]:
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
            "community_context": []
        }
        
        # 1. 向量检索 Chunk（带文档过滤）
        vector_chunks = self._vector_search_chunks(question, top_k, doc_id=doc_id)
        result["chunks"] = vector_chunks
        
        # 2. 从问题中提取并匹配实体（带文档过滤）
        matched_entities = self._match_entities_from_question(question, doc_id=doc_id)
        
        # 3. 从 Chunk 的 MENTIONS 关系找到相关实体
        chunk_entity_ids = set()
        if vector_chunks:
            chunk_neo_ids = [c.get("neo_id") for c in vector_chunks if c.get("neo_id")]
            if chunk_neo_ids:
                with self._session() as sess:
                    try:
                        res = sess.run("""
                            MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
                            WHERE id(c) IN $chunk_ids
                            RETURN DISTINCT e.name as name, e.type as type, id(e) as neo_id, 
                                   e.description as description, e.community_id as community_id
                        """, {"chunk_ids": chunk_neo_ids})
                        for row in res:
                            entity_info = {
                                "name": row["name"],
                                "type": row["type"],
                                "neo_id": row["neo_id"],
                                "description": row["description"],
                                "community_id": row["community_id"],
                                "source": "chunk_mention"
                            }
                            chunk_entity_ids.add(row["neo_id"])
                            # 避免重复
                            if not any(e["name"] == entity_info["name"] for e in matched_entities):
                                matched_entities.append(entity_info)
                    except Exception as e:
                        logger.warning(f"Failed to get entities from chunks: {e}")
        
        result["entities"] = matched_entities
        
        # 4. 获取实体之间的关系
        entity_names = [e["name"] for e in matched_entities]
        if entity_names:
            relations = self._get_entity_relations(entity_names)
            result["relations"] = relations
        
        # 5. 如果启用社区信息，获取相关社区上下文
        if include_community and matched_entities:
            community_ids = set()
            for e in matched_entities:
                if e.get("community_id") is not None:
                    community_ids.add(e["community_id"])
            
            for cid in list(community_ids)[:3]:  # 最多3个社区
                community_entities = self.get_community_entities(cid)
                if community_entities:  # get_community_entities 返回列表
                    result["community_context"].append({
                        "community_id": cid,
                        "members": [e["name"] for e in community_entities[:10]]  # 限制成员数
                    })
        
        # 6. 构建丰富的上下文
        context = self._build_local_search_context(
            chunks=vector_chunks,
            entities=matched_entities,
            relations=result["relations"],
            community_context=result["community_context"]
        )
        
        # 7. LLM 生成答案
        if self.llm and context:
            try:
                answer = self.llm.generate_answer(question, context)
                result["answer"] = answer
            except Exception as e:
                logger.error(f"LLM generate failed: {e}")
                result["answer"] = ""
        
        return result
    
    def _vector_search_chunks(self, question: str, top_k: int = 5, doc_id: str = None) -> List[Dict]:
        """向量检索相关的 Chunk
        
        Args:
            question: 用户问题
            top_k: 返回的候选数量
            doc_id: 文档 ID，用于限定检索范围（可选）
        """
        chunks = []
        q_emb = self.embed_text(question)
        if q_emb is None or not self.vector_store:
            return chunks
        
        try:
            # 如果指定了 doc_id，使用过滤条件
            filter_dict = None
            if doc_id:
                filter_dict = {"doc_id": doc_id}
            
            results = None
            for fn in ("similarity_search_with_score_by_vector", "similarity_search_by_vector"):
                if hasattr(self.vector_store, fn):
                    try:
                        if filter_dict:
                            # 尝试带过滤条件的搜索
                            results = getattr(self.vector_store, fn)(q_emb, k=top_k * 3, filter=filter_dict)
                        else:
                            results = getattr(self.vector_store, fn)(q_emb, k=top_k)
                        break
                    except TypeError:
                        # 如果向量库不支持 filter 参数，回退到无过滤搜索
                        results = getattr(self.vector_store, fn)(q_emb, k=top_k * 3 if doc_id else top_k)
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
                        
                        neo_id = None
                        for k in ('neo_node_id', 'neo_id', 'id'):
                            if k in metadata:
                                try:
                                    neo_id = int(metadata[k])
                                    break
                                except:
                                    pass
                        
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
        """从问题中匹配 Entity 节点
        
        策略：
        1. 全文匹配：问题中包含实体名称
        2. 模糊匹配：使用 CONTAINS 查找
        
        Args:
            question: 用户问题
            doc_id: 文档 ID，用于限定检索范围（可选）
        """
        matched = []
        
        with self._session() as sess:
            try:
                # 根据是否有 doc_id 构建不同的查询
                if doc_id:
                    # 只匹配指定文档的实体
                    res = sess.run("""
                        MATCH (e:Entity) 
                        WHERE e.doc_id = $doc_id
                        RETURN e.name as name, e.type as type, id(e) as neo_id, 
                               e.description as description, e.community_id as community_id
                    """, {"doc_id": doc_id})
                else:
                    # 获取所有实体名称
                    res = sess.run("""
                        MATCH (e:Entity) 
                        RETURN e.name as name, e.type as type, id(e) as neo_id, 
                               e.description as description, e.community_id as community_id
                    """)
                
                for row in res:
                    entity_name = row["name"]
                    # 检查问题中是否包含实体名称
                    if entity_name and entity_name in question:
                        matched.append({
                            "name": entity_name,
                            "type": row["type"],
                            "neo_id": row["neo_id"],
                            "description": row["description"],
                            "community_id": row["community_id"],
                            "source": "question_match"
                        })
            except Exception as e:
                logger.warning(f"Entity matching failed: {e}")
        
        return matched
    
    def _get_entity_relations(self, entity_names: List[str]) -> List[Dict]:
        """获取实体之间的关系"""
        relations = []
        
        if not entity_names:
            return relations
        
        with self._session() as sess:
            try:
                # 获取这些实体之间的所有关系
                res = sess.run("""
                    MATCH (e1:Entity)-[r:RELATES_TO]->(e2:Entity)
                    WHERE e1.name IN $names OR e2.name IN $names
                    RETURN e1.name as source, e2.name as target, 
                           r.type as rel_type, r.description as description
                """, {"names": entity_names})
                
                for row in res:
                    relations.append({
                        "source": row["source"],
                        "target": row["target"],
                        "type": row["rel_type"],
                        "description": row["description"]
                    })
            except Exception as e:
                logger.warning(f"Get relations failed: {e}")
        
        return relations
    
    def _build_local_search_context(self, chunks: List[Dict], entities: List[Dict], 
                                     relations: List[Dict], community_context: List[Dict]) -> str:
        """构建 Local Search 的上下文"""
        context_parts = []
        
        # 1. 实体信息
        if entities:
            entity_lines = ["【相关实体】"]
            for e in entities[:10]:  # 限制数量
                desc = f" - {e['description']}" if e.get('description') else ""
                entity_lines.append(f"• {e['name']} ({e.get('type', '未知类型')}){desc}")
            context_parts.append("\n".join(entity_lines))
        
        # 2. 关系信息
        if relations:
            rel_lines = ["【实体关系】"]
            for r in relations[:15]:  # 限制数量
                desc = f" ({r['description']})" if r.get('description') else ""
                rel_lines.append(f"• {r['source']} --[{r['type']}]--> {r['target']}{desc}")
            context_parts.append("\n".join(rel_lines))
        
        # 3. 社区上下文
        if community_context:
            comm_lines = ["【相关社区】"]
            for c in community_context:
                members = ", ".join(c.get("members", [])[:8])
                comm_lines.append(f"• 社区 {c['community_id']}: {members}")
            context_parts.append("\n".join(comm_lines))
        
        # 4. 原文片段
        if chunks:
            chunk_lines = ["【原文片段】"]
            for idx, c in enumerate(chunks[:5], 1):  # 限制数量
                text = c.get("text", "")[:500]  # 限制长度
                score_info = f" (相似度: {c['score']:.3f})" if c.get('score') else ""
                chunk_lines.append(f"[{idx}]{score_info}: {text}")
            context_parts.append("\n".join(chunk_lines))
        
        return "\n\n".join(context_parts)

    # ========== Phase 2: 社区检测 (Leiden Algorithm) ==========
    
    def detect_communities(self, write_property: bool = True) -> Dict[str, Any]:
        """使用 Leiden 算法检测 Entity 节点的社区
        
        需要安装 Neo4j Graph Data Science (GDS) 插件
        
        Args:
            write_property: 是否将 community_id 写回节点属性
            
        Returns:
            {
                "success": bool,
                "communities": [{"community_id": int, "members": [str], "size": int}],
                "total_communities": int,
                "total_entities": int
            }
        """
        with self._session() as sess:
            try:
                # 1. 检查是否有足够的 Entity 节点
                count_result = sess.run("MATCH (e:Entity) RETURN count(e) as cnt")
                entity_count = count_result.single()["cnt"]
                
                if entity_count < 2:
                    return {
                        "success": False, 
                        "error": f"需要至少 2 个 Entity 节点进行社区检测，当前只有 {entity_count} 个"
                    }
                
                # 2. 检查是否有关系，如果没有则创建共现关系
                rel_count_result = sess.run("MATCH (:Entity)-[r:RELATES_TO]->(:Entity) RETURN count(r) as cnt")
                rel_count = rel_count_result.single()["cnt"]
                
                if rel_count == 0:
                    logger.warning("没有 Entity 之间的关系，将基于共同出现在同一 Chunk 中建立隐式关系")
                    # 创建基于 Chunk 共现的隐式关系
                    sess.run("""
                        MATCH (c:Chunk)-[:MENTIONS]->(e1:Entity)
                        MATCH (c)-[:MENTIONS]->(e2:Entity)
                        WHERE id(e1) < id(e2)
                        MERGE (e1)-[r:CO_OCCURS]->(e2)
                        ON CREATE SET r.weight = 1
                        ON MATCH SET r.weight = r.weight + 1
                    """)
                
                # 3. 删除旧的图投影（如果存在）
                try:
                    sess.run("CALL gds.graph.drop('entityGraph', false)")
                except Exception:
                    pass  # 图不存在，忽略
                
                # 4. 检查可用的关系类型
                has_relates = sess.run("MATCH (:Entity)-[r:RELATES_TO]->(:Entity) RETURN count(r) > 0 as has").single()["has"]
                has_co_occurs = sess.run("MATCH (:Entity)-[r:CO_OCCURS]->(:Entity) RETURN count(r) > 0 as has").single()["has"]
                
                # 构建关系类型配置 - Leiden 需要 UNDIRECTED
                rel_configs = []
                if has_relates:
                    rel_configs.append("RELATES_TO: {orientation: 'UNDIRECTED'}")
                if has_co_occurs:
                    rel_configs.append("CO_OCCURS: {orientation: 'UNDIRECTED'}")
                
                if not rel_configs:
                    return {
                        "success": False,
                        "error": "没有找到 Entity 之间的关系，无法进行社区检测"
                    }
                
                # 5. 创建图投影 - 使用 UNDIRECTED 模式（Leiden 算法要求）
                rel_config_str = ", ".join(rel_configs)
                project_query = f"""
                    CALL gds.graph.project(
                        'entityGraph',
                        'Entity',
                        {{{rel_config_str}}}
                    )
                """
                
                logger.info(f"GDS graph.project query: {project_query}")
                sess.run(project_query)
                
                # 6. 运行 Leiden 社区检测算法
                if write_property:
                    # 写回模式：将 community_id 写入节点属性
                    result = sess.run("""
                        CALL gds.leiden.write('entityGraph', {
                            writeProperty: 'community_id'
                        })
                        YIELD communityCount, modularity
                        RETURN communityCount, modularity
                    """)
                    stats = result.single()
                    community_count = stats["communityCount"]
                    modularity = stats["modularity"]
                    
                    logger.info(f"Leiden 社区检测完成: {community_count} 个社区, 模块度={modularity:.4f}")
                
                # 7. 获取社区详情
                communities_result = sess.run("""
                    MATCH (e:Entity)
                    WHERE e.community_id IS NOT NULL
                    RETURN e.community_id AS community_id, collect(e.name) AS members, count(e) AS size
                    ORDER BY size DESC
                """)
                
                communities = []
                for row in communities_result:
                    communities.append({
                        "community_id": row["community_id"],
                        "members": row["members"],
                        "size": row["size"]
                    })
                
                # 8. 清理图投影
                try:
                    sess.run("CALL gds.graph.drop('entityGraph', false)")
                except Exception:
                    pass
                
                return {
                    "success": True,
                    "communities": communities,
                    "total_communities": len(communities),
                    "total_entities": entity_count
                }
                
            except Exception as e:
                error_msg = str(e)
                if "Unknown function" in error_msg or "gds" in error_msg.lower():
                    return {
                        "success": False,
                        "error": "Neo4j GDS 插件未安装或未启用。请在 Neo4j Desktop 中安装 Graph Data Science Library 插件。"
                    }
                logger.error(f"Community detection failed: {e}")
                import traceback
                traceback.print_exc()
                return {"success": False, "error": error_msg}

    def get_community_entities(self, community_id: int) -> List[Dict[str, Any]]:
        """获取指定社区的所有实体"""
        with self._session() as sess:
            result = sess.run("""
                MATCH (e:Entity {community_id: $cid})
                OPTIONAL MATCH (e)-[r:RELATES_TO]-(other:Entity {community_id: $cid})
                RETURN e.name AS name, e.type AS type, e.description AS description,
                       collect(DISTINCT {target: other.name, rel_type: r.type}) AS relations
            """, {"cid": community_id})
            
            entities = []
            for row in result:
                entities.append({
                    "name": row["name"],
                    "type": row["type"],
                    "description": row["description"],
                    "relations": [r for r in row["relations"] if r["target"]]
                })
            return entities

    def generate_community_report(self, community_id: int) -> Dict[str, Any]:
        """为指定社区生成 LLM 摘要报告"""
        if not self.llm:
            return {"success": False, "error": "LLM not available"}
        
        entities = self.get_community_entities(community_id)
        if not entities:
            return {"success": False, "error": f"Community {community_id} has no entities"}
        
        # 构建社区信息
        entity_info = []
        for e in entities:
            info = f"- {e['name']} ({e['type']}): {e['description'] or '无描述'}"
            if e['relations']:
                rels = ", ".join([f"{r['rel_type']}->{r['target']}" for r in e['relations'][:5]])
                info += f" [关系: {rels}]"
            entity_info.append(info)
        
        prompt = f"""请为以下知识社区生成一份简洁的摘要报告。

【社区实体】
{chr(10).join(entity_info)}

【要求】
1. 总结这个社区的核心主题（1-2句话）
2. 列出关键实体及其重要性
3. 描述实体之间的主要关系模式
4. 总字数不超过300字

请输出摘要报告："""
        
        try:
            # 使用 LangChain 的 ChatOpenAI 接口
            from langchain_core.messages import HumanMessage
            
            response = self.llm.llm.invoke([HumanMessage(content=prompt)])
            report = response.content.strip()
            
            # 存储报告到 Neo4j
            with self._session() as sess:
                sess.run("""
                    MERGE (c:Community {community_id: $cid})
                    SET c.report = $report, c.updated_at = datetime(), c.entity_count = $count
                """, {"cid": community_id, "report": report, "count": len(entities)})
            
            return {
                "success": True,
                "community_id": community_id,
                "report": report,
                "entity_count": len(entities)
            }
            
        except Exception as e:
            logger.error(f"Generate community report failed: {e}")
            return {"success": False, "error": str(e)}

    def generate_all_community_reports(self) -> Dict[str, Any]:
        """为所有社区生成报告"""
        with self._session() as sess:
            result = sess.run("""
                MATCH (e:Entity)
                WHERE e.community_id IS NOT NULL
                RETURN DISTINCT e.community_id AS cid
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
            local_fallback = self.local_search(question, top_k=5, doc_id=doc_id)
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
        
        with self._session() as sess:
            try:
                if doc_id:
                    # 如果指定了 doc_id，只获取包含该文档实体的社区
                    res = sess.run("""
                        MATCH (e:Entity)
                        WHERE e.doc_id = $doc_id AND e.community_id IS NOT NULL
                        WITH DISTINCT e.community_id AS cid
                        MATCH (c:Community {community_id: cid})
                        WHERE c.report IS NOT NULL
                        RETURN c.community_id AS community_id, c.report AS report, 
                               c.entity_count AS entity_count, c.updated_at AS updated_at
                        ORDER BY c.entity_count DESC
                        LIMIT $limit
                    """, {"doc_id": doc_id, "limit": max_communities})
                else:
                    # 获取有报告的社区
                    res = sess.run("""
                        MATCH (c:Community)
                        WHERE c.report IS NOT NULL
                        RETURN c.community_id AS community_id, c.report AS report, 
                               c.entity_count AS entity_count, c.updated_at AS updated_at
                        ORDER BY c.entity_count DESC
                        LIMIT $limit
                    """, {"limit": max_communities})
                
                for row in res:
                    communities.append({
                        "community_id": row["community_id"],
                        "report": row["report"],
                        "entity_count": row["entity_count"] or 0
                    })
                
                # 如果没有 Community 节点但有带 community_id 的 Entity，也尝试获取
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
            local_result = self.local_search(question, top_k=5, doc_id=doc_id)
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
    
    def hybrid_search(self, question: str, top_k: int = 5, 
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
        
        if strategy in ("local", "both"):
            local_result = self.local_search(enhanced_question, top_k=top_k, doc_id=doc_id)
            result["local_result"] = local_result
        
        if strategy in ("global", "both"):
            global_result = self.global_search(enhanced_question, doc_id=doc_id)
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
            if self.vector_store and vec_ids:
                try:
                    if hasattr(self.vector_store, 'delete'):
                        self.vector_store.delete(vec_ids)
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

    def cleanup_isolated_vectors(self) -> Dict[str, Any]:
        """清理孤立向量：删除 PGVector 中存在但 Neo4j 中不存在的向量"""
        if not psycopg2:
            return {"success": False, "error": "psycopg2 module not found"}
        
        try:
            # 1. 获取 Neo4j 中所有有效的 vec_id
            valid_vec_ids = set()
            with self._session() as sess:
                result = sess.run("MATCH (c:Chunk) WHERE c.vec_id IS NOT NULL RETURN c.vec_id as vec_id")
                for row in result:
                    valid_vec_ids.add(row["vec_id"])
            
            logger.info(f"Found {len(valid_vec_ids)} valid vector IDs in Neo4j")

            # 2. 连接 Postgres
            conn = psycopg2.connect(self.pg_conn)
            deleted_count = 0
            total_pg_vectors = 0
            
            try:
                with conn:
                    with conn.cursor() as cur:
                        # 获取 collection_id
                        cur.execute(
                            "SELECT uuid FROM langchain_pg_collection WHERE name = %s", 
                            (self.pg_collection,)
                        )
                        row = cur.fetchone()
                        if not row:
                            return {"success": False, "error": f"Collection {self.pg_collection} not found"}
                        collection_uuid = row[0]
                        
                        # 确定 ID 列名
                        cur.execute(
                            "SELECT column_name FROM information_schema.columns WHERE table_name = 'langchain_pg_embedding'"
                        )
                        columns = [r[0] for r in cur.fetchall()]
                        
                        id_col = None
                        if 'custom_id' in columns:
                            id_col = 'custom_id'
                        elif 'id' in columns:
                            id_col = 'id'
                        
                        if not id_col:
                             return {"success": False, "error": f"Could not find ID column in langchain_pg_embedding. Available columns: {columns}"}

                        logger.info(f"Using ID column: {id_col}")

                        # 获取该 collection 下所有向量 ID
                        cur.execute(
                            f"SELECT {id_col} FROM langchain_pg_embedding WHERE collection_id = %s",
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
                                    f"DELETE FROM langchain_pg_embedding WHERE {id_col} = ANY(%s)",
                                    (batch,)
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
