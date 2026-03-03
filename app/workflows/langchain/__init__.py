# 导出 langchain 聊天相关的核心接口

from .langchain_role import AICharacter, CharacterManager
from .langchain_context import (
    ConversationContext,
    ContextManager,
    PromptBuilder,
    ModelConfig,
    create_llm_instance,
    format_messages_for_context,
    context_manager,
)
from .chat import (
    ChatService,
    ChatManager,
    AdvancedChatService,
    create_chat_service,
    create_advanced_chat_service,
    get_available_characters,
    chat_manager,
)

__all__ = [
    # Role
    'AICharacter',
    'CharacterManager',
    
    # Context
    'ConversationContext',
    'ContextManager',
    'PromptBuilder',
    'ModelConfig',
    'create_llm_instance',
    'format_messages_for_context',
    'context_manager',
    
    # Chat
    'ChatService',
    'ChatManager',
    'AdvancedChatService',
    'create_chat_service',
    'create_advanced_chat_service',
    'get_available_characters',
    'chat_manager',
]
