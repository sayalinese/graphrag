import { useAppConfig } from '@vben/hooks';

import { requestClient } from '#/api/request';

/** 聊天消息类型 */
export interface ChatMessageVO {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: Array<{
    kb_id: number;
    text: string;
    score: number;
    metadata?: Record<string, any>;
    citation_id?: string;
    source_type?: string;
    relevance_level?: 'high' | 'medium' | 'low';
  }>;
  timestamp: string;
  pending?: boolean;
  error?: boolean;
  partialContent?: string;
  showSources?: boolean;  // 控制引用面板展开/收起
}

/** 聊天会话 */
export interface ChatSessionVO {
  session_id: string;
  name?: string;
  character_key: string;
  character_name?: string;
  max_context_length?: number;
  kb_id?: number;
  user_id?: number;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

/** AI 角色 */
export interface CharacterVO {
  id: number;
  key: string;
  name: string;
  product: string;
  hobby: string;
  personality: string;
  expertise: string[];
  system_prompt: string;
  avatar: string;
  is_active: boolean;
}

/** 创建会话请求 */
export interface CreateSessionRequest {
  character_id: string;
  name?: string;
  kb_id?: number;
  max_context_length?: number;
}

/** 发送消息请求 */
export interface SendMessageRequest {
  session_id: string;
  content: string;
  character_id?: string;
  max_context_length?: number;
  kb_id?: number;
  enable_web_search?: boolean;
}

/** 发送消息响应 */
export interface SendMessageResponse {
  success: boolean;
  session_id: string;
  character: string;
  response: string;
  sources?: ChatMessageVO['sources'];
  timestamp: string;
  context_length?: number;
  error?: string;
}

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);
const API_BASE = (apiURL || '').replace(/\/$/, '') || '';
const STREAM_URL = `${API_BASE}/chat/stream`;

function normalizeSession(payload: any): ChatSessionVO {
  return {
    session_id: payload?.session_id,
    name: payload?.name || '',
    character_key: payload?.character_key || 'default',
    character_name: payload?.character_name || '',
    max_context_length: payload?.max_context_length ?? 10,
    kb_id: payload?.kb_id,
    user_id: payload?.user_id,
    created_at: payload?.created_at || '',
    updated_at: payload?.updated_at || '',
    message_count: payload?.message_count ?? 0,
  };
}

function normalizeMessage(payload: any): ChatMessageVO {
  return {
    id: String(payload?.id ?? crypto.randomUUID()),
    session_id: payload?.session_id,
    role: payload?.role,
    content: payload?.content || '',
    sources: payload?.sources || [],
    timestamp: payload?.timestamp || new Date().toISOString(),
  } as ChatMessageVO;
}

function normalizeCharacter(payload: any): CharacterVO {
  return {
    id: payload?.id,
    key: payload?.key,
    name: payload?.name,
    product: payload?.product,
    hobby: payload?.hobby,
    personality: payload?.personality,
    expertise: payload?.expertise || [],
    system_prompt: payload?.system_prompt,
    avatar: payload?.avatar,
    is_active: Boolean(payload?.is_active),
  } as CharacterVO;
}


/** 创建新聊天会话**/
export async function createChatSession(
  data: CreateSessionRequest
): Promise<{ session_id: string }> {
  const res = await requestClient.post('/chat/session/create', {
    character_id: data.character_id,
    kb_id: data.kb_id,
    max_context_length: data.max_context_length,
    name: data.name,
  });
  return { session_id: res.session_id };
}

/**
 * 更新会话信息
 */
export async function updateChatSession(
  sessionId: string,
  data: { name?: string; max_context_length?: number }
): Promise<{ success: boolean }> {
  return requestClient.put(`/chat/session/${sessionId}`, data);
}

/**
 * 获取会话信息
 */
export async function getChatSession(sessionId: string): Promise<ChatSessionVO> {
  const res = await requestClient.get(`/chat/session/${sessionId}`);
  return normalizeSession(res.session);
}

/**
 * 列出用户的所有会话
 */
export async function listChatSessions(
  limit: number = 20,
  offset: number = 0
): Promise<{ sessions: ChatSessionVO[]; total: number }> {
  const res = await requestClient.get('/chat/sessions', {
    params: { limit, offset },
  });
  return {
    sessions: (res.sessions || []).map(normalizeSession),
    total: res.total ?? 0,
  };
}

/**
 * 删除会话
 */
