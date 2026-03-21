import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, date, timezone
from collections import defaultdict
import os
import re
import uuid
from flask import Blueprint, request, jsonify, current_app
from app.services.rag_service import RAGService
from app.services.neo.mapping_manager import MappingManager
from app.models import ChatSession, ChatMessage, Document, DocumentChunk, KnowledgeBase, User, UserSession
from app.extensions import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

# 创建蓝图（注意：在 app/__init__.py 中注册时已经指定了 url_prefix）
kg_bp = Blueprint('kg', __name__)


def get_rag_service():
    """获取或创建 RAG 服务"""
    if not hasattr(current_app, 'rag_service'):
        api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
        current_app.rag_service = RAGService(mode='graphrag', deepseek_api_key=api_key)
    return current_app.rag_service


def _vector_collection_for_database(db_name: Optional[str]) -> str:
    svc = getattr(current_app, 'graphrag_service', None)
    if svc and hasattr(svc, 'get_vector_collection_name'):
        try:
            return svc.get_vector_collection_name(db_name)
        except Exception:
            pass
    base = os.getenv('PGVECTOR_COLLECTION', 'graphrag_collection')
    db = (db_name or '').strip()
    if not db:
        return base
    safe = re.sub(r'[^0-9a-zA-Z_]+', '_', db.lower()).strip('_') or 'default'
    return f"{base}__{safe}"


def _normalize_graph_database(db_name: Optional[str]) -> Optional[str]:
    normalized = (db_name or '').strip()
    if not normalized:
        return None
    if normalized.lower() == 'system':
        raise ValueError('system 数据库不支持图谱查询')
    return normalized


def _require_graph_database(db_name: Optional[str]) -> str:
    normalized = _normalize_graph_database(db_name)
    if not normalized:
        raise ValueError('database is required')
    return normalized


def _count_vectors_for_database(db_name: Optional[str]) -> int:
    collection_name = _vector_collection_for_database(db_name)
    try:
        row = db.session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM kg_pg_embedding e
                JOIN kg_pg_collection c ON e.collection_id = c.uuid
                WHERE c.name = :name
                """
            ),
            {"name": collection_name},
        ).fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def serialize_node_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将 Neo4j 节点记录序列化为可 JSON 输出的字典"""
    if not record:
        return None

    node_obj = record.get('n') or record.get('node') or record.get('center')
    degree = record.get('degree') or record.get('relations_count') or record.get('weight')

    if node_obj is None:
        return None

    labels: List[str] = []
    if hasattr(node_obj, 'labels'):
        try:
            labels = list(getattr(node_obj, 'labels'))
        except TypeError:
            labels = []
    if not labels and isinstance(node_obj, dict):
        raw_labels = node_obj.get('labels') or node_obj.get('label')
        if isinstance(raw_labels, (list, tuple, set)):
            labels = list(raw_labels)
        elif raw_labels:
            labels = [raw_labels]

    getter = getattr(node_obj, 'get', None)
    id_value = None
    if callable(getter):
        try:
            id_value = getter('id')
        except TypeError:
            id_value = None
    if id_value is None and isinstance(node_obj, dict):
        id_value = node_obj.get('id') or node_obj.get('uid')
    if id_value is None:
        id_attr = getattr(node_obj, 'id', None)
        id_value = id_attr if id_attr is not None else getattr(node_obj, 'element_id', None)

    if isinstance(node_obj, dict):
        properties = serialize_neo4j_object(dict(node_obj))
    elif callable(getter):
        try:
            properties = serialize_neo4j_object(dict(node_obj))
        except TypeError:
            properties = {}
    else:
        properties = {}

    name_value = ''
    if callable(getter):
        for key in ('name', 'title', 'label'):
            try:
                name_value = getter(key)
            except TypeError:
                name_value = None
            if name_value:
                break
    if not name_value and isinstance(node_obj, dict):
        for key in ('name', 'title', 'label'):
            name_value = node_obj.get(key)
            if name_value:
                break

    serialized = {
        "id": str(id_value) if id_value is not None else None,
        "name": str(name_value) if name_value else '',
        "labels": labels,
        "properties": properties,
    }
    if degree is not None:
        serialized['degree'] = degree
    return serialized


def serialize_neo4j_object(obj):
    """
    序列化 Neo4j 对象为字典
    """
    if obj is None:
        return None
    
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    
    # 处理 Neo4j 的 DateTime 对象 (如果它不是 datetime 的子类)
    if hasattr(obj, 'iso_format'):
        return obj.iso_format()

    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    if isinstance(obj, (list, tuple)):
        return [serialize_neo4j_object(item) for item in obj]
    
    if isinstance(obj, dict):
        return {k: serialize_neo4j_object(v) for k, v in obj.items()}
    
    # 尝试转换为字典
    try:
        if hasattr(obj, '__dict__'):
            return {k: serialize_neo4j_object(v) for k, v in obj.__dict__.items()}
        elif hasattr(obj, 'items'):
            return {k: serialize_neo4j_object(v) for k, v in obj.items()}
        else:
            return str(obj)
    except:
        return str(obj)


def _coerce_utc_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _build_daily_series(rows: List[Any], days: int) -> Dict[str, List[Any]]:
    today = datetime.now(timezone.utc).date()
    start_date = today.replace() if days <= 1 else today
    dates = [today]
    if days > 1:
        dates = [today.fromordinal(today.toordinal() - offset) for offset in range(days - 1, -1, -1)]

    counts = defaultdict(int)
    for raw_value in rows:
        dt_value = _coerce_utc_datetime(raw_value)
        if not dt_value:
            continue
        bucket = dt_value.date()
        if bucket < dates[0] or bucket > dates[-1]:
            continue
        counts[bucket] += 1

    return {
        "labels": [item.isoformat() for item in dates],
        "values": [int(counts.get(item, 0)) for item in dates],
    }


def _build_monthly_series(rows: List[Any], months: int) -> Dict[str, List[Any]]:
    current = datetime.now(timezone.utc)
    month_keys: List[tuple[int, int]] = []
    year = current.year
    month = current.month
    for _ in range(months):
        month_keys.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    month_keys.reverse()

    counts = defaultdict(int)
    for raw_value in rows:
        dt_value = _coerce_utc_datetime(raw_value)
        if not dt_value:
            continue
        bucket = (dt_value.year, dt_value.month)
        if bucket not in month_keys:
            continue
        counts[bucket] += 1

    return {
        "labels": [f"{year}-{month:02d}" for year, month in month_keys],
        "values": [int(counts.get(key, 0)) for key in month_keys],
    }


def _load_time_values(model, column_attr, start_dt: Optional[datetime] = None) -> List[datetime]:
    try:
        query = db.session.query(column_attr).filter(column_attr.isnot(None))
        if start_dt is not None:
            query = query.filter(column_attr >= start_dt)
        return [row[0] for row in query.all() if row and row[0] is not None]
    except Exception as exc:
        logger.warning(f"加载时序数据失败 {model.__name__}: {exc}")
        return []




