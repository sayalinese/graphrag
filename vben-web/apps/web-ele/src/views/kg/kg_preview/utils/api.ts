/**
 * GraphRAG 閻儴鐦戦崶鎹愭皑闂傤喚鐡?API
 */
import { baseRequestClient } from '#/api/request';

// 閹兼粎鍌ㄧ粵鏍殣缁鐎?
export type SearchStrategy = 'auto' | 'local' | 'global' | 'both';

// 鐎圭偘缍嬫穱鈩冧紖
export interface EntityInfo {
  name: string;
  type: string;
  description?: string;
  neo_id?: number;
  community_id?: number;
  source?: string;
}

// 閸忓磭閮存穱鈩冧紖
export interface RelationInfo {
  source: string;
  target: string;
  type: string;
  description?: string;
}

// Chunk 娣団剝浼?
export interface ChunkInfo {
  text: string;
  score?: number;
  neo_id?: number;
  metadata?: Record<string, any>;
}

// 缁€鎯у隘娑撳﹣绗呴弬?
export interface CommunityContext {
  community_id: number;
  members: string[];
}

// Local Search 缂佹挻鐏?
export interface LocalSearchResult {
  success: boolean;
  answer: string;
  entities: EntityInfo[];
  relations: RelationInfo[];
  chunks: ChunkInfo[];
  community_context: CommunityContext[];
}

// Global Search 缂佹挻鐏?
export interface GlobalSearchResult {
  success: boolean;
  answer: string;
  communities_used: number;
  map_results?: Array<{
    community_id: number;
    entity_count: number;
    answer: string;
    has_relevant_info: boolean;
  }>;
  coverage?: {
    total_communities: number;
    total_entities: number;
  };
  error?: string;
}

// Hybrid Search 缂佹挻鐏?
export interface HybridSearchResult {
  success: boolean;
  strategy_used: SearchStrategy;
  answer: string;
  local_result?: LocalSearchResult;
  global_result?: GlobalSearchResult;
}

// 閼卞﹤銇夊☉鍫熶紖
export interface KgChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  // 闂勫嫬濮炴穱鈩冧紖閿涘牅绮?assistant 濞戝牊浼呴敍?
  strategy?: SearchStrategy;
  entities?: EntityInfo[];
  relations?: RelationInfo[];
  chunks?: ChunkInfo[];
  communities_used?: number;
  loading?: boolean;
  loadingText?: string;
  error?: string;
}

// 鐎电鐦介崢鍡楀蕉閿涘牏鏁ゆ禍?API 鐠囬攱鐪伴敍?
export interface ChatHistoryItem {
  role: 'user' | 'assistant';
  content: string;
}

// API 閸濆秴绨查崠鍛邦棅
interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: string;
}

// 娴兼俺鐦芥穱鈩冧紖
export interface KgSession {
  session_id: string;
  name: string;
  updated_at: string;
  created_at: string;
}

// 娴兼俺鐦藉☉鍫熶紖
export interface KgSessionMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: {
    local?: LocalSearchResult;
    global?: GlobalSearchResult;
  };
}

export interface AskKgResponse {
  answer: string;
  seed_node_ids: string[];
  graph?: { nodes: any[]; edges: any[] };
  highlight: {
    node_ids: string[];
    link_ids: string[];
    max_depth?: number;
  };
}

/**
 * GraphRAG Hybrid Search - 濞ｅ嘲鎮庨幖婊呭偍
 * @param question 閻劍鍩涢梻顕€顣?
 * @param strategy 閹兼粎鍌ㄧ粵鏍殣
 * @param topK 鏉╂柨娲栭惃鍕偓娆撯偓澶嬫殶闁?
 * @param chatHistory 鐎电鐦介崢鍡楀蕉閿涘牏鏁ゆ禍搴濈瑐娑撳鏋冮敍?
 * @param sessionId 娴兼俺鐦?ID閿涘牏鏁ゆ禍搴㈠瘮娑斿懎瀵查敍?
 * @param docId 閺傚洦銆?ID閿涘牏鏁ゆ禍搴ㄦ鐎规碍顥呯槐銏ｅ瘱閸ヨ揪绱?
 */