export async function deleteChatSession(sessionId: string): Promise<{ success: boolean }> {
  return requestClient.delete(`/chat/session/${sessionId}`);
}

/**
 * 发送消息（单轮对话）
 */
export async function sendChatMessage(
  data: SendMessageRequest
): Promise<SendMessageResponse> {
  return requestClient.post('/chat/send', {
    session_id: data.session_id,
    user_message: data.content,
    character_id: data.character_id,
    max_context_length: data.max_context_length,
    kb_id: data.kb_id,
    enable_web_search: data.enable_web_search,
  });
}

/**
 * 流式发送消息
 */
export async function sendChatMessageStream(
  data: SendMessageRequest,
  onChunk: (chunk: {
    type: string;
    content?: string;
    accumulated?: string;
    error?: string;
    sources?: any;
  }) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const query = new URLSearchParams({
      session_id: data.session_id,
      user_message: data.content,
    });
    if (data.character_id) {
      query.set('character_id', data.character_id);
    }
    if (data.max_context_length) {
      query.set('max_context_length', String(data.max_context_length));
    }
    if (data.kb_id) {
      query.set('kb_id', String(data.kb_id));
    }
    if (data.enable_web_search) {
      query.set('enable_web_search', 'true');
    }

    const url = `${API_BASE}/chat/stream?${query.toString()}`;
    console.log('[SSE] Connecting to:', url);
    
    const eventSource = new EventSource(url);
    let messageReceived = false;

    eventSource.onopen = () => {
      console.log('[SSE] Connection opened');
    };

    eventSource.onmessage = (event) => {
      try {
        console.log('[SSE] Received message:', event.data);
        messageReceived = true;
        const chunk = JSON.parse(event.data);
        onChunk(chunk);
        if (chunk.type === 'complete' || chunk.type === 'error') {
          eventSource.close();
          resolve({
            content: chunk.accumulated || '',
            session_id: data.session_id,
          } as any);
        }
      } catch (e) {
        console.error('[SSE] Failed to parse stream chunk:', e, 'Raw data:', event.data);
      }
    };

    eventSource.onerror = (error) => {
      console.error('[SSE] Connection error:', error);
      console.error('[SSE] Ready state:', eventSource.readyState);
      console.error('[SSE] Messages received before error:', messageReceived);
      eventSource.close();
      
      // 如果没有收到任何消息，说明连接失败或后端没响应
      if (!messageReceived) {
        reject(new Error('Stream connection failed - no messages received'));
      } else {
        reject(error);
      }
    };
  });
}

/**
 * 获取会话消息历史
 */
export async function getChatHistory(
  sessionId: string,
  limit: number = 50,
  offset: number = 0
): Promise<{ messages: ChatMessageVO[] }> {
  const res = await requestClient.get(`/chat/history/${sessionId}`, {
    params: { limit, offset },
  });
  return {
    messages: (res.messages || []).map(normalizeMessage),
  };
}

/**
 * 清空会话上下文
 */
export async function clearChatContext(sessionId: string): Promise<{ success: boolean }> {
  return requestClient.post(`/chat/session/${sessionId}/clear`);
}

// ============ Character APIs ============

/**
 * 获取可用角色列表
 */
export async function getAvailableCharacters(): Promise<CharacterVO[]> {
  const res = await requestClient.get('/character/available');
  return (res.characters || []).map(normalizeCharacter);
}

/**
 * 获取角色详情
 */
export async function getCharacter(key: string): Promise<CharacterVO> {
  const res = await requestClient.get(`/character/${key}`);
  return normalizeCharacter(res.character);
}

/**
 * 列出所有角色
 */
export async function listCharacters(): Promise<CharacterVO[]> {
  const res = await requestClient.get('/character/list');
  return (res.characters || []).map(normalizeCharacter);
}

/**
 * 创建角色
 */
export async function createCharacter(data: Partial<CharacterVO>): Promise<CharacterVO> {
  const res = await requestClient.post('/character/create', data);
  return normalizeCharacter(res.character);
}

/**
 * 更新角色
 */
export async function updateCharacter(
  id: number,
  data: Partial<CharacterVO>
): Promise<CharacterVO> {
  const res = await requestClient.put(`/character/${id}`, data);
  return normalizeCharacter(res.character);
}

/**
 * 删除角色
 */
export async function deleteCharacter(id: number): Promise<{ success: boolean }> {
  return requestClient.delete(`/character/${id}`);
}
