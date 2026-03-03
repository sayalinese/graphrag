import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional, Union, Callable, Generator, Tuple
from datetime import datetime, timezone
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .langchain_context import (
    context_manager,
    CharacterManager,
    create_llm_instance,
    format_messages_for_context
)
from app import db
from app.models import ChatSession, ChatMessage
from app.services.rag.rag_up.doc_magene import DocumentManager
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)

# 单例文档管理器
_doc_manager = DocumentManager()

# RAG 配置已移除；如需恢复，请在新实现中注入配置

def _safe_query_kb(kb_id: int, query: str, top_k: int = 3):
    """安全查询知识库，失败时返回空列表。"""
    try:
        return _doc_manager.query_knowledge_base(kb_id, query, top_k) or []
    except Exception as _:
        return []

def _is_trivial_greeting(text: str) -> bool:
    """判断是否为寒暄或过短的无信息问候，避免触发RAG。"""
    if not text:
        return True
    t = (text or '').strip().lower()
    # 常见中英文寒暄与短语
    greetings = [
        '你好', '您好', '在吗', '吗', 'hello', 'hi', 'hey', '喂', '嗨', '哈喽', '早', '早上好', '中午好', '晚上好'
    ]
    # 过短或纯标点
    if len(t) <= 2:
        return True
    for g in greetings:
        if g in t and len(t) <= max(6, len(g) + 2):
            return True
    # 全是标点或空白
    import string
    punct_ws = set(string.punctuation + string.whitespace)
    if all(ch in punct_ws for ch in t):
        return True
    return False

def _enhanced_query_kb(kb_id: int, query: str, session_id: str = None, message_id: str = None):
    """
    使用 RAG 服务进行检索，并格式化为 sources 结构。
    """
    try:
        if _is_trivial_greeting(query):
            return []
        result = rag_service.query_knowledge_base(kb_id, query, session_id, message_id)
        if not result.get('success'):
            return []
        sources = []
        for c in result.get('citations', []) or []:
            score = c.get('score', 0.0) or 0.0
            # 基于得分给出相关性等级，便于前端展示
            if score >= 0.75:
                rel = 'high'
            elif score >= 0.5:
                rel = 'medium'
            else:
                rel = 'low'
            sources.append({
                'kb_id': kb_id,
                'text': c.get('content', ''),
                'score': score,
                'metadata': c.get('metadata', {}) or {},
                'citation_id': c.get('id', ''),
                'source_type': (c.get('metadata', {}) or {}).get('source_type', 'document'),
                'relevance_level': rel,
                'rank': c.get('rank', 0),
            })
        return sources
    except Exception:
        return []

def _format_sources(kb_id: int, docs: List[Any]) -> List[Dict[str, Any]]:
    """将检索结果格式化为 ChatMessage.sources 结构。"""
    formatted: List[Dict[str, Any]] = []
    for d in docs:
        try:
            meta = getattr(d, 'metadata', {}) or {}
            formatted.append({
                'kb_id': kb_id,
                'text': getattr(d, 'page_content', ''),
                'score': getattr(d, 'score', None),
                'metadata': meta,
            })
        except Exception:
            pass
    return formatted

def _inject_rag_system(messages: List[Any], docs: List[Any]) -> List[Any]:
    """把检索片段拼成系统提示，插入到现有消息最前或系统消息之后。"""
    try:
        if not docs:
            return messages
        context_texts = []
        for i, d in enumerate(docs, start=1):
            snippet = getattr(d, 'page_content', '')
            if snippet:
                context_texts.append(f"[{i}] {snippet}")
        if not context_texts:
            return messages
        rag_block = (
            "你可以使用以下检索到的资料回答用户问题，回答时尽量基于资料作答，并在需要时引用序号：\n\n" +
            "\n\n".join(context_texts)
        )
        # 在现有系统消息后面插入一个新的 SystemMessage；若没有系统消息，则作为第一条
        from langchain_core.messages import SystemMessage
        new_msgs: List[Any] = []
        inserted = False
        for m in messages:
            new_msgs.append(m)
            if isinstance(m, SystemMessage) and not inserted:
                new_msgs.append(SystemMessage(content=rag_block))
                inserted = True
        if not inserted:
            new_msgs = [SystemMessage(content=rag_block)] + messages
        return new_msgs
    except Exception:
        return messages