export async function hybridSearch(
  question: string,
  strategy: SearchStrategy = 'auto',
  topK: number = 5,
  chatHistory: ChatHistoryItem[] = [],
  sessionId?: string,
  docId?: string,
  database?: string
): Promise<HybridSearchResult> {
  const axiosResponse = await baseRequestClient.post<ApiResponse<HybridSearchResult>>(
    '/kg/graphrag/hybrid_search',
    {
      question,
      strategy,
      top_k: topK,
      chat_history: chatHistory,
      session_id: sessionId,
      doc_id: docId,
      database,
    },
    {
      timeout: 60000, // 60 缁夋帟绉撮弮?
    }
  );
  const response = axiosResponse.data as unknown as ApiResponse<HybridSearchResult>;
  if (!response.success) {
    throw new Error(response.error || '閹兼粎鍌ㄦ径杈Е');
  }
  return response.data;
}

/**
 * 閼惧嘲褰?KG 娴兼俺鐦介崚妤勩€?
 */
export async function getKgSessions(): Promise<KgSession[]> {
  const axiosResponse = await baseRequestClient.get<ApiResponse<KgSession[]>>('/kg/sessions');
  const response = axiosResponse.data as unknown as ApiResponse<KgSession[]>;
  if (!response.success) {
    throw new Error(response.error || '閼惧嘲褰囨导姘崇樈閸掓銆冩径杈Е');
  }
  return response.data;
}

/**
 * 閸掓稑缂撻弬鎵畱 KG 娴兼俺鐦?
 */
export async function createKgSession(name?: string): Promise<{ session_id: string; name: string }> {
  const axiosResponse = await baseRequestClient.post<ApiResponse<{ session_id: string; name: string }>>(
    '/kg/sessions',
    { name }
  );
  const response = axiosResponse.data as unknown as ApiResponse<{ session_id: string; name: string }>;
  if (!response.success) {
    throw new Error(response.error || '创建会话失败');
  }
  return response.data;
}

/**
 * 閼惧嘲褰囨导姘崇樈濞戝牊浼呴崢鍡楀蕉
 */
export async function getKgSessionMessages(sessionId: string): Promise<KgSessionMessage[]> {
  const axiosResponse = await baseRequestClient.get<ApiResponse<KgSessionMessage[]>>(
    `/kg/sessions/${sessionId}/messages`
  );
  const response = axiosResponse.data as unknown as ApiResponse<KgSessionMessage[]>;
  if (!response.success) {
    throw new Error(response.error || '閼惧嘲褰囧☉鍫熶紖閸樺棗褰舵径杈Е');
  }
  return response.data;
}

/**
 * 閸掔娀娅庢导姘崇樈
 */
export async function deleteKgSession(sessionId: string): Promise<void> {
  const axiosResponse = await baseRequestClient.delete<ApiResponse<void>>(
    `/kg/sessions/${sessionId}`
  );
  const response = axiosResponse.data as unknown as ApiResponse<void>;
  if (!response.success) {
    throw new Error(response.error || '删除会话失败');
  }
}

/**
 * GraphRAG Local Search - 鐏炩偓闁劍鎮崇槐?
 */
export async function localSearch(
  question: string,
  topK: number = 5
): Promise<LocalSearchResult> {
  const axiosResponse = await baseRequestClient.post<ApiResponse<LocalSearchResult>>(
    '/kg/graphrag/local_search',
    {
      question,
      top_k: topK,
    }
  );
  const response = axiosResponse.data as unknown as ApiResponse<LocalSearchResult>;
  if (!response.success) {
    throw new Error(response.error || '閹兼粎鍌ㄦ径杈Е');
  }
  return response.data;
}

/**
 * GraphRAG Global Search - 閸忋劌鐪幖婊呭偍
 */
export async function globalSearch(
  question: string,
  maxCommunities: number = 10
): Promise<GlobalSearchResult> {
  const axiosResponse = await baseRequestClient.post<ApiResponse<GlobalSearchResult>>(
    '/kg/graphrag/global_search',
    {
      question,
      max_communities: maxCommunities,
    }
  );
  const response = axiosResponse.data as unknown as ApiResponse<GlobalSearchResult>;
  if (!response.success) {
    throw new Error(response.error || '閹兼粎鍌ㄦ径杈Е');
  }
  return response.data;
}

