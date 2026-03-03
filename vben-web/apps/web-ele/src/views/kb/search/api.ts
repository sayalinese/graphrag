/**
 * RAG 搜索 API 客户端
 * vben-web 前端集成
 */

import { requestClient } from '#/api/request';
import { useAppConfig } from '@vben/hooks';

export interface SearchResult {
  rank?: number;
  id: string | number;
  doc_id?: string | null;
  kb_id: number;
  content: string;
  metadata?: Record<string, any>;
  vector_score?: number;
  bm25_score?: number;
  fused_score?: number;
  rerank_score?: number;
  distance?: number | null;
  score_type?: string;
  created_at?: string;
}

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);
const API_BASE = (apiURL || '').replace(/\/$/, '') || '/api';

function normalizeResponse(payload: any) {
  if (!payload) return {};
  const data = payload?.data ?? payload;
  if (typeof data.code === 'number' && 'data' in data) {
    return data.data ?? {};
  }
  return data;
}

function extractResults(payload: any): SearchResult[] {
  const normalized = normalizeResponse(payload);
  if (Array.isArray(normalized)) {
    return normalized;
  }
  if (Array.isArray(normalized?.results)) {
    return normalized.results;
  }
  if (Array.isArray(normalized?.data?.results)) {
    return normalized.data.results;
  }
  throw new Error(payload?.message || '搜索失败');
}

export interface HybridSearchOptions {
  vector_weight?: number;
  bm25_weight?: number;
  threshold?: number;
}

/**
 * 执行混合搜索
 * @param kb_id 知识库 ID
 * @param query 查询文本
 * @param top_k 返回数量
 * @param options 额外参数
 * @returns 搜索结果
 */
export async function hybridSearch(
  kb_id: number,
  query: string,
  top_k: number = 5,
  options: HybridSearchOptions = {}
): Promise<SearchResult[]> {
  const response = await requestClient.post(
    `${API_BASE}/rag/search/hybrid`,
    {
      kb_id,
      query,
      top_k,
      ...options,
    }
  );
  return extractResults(response);
}

/**
 * 执行重排搜索
 * @param kb_id 知识库 ID
 * @param query 查询文本
 * @param top_k 返回数量
 * @returns 搜索结果
 */
export async function rerankSearch(
  kb_id: number,
  query: string,
  top_k: number = 5
): Promise<SearchResult[]> {
  return pgvectorSearch(kb_id, query, {
    top_k,
    mode: 'rerank',
  });
}

/**
 * 执行完整的 pgvector 搜索
 * @param kb_id 知识库 ID
 * @param query 查询文本
 * @param options 搜索选项
 * @returns 搜索结果
 */
export async function pgvectorSearch(
  kb_id: number,
  query: string,
  options?: {
    top_k?: number;
    mode?: 'hybrid' | 'rerank';
    vector_weight?: number;
    bm25_weight?: number;
    threshold?: number;
  }
): Promise<SearchResult[]> {
  const response = await requestClient.post(
    `${API_BASE}/rag/search/query_pgvector`,
    {
      kb_id,
      query,
      top_k: options?.top_k ?? 10,
      mode: options?.mode ?? 'hybrid',
      vector_weight: options?.vector_weight ?? 0.6,
      bm25_weight: options?.bm25_weight ?? 0.4,
      threshold: options?.threshold ?? 0.0,
    }
  );
  return extractResults(response);
}

/**
 * 执行向量搜索
 */
export async function vectorSearch(
  kb_id: number,
  query: string,
  top_k: number = 10
): Promise<SearchResult[]> {
  const response = await requestClient.post(
    `${API_BASE}/rag/search/vector`,
    { kb_id, query, top_k }
  );
  return extractResults(response);
}

/**
 * 执行 BM25 搜索
 */
export async function bm25Search(
  kb_id: number,
  query: string,
  top_k: number = 10
): Promise<SearchResult[]> {
  const response = await requestClient.post(
    `${API_BASE}/rag/search/bm25`,
    { kb_id, query, top_k }
  );
  return extractResults(response);
}

/**
 * 获取搜索统计信息
 */
export async function getSearchStats(kb_id?: number) {
  const params = kb_id ? `?kb_id=${kb_id}` : '';
  const response = await requestClient.get(
    `${API_BASE}/rag/search/stats${params}`
  );

  const data = response.data || response;
  if (data.code === 0) {
    return data.data;
  }
  throw new Error(data.message || '获取统计失败');
}

/**
 * 重建搜索索引
 */
export async function rebuildSearchIndex(kb_id?: number) {
  const response = await requestClient.post(
    `${API_BASE}/rag/search/rebuild-index`,
    { kb_id }
  );

  const data = response.data || response;
  if (data.code === 0) {
    return data.data;
  }
  throw new Error(data.message || '索引重建失败');
}

/**
 * 获取知识库列表
 * @returns 知识库列表
 */
export async function getKBList(): Promise<{ id: number; name: string; description?: string }[]> {
  const response = await requestClient.get(`${API_BASE}/kb/list`);
  const data = response.data || response;
  // 兼容后端返回字段 knowledge_bases
  return data.data?.knowledge_bases || data.knowledge_bases || data.data?.kbs || data.kbs || [];
}
