/**
 * Board / 视觉检索 - Mock API
 * 不接后端，用于演示“已有文本RAG平台 + 视觉RAG检索视图”的交互与结果展示。
 */
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

export interface HybridSearchOptions {
  vector_weight?: number;
  bm25_weight?: number;
  threshold?: number;
}

const mockKBs = [
  { id: 101, name: '校园生活（文本库）', description: '食堂/图书馆/运动场景文本描述' },
  { id: 102, name: '视觉RAG（模拟库）', description: '图片转写/Caption/结构化字段' },
  { id: 103, name: '设施与服务（文本库）', description: '场馆/设备/开放时间/位置' },
];

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

function clamp01(v: number) {
  return Math.max(0, Math.min(1, v));
}

function rand(min: number, max: number) {
  return min + Math.random() * (max - min);
}

function score4(v: number) {
  return Number(v.toFixed(4));
}

function nowISO() {
  return new Date().toISOString();
}

function buildContent(query: string, i: number) {
  const templates = [
    `【场景描述】${query}\n【关键要素】环境、人员分布、可用资源\n【结论】整体状态良好，建议按需前往。`,
    `【图片文字描述】围绕“${query}”的文本记录：空间开阔，通道顺畅，拥挤度低。\n【建议】错峰/选择边缘区域。`,
    `【结构化字段】地点：校园区域；时间：${Math.floor(rand(10, 16))}:${String(Math.floor(rand(0, 59))).padStart(2, '0')}\n关键物体：桌椅/球台/长桌；人数：少量；拥挤度：中低。`,
    `【证据片段】与“${query}”相关的文本片段命中：空位较多；队伍较短；环境整洁。\n【备注】该条为模拟检索结果（Mock）。`,
  ];
  return templates[i % templates.length];
}

function buildSource(kbId: number, i: number) {
  const kbName = mockKBs.find((k) => k.id === kbId)?.name ?? 'KB';
  const cams = ['Cam-A', 'Cam-S', 'Cam-L', 'Cam-P', 'Doc'];
  return `${kbName} · ${cams[i % cams.length]}-${String(i + 1).padStart(2, '0')}`;
}

function makeResults(
  kbId: number,
  query: string,
  topK: number,
  mode: 'vector' | 'bm25' | 'hybrid' | 'rerank',
  options?: HybridSearchOptions,
): SearchResult[] {
  const n = Math.max(1, Math.min(20, topK));
  const threshold = options?.threshold ?? 0;
  const vw = options?.vector_weight ?? 0.6;
  const bw = options?.bm25_weight ?? 0.4;

  const raw = Array.from({ length: n }).map((_, i) => {
    const base = clamp01(0.92 - i * 0.03 + rand(-0.02, 0.02));
    const vec = clamp01(base + rand(-0.03, 0.03));
    const bm = clamp01(base + rand(-0.05, 0.05));
    const fused = clamp01(vec * vw + bm * bw);
    const rerank = clamp01(fused + rand(-0.02, 0.02));

    const content = buildContent(query, i);
    const source = buildSource(kbId, i);

    const item: SearchResult = {
      rank: i + 1,
      id: `${kbId}-${Date.now()}-${i}`,
      kb_id: kbId,
      doc_id: `${kbId}-doc-${Math.floor(i / 3) + 1}`,
      content,
      metadata: { source, chunk: i + 1, note: 'mock' },
      created_at: nowISO(),
    };

    if (mode === 'vector') {
      item.vector_score = score4(vec);
      item.score_type = 'vector';
      item.fused_score = score4(vec);
    } else if (mode === 'bm25') {
      item.bm25_score = score4(bm);
      item.score_type = 'bm25';
      item.fused_score = score4(bm);
    } else if (mode === 'hybrid') {
      item.vector_score = score4(vec);
      item.bm25_score = score4(bm);
      item.fused_score = score4(fused);
      item.score_type = 'hybrid';
    } else {
      // rerank
      item.vector_score = score4(vec);
      item.bm25_score = score4(bm);
      item.fused_score = score4(fused);
      item.rerank_score = score4(rerank);
      item.score_type = 'rerank';
    }

    return item;
  });

  // threshold 过滤：按 fused/rerank 过滤
  const filtered = raw.filter((r) => {
    const s = r.rerank_score ?? r.fused_score ?? 0;
    return s >= threshold;
  });

  return filtered;
}

export async function getKBList(): Promise<
  { id: number; name: string; description?: string }[]
> {
  await sleep(Math.floor(rand(120, 260)));
  return mockKBs;
}

export async function vectorSearch(
  kb_id: number,
  query: string,
  top_k: number = 10,
): Promise<SearchResult[]> {
  await sleep(Math.floor(rand(260, 520)));
  return makeResults(kb_id, query, top_k, 'vector');
}

export async function bm25Search(
  kb_id: number,
  query: string,
  top_k: number = 10,
): Promise<SearchResult[]> {
  await sleep(Math.floor(rand(220, 480)));
  return makeResults(kb_id, query, top_k, 'bm25');
}

export async function pgvectorSearch(
  kb_id: number,
  query: string,
  options?: {
    top_k?: number;
    mode?: 'hybrid' | 'rerank';
    vector_weight?: number;
    bm25_weight?: number;
    threshold?: number;
  },
): Promise<SearchResult[]> {
  await sleep(Math.floor(rand(320, 680)));
  const topK = options?.top_k ?? 10;
  const mode = options?.mode ?? 'hybrid';
  return makeResults(kb_id, query, topK, mode, {
    vector_weight: options?.vector_weight,
    bm25_weight: options?.bm25_weight,
    threshold: options?.threshold,
  });
}