/**
 * 閼惧嘲褰囬崶鎹愭皑缂佺喕顓告穱鈩冧紖
 */
export async function getGraphStats(): Promise<{
  nodes: number;
  edges: number;
  communities?: number;
}> {
  const axiosResponse = await baseRequestClient.get<ApiResponse<any>>('/kg/stats');
  const response = axiosResponse.data as unknown as ApiResponse<any>;
  if (!response.success) {
    throw new Error(response.error || '閼惧嘲褰囩紒鐔活吀娣団剝浼呮径杈Е');
  }
  return response.data;
}

/**
 * 鐟欙箑褰傜粈鎯у隘濡偓濞?
 */
export async function detectCommunities(): Promise<{
  success: boolean;
  communities: Array<{
    community_id: number;
    members: string[];
    size: number;
  }>;
  total_communities: number;
  total_entities: number;
  error?: string;
}> {
  const axiosResponse = await baseRequestClient.post<ApiResponse<any>>(
    '/kg/graphrag/detect_communities'
  );
  const response = axiosResponse.data as unknown as ApiResponse<any>;
  if (!response.success) {
    throw new Error(response.error || '社区检测失败');
  }
  return response.data;
}

/**
 * 閻㈢喐鍨氶幍鈧張澶屻仦閸栫儤濮ら崨?
 */
export async function generateCommunityReports(): Promise<{
  success: boolean;
  total_communities: number;
  generated_reports: number;
}> {
  const axiosResponse = await baseRequestClient.post<ApiResponse<any>>(
    '/kg/graphrag/generate_reports'
  );
  const response = axiosResponse.data as unknown as ApiResponse<any>;
  if (!response.success) {
    throw new Error(response.error || '生成报告失败');
  }
  return response.data;
}

/**
 * 缁犫偓閸楁洟妫剁粵鏃撶礄娴ｈ法鏁ら崢鐔告箒閻?graph_rag_qa 閹恒儱褰涢敍?
 */
export async function simpleQA(
  question: string,
  topK: number = 5
): Promise<{
  success: boolean;
  answer: string;
  candidates: any[];
  raw_docs: any[];
}> {
  const axiosResponse = await baseRequestClient.post<ApiResponse<any>>('/kg/graph_rag_qa', {
    question,
    top_k: topK,
  }, {
    timeout: 60000, // 60 缁夋帟绉撮弮?
  });
  const response = axiosResponse.data as unknown as ApiResponse<any>;
  if (!response.success) {
    throw new Error(response.error || '闂傤喚鐡熸径杈Е');
  }
  return response.data;
}

function normalizeEdgeEndpoint(endpoint: any): string {
  if (typeof endpoint === 'string') return endpoint;
  if (typeof endpoint === 'number') return String(endpoint);
  if (endpoint && typeof endpoint === 'object') {
    const nestedId = endpoint.id ?? endpoint.nodeId ?? endpoint.neo_id ?? endpoint.elementId;
    if (typeof nestedId === 'string' || typeof nestedId === 'number') {
      return String(nestedId);
    }
  }
  return '';
}

