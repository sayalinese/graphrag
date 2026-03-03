import os
import json
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
try:  # DeepSeek SDK 是可选的，若未安装则使用 OpenAI 兼容入口
    from langchain_deepseek import ChatDeepSeek  # type: ignore
except ImportError:  # pragma: no cover - 仅在无 SDK 时执行
    ChatDeepSeek = None  # type: ignore
from .langchain_role import AICharacter, CharacterManager
try:
    from app.services.api_setting.service import ApiSettingService  # type: ignore
except Exception:  # 兼容尚未导入时
    ApiSettingService = None  # type: ignore

logger = logging.getLogger(__name__)

# ==================== 角色配置 ====================
# 已迁移到 langchain_role.py：AICharacter 与 CharacterManager


@dataclass
class ConversationContext:
    """对话上下文"""
    session_id: str
    character: AICharacter
    messages: List[BaseMessage]
    max_context_length: int = 20
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)
    
    def add_message(self, message: BaseMessage):
        """添加消息到上下文"""
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)
        
        # 保持上下文长度限制
        if len(self.messages) > self.max_context_length:
            # 保留系统消息和最近的对话
            system_messages = [msg for msg in self.messages if isinstance(msg, SystemMessage)]
            recent_messages = self.messages[-self.max_context_length + len(system_messages):]
            self.messages = system_messages + recent_messages
    
    def get_context_messages(self) -> List[BaseMessage]:
        """获取上下文消息"""
        return self.messages.copy()
    
    def clear_context(self):
        """清空对话上下文（保留系统消息）"""
        system_messages = [msg for msg in self.messages if isinstance(msg, SystemMessage)]
        self.messages = system_messages
        self.updated_at = datetime.now(timezone.utc)


## 这里原有 CharacterManager 与默认角色表已移除


class ContextManager:
    """上下文管理器"""
    
    def __init__(self):
        self.conversations: Dict[str, ConversationContext] = {}
    
    def create_conversation(self, session_id: str, character: Union[str, AICharacter], 
                           max_context_length: int = 10) -> ConversationContext:
        """创建新的对话会话"""
        if isinstance(character, str):
            character = CharacterManager.get_character(character)
            if not character:
                raise ValueError(f"Unknown character: {character}")
        
        # 创建系统消息
        system_message = SystemMessage(content=character.system_prompt)
        
        # 创建对话上下文
        context = ConversationContext(
            session_id=session_id,
            character=character,
            messages=[system_message],
            max_context_length=max_context_length
        )
        
        self.conversations[session_id] = context
        logger.info(f"Created conversation session: {session_id} with character: {character.name}")
        return context
    
    def get_conversation(self, session_id: str) -> Optional[ConversationContext]:
        """获取对话会话"""
        return self.conversations.get(session_id)
    
    def add_message(self, session_id: str, message: BaseMessage) -> bool:
        """添加消息到指定会话"""
        context = self.get_conversation(session_id)
        if not context:
            logger.warning(f"Conversation session not found: {session_id}")
            return False
        
        context.add_message(message)
        return True
    
    def get_context_messages(self, session_id: str) -> List[BaseMessage]:
        """获取指定会话的上下文消息"""
        context = self.get_conversation(session_id)
        if not context:
            return []
        return context.get_context_messages()
    
    def clear_conversation(self, session_id: str) -> bool:
        """清空指定会话的上下文"""
        context = self.get_conversation(session_id)
        if not context:
            return False
        
        context.clear_context()
        return True
    
    def remove_conversation(self, session_id: str) -> bool:
        """移除对话会话"""
        if session_id in self.conversations:
            del self.conversations[session_id]
            logger.info(f"Removed conversation session: {session_id}")
            return True
        return False
    
    def list_conversations(self) -> List[str]:
        """列出所有会话ID"""
        return list(self.conversations.keys())