def _inject_enhanced_rag_system(messages: List[Any], sources: List[Dict[str, Any]]) -> List[Any]:
    """注入增强的 RAG 系统提示（合并重复定义，并强化引用/格式/语言风格约束）。"""
    try:
        if not sources:
            return messages
        context_texts: List[str] = []
        for s in sources:
            cid = s.get('citation_id', '')
            content = s.get('text', '')
            relevance = s.get('relevance_level', 'low')
            meta = s.get('metadata', {}) or {}
            filename = meta.get('filename')
            src_type = s.get('source_type', 'document')
            # 控制每段最长截断，避免提示过长（可调）
            if len(content) > 1500:
                content = content[:1500] + '...'
            source_line = f"[{cid}] ({src_type}{' · ' + filename if filename else ''} · 相关性:{relevance})\n{content}"
            context_texts.append(source_line)
        if not context_texts:
            return messages

        rag_block = (
            "你将基于以下检索资料回答用户问题。务必：精确、客观、可追溯。\n\n" +
            "\n\n".join(context_texts) +
            "\n\n回答规范：\n" +
            "1. 必须只引用给定资料，引用格式统一使用‘引用1’、‘引用2’编号：例如 引用1。多个引用用空格或逗号分隔，如 引用1引用3。\n" +
            "2. 先给出'简要结论'一行，再列出'要点说明'（分条）。\n" +
            "3. 若资料存在差异/多条，合并对比后再输出，不要重复大段粘贴原文。\n" +
            "4. 不得编造资料中没有的细节；若未命中相关信息，直接说明'本次检索未命中相关资料'，并给出可继续检索的关键词建议。\n" +
            "5. 禁止出现'无法访问知识库/外部系统'等措辞。\n" +
            "6. 输出末尾添加'引用：'段，列出实际用到的引用编号及对应来源文件（格式：引用：引用1 文件名A；引用2 文件名B）。\n" +
            "7. 回答使用与用户提问语言一致，术语保持原文。\n" +
            "8. 若法规/期限类问题，优先提取明确时间/范围并引用来源。\n" +
            "9. 不要一次性原样贴出全部引用内容，只摘要关键点。"
        )
        from langchain_core.messages import SystemMessage
        new_msgs: List[Any] = []
        inserted = False
        for m in messages:
            new_msgs.append(m)
            if isinstance(m, SystemMessage) and not inserted:
                new_msgs.append(SystemMessage(content=rag_block))
                inserted = True
        if not inserted:
            new_msgs = [SystemMessage(content=rag_block)] + messages
        return new_msgs
    except Exception as e:
        logger.error(f"Enhanced RAG injection failed: {e}")
        return messages

def _inject_no_hit_guidance(messages: List[Any]) -> List[Any]:
    """当绑定了知识库但未命中任何片段时，注入温和的系统指令，避免模型宣称"无法访问知识库"。"""
    try:
        from langchain_core.messages import SystemMessage
        guidance = (
            "你已绑定一个知识库，但当前检索未命中相关资料。\n"
            "要求：\n"
            "- 绝不要说'我的知识库没有存储……'、'无法访问知识库/外部系统'、'知识库中没有……'等措辞；\n"
            "- 可以明确表达'这次检索未命中相关片段'，并基于通用常识与经验给出谨慎的回答或建议；\n"
            "- 鼓励用户提供更具体的关键词或条例全名（例如：'重庆市节约用水条例'、'城市供水节水管理办法'）。"
        )
        # 插入到首个系统消息之后，或作为第一条
        new_msgs: List[Any] = []
        inserted = False
        for m in messages:
            new_msgs.append(m)
            if isinstance(m, SystemMessage) and not inserted:
                new_msgs.append(SystemMessage(content=guidance))
                inserted = True
        if not inserted:
            new_msgs = [SystemMessage(content=guidance)] + messages
        return new_msgs
    except Exception:
        return messages