function buildAskKgMockResponse(question: string): AskKgResponse {
  const fallbackGraph = {
    nodes: [
      { id: 'node1', label: 'Pneumonia', category: 'DISEASE' },
      { id: 'node2', label: 'Fever', category: 'SYMPTOM' },
      { id: 'node3', label: 'Dyspnea', category: 'SYMPTOM' },
      { id: 'node4', label: 'Chest CT', category: 'EXAM' },
      { id: 'node5', label: 'Blood Routine', category: 'LAB' },
      { id: 'node6', label: 'CRP', category: 'LAB' },
      { id: 'node7', label: 'Azithromycin', category: 'DRUG' },
      { id: 'node8', label: 'Moxifloxacin', category: 'DRUG' },
      { id: 'node9', label: 'Respiratory Dept', category: 'DEPARTMENT' },
      { id: 'node10', label: 'Clinical Guideline', category: 'GUIDELINE' },
      { id: 'node11', label: 'RCT Evidence', category: 'EVIDENCE' },
      { id: 'node12', label: 'KG QA', category: 'CONCEPT' },
      { id: 'node13', label: 'Chest X-ray', category: 'EXAM' },
      { id: 'node14', label: 'Pathogen Test', category: 'LAB' },
      { id: 'node15', label: 'Inpatient Care', category: 'CONCEPT' },
    ],
    edges: [
      { source: 'node12', target: 'node1', label: 'answer-target' },
      { source: 'node1', target: 'node2', label: 'has-symptom' },
      { source: 'node1', target: 'node3', label: 'has-symptom' },
      { source: 'node1', target: 'node4', label: 'diagnosed-by' },
      { source: 'node1', target: 'node13', label: 'diagnosed-by' },
      { source: 'node1', target: 'node5', label: 'lab-indicator' },
      { source: 'node1', target: 'node6', label: 'lab-indicator' },
      { source: 'node1', target: 'node7', label: 'treated-by' },
      { source: 'node1', target: 'node8', label: 'treated-by' },
      { source: 'node1', target: 'node9', label: 'department' },
      { source: 'node10', target: 'node11', label: 'backed-by' },
      { source: 'node10', target: 'node15', label: 'pathway' },
      { source: 'node11', target: 'node7', label: 'supports-drug' },
      { source: 'node11', target: 'node8', label: 'supports-drug' },
      { source: 'node14', target: 'node1', label: 'confirmatory-test' },
      { source: 'node12', target: 'node10', label: 'cite-guideline' },
    ],
  };

  let graph = fallbackGraph;
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      const raw = window.sessionStorage.getItem('kg_graph_cache');
      if (raw) {
        const parsed = JSON.parse(raw) as { data?: { nodes?: any[]; edges?: any[] } };
        const nodes = Array.isArray(parsed?.data?.nodes) ? parsed.data.nodes : [];
        const edges = Array.isArray(parsed?.data?.edges) ? parsed.data.edges : [];
        if (nodes.length >= 6 && edges.length >= 5) {
          graph = {
            nodes: nodes.slice(0, 60),
            edges: edges.slice(0, 100),
          };
        }
      }
    }
  } catch {
    // Ignore cache read failures and keep fallback graph.
  }

  const seedNodeIds: string[] = [];
  const nodeIds: string[] = [];
  const linkIds: string[] = [];

  const normalizedEdges = graph.edges
    .map((edge) => {
      const source = normalizeEdgeEndpoint((edge as any).source);
      const target = normalizeEdgeEndpoint((edge as any).target);
      if (!source || !target) return null;
      return { source, target };
    })
    .filter((edge): edge is { source: string; target: string } => Boolean(edge));

  const pickedEdges = normalizedEdges.slice(0, 8);
  pickedEdges.forEach((edge) => {
    linkIds.push(`${edge.source}-${edge.target}`);
    nodeIds.push(edge.source, edge.target);
    if (seedNodeIds.length < 2 && !seedNodeIds.includes(edge.source)) {
      seedNodeIds.push(edge.source);
    }
  });

  if (!seedNodeIds.length) {
    const graphNodeIds = graph.nodes
      .map((node) => {
        const id = (node as any).id;
        return typeof id === 'string' || typeof id === 'number' ? String(id) : '';
      })
      .filter(Boolean);
    if (graphNodeIds.length > 0) {
      seedNodeIds.push(graphNodeIds[0]!);
      if (graphNodeIds[1]) seedNodeIds.push(graphNodeIds[1]);
      nodeIds.push(...graphNodeIds.slice(0, 16));
    } else {
      seedNodeIds.push('node12');
      nodeIds.push('node12', 'node1', 'node11');
      linkIds.push('node12-node1', 'node1-node11');
    }
  }

  return {
    answer: `演示答案：已为问题“${question}”生成可解释链路，图中会从种子节点逐层点亮到证据节点。`,
    seed_node_ids: Array.from(new Set(seedNodeIds)),
    graph,
    highlight: {
      node_ids: Array.from(new Set(nodeIds)),
      link_ids: Array.from(new Set(linkIds)),
      max_depth: 3,
    },
  };
}

