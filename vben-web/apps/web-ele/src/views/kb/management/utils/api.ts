// Knowledge Base API 实现
import { ref } from 'vue';

import { requestClient } from '#/api/request';

/** 知识库项 */
export interface KnowledgeBaseVO {
  id?: number;
  kb_id?: string;
  name: string;
  description?: string;
  user_id?: number;
  document_count?: number;
  chunk_count?: number;
  created_at?: string;
  updated_at?: string;
  documents?: DocumentVO[];
}

/** 文档项 */
export interface DocumentVO {
  id?: number;
  doc_id?: string;
  kb_id?: string;
  filename: string;
  file_type: string;
  status: 'processing' | 'completed' | 'failed' | 'indexing';
  chunk_count?: number;
  content?: string;
  created_at?: string;
  updated_at?: string;
}

/** 创建知识库请求 */
export interface CreateKBRequest {
  name: string;
  description?: string;
}

/** 更新知识库请求 */
export interface UpdateKBRequest {
  name?: string;
  description?: string;
}

/** 知识库统计信息 */
export interface KBStats {
  kb_id: string;
  name: string;
  document_count: number;
  total_chunks: number;
  completed_docs: number;
  processing_docs: number;
  failed_docs: number;
}

/**
 * 列出知识库
 */
function normalizeKB(payload: any): KnowledgeBaseVO {
  return {
    id: payload?.id,
    kb_id: payload?.kb_id,
    name: payload?.name,
    description: payload?.description,
    user_id: payload?.user_id,
    document_count: payload?.document_count ?? payload?.doc_count,
    chunk_count: payload?.chunk_count ?? 0,
    created_at: payload?.created_at,
    updated_at: payload?.updated_at,
    documents: payload?.documents?.map(normalizeDocument) || [],
  };
}

function normalizeDocument(payload: any): DocumentVO {
  return {
    id: payload?.id,
    doc_id: payload?.doc_id,
    kb_id: payload?.kb_id,
    filename: payload?.filename,
    file_type: payload?.file_type,
    status: payload?.status,
    chunk_count: payload?.chunk_count,
    content: payload?.content,
    created_at: payload?.created_at,
    updated_at: payload?.updated_at,
  };
}

export async function listKnowledgeBases(
  limit: number = 20,
  offset: number = 0,
  userId?: number
): Promise<{ knowledge_bases: KnowledgeBaseVO[]; total: number }> {
  const res = await requestClient.get('/kb/list', {
    params: { limit, offset, user_id: userId },
  });
  return {
    knowledge_bases: (res.knowledge_bases || []).map(normalizeKB),
    total: res.total ?? 0,
  };
}

/**
 * 创建知识库
 */
export async function createKnowledgeBase(
  data: CreateKBRequest
): Promise<KnowledgeBaseVO> {
  const res = await requestClient.post('/kb/create', data);
  return normalizeKB(res.knowledge_base);
}

/**
 * 获取知识库详情
 */
export async function getKnowledgeBase(
  kbId: string | number
): Promise<KnowledgeBaseVO> {
  const res = await requestClient.get(`/kb/${kbId}`);
  return normalizeKB(res.knowledge_base);
}

/**
 * 更新知识库
 */
export async function updateKnowledgeBase(
  kbId: string | number,
  data: UpdateKBRequest
): Promise<KnowledgeBaseVO> {
  const res = await requestClient.put(`/kb/${kbId}`, data);
  return normalizeKB(res.knowledge_base);
}

/**
 * 删除知识库
 */
export async function deleteKnowledgeBase(
  kbId: string | number
): Promise<{ success: boolean }> {
  return requestClient.delete(`/kb/${kbId}`);
}

/**
 * 上传文档到知识库
 */
export async function uploadDocument(
  kbId: string | number,
  file: File,
  options?: {
    split_mode?: string;
    chunk_size?: number;
    overlap?: number;
  }
): Promise<DocumentVO> {
  const formData = new FormData();
  formData.append('file', file);
  if (options) {
    if (options.split_mode) formData.append('split_mode', options.split_mode);
    if (options.chunk_size) formData.append('chunk_size', String(options.chunk_size));
    if (options.overlap) formData.append('overlap', String(options.overlap));
  }

  // NOTE: 不要手动设置 multipart/form-data 的 Content-Type
  // 否则在部分请求实现下会丢失 boundary，导致后端无法解析文件。
  // 同时要移除 RequestClient 的默认 JSON Content-Type，否则后端无法解析 request.files
  const res = await requestClient.post(`/kb/${kbId}/upload`, formData, {
    transformRequest: [
      (data, headers) => {
        if (headers) {
          // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
          delete (headers as any)['Content-Type'];
          // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
          delete (headers as any)['content-type'];
        }
        return data;
      },
    ],
  });
  return normalizeDocument(res.document);
}