class ChatService:
    """AI对话服务"""
    
    def __init__(self, model_type: str = "deepseek", user_id: int | None = None, **kwargs):
        """
        初始化对话服务

        Args:
            model_type: 模型类型 (deepseek, openai)
            user_id: 当前用户ID（用于解析自定义 key）
            **kwargs: 其他模型参数
        """
        self.model_type = model_type
        self.user_id = user_id
        self.llm = create_llm_instance(model_type, user_id=user_id, **kwargs)
        self.model_params = kwargs
    
    def chat(self, 
             session_id: str, 
             user_message: str, 
             character_id: str = "student",
             max_context_length: int = 10,
             user_id: int | None = None,
             kb_id: Optional[int] = None,
             enable_web_search: bool = False) -> Dict[str, Any]:
        """
        单轮对话
        
        Args:
            session_id: 会话ID
            user_message: 用户消息
            character_id: 角色ID
            max_context_length: 最大上下文长度
            
        Returns:
            对话结果字典
        """
        try:
            # 获取或创建对话会话（若内存无会话，优先用DB记录的角色与上下文长度恢复）
            conversation = context_manager.get_conversation(session_id)
            if not conversation:
                try:
                    cs = ChatSession.query.filter_by(session_id=session_id).first()
                    if cs and getattr(cs, 'character_key', None):
                        character_id = cs.character_key or character_id
                        max_context_length = getattr(cs, 'max_context_length', max_context_length) or max_context_length
                except Exception:
                    pass
                conversation = context_manager.create_conversation(
                    session_id, character_id, max_context_length
                )
            
            # 添加用户消息
            human_msg = HumanMessage(content=user_message)
            context_manager.add_message(session_id, human_msg)
            # 持久化用户消息
            try:
                db.session.add(ChatMessage(
                    session_id=session_id,
                    role='user',
                    content=user_message,
                    timestamp=datetime.now(timezone.utc)
                ))
                db.session.commit()
                # 更新会话活跃时间
                try:
                    cs = ChatSession.query.filter_by(session_id=session_id).first()
                    if cs:
                        cs.updated_at = datetime.now(timezone.utc)
                        db.session.commit()
                except Exception:
                    db.session.rollback()
            except Exception:
                db.session.rollback()
            
            # 获取上下文消息 + 可选RAG增强
            context_messages = context_manager.get_context_messages(session_id)
            sources: List[Dict[str, Any]] = []
            try:
                cs = ChatSession.query.filter_by(session_id=session_id).first()
                effective_kb_id = kb_id if kb_id is not None else (getattr(cs, 'kb_id', None) if cs else None)
                
                if effective_kb_id:
                    # 使用增强的RAG查询
                    # 将 user_id（显式传参优先，其次 ChatService.user_id）传递下去
                    _uid = user_id if user_id is not None else self.user_id
                    sources = _enhanced_query_kb(effective_kb_id, user_message, session_id, str(uuid.uuid4()))
                    if sources:
                        context_messages = _inject_enhanced_rag_system(context_messages, sources)
                    else:
                        # 绑定KB但未命中时，注入温和指引，避免"无法访问知识库"的措辞
                        context_messages = _inject_no_hit_guidance(context_messages)
            except Exception as e:
                logger.warning(f"RAG enhancement failed: {str(e)}")
                pass
            
            # 调用LLM
            response = self.llm.invoke(context_messages)
            
            # 添加AI回复
            ai_msg = AIMessage(content=response.content)
            context_manager.add_message(session_id, ai_msg)
            # 持久化AI消息（带sources）
            try:
                db.session.add(ChatMessage(
                    session_id=session_id,
                    role='assistant',
                    content=response.content,
                    sources=sources if sources else None,
                    timestamp=datetime.now(timezone.utc)
                ))
                db.session.commit()
                # 更新会话活跃时间
                try:
                    cs = ChatSession.query.filter_by(session_id=session_id).first()
                    if cs:
                        cs.updated_at = datetime.now(timezone.utc)
                        db.session.commit()
                except Exception:
                    db.session.rollback()
            except Exception:
                db.session.rollback()
            
            return {
                "success": True,
                "session_id": session_id,
                "character": conversation.character.name,
                "response": response.content,
                "sources": sources,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "context_length": len(context_messages)
            }
            
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def chat_stream(self, 
                    session_id: str, 
                    user_message: str, 
                    character_id: str = "student",
                    max_context_length: int = 10,
                    kb_id: Optional[int] = None,
                    enable_web_search: bool = False) -> Generator[Dict[str, Any], None, None]:
        """
        流式对话
        
        Args:
            session_id: 会话ID
            user_message: 用户消息
            character_id: 角色ID
            max_context_length: 最大上下文长度
            
        Yields:
            流式响应块
        """
        try:
            # 获取或创建对话会话（若内存无会话，优先用DB恢复角色）
            conversation = context_manager.get_conversation(session_id)
            if not conversation:
                try:
                    cs = ChatSession.query.filter_by(session_id=session_id).first()
                    if cs and getattr(cs, 'character_key', None):
                        character_id = cs.character_key or character_id
                        max_context_length = getattr(cs, 'max_context_length', max_context_length) or max_context_length
                except Exception:
                    pass
                conversation = context_manager.create_conversation(
                    session_id, character_id, max_context_length
                )
            
            # 添加用户消息
            human_msg = HumanMessage(content=user_message)
            context_manager.add_message(session_id, human_msg)
            # 持久化用户消息
            try:
                db.session.add(ChatMessage(
                    session_id=session_id,
                    role='user',
                    content=user_message,
                    timestamp=datetime.now(timezone.utc)
                ))
                db.session.commit()
                # 更新会话活跃时间
                try:
                    cs = ChatSession.query.filter_by(session_id=session_id).first()
                    if cs:
                        cs.updated_at = datetime.now(timezone.utc)
                        db.session.commit()
                except Exception:
                    db.session.rollback()
            except Exception:
                db.session.rollback()
            
            # 获取上下文消息 + 可选RAG增强
            context_messages = context_manager.get_context_messages(session_id)
            sources: List[Dict[str, Any]] = []
            try:
                cs = ChatSession.query.filter_by(session_id=session_id).first()
                effective_kb_id = kb_id if kb_id is not None else (getattr(cs, 'kb_id', None) if cs else None)
                
                if effective_kb_id:
                    # 使用增强的RAG查询
                    sources = _enhanced_query_kb(effective_kb_id, user_message, session_id, str(uuid.uuid4()))
                    if sources:
                        context_messages = _inject_enhanced_rag_system(context_messages, sources)
                    else:
                        context_messages = _inject_no_hit_guidance(context_messages)
            except Exception as _e:
                logger.warning(f"Stream RAG enhancement failed: {str(_e)}")
                pass
            
            # 流式调用LLM
            response_stream = self.llm.stream(context_messages)
            
            accumulated_content = ""
            
            # 发送开始标记
            yield {
                "type": "start",
                "session_id": session_id,
                "character": conversation.character.name,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # 处理流式响应
            for chunk in response_stream:
                if hasattr(chunk, 'content') and chunk.content:
                    accumulated_content += chunk.content
                    yield {
                        "type": "chunk",
                        "session_id": session_id,
                        "content": chunk.content,
                        "accumulated": accumulated_content,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
            
            # 添加完整的AI回复到上下文
            ai_msg = AIMessage(content=accumulated_content)
            context_manager.add_message(session_id, ai_msg)
            # 持久化AI完整消息（带sources）
            try:
                db.session.add(ChatMessage(
                    session_id=session_id,
                    role='assistant',
                    content=accumulated_content,
                    sources=sources if sources else None,
                    timestamp=datetime.now(timezone.utc)
                ))
                db.session.commit()
                # 更新会话活跃时间
                try:
                    cs = ChatSession.query.filter_by(session_id=session_id).first()
                    if cs:
                        cs.updated_at = datetime.now(timezone.utc)
                        db.session.commit()
                except Exception:
                    db.session.rollback()
            except Exception:
                db.session.rollback()
            
            # 发送完成标记
            yield {
                "type": "complete",
                "session_id": session_id,
                "response": accumulated_content,
                "sources": sources,
                "context_length": len(context_manager.get_context_messages(session_id)),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in chat_stream: {str(e)}")
            yield {
                "type": "error",
                "session_id": session_id,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def chat_with_context(self, 
                          session_id: str, 
                          user_message: str, 
                          character_id: str = "student",
                          context_variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        带上下文的对话
        
        Args:
            session_id: 会话ID
            user_message: 用户消息
            character_id: 角色ID
            context_variables: 上下文变量
            
        Returns:
            对话结果字典
        """
        try:
            # 获取或创建对话会话（若内存无会话，优先用DB恢复角色）
            conversation = context_manager.get_conversation(session_id)
            if not conversation:
                try:
                    cs = ChatSession.query.filter_by(session_id=session_id).first()
                    if cs and getattr(cs, 'character_key', None):
                        character_id = cs.character_key or character_id
                        # chat_with_context 未显式传 max_context_length，这里从DB取或回退默认10
                        max_context_length = getattr(cs, 'max_context_length', 10) or 10
                except Exception:
                    pass
                conversation = context_manager.create_conversation(session_id, character_id)
            
            # 如果有上下文变量，更新系统提示词
            if context_variables:
                # 这里可以实现动态提示词更新
                pass
            
            # 添加用户消息
            human_msg = HumanMessage(content=user_message)
            context_manager.add_message(session_id, human_msg)
            
            # 获取上下文消息 + 可选RAG增强
            context_messages = context_manager.get_context_messages(session_id)
            sources: List[Dict[str, Any]] = []
            try:
                cs = ChatSession.query.filter_by(session_id=session_id).first()
                kb_id = getattr(cs, 'kb_id', None) if cs else None
                if kb_id:
                    # 使用增强的RAG查询
                    sources = _enhanced_query_kb(kb_id, user_message, session_id, str(uuid.uuid4()))
                    if sources:
                        context_messages = _inject_enhanced_rag_system(context_messages, sources)
            except Exception as e:
                logger.warning(f"Context RAG enhancement failed: {str(e)}")
                pass
            
            # 调用LLM
            response = self.llm.invoke(context_messages)
            
            # 添加AI回复
            ai_msg = AIMessage(content=response.content)
            context_manager.add_message(session_id, ai_msg)
            
            return {
                "success": True,
                "session_id": session_id,
                "character": conversation.character.name,
                "response": response.content,
                "sources": sources,
                "context_messages": format_messages_for_context(context_messages),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in chat_with_context: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def multi_turn_chat(self, 
                        session_id: str, 
                        messages: List[str], 
                        character_id: str = "student") -> List[Dict[str, Any]]:
        """
        多轮对话
        
        Args:
            session_id: 会话ID
            messages: 消息列表
            character_id: 角色ID
            
        Returns:
            对话结果列表
        """
        results = []
        
        for i, message in enumerate(messages):
            try:
                result = self.chat(session_id, message, character_id)
                results.append({
                    "turn": i + 1,
                    "user_message": message,
                    "ai_response": result.get("response", ""),
                    "success": result.get("success", False)
                })
                
            except Exception as e:
                logger.error(f"Error in turn {i + 1}: {str(e)}")
                results.append({
                    "turn": i + 1,
                    "user_message": message,
                    "error": str(e),
                    "success": False
                })
        
        return results


class ChatManager:
    """对话管理器 (增加按 user_id 维度的 ChatService 实例缓存)"""
    
    def __init__(self):
        self.chat_services: Dict[str, ChatService] = {}
        self.default_model = "deepseek"
    
    def get_chat_service(self, model_type: str = None, user_id: int | None = None, **kwargs) -> ChatService:
        """获取对话服务实例（按模型+user_id 进行区分，确保不同用户使用各自的密钥/模型配置）。"""
        model_type = model_type or self.default_model
        # user_id 参与 key，避免不同用户复用同一个 LLM 实例导致密钥混用
        service_key = f"{model_type}_{user_id}_{hash(str(kwargs))}"
        if service_key not in self.chat_services:
            self.chat_services[service_key] = ChatService(model_type, user_id=user_id, **kwargs)
        return self.chat_services[service_key]
    
    def create_session(self, character_id: str = "student", max_context_length: int = 10, user_id: int | None = None, name: str | None = None, kb_id: int | None = None) -> str:
        """
        创建新的对话会话
        
        Args:
            character_id: 角色ID
            max_context_length: 最大上下文长度
            user_id: 用户ID
            name: 会话名称
            kb_id: 知识库ID
            
        Returns:
            会话ID
        """
        session_id = str(uuid.uuid4())
        context_manager.create_conversation(session_id, character_id, max_context_length)
        # 持久化会话元信息
        try:
            cs = ChatSession(
                session_id=session_id,
                character_key=character_id,
                max_context_length=max_context_length,
                user_id=user_id,
                name=name,
                kb_id=kb_id,
            )
            cs.touch()
            db.session.add(cs)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return session_id
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话信息字典
        """
        conversation = context_manager.get_conversation(session_id)
        if not conversation:
            return None
        
        return {
            "session_id": session_id,
            "character": {
                "name": conversation.character.name,
                "product": conversation.character.product,
                "hobby": conversation.character.hobby,
                "personality": conversation.character.personality,
                "expertise": conversation.character.expertise
            },
            "message_count": len(conversation.messages),
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat()
        }
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        列出所有会话
        
        Returns:
            会话列表
        """
        sessions = []
        for session_id in context_manager.list_conversations():
            session_info = self.get_session_info(session_id)
            if session_info:
                sessions.append(session_info)
        return sessions
    
    def clear_session(self, session_id: str) -> bool:
        """
        清空会话上下文
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否成功
        """
        return context_manager.clear_conversation(session_id)
    
    def remove_session(self, session_id: str) -> bool:
        """
        移除会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否成功
        """
        return context_manager.remove_conversation(session_id)


# ==================== 高级对话功能 ====================

class AdvancedChatService(ChatService):
    """高级对话服务"""
    
    def __init__(self, model_type: str = "deepseek", **kwargs):
        super().__init__(model_type, **kwargs)
        self.callbacks = {}
    
    def add_callback(self, event_type: str, callback: Callable):
        """添加回调函数"""
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []
        self.callbacks[event_type].append(callback)
    
    def _trigger_callback(self, event_type: str, data: Any):
        """触发回调函数"""
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Callback error: {str(e)}")
    
    def chat_with_memory(self, 
                         session_id: str, 
                         user_message: str, 
                         character_id: str = "student",
                         memory_keywords: List[str] = None) -> Dict[str, Any]:
        """
        带记忆的对话
        
        Args:
            session_id: 会话ID
            user_message: 用户消息
            character_id: 角色ID
            memory_keywords: 记忆关键词
            
        Returns:
            对话结果字典
        """
        try:
            # 触发对话开始回调
            self._trigger_callback("chat_start", {
                "session_id": session_id,
                "user_message": user_message,
                "character_id": character_id
            })
            
            # 执行基础对话
            result = super().chat(session_id, user_message, character_id)
            
            # 触发对话完成回调
            self._trigger_callback("chat_complete", result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in chat_with_memory: {str(e)}")
            self._trigger_callback("chat_error", {"error": str(e)})
            raise
    
    def multi_turn_chat(self, 
                        session_id: str, 
                        messages: List[str], 
                        character_id: str = "student") -> List[Dict[str, Any]]:
        """
        多轮对话（带回调）
        
        Args:
            session_id: 会话ID
            messages: 消息列表
            character_id: 角色ID
            
        Returns:
            对话结果列表
        """
        results = []
        
        for i, message in enumerate(messages):
            try:
                result = self.chat(session_id, message, character_id)
                results.append({
                    "turn": i + 1,
                    "user_message": message,
                    "ai_response": result.get("response", ""),
                    "success": result.get("success", False)
                })
                
                # 触发轮次完成回调
                self._trigger_callback("turn_complete", {
                    "turn": i + 1,
                    "result": result
                })
                
            except Exception as e:
                logger.error(f"Error in turn {i + 1}: {str(e)}")
                results.append({
                    "turn": i + 1,
                    "user_message": message,
                    "error": str(e),
                    "success": False
                })
        
        return results


# ==================== 工具函数 ====================

def create_chat_service(model_type: str = "deepseek", **kwargs) -> ChatService:
    """创建对话服务实例"""
    return ChatService(model_type, **kwargs)


def create_advanced_chat_service(model_type: str = "deepseek", **kwargs) -> AdvancedChatService:
    """创建高级对话服务实例"""
    return AdvancedChatService(model_type, **kwargs)


def get_available_characters() -> List[Dict[str, Any]]:
    """获取可用角色列表，返回包含 id 与基础信息的列表"""
    characters: List[Dict[str, Any]] = []
    try:
        ids = CharacterManager.list_characters()
        for cid in ids:
            ch = CharacterManager.get_character(cid)
            if ch:
                characters.append({
                    "id": cid,
                    "key": cid,
                    "name": ch.name,
                    "product": ch.product,
                    "hobby": ch.hobby,
                    "personality": ch.personality,
                    "expertise": ch.expertise,
                    "avatar": getattr(ch, "avatar", ""),
                })
    except Exception as e:
        logger.error(f"get_available_characters error: {e}")
    return characters


# 全局对话管理器实例，供路由使用
chat_manager = ChatManager()