class PromptBuilder:
    """提示词构建器"""
    
    @staticmethod
    def build_system_prompt(character: AICharacter, **kwargs) -> str:
        """构建系统提示词"""
        # 支持动态变量替换
        prompt = character.system_prompt
        
        # 替换变量
        for key, value in kwargs.items():
            if f"{{{key}}}" in prompt:
                prompt = prompt.replace(f"{{{key}}}", str(value))
        
        return prompt
    
    @staticmethod
    def create_chat_template(character: AICharacter) -> ChatPromptTemplate:
        """创建聊天模板"""
        system_template = character.system_prompt
        
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template("{query}"),
        ])
    
    @staticmethod
    def create_contextual_template(character: AICharacter) -> ChatPromptTemplate:
        """创建支持上下文的聊天模板"""
        system_template = character.system_prompt
        
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            # 这里可以添加对话历史
            # MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{query}"),
        ])


# ==================== 环境配置 ====================

class ModelConfig:
    """模型配置管理"""
    
    @staticmethod
    def get_deepseek_config() -> Dict[str, Any]:
        """获取DeepSeek配置"""
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            raise ValueError("因为你没资格啊没资格")
        
        return {
            "api_key": api_key,
            "base_url": os.getenv('DEEPSEEK_API_BASE_URL', "https://api.deepseek.com"),
            "model": os.getenv('DEEPSEEK_MODEL', "deepseek-chat"),
            "temperature": float(os.getenv('DEEPSEEK_TEMPERATURE', "0.7")),
            "max_tokens": int(os.getenv('DEEPSEEK_MAX_TOKENS', "2000"))
        }
    
    @staticmethod
    def get_openai_config() -> Dict[str, Any]:
        """获取OpenAI配置"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("你没资格啊没资格")
        
        return {
            "api_key": api_key,
            "base_url": os.getenv('OPENAI_BASE_URL'),
            "model": os.getenv('OPENAI_MODEL', "gpt-4o-mini"),
            "temperature": float(os.getenv('OPENAI_TEMPERATURE', "0.7")),
            "max_tokens": int(os.getenv('OPENAI_MAX_TOKENS', "2000"))
        }




def create_llm_instance(model_type: str = "deepseek", user_id: int | None = None, **kwargs) -> Union[ChatOpenAI, Any]:
    """创建LLM实例：引入 ApiSettingService 解析优先级
    优先：用户自定义(api_setting) -> 环境变量
    model_type: deepseek | openai
    """
    model_key = model_type.lower()
    try:
        resolved = {}
        if ApiSettingService:
            # llm provider 名称与我们 service 映射保持：deepseek / openai_compatible(openai)
            provider_name = 'deepseek' if model_key == 'deepseek' else 'openai_compatible' if model_key == 'openai' else model_key
            resolved = ApiSettingService.resolve('llm', provider_name, user_id)

        if model_key == "deepseek":
            config = ModelConfig.get_deepseek_config()
        elif model_key == "openai":
            config = ModelConfig.get_openai_config()
        else:
            raise ValueError(f"不支持啊不支持: {model_type}")

        # 用解析结果覆盖 env 默认（为空则跳过）
        if resolved.get('api_key'):
            config['api_key'] = resolved['api_key']
        if resolved.get('base_url'):
            config['base_url'] = resolved['base_url']
        if resolved.get('model_name'):
            config['model'] = resolved['model_name']

        config.update(kwargs)

        if model_key == 'deepseek' and ChatDeepSeek:
            return ChatDeepSeek(**config)

        # DeepSeek SDK 未安装时退化为 OpenAI 兼容调用，只要 base_url / api_key 配置正确即可
        return ChatOpenAI(**config)
    except Exception as e:
        logger.error(f"Failed to create LLM instance: {str(e)}")
        raise


def format_messages_for_context(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """格式化消息用于上下文传递"""
    formatted = []
    for msg in messages:
        formatted.append({
            "type": msg.__class__.__name__,
            "content": msg.content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    return formatted


# 全局上下文管理器实例
context_manager = ContextManager()