/**
 * 预览文档切分
 */
export async function previewDocumentSplit(
  file: File,
  options?: {
    split_mode?: string;
    chunk_size?: number;
    overlap?: number;
  }
): Promise<{ chunks: any[]; total_count: number }> {
  const formData = new FormData();
  formData.append('file', file);
  if (options) {
    if (options.split_mode) formData.append('split_mode', options.split_mode);
    if (options.chunk_size) formData.append('chunk_size', String(options.chunk_size));
    if (options.overlap) formData.append('overlap', String(options.overlap));
  }

  // NOTE: 同 uploadDocument，避免手动 Content-Type 导致 boundary 丢失
  // 同时移除默认 JSON Content-Type，保证 request.files 能拿到 file
  const res = await requestClient.post('/documents/preview', formData, {
    transformRequest: [
      (data, headers) => {
        if (headers) {
          // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
          delete (headers as any)['Content-Type'];
          // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
          delete (headers as any)['content-type'];
        }
        return data;
      },
    ],
  });
  return res;
}

/**
 * 获取文档切片列表
 */
export async function getDocumentChunks(
  docId: string,
  page: number = 1,
  perPage: number = 20
): Promise<{ items: any[]; total: number; pages: number; current_page: number }> {
  const res = await requestClient.get(`/document/${docId}/chunks`, {
    params: { page, per_page: perPage },
  });
  return res;
}

/**
 * 文档切片去重
 */
export async function deduplicateDocument(
  docId: string
): Promise<{ removed_count: number }> {
  const res = await requestClient.post(`/document/${docId}/dedupe`);
  return res;
}

/**
 * 列出知识库的文档
 */
export async function listDocuments(
  kbId: string | number,
  limit: number = 20,
  offset: number = 0
): Promise<{ documents: DocumentVO[]; total: number }> {
  const res = await requestClient.get(`/kb/${kbId}/documents`, {
    params: { limit, offset },
  });
  return {
    documents: (res.items || []).map(normalizeDocument),
    total: res.total ?? 0,
  };
}

/**
 * 获取文档详情
 */
export async function getDocument(
  kbId: string | number,
  docId: string
): Promise<DocumentVO> {
  const res = await requestClient.get(`/kb/${kbId}/document/${docId}`);
  return normalizeDocument(res.document);
}

/**
 * 获取文档原文内容
 */
export async function getDocumentContent(
  kbId: string | number,
  docId: string
): Promise<string> {
  const res = await requestClient.get(`/kb/${kbId}/document/${docId}/content`);
  return res?.content || '';
}

/**
 * 删除文档
 */
export async function deleteDocument(
  kbId: string | number,
  docId: string
): Promise<{ success: boolean }> {
  return requestClient.delete(`/kb/${kbId}/document/${docId}`);
}

/**
 * 批量删除文档
 */
export async function batchDeleteDocuments(
  kbId: string | number,
  docIds: (string | number)[]
): Promise<{ deleted: (string | number)[]; failed: any[] }> {
  const deleted: (string | number)[] = [];
  const failed: any[] = [];
  
  for (const docId of docIds) {
    try {
      await deleteDocument(kbId, String(docId));
      deleted.push(docId);
    } catch (error) {
      failed.push({ docId, error });
    }
  }
  return { deleted, failed };
}

/**
 * 获取知识库统计信息
 */
export async function getKBStats(
  kbId: string | number
): Promise<KBStats> {
  const res = await requestClient.get(`/kb/${kbId}/stats`);
  return res.stats as KBStats;
}

export function useKBApi() {
  const kbList = ref<KnowledgeBaseVO[]>([]);
  const loading = ref(false);

  const listKBs = async (limit = 50, offset = 0) => {
    loading.value = true;
    try {
      const res = await listKnowledgeBases(limit, offset);
      kbList.value = res.knowledge_bases;
      return kbList.value;
    } catch (error) {
      console.error('Failed to list KBs:', error);
      throw error;
    } finally {
      loading.value = false;
    }
  };

  const createKB = async (payload: CreateKBRequest) => {
    const kb = await createKnowledgeBase(payload);
    await listKBs();
    return kb;
  };

  const updateKB = async (id: number | string, payload: UpdateKBRequest) => {
    const kb = await updateKnowledgeBase(id, payload);
    await listKBs();
    return kb;
  };

  const deleteKB = async (id: number | string) => {
    await requestClient.delete(`/kb/${id}`);
    await listKBs();
  };

  return {
    kbList,
    loading,
    listKBs,
    createKB,
    updateKB,
    deleteKB,
  };
}