@kg_bp.route('/stats', methods=['GET'])
def get_graph_stats():
    """获取图谱统计信息"""
    try:
        rag_service = get_rag_service()
        try:
            database = _normalize_graph_database(request.args.get('database', None, type=str))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        graph_service = rag_service.graph_service

        node_row = graph_service.execute_query_single(
            "MATCH (n) WHERE NOT n:Chunk RETURN count(n) AS c",
            {},
            database=database,
        )
        edge_row = graph_service.execute_query_single(
            "MATCH ()-[r]->() RETURN count(r) AS c",
            {},
            database=database,
        )
        comm_row = graph_service.execute_query_single(
            "MATCH (n) WHERE n.community_id IS NOT NULL RETURN count(DISTINCT n.community_id) AS c",
            {},
            database=database,
        )

        nodes = int((node_row or {}).get('c', 0))
        edges = int((edge_row or {}).get('c', 0))
        communities = int((comm_row or {}).get('c', 0))

        stats = {
            "nodes": nodes,
            "edges": edges,
            "communities": communities,
            "total_nodes": nodes,
            "total_relations": edges,
            "average_degree": round((edges / nodes), 4) if nodes else 0.0,
            "database": database or "default",
        }
        return jsonify({"success": True, "data": stats})
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@kg_bp.route('/connection', methods=['GET'])
def get_connection_info():
    """获取 Neo4j 连接与数据库信息"""
    try:
        rag_service = get_rag_service()
        if not hasattr(rag_service, 'graph_service'):
            return jsonify({"success": False, "error": "GraphRAG 模式未启用"}), 400
        info = rag_service.graph_service.get_connection_info()
        return jsonify({"success": True, "data": info})
    except Exception as e:
        logger.error(f"获取连接信息失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/overview', methods=['GET'])
def get_overview():
    """获取图谱概览"""
    try:
        rag_service = get_rag_service()
        try:
            database = _normalize_graph_database(request.args.get('database', None, type=str))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        stats = rag_service.get_graph_stats(database=database)
        
        # 获取中心节点
        central_nodes = rag_service.kg_query.get_central_nodes(limit=5, database=database)

        serialized_nodes: List[Dict[str, Any]] = []
        for item in central_nodes:
            serialized = serialize_node_record(item)
            if serialized:
                serialized_nodes.append(serialized)
        
        overview = {
            "stats": stats,
            "central_nodes": serialized_nodes,
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "database": database or "default",
        }
        
        return jsonify({"success": True, "data": overview})
    except Exception as e:
        logger.error(f"获取概览失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """获取工作台/分析页专用聚合数据"""
    try:
        rag_service = get_rag_service()
        try:
            database = _normalize_graph_database(request.args.get('database', None, type=str))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        stats = rag_service.get_graph_stats(database=database) or {}
        central_nodes = rag_service.kg_query.get_central_nodes(limit=6, database=database) or []

        serialized_nodes: List[Dict[str, Any]] = []
        for item in central_nodes:
            serialized = serialize_node_record(item)
            if serialized:
                serialized_nodes.append(serialized)

        now = datetime.now(timezone.utc)
        recent_days = 14
        recent_months = 12
        start_daily = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_daily = start_daily.replace(day=start_daily.day)  # keep explicit day boundary
        start_daily = datetime.fromordinal(start_daily.date().toordinal() - (recent_days - 1)).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=timezone.utc,
        )

        document_times = _load_time_values(Document, Document.created_at, start_daily)
        chunk_times = _load_time_values(DocumentChunk, DocumentChunk.created_at, start_daily)
        message_times = _load_time_values(ChatMessage, ChatMessage.timestamp, start_daily)
        session_times = _load_time_values(ChatSession, ChatSession.created_at, start_daily)
        kb_times = _load_time_values(KnowledgeBase, KnowledgeBase.created_at, start_daily)
        user_times = _load_time_values(User, User.created_at, start_daily)
        login_times = _load_time_values(UserSession, UserSession.created_at, start_daily)

        monthly_start_year = now.year
        monthly_start_month = now.month - (recent_months - 1)
        while monthly_start_month <= 0:
            monthly_start_month += 12
            monthly_start_year -= 1
        start_monthly = datetime(monthly_start_year, monthly_start_month, 1, tzinfo=timezone.utc)

        monthly_document_times = _load_time_values(Document, Document.created_at, start_monthly)
        monthly_message_times = _load_time_values(ChatMessage, ChatMessage.timestamp, start_monthly)

        payload = {
            "stats": stats,
            "central_nodes": serialized_nodes,
            "database": database or "default",
            "timestamp": now.isoformat(),
            "trends": {
                "daily": {
                    "documents": _build_daily_series(document_times, recent_days),
                    "chunks": _build_daily_series(chunk_times, recent_days),
                    "messages": _build_daily_series(message_times, recent_days),
                    "sessions": _build_daily_series(session_times, recent_days),
                    "knowledge_bases": _build_daily_series(kb_times, recent_days),
                    "users": _build_daily_series(user_times, recent_days),
                    "logins": _build_daily_series(login_times, recent_days),
                },
                "monthly": {
                    "documents": _build_monthly_series(monthly_document_times, recent_months),
                    "messages": _build_monthly_series(monthly_message_times, recent_months),
                },
            },
        }

        return jsonify({"success": True, "data": payload})
    except Exception as e:
        logger.error(f"获取 dashboard 数据失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 节点操作 ====================

@kg_bp.route('/nodes', methods=['GET'])
def list_nodes():
    """获取节点列表"""
    try:
        limit = request.args.get('limit', 50, type=int)
        node_type = request.args.get('type', None)
        
        rag_service = get_rag_service()
        
        if node_type:
            nodes = rag_service.kg_query.get_central_nodes(node_type=node_type, limit=limit)
        else:
            nodes = rag_service.kg_query.get_central_nodes(limit=limit)
        # 对返回的记录进行序列化，避免直接返回 Neo4j Node 对象导致 JSON 序列化失败
        serialized = []
        for item in nodes:
            neo_node = item.get('n')
            degree = item.get('degree', 0)
            try:
                if neo_node is not None:
                    labels = list(getattr(neo_node, 'labels', [])) if hasattr(neo_node, 'labels') else []
                    data_dict = {
                        "id": neo_node.get('id') if hasattr(neo_node, 'get') else neo_node.get('id', None),
                        "name": neo_node.get('name', '') if hasattr(neo_node, 'get') else '',
                        "labels": labels,
                        "properties": serialize_neo4j_object(dict(neo_node)) if hasattr(neo_node, 'items') else {},
                        "degree": degree
                    }
                    serialized.append(data_dict)
            except Exception:
                # 回退为字符串表示，保证不抛出
                serialized.append({"raw": str(neo_node), "degree": degree})

        return jsonify({"success": True, "data": serialized, "count": len(serialized)})
    except Exception as e:
        logger.error(f"获取节点列表失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/nodes/<node_id>', methods=['GET'])
def get_node(node_id):
    """获取单个节点及其关系"""
    try:
        depth = request.args.get('depth', 2, type=int)
        
        rag_service = get_rag_service()
        node_data = rag_service.get_node_context(node_id, depth=depth)
        
        return jsonify({"success": True, "data": node_data})
    except Exception as e:
        logger.error(f"获取节点失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/search', methods=['GET'])
def search_nodes():
    """搜索节点"""
    try:
        query = request.args.get('q', '')
        node_type = request.args.get('type', None)
        limit = request.args.get('limit', 20, type=int)
        
        if not query:
            return jsonify({"success": False, "error": "查询参数不能为空"}), 400
        
        rag_service = get_rag_service()
        nodes = rag_service.search_nodes(query, node_type=node_type, limit=limit)
        
        # 序列化 Neo4j 对象
        serialized = [serialize_neo4j_object(node) for node in nodes]
        
        return jsonify({"success": True, "data": serialized, "count": len(serialized)})
    except Exception as e:
        logger.error(f"搜索节点失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/nodes/<node_id>/relations', methods=['GET'])
def get_node_relations(node_id):
    """获取节点的关系"""
    try:
        direction = request.args.get('direction', 'all')
        rel_type = request.args.get('type', None)
        
        rag_service = get_rag_service()
        relations = rag_service.kg_query.get_related_nodes(
            node_id,
            relation_type=rel_type,
            direction=direction
        )
        
        # 序列化 Neo4j 对象
        serialized = []
        for item in relations:
            try:
                m = item.get('m', {})
                r = item.get('r', {})
                serialized.append({
                    "node": serialize_neo4j_object(dict(m)) if hasattr(m, 'items') else serialize_neo4j_object(m),
                    "relation": serialize_neo4j_object(dict(r)) if hasattr(r, 'items') else serialize_neo4j_object(r)
                })
            except:
                pass
        
        return jsonify({"success": True, "data": serialized, "count": len(serialized)})
    except Exception as e:
        logger.error(f"获取节点关系失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 文档列表 ====================

@kg_bp.route('/documents', methods=['GET'])
def list_documents():
    """获取已入库的文档列表
    
    从 Neo4j 中查询所有具有 doc_id 或 source 属性的节点，提取唯一文档标识
    """
    try:
        rag_service = get_rag_service()
        try:
            database = _normalize_graph_database(request.args.get('database', None, type=str))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        
        # 查询所有具有 doc_id 或 source 属性的唯一文档
        cypher = """
        MATCH (n)
        WHERE n.doc_id IS NOT NULL OR n.source IS NOT NULL
        WITH COALESCE(n.doc_id, n.source) AS doc_id, 
             COALESCE(n.doc_title, n.title, n.source) AS title
        RETURN DISTINCT doc_id, title
        ORDER BY doc_id
        LIMIT 100
        """
        
        results = rag_service.graph_service.execute_query(cypher, {}, database=database)
        
        documents = []
        for item in results:
            doc_id = item.get('doc_id')
            title = item.get('title')
            if doc_id:
                documents.append({
                    "doc_id": str(doc_id),
                    "title": str(title) if title else str(doc_id)
                })
        
        return jsonify({
            "success": True, 
            "data": {
                "documents": documents,
                "count": len(documents)
            }
        })
    except Exception as e:
        logger.error(f"获取文档列表失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/databases', methods=['GET'])
def list_databases():
    """获取 Neo4j 可用数据库列表"""
    try:
        rag_service = get_rag_service()
        conn_info = rag_service.graph_service.get_connection_info()
        databases = conn_info.get('databases', []) if isinstance(conn_info, dict) else []

        normalized = []
        for db in databases:
            name = db.get('name') if isinstance(db, dict) else None
            if not name:
                continue
            normalized.append({
                "name": str(name),
                "status": db.get('currentStatus') if isinstance(db, dict) else None,
                "default": bool(db.get('default')) if isinstance(db, dict) else False,
                "access": db.get('access') if isinstance(db, dict) else None,
            })

        normalized.sort(key=lambda x: (not x.get('default', False), x['name']))
        return jsonify({"success": True, "data": {"databases": normalized}})
    except Exception as e:
        logger.error(f"获取数据库列表失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/databases/<string:db_name>/export', methods=['GET'])
def export_database_graph(db_name: str):
    """按数据库导出图谱数据"""
    try:
        if not db_name or db_name.strip().lower() == 'system':
            return jsonify({"success": False, "error": "非法数据库名称"}), 400

        rag_service = get_rag_service()
        graph_service = rag_service.graph_service

        node_query = """
        MATCH (n)
        RETURN elementId(n) AS element_id, elementId(n) AS neo_id, labels(n) AS labels, properties(n) AS properties
        """
        rel_query = """
        MATCH (a)-[r]->(b)
        RETURN elementId(r) AS element_id, elementId(r) AS neo_id, type(r) AS type,
               elementId(a) AS source, elementId(b) AS target, properties(r) AS properties
        """

        node_rows = graph_service.execute_query(node_query, {}, database=db_name)
        rel_rows = graph_service.execute_query(rel_query, {}, database=db_name)

        nodes = [
            {
                "id": str(row.get("element_id") or row.get("neo_id")),
                "neo_id": row.get("neo_id"),
                "labels": serialize_neo4j_object(row.get("labels") or []),
                "properties": serialize_neo4j_object(row.get("properties") or {}),
            }
            for row in node_rows
        ]

        edges = [
            {
                "id": str(row.get("element_id") or row.get("neo_id")),
                "neo_id": row.get("neo_id"),
                "type": str(row.get("type") or "UNKNOWN"),
                "source": str(row.get("source")),
                "target": str(row.get("target")),
                "properties": serialize_neo4j_object(row.get("properties") or {}),
            }
            for row in rel_rows
        ]

        return jsonify({
            "success": True,
            "data": {
                "database": db_name,
                "nodes": nodes,
                "edges": edges,
                "stats": {
                    "nodes": len(nodes),
                    "edges": len(edges),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        })
    except Exception as e:
        logger.error(f"数据库导出失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/databases/<string:db_name>/clear', methods=['POST'])
def clear_database_graph(db_name: str):
    """按数据库清空图谱数据（仅清空节点与关系，不删除数据库）"""
    try:
        if not db_name or db_name.strip().lower() == 'system':
            return jsonify({"success": False, "error": "非法数据库名称"}), 400

        rag_service = get_rag_service()
        graph_service = rag_service.graph_service

        before_nodes = graph_service.execute_query_single(
            "MATCH (n) RETURN count(n) AS count",
            {},
            database=db_name,
        )
        before_edges = graph_service.execute_query_single(
            "MATCH ()-[r]->() RETURN count(r) AS count",
            {},
            database=db_name,
        )

        graph_service.execute_query("MATCH (n) DETACH DELETE n", {}, database=db_name)

        after_nodes = graph_service.execute_query_single(
            "MATCH (n) RETURN count(n) AS count",
            {},
            database=db_name,
        )
        after_edges = graph_service.execute_query_single(
            "MATCH ()-[r]->() RETURN count(r) AS count",
            {},
            database=db_name,
        )

        nodes_before = int((before_nodes or {}).get("count", 0))
        edges_before = int((before_edges or {}).get("count", 0))
        nodes_after = int((after_nodes or {}).get("count", 0))
        edges_after = int((after_edges or {}).get("count", 0))

        return jsonify({
            "success": True,
            "data": {
                "database": db_name,
                "nodes_before": nodes_before,
                "edges_before": edges_before,
                "nodes_after": nodes_after,
                "edges_after": edges_after,
                "deleted_nodes": max(0, nodes_before - nodes_after),
                "deleted_edges": max(0, edges_before - edges_after),
            }
        })
    except Exception as e:
        logger.error(f"数据库清空失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/databases/<string:db_name>/integrity', methods=['GET'])
def check_database_integrity(db_name: str):
    """检测数据库完整性：向量/源数据/Neo4j 三类状态"""
    try:
        if not db_name or db_name.strip().lower() == 'system':
            return jsonify({"success": False, "error": "非法数据库名称"}), 400

        rag_service = get_rag_service()
        graph_service = rag_service.graph_service

        neo_nodes = graph_service.execute_query_single(
            "MATCH (n) WHERE NOT n:Chunk RETURN count(n) AS count",
            {},
            database=db_name,
        )
        neo_edges = graph_service.execute_query_single(
            "MATCH ()-[r]->() RETURN count(r) AS count",
            {},
            database=db_name,
        )

        source_docs_row = graph_service.execute_query_single(
            "MATCH (d:Document) RETURN count(d) AS count",
            {},
            database=db_name,
        )
        source_chunks_row = graph_service.execute_query_single(
            "MATCH (c:Chunk) RETURN count(c) AS count",
            {},
            database=db_name,
        )
        graph_chunks_row = graph_service.execute_query_single(
            """
            MATCH (d:Document)-[:CONTAINS]->(c:Chunk)
            RETURN count(DISTINCT c) AS count
            """,
            {},
            database=db_name,
        )
        
        # 检测孤立Chunk（1. 没有vec_id或 2. 没有对应Document）
        orphaned_chunks_row = graph_service.execute_query_single(
            """
            MATCH (c:Chunk)
            WHERE (c.vec_id IS NULL OR c.vec_id = '') 
               OR NOT EXISTS { MATCH (d:Document)-[:CONTAINS]->(c) }
            RETURN count(c) AS count
            """,
            {},
            database=db_name,
        )

        source_docs = int((source_docs_row or {}).get('count', 0))
        source_chunks = int((source_chunks_row or {}).get('count', 0))
        graph_chunks = int((graph_chunks_row or {}).get('count', 0))
        orphaned_chunks = int((orphaned_chunks_row or {}).get('count', 0))

        vector_count = _count_vectors_for_database(db_name)

        neo_nodes_count = int((neo_nodes or {}).get('count', 0))
        neo_edges_count = int((neo_edges or {}).get('count', 0))

        # 实体节点数（纯实体型 KG 的向量覆盖率计算基准）——排除 Chunk/Document/Community
        entity_nodes_row = graph_service.execute_query_single(
            "MATCH (n) WHERE NOT n:Chunk AND NOT n:Document AND NOT n:Community RETURN COUNT(n) AS count",
            {},
            database=db_name,
        )
        entity_nodes_count = int((entity_nodes_row or {}).get('count', 0))

        # 向量覆盖率：如果是文档型用 graph_chunks 作分母，实体型用 entity_nodes_count 作分母
        reference_count = graph_chunks if graph_chunks > 0 else entity_nodes_count
        raw_coverage = (vector_count / reference_count) if reference_count > 0 else 1.0
        vector_coverage = round(min(raw_coverage, 1.0), 4)  # cap 到 1.0，避免向量重复导致超过 100%

        # 向量缺失：完全为空，或覆盖率（未 cap）低于 100%（且实体/chunk 数足够）
        vector_missing = vector_count == 0 or (
            reference_count >= 50 and raw_coverage < 1.0
        )

        # 社区数量（统计有 community_id 属性的非Chunk/Document节点的不同社区数）
        comm_row = graph_service.execute_query_single(
            """
            MATCH (n)
            WHERE n.community_id IS NOT NULL AND NOT n:Chunk AND NOT n:Document
            RETURN COUNT(DISTINCT n.community_id) AS count
            """,
            {},
            database=db_name,
        )
        communities_count = int((comm_row or {}).get('count', 0))

        # 社区缺失：节点数足够多（>100）但没有社区划分
        community_missing = communities_count == 0 and neo_nodes_count > 100

        status = {
            "vector_missing": vector_missing,
            # 纯实体型 KG（neo_nodes 足够多）无需文档源，不标记 source_missing
            "source_missing": source_docs == 0 and source_chunks == 0 and neo_nodes_count < 50,
            "neo_missing": neo_nodes_count == 0,
            "orphaned_chunks": orphaned_chunks > 0,
            "community_missing": community_missing,
        }
        status["all_healthy"] = not any(status.values())

        return jsonify({
            "success": True,
            "data": {
                "database": db_name,
                "status": status,
                "counts": {
                    "neo_nodes": neo_nodes_count,
                    "neo_edges": neo_edges_count,
                    "source_docs": source_docs,
                    "source_chunks": source_chunks,
                    "graph_chunks": graph_chunks,
                    "vectors": vector_count,
                    "orphaned_chunks": orphaned_chunks,
                    "entity_nodes": entity_nodes_count,
                    "vector_coverage": vector_coverage,
                    "communities": communities_count,
                }
            }
        })
    except Exception as e:
        logger.error(f"数据库完整性检测失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500



@kg_bp.route('/databases/<string:db_name>/repair', methods=['POST'])
def repair_database_integrity(db_name: str):
    """自动修复数据库缺失：支持向量重建与 Neo4j 重建"""
    try:
        if not db_name or db_name.strip().lower() == 'system':
            return jsonify({"success": False, "error": "非法数据库名称"}), 400

        payload = request.json or {}
        targets = payload.get('targets') or ['neo4j']
        if not isinstance(targets, list):
            targets = ['neo4j']
        neo4j_only = bool(payload.get('neo4j_only') or payload.get('prefer_neo4j_only'))
        max_neo_chunks = int(payload.get('max_neo_chunks') or 8000)
        if max_neo_chunks <= 0:
            max_neo_chunks = 8000

        svc = getattr(current_app, 'graphrag_service', None) or get_rag_service()

        repaired = {
            "vector_repaired": False,
            "neo4j_repaired": False,
            "vector_docs_upserted": 0,
            "neo4j_docs_reingested": 0,
            "vector_error": None,
            "neo4j_error": None,
            "notes": [],
        }

        # 优先绑定当前数据库已出现的 doc_id，避免跨库误修复
        graph_service = get_rag_service().graph_service
        db_doc_id_rows = graph_service.execute_query(
            """
            MATCH (d:Document)
            WHERE d.doc_id IS NOT NULL
            RETURN DISTINCT d.doc_id AS doc_id
            LIMIT 5000
            """,
            {},
            database=db_name,
        )
        scoped_doc_ids = {
            str(row.get('doc_id')).strip()
            for row in (db_doc_id_rows or [])
            if row and row.get('doc_id') is not None and str(row.get('doc_id')).strip()
        }

        source_chunks_all = db.session.query(DocumentChunk).order_by(DocumentChunk.created_at.asc()).limit(5000).all()
        source_docs_all = db.session.query(Document).order_by(Document.created_at.asc()).limit(200).all()

        if scoped_doc_ids:
            source_chunks = [c for c in source_chunks_all if str(c.doc_id) in scoped_doc_ids]
            source_docs = [d for d in source_docs_all if str(d.doc_id) in scoped_doc_ids]
            if not source_chunks:
                source_chunks = source_chunks_all
            if not source_docs:
                source_docs = source_docs_all
        else:
            source_chunks = source_chunks_all
            source_docs = source_docs_all

        if neo4j_only:
            source_chunks = []
            source_docs = []
            repaired['notes'].append('已启用 neo4j_only：跳过 kb_* 源表，仅使用 Neo4j 数据修复')

        # Neo4j Chunk 回退源（当 kb_* 源表不可用时）
        neo_chunks = graph_service.execute_query(
            """
            MATCH (c:Chunk)
            RETURN elementId(c) AS neo_id,
                   c.doc_id AS doc_id,
                   c.idx AS chunk_index,
                   c.text AS content,
                   c.vec_id AS vec_id
            LIMIT $limit
            """,
            {"limit": max_neo_chunks},
            database=db_name,
        ) or []

        # 查询实体节点数（纯实体型 KG 向量修复的判断依据）
        entity_nodes_count_row = graph_service.execute_query_single(
            "MATCH (n) WHERE NOT n:Chunk AND NOT n:Document RETURN COUNT(n) AS count",
            {},
            database=db_name,
        )
        entity_nodes_count = int((entity_nodes_count_row or {}).get('count', 0))
        max_entity_limit = int(payload.get('max_entity_limit') or 50000)
        if max_entity_limit <= 0:
            max_entity_limit = 50000

        if 'vector' in targets:
            if source_chunks:
                try:
                    from langchain_core.documents import Document as LCDocument
                    from app.services.embedding import EmbeddingService

                    docs = []
                    for chunk in source_chunks:
                        content = (chunk.content or '').strip()
                        if not content:
                            continue
                        docs.append(LCDocument(
                            page_content=content,
                            metadata={
                                'doc_id': str(chunk.doc_id),
                                'chunk_index': chunk.chunk_index,
                                'repair': True,
                                'database': db_name,
                            }
                        ))

                    if docs:
                        emb = EmbeddingService()
                        collection = _vector_collection_for_database(db_name)
                        emb.add_documents(docs, collection)
                        repaired['vector_repaired'] = True
                        repaired['vector_docs_upserted'] = len(docs)
                    else:
                        repaired['notes'].append('无可用 chunk 文本用于向量修复')
                except Exception as vector_error:
                    repaired['vector_error'] = str(vector_error)
                    repaired['notes'].append('向量修复失败，已跳过并继续执行其他修复项')
            elif neo_chunks:
                try:
                    vector_docs_upserted = 0
                    use_db_ctx = hasattr(svc, '_use_database')
                    vector_store_getter = getattr(svc, '_get_vector_store', None)

                    if not callable(vector_store_getter):
                        raise RuntimeError('GraphRAG service missing _get_vector_store')

                    if use_db_ctx:
                        with svc._use_database(db_name):
                            vector_store, _ = svc._get_vector_store(database=db_name)
                            if not vector_store or not hasattr(vector_store, 'add_texts'):
                                raise RuntimeError('Vector store not available for Neo4j fallback repair')

                            for row in neo_chunks:
                                content = str((row or {}).get('content') or '').strip()
                                if not content:
                                    continue

                                neo_id = str((row or {}).get('neo_id') or '').strip()
                                vec_id = str((row or {}).get('vec_id') or '').strip()
                                if not vec_id:
                                    vec_id = f"chunk_{neo_id}"

                                vector_store.add_texts(
                                    [content],
                                    metadatas=[{
                                        'doc_id': str((row or {}).get('doc_id') or ''),
                                        'chunk_index': (row or {}).get('chunk_index'),
                                        'neo_node_id': neo_id,
                                        'repair': True,
                                        'database': db_name,
                                    }],
                                    ids=[vec_id],
                                )
                                vector_docs_upserted += 1

                                if not (row or {}).get('vec_id'):
                                    graph_service.execute_query(
                                        "MATCH (c:Chunk) WHERE elementId(c) = $eid SET c.vec_id = $vec",
                                        {'eid': neo_id, 'vec': vec_id},
                                        database=db_name,
                                    )
                    else:
                        vector_store, _ = svc._get_vector_store(database=db_name)
                        if not vector_store or not hasattr(vector_store, 'add_texts'):
                            raise RuntimeError('Vector store not available for Neo4j fallback repair')

                        for row in neo_chunks:
                            content = str((row or {}).get('content') or '').strip()
                            if not content:
                                continue

                            neo_id = str((row or {}).get('neo_id') or '').strip()
                            vec_id = str((row or {}).get('vec_id') or '').strip()
                            if not vec_id:
                                vec_id = f"chunk_{neo_id}"

                            vector_store.add_texts(
                                [content],
                                metadatas=[{
                                    'doc_id': str((row or {}).get('doc_id') or ''),
                                    'chunk_index': (row or {}).get('chunk_index'),
                                    'neo_node_id': neo_id,
                                    'repair': True,
                                    'database': db_name,
                                }],
                                ids=[vec_id],
                            )
                            vector_docs_upserted += 1

                            if not (row or {}).get('vec_id'):
                                graph_service.execute_query(
                                    "MATCH (c:Chunk) WHERE elementId(c) = $eid SET c.vec_id = $vec",
                                    {'eid': neo_id, 'vec': vec_id},
                                    database=db_name,
                                )

                    repaired['vector_repaired'] = vector_docs_upserted > 0
                    repaired['vector_docs_upserted'] = vector_docs_upserted
                    if vector_docs_upserted == 0:
                        repaired['notes'].append('Neo4j Chunk 文本为空，未写入向量')
                except Exception as vector_error:
                    repaired['vector_error'] = str(vector_error)
                    repaired['notes'].append('Neo4j 回退向量修复失败')
            elif entity_nodes_count > 0:
                # Level 3: 纯实体型 KG — 排除 Community 节点，分页拉取（每页 2000 条）
                try:
                    vector_store_getter = getattr(svc, '_get_vector_store', None)
                    if not callable(vector_store_getter):
                        repaired['notes'].append('GraphRAG 服务不支持 _get_vector_store，实体向量化跳过')
                    else:
                        if hasattr(svc, '_use_database'):
                            with svc._use_database(db_name):
                                vector_store, _ = svc._get_vector_store(database=db_name)
                        else:
                            vector_store, _ = svc._get_vector_store(database=db_name)

                        if not (vector_store and hasattr(vector_store, 'add_texts')):
                            repaired['notes'].append('向量存储不可用，实体向量化跳过')
                        else:
                            # 先删除旧向量，避免重复进行导致统计超过 100%
                            collection_name = _vector_collection_for_database(db_name)
                            try:
                                db.session.execute(
                                    text("""
                                        DELETE FROM kg_pg_embedding
                                        WHERE collection_id = (
                                            SELECT uuid FROM kg_pg_collection WHERE name = :name LIMIT 1
                                        )
                                    """),
                                    {"name": collection_name},
                                )
                                db.session.commit()
                                repaired['notes'].append(f'已清空旧向量（collection: {collection_name}）')
                            except Exception as del_err:
                                db.session.rollback()
                                repaired['notes'].append(f'清除旧向量失败（继续写入）: {del_err}')

                            page_size = 2000
                            skip = 0
                            entity_added = 0
                            while True:
                                if skip >= max_entity_limit:
                                    break
                                # 同时拉取直接关系（每节点取 Top-10），用于丰富向量文本
                                entity_rows = graph_service.execute_query(
                                    """
                                    MATCH (n)
                                    WHERE NOT n:Chunk AND NOT n:Document AND NOT n:Community
                                    OPTIONAL MATCH (n)-[r]->(m)
                                    WHERE NOT m:Chunk AND NOT m:Document AND NOT m:Community
                                    WITH n, labels(n) AS node_labels, properties(n) AS props,
                                         elementId(n) AS neo_id,
                                         collect({t: type(r), n: coalesce(m.name, m.id, '')})[0..10] AS rels
                                    RETURN node_labels, props, neo_id, rels
                                    ORDER BY neo_id
                                    SKIP $skip LIMIT $page_size
                                    """,
                                    {"skip": skip, "page_size": page_size},
                                    database=db_name,
                                ) or []
                                if not entity_rows:
                                    break
                                skip += len(entity_rows)

                                batch_texts, batch_metas, batch_ids = [], [], []
                                for row in entity_rows:
                                    props = (row or {}).get('props') or {}
                                    node_labels = (row or {}).get('node_labels') or []
                                    neo_id = str((row or {}).get('neo_id') or '')
                                    rels = (row or {}).get('rels') or []
                                    if not isinstance(props, dict):
                                        continue
                                    name = (
                                        props.get('name') or props.get('title') or
                                        props.get('id') or props.get('node_id') or ''
                                    )
                                    desc = (
                                        props.get('description') or props.get('text') or
                                        props.get('intro') or ''
                                    )
                                    parts = []
                                    if name:
                                        parts.append(f"名称：{name}")
                                    if desc:
                                        parts.append(f"描述：{str(desc)[:300]}")
                                    if not parts:
                                        for k, v in list(props.items())[:5]:
                                            if v is not None and k not in ('embedding', 'vec_id', 'id', 'community_id'):
                                                parts.append(f"{k}：{v}")
                                    if not parts:
                                        continue

                                    # 按关系类型分组，每种类型取 Top-5 目标节点名
                                    if rels:
                                        rel_groups: dict = {}
                                        for rel in rels:
                                            if not isinstance(rel, dict):
                                                continue
                                            rt = rel.get('t') or ''
                                            rn = rel.get('n') or ''
                                            if rt and rn:
                                                rel_groups.setdefault(rt, [])
                                                if len(rel_groups[rt]) < 5:
                                                    rel_groups[rt].append(rn)
                                        for rel_type, targets in list(rel_groups.items())[:6]:
                                            # 关系类型名转中文展示（尽量可读）
                                            parts.append(f"{rel_type}：{'、'.join(targets)}")

                                    text = f"[{','.join(node_labels)}] " + "；".join(parts)
                                    batch_texts.append(text.strip())
                                    batch_metas.append({
                                        'neo_node_id': neo_id,
                                        'labels': ','.join(node_labels),
                                        'database': db_name,
                                        'entity_name': str(name),
                                        'repair': True,
                                    })
                                    batch_ids.append(f"entity_{neo_id}")

                                if batch_texts:
                                    batch_size = 200
                                    for i in range(0, len(batch_texts), batch_size):
                                        vector_store.add_texts(
                                            batch_texts[i:i + batch_size],
                                            metadatas=batch_metas[i:i + batch_size],
                                            ids=batch_ids[i:i + batch_size],
                                        )
                                    entity_added += len(batch_texts)

                            if entity_added > 0:
                                repaired['vector_repaired'] = True
                                repaired['vector_docs_upserted'] = entity_added
                                repaired['notes'].append(
                                    f'已对 {entity_added} 个实体节点完成向量化（知识图谱实体模式）'
                                )
                            else:
                                repaired['notes'].append('实体节点无有效文本属性，无法向量化')
                except Exception as entity_vec_err:
                    repaired['vector_error'] = str(entity_vec_err)
                    repaired['notes'].append('实体向量化出错')
            else:
                repaired['notes'].append('缺少源 chunk 且无实体节点，无法修复向量')

        if 'neo4j' in targets and svc and hasattr(svc, 'ingest_text'):
            if entity_nodes_count > 0 and not source_docs:
                # 纯实体型 KG：实体已存在，通过向量化路径处理即可
                repaired['notes'].append('知识图谱实体库结构完整，无需重建文档节点，已跳过 Neo4j 修复')
                repaired['neo4j_repaired'] = True
                repaired['neo4j_docs_reingested'] = 0
            else:
                reingested = 0
                use_db_ctx = hasattr(svc, '_use_database')

                try:
                    for doc in source_docs:
                        content = (doc.content or '').strip()
                        if not content:
                            continue
                        if use_db_ctx:
                            with svc._use_database(db_name):
                                svc.ingest_text(str(doc.doc_id), content, filename=doc.filename)
                        else:
                            svc.ingest_text(str(doc.doc_id), content, filename=doc.filename)
                        reingested += 1

                    if reingested == 0 and source_chunks:
                        # 回退：按 doc_id 聚合 chunk 文本重建 Neo4j
                        chunks_by_doc: Dict[str, List[str]] = {}
                        for chunk in source_chunks:
                            key = str(chunk.doc_id)
                            chunks_by_doc.setdefault(key, []).append(chunk.content or '')

                        for doc_id, texts in list(chunks_by_doc.items())[:80]:
                            merged = '\n'.join([t for t in texts if t.strip()][:20]).strip()
                            if not merged:
                                continue
                            if use_db_ctx:
                                with svc._use_database(db_name):
                                    svc.ingest_text(doc_id, merged, filename=f'repair_{doc_id}')
                            else:
                                svc.ingest_text(doc_id, merged, filename=f'repair_{doc_id}')
                            reingested += 1

                except Exception as neo_error:
                    repaired['neo4j_error'] = str(neo_error)

                repaired['neo4j_repaired'] = reingested > 0
                repaired['neo4j_docs_reingested'] = reingested
                if reingested == 0:
                    repaired['notes'].append('缺少可用源文本，无法重建 Neo4j')

        if 'neo4j' in targets and (not svc or not hasattr(svc, 'ingest_text')):
            repaired['notes'].append('当前服务不支持 ingest_text，已跳过 Neo4j 修复')

        return jsonify({"success": True, "data": {"database": db_name, **repaired}})
    except Exception as e:
        logger.error(f"数据库自动修复失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/databases/<string:db_name>/vectors/reconcile', methods=['POST'])
def reconcile_database_vectors(db_name: str):
    """收口历史全局向量：支持 keep/migrate/delete 三种策略。"""
    try:
        if not db_name or db_name.strip().lower() == 'system':
            return jsonify({"success": False, "error": "非法数据库名称"}), 400

        payload = request.json or {}
        strategy = str(payload.get('strategy', 'migrate')).strip().lower()
        source_collection = payload.get('source_collection')

        svc = getattr(current_app, 'graphrag_service', None) or get_rag_service()
        if not svc or not hasattr(svc, 'reconcile_legacy_vectors'):
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500

        result = svc.reconcile_legacy_vectors(
            database=db_name,
            strategy=strategy,
            source_collection=source_collection,
        )
        if not result.get('success'):
            return jsonify({"success": False, "error": result.get('error', '收口失败'), "data": result}), 500

        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"向量收口失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/documents/analysis', methods=['GET'])
def get_documents_analysis():
    """获取文档分析数据（关键节点和类型分布）"""
    try:
        limit = request.args.get('limit', 20, type=int)
        rag_service = get_rag_service()
        
        # 确保 rag_service.kg_query 有 get_document_analysis 方法
        # 如果没有（例如旧版本），则需要更新 kg_query.py
        if not hasattr(rag_service.kg_query, 'get_document_analysis'):
             return jsonify({"success": False, "error": "Method not implemented"}), 501
             
        analysis = rag_service.kg_query.get_document_analysis(limit=limit)
        
        # 序列化结果中的 Neo4j 对象（如果有）
        # get_document_analysis 已经返回了字典结构，但为了保险起见，可以再处理一下
        # 这里假设 get_document_analysis 返回的是纯 Python 字典/列表
        
        return jsonify({"success": True, "data": analysis})
    except Exception as e:
        logger.error(f"获取文档分析失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 路径查询 ====================

@kg_bp.route('/paths/shortest', methods=['GET'])
def find_shortest_path():
    """查找最短路径"""
    try:
        start_id = request.args.get('start', '')
        end_id = request.args.get('end', '')
        
        if not start_id or not end_id:
            return jsonify({"success": False, "error": "start 和 end 参数不能为空"}), 400
        
        rag_service = get_rag_service()
        path = rag_service.kg_query.find_shortest_path(start_id, end_id)
        
        # 序列化路径数据
        serialized_path = serialize_neo4j_object(path)
        
        return jsonify({"success": True, "data": serialized_path, "path_length": len(path) if path else 0})
    except Exception as e:
        logger.error(f"路径查询失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/paths', methods=['GET'])
def find_paths():
    """查找所有路径"""
    try:
        start_id = request.args.get('start', '')
        end_id = request.args.get('end', '')
        max_length = request.args.get('max_length', 5, type=int)
        
        if not start_id or not end_id:
            return jsonify({"success": False, "error": "start 和 end 参数不能为空"}), 400
        
        rag_service = get_rag_service()
        paths = rag_service.kg_query.find_paths(start_id, end_id, max_length=max_length)
        
        return jsonify({"success": True, "data": paths, "count": len(paths)})
    except Exception as e:
        logger.error(f"路径查询失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 文档入库 ====================

@kg_bp.route('/upload', methods=['POST'])
def upload_document():
    """上传文档并构建知识图谱（含向量化）
    
    统一调用 ingest 逻辑，实现：
    - 文本分块
    - 实体/关系提取 → Neo4j
    - 向量生成 → PGVector
    """
    try:
        data = request.json
        text = data.get('text', '')
        document_id = data.get('document_id', '')
        document_title = data.get('document_title', '')
        try:
            database = _require_graph_database(data.get('database'))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        
        if not text:
            return jsonify({"success": False, "error": "文本不能为空"}), 400
        
        # 使用 graphrag_service.ingest_text 实现完整的 GraphRAG 入库
        svc = getattr(current_app, 'graphrag_service', None) or get_rag_service()
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500
        
        if hasattr(svc, '_use_database'):
            with svc._use_database(database):
                result = svc.ingest_text(
                    doc_id=document_id or document_title or 'doc',
                    text=text,
                    kb_id=None,
                    filename=document_title
                )
        else:
            result = svc.ingest_text(
                doc_id=document_id or document_title or 'doc',
                text=text,
                kb_id=None,
                filename=document_title
            )
        
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"文档上传失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/excel/import', methods=['POST'])
def import_excel():
    """Excel/CSV Schema 映射导入接口
    
    混合模式策略:
    1. 解析表格结构,识别列类型(实体/关系/属性)
    2. 结构化字段 → 直接创建 Neo4j 节点/边
    3. 自由文本列 → LLM 增强提取(可选)
    """
    file_path = None
    try:
        from werkzeug.utils import secure_filename
        import pandas as pd
        import os
        
        logger.info(f"收到 Excel 导入请求, files={list(request.files.keys())}, form={dict(request.form)}")
        
        # 检查文件
        if 'file' not in request.files:
            logger.error("未找到上传文件字段")
            return jsonify({"success": False, "error": "未找到上传文件"}), 400
        
        file = request.files['file']
        if not file or file.filename == '':
            logger.error("文件对象为空或文件名为空")
            return jsonify({"success": False, "error": "文件名为空"}), 400
        
        logger.info(f"接收到文件: {file.filename}")
        
        # 获取参数
        doc_id = request.form.get('doc_id', str(uuid.uuid4()))
        title = request.form.get('title', file.filename)
        database = request.form.get('database')
        
        # 保存临时文件 (处理中文文件名)
        original_filename = file.filename
        # 提取文件扩展名
        file_ext = os.path.splitext(original_filename)[1].lower()
        # 使用 UUID 生成临时文件名,避免 secure_filename 移除中文
        temp_filename = f"{uuid.uuid4()}{file_ext}"
        
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads/temp')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, temp_filename)
        file.save(file_path)
        logger.info(f"文件已保存至: {file_path}")
        
        # 解析表格
        logger.info(f"开始解析文件: {file_path}")
        if file_ext == '.csv':
            df = pd.read_csv(file_path, encoding='utf-8-sig')
        elif file_ext == '.xlsx':
            df = pd.read_excel(file_path, engine='openpyxl')
        else:
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({"success": False, "error": f"仅支持 .csv 和 .xlsx 格式,当前: {file_ext}"}), 400
        
        logger.info(f"文件解析成功, 行数={len(df)}, 列={list(df.columns)}")
        
        # Schema 自动推断 (智能检测列类型)
        entity_columns = []
        relation_columns = []
        attribute_columns = []
        text_columns = []
        
        for col in df.columns:
            col_lower = col.lower()
            sample_values = df[col].dropna().head(5).tolist()
            
            # 启发式规则判断
            if any(keyword in col_lower for keyword in ['id', 'name', 'title', 'entity']):
                entity_columns.append(col)
            elif any(keyword in col_lower for keyword in ['relation', 'link', 'connect', 'ref']):
                relation_columns.append(col)
            elif any(keyword in col_lower for keyword in ['desc', 'content', 'comment', 'review']):
                text_columns.append(col)
            else:
                attribute_columns.append(col)
        
        # 如果没有明确实体列,使用第一列作为实体
        if not entity_columns and len(df.columns) > 0:
            entity_columns = [df.columns[0]]
        
        # 调用 GraphRAG 服务导入数据
        svc = getattr(current_app, 'graphrag_service', None) or get_rag_service()
        if not svc:
            os.remove(file_path)
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500
        
        # 批量创建节点
        node_count = 0
        edge_count = 0
        text_ingest_count = 0
        
        logger.info(f"开始批量导入, 实体列={entity_columns}, 属性列={attribute_columns}, 文本列={text_columns}")
        
        for idx, row in df.iterrows():
            # 创建实体节点
            for entity_col in entity_columns:
                entity_name = str(row.get(entity_col, '')).strip()
                if not entity_name or entity_name == 'nan':
                    continue
                
                # 收集属性
                properties = {
                    'name': entity_name,
                    'source': title,
                    'doc_id': doc_id
                }
                for attr_col in attribute_columns:
                    attr_value = row.get(attr_col)
                    if pd.notna(attr_value):
                        properties[attr_col] = str(attr_value)
                
                # 写入 Neo4j
                try:
                    if hasattr(svc, '_use_database'):
                        with svc._use_database(database):
                            with (svc._session() if hasattr(svc, '_session') else svc.driver.session()) as session:
                                result = session.run("""
                                    MERGE (n:Entity {name: $name, doc_id: $doc_id})
                                    SET n += $properties
                                    RETURN n.name as name
                                """, name=entity_name, doc_id=doc_id, properties=properties)
                    else:
                        with (svc._session() if hasattr(svc, '_session') else svc.driver.session()) as session:
                            result = session.run("""
                                MERGE (n:Entity {name: $name, doc_id: $doc_id})
                                SET n += $properties
                                RETURN n.name as name
                            """, name=entity_name, doc_id=doc_id, properties=properties)
                        if result.single():
                            node_count += 1
                            if node_count <= 3:  # 只打印前3个
                                logger.info(f"  ✓ 创建节点: {entity_name}, 属性={list(properties.keys())}")
                except Exception as e:
                    logger.error(f"创建节点失败: {entity_name}, 错误={e}")
                
                # 处理文本列 (LLM 增强) - 暂时禁用,避免触发实体抽取
                # for text_col in text_columns:
                #     text_value = str(row.get(text_col, '')).strip()
                #     if text_value and len(text_value) > 10:
                #         try:
                #             svc.ingest_text(
                #                 doc_id=f"{doc_id}_{entity_name}_{text_col}",
                #                 text=f"{entity_name}: {text_value}",
                #                 kb_id=None,
                #                 filename=f"{title}_{text_col}"
                #             )
                #             text_ingest_count += 1
                #         except Exception as e:
                #             logger.error(f"文本入库失败: {e}")
        
        logger.info(f"批量导入完成, 共创建 {node_count} 个节点")
        
        # 验证数据是否写入 Neo4j
        actual_count = 0
        try:
            if hasattr(svc, '_use_database'):
                with svc._use_database(database):
                    with (svc._session() if hasattr(svc, '_session') else svc.driver.session()) as session:
                        result_check = session.run("""
                            MATCH (n:Entity {doc_id: $doc_id})
                            RETURN count(n) as cnt
                        """, doc_id=doc_id)
            else:
                with (svc._session() if hasattr(svc, '_session') else svc.driver.session()) as session:
                    result_check = session.run("""
                        MATCH (n:Entity {doc_id: $doc_id})
                        RETURN count(n) as cnt
                    """, doc_id=doc_id)
                record = result_check.single()
                if record:
                    actual_count = record['cnt']
                    logger.info(f"Neo4j 验证: doc_id={doc_id} 实际节点数={actual_count}")
        except Exception as e:
            logger.error(f"Neo4j 验证失败: {e}")
        
        # 清理临时文件
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"临时文件已清理: {file_path}")
        
        result = {
            "doc_id": doc_id,
            "title": title,
            "row_count": len(df),
            "node_count": node_count,
            "actual_node_count": actual_count,  # 实际 Neo4j 中的节点数
            "edge_count": edge_count,
            "entity_columns": entity_columns,
            "relation_columns": relation_columns,
            "attribute_columns": attribute_columns,
            "text_columns": text_columns
        }
        logger.info(f"Excel 导入成功: {result}")
        
        return jsonify({"success": True, "data": result})
        
    except Exception as e:
        logger.error(f"Excel导入失败: {e}", exc_info=True)
        # 清理临时文件
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/ingest', methods=['POST'])
def ingest():
    """最简入库接口：将文本切分并入 Neo4j + pgvector via graphrag_service.ingest_text"""
    try:
        data = request.json or {}
        text = data.get('text', '')
        doc_id = data.get('doc_id') or data.get('document_id') or ''
        kb_id = data.get('kb_id')
        filename = data.get('filename')
        try:
            database = _require_graph_database(data.get('database'))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        if not text:
            return jsonify({"success": False, "error": "text is required"}), 400

        svc = getattr(current_app, 'graphrag_service', None) or get_rag_service()
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500

        if hasattr(svc, '_use_database'):
            with svc._use_database(database):
                result = svc.ingest_text(doc_id or '', text, kb_id=kb_id, filename=filename)
        else:
            result = svc.ingest_text(doc_id or '', text, kb_id=kb_id, filename=filename)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"ingest failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/graph_rag_qa', methods=['POST'])
def graph_rag_qa():
    """最简问答接口：调用 graphrag_service.query 返回答案与候选子图"""
    try:
        data = request.json or {}
        question = data.get('question') or data.get('q') or ''
        top_k = int(data.get('top_k', 20))

        if not question:
            return jsonify({"success": False, "error": "question is required"}), 400

        svc = getattr(current_app, 'graphrag_service', None) or get_rag_service()
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500

        res = svc.query(question, top_k=top_k)
        return jsonify({"success": True, "data": res})
    except Exception as e:
        logger.error(f"graph_rag_qa failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# 可视化数据 

@kg_bp.route('/visualize', methods=['GET'])
def get_visualize_data():
    """获取图谱可视化数据
    
    Query Parameters:
        limit: 返回节点数量限制 (默认 1000，最大 5000)
        doc_id: 文档 ID，按文档筛选图谱范围 (可选)
        community_id: 社区 ID，按社区筛选图谱范围 (可选)
    """
    try:
        requested_limit = request.args.get('limit', 1000, type=int)
        limit = max(100, min(5000, requested_limit or 1000))
        doc_id = request.args.get('doc_id', None, type=str)
        community_id = request.args.get('community_id', None, type=int)
        try:
            database = _normalize_graph_database(request.args.get('database', None, type=str))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        
        rag_service = get_rag_service()
        
                # 根据筛选条件构建不同的 Cypher 查询
        if doc_id:
                        # 按文档 ID 筛选：查询该文档相关的所有节点和关系 (排除 Chunk 节点)
            cypher = """
                        MATCH (a)-[r]->(b)
            WHERE a <> b 
                            AND NOT a:Chunk AND NOT b:Chunk
              AND (a.source = $doc_id OR a.doc_id = $doc_id OR b.source = $doc_id OR b.doc_id = $doc_id)
            RETURN a, r, b
            LIMIT $limit
            """
            params = {"limit": limit, "doc_id": doc_id}
        elif community_id is not None:
            # 按社区 ID 筛选：查询该社区内的所有节点和关系 (排除 Chunk 节点)
            cypher = """
                        MATCH (a)-[r]->(b)
            WHERE a <> b 
                            AND NOT a:Chunk AND NOT b:Chunk
              AND (a.community_id = $community_id OR b.community_id = $community_id)
            RETURN a, r, b
            LIMIT $limit
            """
            params = {"limit": limit, "community_id": community_id}
        else:
            # 默认：返回所有节点和关系 (排除 Chunk 节点)
            cypher = """
                        MATCH (a)-[r]->(b)
            WHERE a <> b 
                            AND NOT a:Chunk AND NOT b:Chunk
            RETURN a, r, b
            LIMIT $limit
            """
            params = {"limit": limit}
        
        rels_data = rag_service.graph_service.execute_query(cypher, params, database=database)

        # 若当前数据库只有孤立节点（无边），补充返回节点，避免前端空白
        node_rows = []
        if not rels_data:
            if doc_id:
                node_cypher = """
                MATCH (n)
                WHERE NOT n:Chunk
                  AND (n.source = $doc_id OR n.doc_id = $doc_id)
                RETURN n
                LIMIT $limit
                """
                node_rows = rag_service.graph_service.execute_query(
                    node_cypher,
                    {"limit": limit, "doc_id": doc_id},
                    database=database,
                )
            elif community_id is not None:
                node_cypher = """
                MATCH (n)
                WHERE NOT n:Chunk
                  AND n.community_id = $community_id
                RETURN n
                LIMIT $limit
                """
                node_rows = rag_service.graph_service.execute_query(
                    node_cypher,
                    {"limit": limit, "community_id": community_id},
                    database=database,
                )
            else:
                node_cypher = """
                MATCH (n)
                WHERE NOT n:Chunk
                RETURN n
                LIMIT $limit
                """
                node_rows = rag_service.graph_service.execute_query(
                    node_cypher,
                    {"limit": limit},
                    database=database,
                )
        
        # 转换为可视化格式
        def resolve_node_label(node_obj):
            if node_obj is None:
                return ""
            
            # 优先查找的属性列表
            label_keys = ("name", "title", "label", "caption", "filename", "text", "content", "description")
            
            if isinstance(node_obj, dict):
                for key in label_keys:
                    value = node_obj.get(key)
                    if value:
                        val_str = str(value)
                        # 如果是长文本（如 text/content），截断显示
                        if key in ("text", "content", "description") and len(val_str) > 20:
                            return val_str[:20] + "..."
                        return val_str
                return ""
            
            getter = getattr(node_obj, "get", None)
            if callable(getter):
                for key in label_keys:
                    try:
                        value = getter(key)
                    except TypeError:
                        value = None
                    if value:
                        val_str = str(value)
                        if key in ("text", "content", "description") and len(val_str) > 20:
                            return val_str[:20] + "..."
                        return val_str
            return ""

        def resolve_node_category(node_obj):
            if node_obj is None:
                return "unknown"
            
            # 优先从 type 属性获取分类（这是实体的真实类型，如 PERSON, ORGANIZATION 等）
            type_value = None
            if isinstance(node_obj, dict):
                type_value = node_obj.get("type") or node_obj.get("category") or node_obj.get("kind")
            else:
                getter = getattr(node_obj, "get", None)
                if callable(getter):
                    try:
                        type_value = getter("type") or getter("category") or getter("kind")
                    except TypeError:
                        pass
            
            if type_value:
                return str(type_value).upper()
            
            # 回退到 labels
            labels: list = []
            if hasattr(node_obj, "labels"):
                try:
                    labels = list(getattr(node_obj, "labels"))
                except TypeError:
                    labels = []
            if not labels and isinstance(node_obj, dict):
                raw_labels = node_obj.get("labels") or node_obj.get("label")
                if isinstance(raw_labels, (list, tuple, set)):
                    labels = list(raw_labels)
                elif raw_labels:
                    labels = [raw_labels]
            
            # 过滤掉通用标签，优先返回更具体的标签
            specific_labels = [l for l in labels if l not in ('Entity', 'Chunk', 'Document', 'Node')]
            if specific_labels:
                return str(specific_labels[0]).upper()
            
            category = labels[0] if labels else "unknown"
            return str(category).upper()

        def resolve_node_id(node_obj):
            if node_obj is None:
                return None
            candidate_keys = ("id", "uid", "uuid", "guid", "element_id")
            if isinstance(node_obj, dict):
                for key in candidate_keys:
                    value = node_obj.get(key)
                    if value:
                        return str(value)
            getter = getattr(node_obj, "get", None)
            if callable(getter):
                for key in candidate_keys:
                    try:
                        value = getter(key)
                    except TypeError:
                        value = None
                    if value:
                        return str(value)
            element_id = getattr(node_obj, "element_id", None)
            if element_id:
                return str(element_id)
            internal_id = getattr(node_obj, "id", None)
            if internal_id is not None:
                return str(internal_id)
            fallback_label = resolve_node_label(node_obj)
            return str(fallback_label) if fallback_label else None

        def resolve_relation_label(rel_obj):
            if rel_obj is None:
                return "UNKNOWN"
            relation_type = None
            if hasattr(rel_obj, "type"):
                relation_type = getattr(rel_obj, "type")
                if callable(relation_type):
                    relation_type = relation_type()
                if isinstance(relation_type, bytes):
                    try:
                        relation_type = relation_type.decode('utf-8')
                    except Exception:
                        relation_type = relation_type.decode('utf-8', errors='ignore')
            if not relation_type:
                if isinstance(rel_obj, dict):
                    relation_type = rel_obj.get("type")
                else:
                    getter = getattr(rel_obj, "get", None)
                    if callable(getter):
                        try:
                            relation_type = getter("type")
                        except TypeError:
                            relation_type = None
            if not relation_type:
                cls = getattr(rel_obj, "__class__", None)
                if cls is not None:
                    name = getattr(cls, "__name__", "")
                    if name:
                        relation_type = name
            return str(relation_type) if relation_type else "UNKNOWN"

        def resolve_relation_value(rel_obj):
            if rel_obj is None:
                return 1
            candidates = ("strength", "weight", "value", "count")
            if isinstance(rel_obj, dict):
                for key in candidates:
                    if key in rel_obj and rel_obj[key] is not None:
                        return rel_obj[key]
            getter = getattr(rel_obj, "get", None)
            if callable(getter):
                for key in candidates:
                    try:
                        value = getter(key)
                    except TypeError:
                        value = None
                    if value is not None:
                        return value
            return 1

        nodes = []
        node_index: dict = {}

        # 从关系数据中提取节点和边
        edges = []
        for item in rels_data:
            a = item.get('a')
            if a is None:
                a = item.get('start')
            if a is None:
                a = item.get('source')

            r = item.get('r')
            if r is None:
                r = item.get('rel')
            if r is None:
                r = item.get('relationship')

            b = item.get('b')
            if b is None:
                b = item.get('end')
            if b is None:
                b = item.get('target')

            source_id = resolve_node_id(a)
            target_id = resolve_node_id(b)

            if not source_id or not target_id:
                continue

            # 添加源节点
            if source_id not in node_index and a is not None:
                raw_props = dict(a) if hasattr(a, 'items') else {}
                node_index[source_id] = {
                    "id": source_id,
                    "label": resolve_node_label(a) or source_id,
                    "value": 1,
                    "category": resolve_node_category(a),
                    "properties": serialize_neo4j_object(raw_props)
                }
                nodes.append(node_index[source_id])

            # 添加目标节点
            if target_id not in node_index and b is not None:
                raw_props = dict(b) if hasattr(b, 'items') else {}
                node_index[target_id] = {
                    "id": target_id,
                    "label": resolve_node_label(b) or target_id,
                    "value": 1,
                    "category": resolve_node_category(b),
                    "properties": serialize_neo4j_object(raw_props)
                }
                nodes.append(node_index[target_id])

            # 添加边
            raw_props = dict(r) if hasattr(r, 'items') else {}
            edges.append({
                "id": resolve_relation_id(r),
                "source": source_id,
                "target": target_id,
                "label": resolve_relation_label(r),
                "value": resolve_relation_value(r),
                "properties": serialize_neo4j_object(raw_props)
            })
        
        if not edges and node_rows:
            for row in node_rows:
                n = row.get('n') if isinstance(row, dict) else None
                node_id = resolve_node_id(n)
                if not node_id or node_id in node_index or n is None:
                    continue
                raw_props = dict(n) if hasattr(n, 'items') else {}
                node_index[node_id] = {
                    "id": node_id,
                    "label": resolve_node_label(n) or node_id,
                    "value": 1,
                    "category": resolve_node_category(n),
                    "properties": serialize_neo4j_object(raw_props)
                }
                nodes.append(node_index[node_id])

        return jsonify({
            "success": True,
            "data": {
                "nodes": nodes,
                "edges": edges
            }
        })
    except Exception as e:
        logger.error(f"获取可视化数据失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def resolve_relation_id(rel_obj):
    if rel_obj is None:
        return None
    if hasattr(rel_obj, "element_id"):
        return str(rel_obj.element_id)
    if hasattr(rel_obj, "id"):
        return str(rel_obj.id)
    return None


# ==================== 知识管理接口 ====================

@kg_bp.route('/communities', methods=['GET'])
def list_communities():
    """获取社区列表"""
    try:
        doc_id = request.args.get('doc_id')
        try:
            database = _normalize_graph_database(request.args.get('database', None, type=str))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        rag_service = get_rag_service()
        
        if doc_id:
            cypher = """
            MATCH (n)
            WHERE (n.doc_id = $doc_id OR n.source = $doc_id) AND n.community_id IS NOT NULL
            RETURN DISTINCT n.community_id as community_id
            ORDER BY community_id
            """
            params = {"doc_id": doc_id}
        else:
            cypher = """
            MATCH (n)
            WHERE n.community_id IS NOT NULL
            RETURN DISTINCT n.community_id as community_id
            ORDER BY community_id
            LIMIT 100
            """
            params = {}
            
        results = rag_service.graph_service.execute_query(cypher, params, database=database)
        communities = [r['community_id'] for r in results]
        
        return jsonify({"success": True, "data": communities})
    except Exception as e:
        logger.error(f"获取社区列表失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/nodes/<node_id>', methods=['PUT'])
def update_node(node_id):
    """更新节点属性"""
    try:
        data = request.json
        properties = data.get('properties', {})
        
        rag_service = get_rag_service()
        
        # 尝试按 id 属性或 elementId 匹配
        cypher = """
        MATCH (n)
        WHERE n.id = $node_id OR elementId(n) = $node_id OR toString(id(n)) = $node_id
        SET n += $properties
        RETURN n
        """
        
        rag_service.graph_service.execute_query(cypher, {"node_id": node_id, "properties": properties})
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"更新节点失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/relations/<relation_id>', methods=['PUT'])
def update_relation(relation_id):
    """更新关系属性"""
    try:
        data = request.json
        properties = data.get('properties', {})
        
        rag_service = get_rag_service()
        
        # 尝试按 elementId 或 id() 匹配
        # 注意：id() 接受整数，elementId 接受字符串
        cypher = """
        MATCH ()-[r]->()
        WHERE elementId(r) = $rel_id OR toString(id(r)) = $rel_id
        SET r += $properties
        RETURN r
        """
        
        rag_service.graph_service.execute_query(cypher, {"rel_id": relation_id, "properties": properties})
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"更新关系失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/nodes/<node_id>', methods=['DELETE'])
def delete_node(node_id):
    """删除单个节点及其关联关系"""
    try:
        rag_service = get_rag_service()
        
        # 尝试按 id 属性或 elementId 匹配
        cypher = """
        MATCH (n)
        WHERE n.id = $node_id OR elementId(n) = $node_id
        DETACH DELETE n
        """
        
        rag_service.graph_service.execute_query(cypher, {"node_id": node_id})
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"删除节点失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/relations/<relation_id>', methods=['DELETE'])
def delete_relation(relation_id):
    """删除单个关系"""
    try:
        rag_service = get_rag_service()
        
        # 尝试按 elementId 或 id() 匹配
        cypher = """
        MATCH ()-[r]->()
        WHERE elementId(r) = $rel_id OR toString(id(r)) = $rel_id
        DELETE r
        """
        
        rag_service.graph_service.execute_query(cypher, {"rel_id": relation_id})
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"删除关系失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """删除文档及其关联的图数据"""
    try:
        # 尝试获取 GraphRAGService 以执行完整删除（含向量）
        svc = getattr(current_app, 'graphrag_service', None)
        
        if svc and hasattr(svc, 'delete_document'):
            result = svc.delete_document(doc_id)
            if not result.get("success"):
                raise Exception(result.get("error", "Unknown error"))
        else:
            # 回退：仅删除 Neo4j 数据
            rag_service = get_rag_service()
            cypher = """
            MATCH (n)
            WHERE n.doc_id = $doc_id OR n.source = $doc_id
            DETACH DELETE n
            """
            rag_service.graph_service.execute_query(cypher, {"doc_id": doc_id})
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/documents/<doc_id>/export', methods=['GET'])
def export_document_graph(doc_id):
    """导出文档图谱数据"""
    try:
        rag_service = get_rag_service()
        
        cypher = """
        MATCH (a)-[r]->(b)
        WHERE (a.source = $doc_id OR a.doc_id = $doc_id) AND (b.source = $doc_id OR b.doc_id = $doc_id)
        RETURN a, r, b
        """
        
        rels_data = rag_service.graph_service.execute_query(cypher, {"doc_id": doc_id})
        
        # 复用 get_visualize_data 的序列化逻辑 (简化版)
        nodes = []
        node_index = {}
        edges = []
        
        # 辅助函数需要重新定义或提取到外部，这里简单复制必要的逻辑
        def _resolve_id(obj):
            if hasattr(obj, 'element_id'): return str(obj.element_id)
            if hasattr(obj, 'id'): return str(obj.id)
            return obj.get('id') if isinstance(obj, dict) else None

        for item in rels_data:
            a = item.get('a') or item.get('start') or item.get('source')
            b = item.get('b') or item.get('end') or item.get('target')
            r = item.get('r') or item.get('rel') or item.get('relationship')
            
            if not a or not b: continue
            
            a_id = _resolve_id(a)
            b_id = _resolve_id(b)
            
            if a_id and a_id not in node_index:
                node_index[a_id] = True
                nodes.append({
                    "id": a_id,
                    "labels": list(getattr(a, 'labels', [])),
                    "properties": serialize_neo4j_object(a)
                })
            
            if b_id and b_id not in node_index:
                node_index[b_id] = True
                nodes.append({
                    "id": b_id,
                    "labels": list(getattr(b, 'labels', [])),
                    "properties": serialize_neo4j_object(b)
                })
                
            if r:
                edges.append({
                    "id": _resolve_id(r),
                    "source": a_id,
                    "target": b_id,
                    "type": getattr(r, 'type', 'UNKNOWN'),
                    "properties": serialize_neo4j_object(r)
                })
                
        return jsonify({
            "success": True,
            "data": {
                "doc_id": doc_id,
                "nodes": nodes,
                "edges": edges,
                "timestamp": __import__('datetime').datetime.now().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"导出文档失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== GraphRAG 高级搜索接口 ====================

def get_graphrag_service():
    """获取 GraphRAG 服务实例"""
    if hasattr(current_app, 'graphrag_service') and current_app.graphrag_service:
        return current_app.graphrag_service
    
    # 尝试从 rag_service 获取
    rag_service = get_rag_service()
    if hasattr(rag_service, 'graph_service') and rag_service.graph_service:
        return rag_service.graph_service
    
    return None


@kg_bp.route('/graphrag/local_search', methods=['POST'])
def graphrag_local_search():
    """GraphRAG Local Search - 基于实体和关系的精确搜索"""
    try:
        data = request.json or {}
        question = data.get('question') or data.get('q') or ''
        top_k = int(data.get('top_k', 20))
        include_community = data.get('include_community', True)
        doc_id = data.get('doc_id')
        try:
            database = _require_graph_database(data.get('database'))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        
        if not question:
            return jsonify({"success": False, "error": "question is required"}), 400
        svc = get_graphrag_service()
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500
        
        if not hasattr(svc, 'local_search'):
            return jsonify({"success": False, "error": "local_search method not available"}), 500
        
        with svc._use_database(database):
            result = svc.local_search(question, top_k=top_k, include_community=include_community, doc_id=doc_id, database=database)
        return jsonify({"success": True, "data": result})
    
    except Exception as e:
        logger.error(f"GraphRAG local_search failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/graphrag/global_search', methods=['POST'])
def graphrag_global_search():
    """GraphRAG Global Search - 基于社区知识的全局搜索"""
    try:
        data = request.json or {}
        question = data.get('question') or data.get('q') or ''
        max_communities = int(data.get('max_communities', 10))
        include_intermediate = data.get('include_intermediate', False)
        doc_id = data.get('doc_id')
        try:
            database = _require_graph_database(data.get('database'))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        
        if not question:
            return jsonify({"success": False, "error": "question is required"}), 400
        svc = get_graphrag_service()
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500
        
        if not hasattr(svc, 'global_search'):
            return jsonify({"success": False, "error": "global_search method not available"}), 500
        
        with svc._use_database(database):
            result = svc.global_search(
                question, 
                max_communities=max_communities, 
                include_intermediate=include_intermediate,
                doc_id=doc_id,
                database=database
            )
        return jsonify({"success": True, "data": result})
    
    except Exception as e:
        logger.error(f"GraphRAG global_search failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/graphrag/hybrid_search', methods=['POST'])
def graphrag_hybrid_search():
    """GraphRAG Hybrid Search - 混合搜索（自动选择或组合搜索策略）
    
    支持对话上下文：
    - chat_history: 可选，对话历史列表 [{"role": "user"|"assistant", "content": str}, ...]
    """
    try:
        data = request.json or {}
        question = data.get('question') or data.get('q') or ''
        top_k = int(data.get('top_k', 5))
        strategy = data.get('strategy', 'auto')  # auto, local, global, both
        chat_history = data.get('chat_history', [])  # 对话历史
        session_id = data.get('session_id') # 可选：会话 ID，用于持久化
        doc_id = data.get('doc_id')  # 可选：文档 ID，用于限定检索范围
        try:
            database = _require_graph_database(data.get('database'))  # 必填：Neo4j database
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        
        if not question:
            return jsonify({"success": False, "error": "question is required"}), 400
        if strategy not in ('auto', 'local', 'global', 'both'):
            return jsonify({"success": False, "error": "invalid strategy, must be: auto, local, global, both"}), 400
        
        # 1. 如果提供了 session_id，先保存用户消息
        if session_id:
            try:
                # 检查会话是否存在
                session = ChatSession.query.filter_by(session_id=session_id).first()
                if session:
                    user_msg = ChatMessage(
                        session_id=session_id,
                        role='user',
                        content=question,
                        timestamp=datetime.now(timezone.utc)
                    )
                    db.session.add(user_msg)
                    session.touch() # 更新会话时间
                    db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"保存用户消息失败: {e}")

        svc = get_graphrag_service()
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500
        
        if not hasattr(svc, 'hybrid_search'):
            return jsonify({"success": False, "error": "hybrid_search method not available"}), 500
        
        with svc._use_database(database):
            result = svc.hybrid_search(
                question,
                top_k=top_k,
                strategy=strategy,
                chat_history=chat_history,
                doc_id=doc_id,
                database=database,
            )
        
        # 3. 如果提供了 session_id，保存 AI 回复
        if session_id and result.get('success'):
            try:
                session = ChatSession.query.filter_by(session_id=session_id).first()
                if session:
                    # 收集引用源 (Local/Global result)
                    sources = {}
                    if result.get('local_result'):
                        sources['local'] = result['local_result']
                    if result.get('global_result'):
                        sources['global'] = result['global_result']
                    
                    ai_msg = ChatMessage(
                        session_id=session_id,
                        role='assistant',
                        content=result.get('answer', ''),
                        sources=sources if sources else None,
                        timestamp=datetime.now(timezone.utc)
                    )
                    db.session.add(ai_msg)
                    session.touch()
                    db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"保存 AI 消息失败: {e}")

        return jsonify({"success": True, "data": result})
    
    except Exception as e:
        logger.error(f"GraphRAG hybrid_search failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/graphrag/detect_communities', methods=['POST'])
def graphrag_detect_communities():
    """触发 Leiden 社区检测"""
    try:
        data = request.json or {}
        write_property = data.get('write_property', True)
        try:
            database = _require_graph_database(data.get('database'))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        
        svc = get_graphrag_service()
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500
        
        mode = data.get('mode', 'auto')

        if not hasattr(svc, 'detect_communities'):
            return jsonify({"success": False, "error": "detect_communities method not available"}), 500
        
        if hasattr(svc, '_use_database'):
            with svc._use_database(database):
                result = svc.detect_communities(write_property=write_property, mode=mode)
        else:
            result = svc.detect_communities(write_property=write_property, mode=mode)
        return jsonify({"success": True, "data": result})
    
    except Exception as e:
        logger.error(f"GraphRAG detect_communities failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/graphrag/generate_reports', methods=['POST'])
def graphrag_generate_reports():
    """生成所有社区的 LLM 摘要报告"""
    try:
        data = request.json or {}
        try:
            database = _require_graph_database(data.get('database'))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        svc = get_graphrag_service()
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500
        
        if not hasattr(svc, 'generate_all_community_reports'):
            return jsonify({"success": False, "error": "generate_all_community_reports method not available"}), 500
        
        if hasattr(svc, '_use_database'):
            with svc._use_database(database):
                result = svc.generate_all_community_reports()
        else:
            result = svc.generate_all_community_reports()
        return jsonify({"success": True, "data": result})
    
    except Exception as e:
        logger.error(f"GraphRAG generate_reports failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/graphrag/community/<int:community_id>', methods=['GET'])
def get_community_details(community_id: int):
    """获取指定社区的详细信息"""
    try:
        try:
            database = _require_graph_database(request.args.get('database'))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        svc = get_graphrag_service()
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500
        
        if not hasattr(svc, 'get_community_entities'):
            return jsonify({"success": False, "error": "get_community_entities method not available"}), 500
        
        with svc._use_database(database):
            entities = svc.get_community_entities(community_id)
        return jsonify({
            "success": True, 
            "data": {
                "community_id": community_id,
                "entities": entities,
                "entity_count": len(entities)
            }
        })
    
    except Exception as e:
        logger.error(f"Get community details failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/cleanup', methods=['POST'])
def cleanup_all_orphaned_data():
    """清理所有孤立数据：同时清理孤立向量和孤立Chunk"""
    try:
        payload = request.get_json(silent=True) or {}
        database = (payload.get('database') or '').strip() or None

        svc = getattr(current_app, 'graphrag_service', None) or get_rag_service()
        if not svc:
            rag_service = get_rag_service()
            if hasattr(rag_service, 'graph_service'):
                svc = rag_service.graph_service
        
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500
            
        if not hasattr(svc, 'cleanup_all_orphaned_data'):
            return jsonify({"success": False, "error": "cleanup_all_orphaned_data method not available"}), 500

        result = svc.cleanup_all_orphaned_data(database=database)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"清理孤立数据失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/vectors/cleanup', methods=['POST'])
def cleanup_vectors():
    """清理孤立向量"""
    try:
        svc = getattr(current_app, 'graphrag_service', None) or get_rag_service()
        if not svc:
            # Try to get from rag_service.graph_service
            rag_service = get_rag_service()
            if hasattr(rag_service, 'graph_service'):
                svc = rag_service.graph_service
        
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500
            
        if not hasattr(svc, 'cleanup_isolated_vectors'):
             return jsonify({"success": False, "error": "cleanup_isolated_vectors method not available"}), 500

        result = svc.cleanup_isolated_vectors()
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"清理孤立向量失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/chunks/cleanup-orphaned', methods=['POST'])
def cleanup_orphaned_chunks():
    """清理孤立Chunk（没有向量的Chunk）"""
    try:
        svc = getattr(current_app, 'graphrag_service', None) or get_rag_service()
        if not svc:
            rag_service = get_rag_service()
            if hasattr(rag_service, 'graph_service'):
                svc = rag_service.graph_service
        
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500
        
        if not hasattr(svc, 'cleanup_orphaned_chunks'):
            return jsonify({"success": False, "error": "cleanup_orphaned_chunks method not available"}), 500

        result = svc.cleanup_orphaned_chunks()
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"清理孤立Chunk失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/chunks/status', methods=['GET'])
def get_chunks_vector_status():
    """获取Chunk与向量的关联状态"""
    try:
        try:
            database = _normalize_graph_database(request.args.get('database'))
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        svc = getattr(current_app, 'graphrag_service', None) or get_rag_service()
        if not svc:
            rag_service = get_rag_service()
            if hasattr(rag_service, 'graph_service'):
                svc = rag_service.graph_service
        
        if not svc:
            return jsonify({"success": False, "error": "GraphRAG service unavailable"}), 500
        
        if not hasattr(svc, 'cleanup_chunks_without_vectors'):
            return jsonify({"success": False, "error": "cleanup_chunks_without_vectors method not available"}), 500

        result = svc.cleanup_chunks_without_vectors(database=database)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"获取Chunk状态失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 会话管理接口 ====================

@kg_bp.route('/sessions', methods=['GET'])
def list_kg_sessions():
    """获取 KG 聊天会话列表"""
    try:
        # 假设 KG 会话通过特定的 character_key 或 name 标识，或者直接返回所有会话
        # 这里我们简单地返回所有会话，或者你可以添加过滤逻辑
        # 为了区分，我们可以在创建时加上特定的前缀，或者这里只返回最近的会话
        
        # 暂时返回所有会话，按更新时间倒序
        sessions = ChatSession.query.order_by(ChatSession.updated_at.desc()).limit(50).all()
        
        session_list = []
        for s in sessions:
            session_list.append({
                'session_id': s.session_id,
                'name': s.name or '未命名会话',
                'updated_at': s.updated_at.isoformat() if s.updated_at else None,
                'created_at': s.created_at.isoformat() if s.created_at else None
            })
            
        return jsonify({"success": True, "data": session_list})
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/sessions', methods=['POST'])
def create_kg_session():
    """创建新的 KG 聊天会话"""
    try:
        data = request.get_json() or {}
        name = data.get('name', f"KG对话-{datetime.now().strftime('%m-%d %H:%M')}")
        
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        new_session = ChatSession(
            session_id=session_id,
            name=name,
            character_key='kg_assistant', # 标识为 KG 助手
            created_at=now,
            updated_at=now
        )
        
        db.session.add(new_session)
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "data": {
                "session_id": session_id,
                "name": name
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建会话失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/sessions/<session_id>/messages', methods=['GET'])
def get_session_messages(session_id):
    """获取指定会话的消息历史"""
    try:
        messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
        
        msg_list = []
        for m in messages:
            msg_data = {
                'role': m.role,
                'content': m.content,
                'timestamp': m.timestamp.isoformat() if m.timestamp else None
            }
            # 尝试解析 sources (如果是 JSON 字符串或已经是 dict)
            if m.sources:
                msg_data['sources'] = m.sources
                
            msg_list.append(msg_data)
            
        return jsonify({"success": True, "data": msg_list})
    except Exception as e:
        logger.error(f"获取消息历史失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/sessions/<session_id>', methods=['DELETE'])
def delete_kg_session(session_id):
    """删除会话"""
    try:
        session = ChatSession.query.filter_by(session_id=session_id).first()
        if session:
            db.session.delete(session)
            db.session.commit()
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "会话不存在"}), 404
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除会话失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 映射管理接口 ====================

@kg_bp.route('/mappings', methods=['GET'])
def get_mappings():
    """获取实体和关系映射配置"""
    try:
        manager = MappingManager()
        return jsonify({"success": True, "data": manager.get_mappings()})
    except Exception as e:
        logger.error(f"获取映射配置失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/mappings', methods=['POST'])
def update_mappings():
    """更新实体和关系映射配置"""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "请求体不能为空"}), 400
            
        manager = MappingManager()
        if manager.save_mappings(data):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "保存失败"}), 500
    except Exception as e:
        logger.error(f"更新映射配置失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/mappings/item', methods=['POST'])
def add_mapping_item():
    """添加或更新单个映射规则"""
    try:
        data = request.json
        category = data.get('category')
        key = data.get('key')
        value = data.get('value')
        
        if not all([category, key, value]):
            return jsonify({"success": False, "error": "缺少必要参数"}), 400
            
        manager = MappingManager()
        if manager.add_mapping(category, key, value):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "添加失败"}), 500
    except Exception as e:
        logger.error(f"添加映射规则失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@kg_bp.route('/mappings/item', methods=['DELETE'])
def delete_mapping_item():
    """删除单个映射规则"""
    try:
        category = request.args.get('category')
        key = request.args.get('key')
        
        if not all([category, key]):
            return jsonify({"success": False, "error": "缺少必要参数"}), 400
            
        manager = MappingManager()
        if manager.delete_mapping(category, key):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "删除失败"}), 500
    except Exception as e:
        logger.error(f"删除映射规则失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500