export async function askKg(question: string, docId?: string, database?: string): Promise<AskKgResponse> {
  try {
    const raw = await baseRequestClient.post<any>(
      '/kg/ask',
      {
        question,
        ...(docId ? { doc_id: docId } : {}),
        ...(database ? { database } : {}),
      },
      {
        timeout: 60000,
      }
    );
    const payload: AskKgResponse = raw?.data ? raw.data : raw;

    if (!payload || typeof payload !== 'object') {
      throw new Error('Invalid /kg/ask response');
    }

    return {
      answer: typeof payload.answer === 'string' ? payload.answer : '',
      seed_node_ids: Array.isArray(payload.seed_node_ids) ? payload.seed_node_ids.map((id: any) => String(id)) : [],
      graph: payload.graph && Array.isArray(payload.graph.nodes) && Array.isArray(payload.graph.edges)
        ? payload.graph
        : undefined,
      highlight: {
        node_ids: Array.isArray(payload.highlight?.node_ids)
          ? payload.highlight.node_ids.map((id: any) => String(id))
          : [],
        link_ids: Array.isArray(payload.highlight?.link_ids)
          ? payload.highlight.link_ids.map((id: any) => String(id))
          : [],
        max_depth: Number.isFinite(payload.highlight?.max_depth)
          ? Number(payload.highlight.max_depth)
          : 3,
      },
    };
  } catch {
    return buildAskKgMockResponse(question);
  }
}

/**
 * 閼惧嘲褰囬崣顖濐潒閸栨牗鏆熼幑?
 * @param limit 鏉╂柨娲栭懞鍌滃仯閺佷即鍣洪梽鎰煑
 * @param docId 閺傚洦銆?ID閿涘本瀵滈弬鍥ㄣ€傜粵娑⑩偓澶婃禈鐠嬭精瀵栭崶?
 * @param communityId 缁€鎯у隘 ID閿涘本瀵滅粈鎯у隘缁涙盯鈧娴樼拫杈瘱閸?
 */
export async function getVisualizeData(
  limit = 300,
  docId?: string,
  communityId?: number,
  database?: string
): Promise<{
  nodes: Array<{ id: string; name: string; category: string }>;
  links: Array<{ source: string; target: string; label: string }>;
}> {
  const params: Record<string, any> = { limit };
  if (docId) params.doc_id = docId;
  if (communityId !== undefined) params.community_id = communityId;
  if (database) params.database = database;
  
  const axiosResponse = await baseRequestClient.get<ApiResponse<any>>('/kg/visualize', { params });
  const response = axiosResponse.data as unknown as ApiResponse<any>;
  if (!response.success) {
    throw new Error(response.error || '获取可视化数据失败');
  }
  return response.data;
}

/**
 * 閼惧嘲褰囬弬鍥ㄣ€傞崚妤勩€?
 */
export interface DocumentInfo {
  doc_id: string;
  title?: string;
  created_at?: string;
}

export async function getDocuments(): Promise<DocumentInfo[]> {
  const axiosResponse = await baseRequestClient.get<ApiResponse<{ documents: DocumentInfo[] }>>('/kg/documents');
  const response = axiosResponse.data as unknown as ApiResponse<{ documents: DocumentInfo[] }>;
  if (!response.success) {
    throw new Error(response.error || '閼惧嘲褰囬弬鍥ㄣ€傞崚妤勩€冩径杈Е');
  }
  return response.data?.documents || [];
}

export interface Neo4jDatabaseInfo {
  access?: string;
  default?: boolean;
  name: string;
  status?: string;
}

export async function getNeo4jDatabases(): Promise<Neo4jDatabaseInfo[]> {
  const axiosResponse = await baseRequestClient.get<ApiResponse<{ databases: Neo4jDatabaseInfo[] }>>('/kg/databases');
  const response = axiosResponse.data as unknown as ApiResponse<{ databases: Neo4jDatabaseInfo[] }>;
  if (!response.success) {
    throw new Error(response.error || '获取 Neo4j 数据库列表失败');
  }
  return response.data?.databases || [];
}

