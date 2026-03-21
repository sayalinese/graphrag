import { baseRequestClient } from '#/api/request';

interface ApiResponse<T> {
  data?: T;
  error?: string;
  success?: boolean;
}

interface DashboardDatabaseItem {
  default?: boolean;
  name: string;
}

export interface DashboardCentralNode {
  degree: number;
  id: null | string;
  labels: string[];
  name: string;
  properties: Record<string, unknown>;
}

export interface DashboardStats {
  averageDegree: number;
  communities: number;
  edges: number;
  nodeTypes: Record<string, number>;
  nodes: number;
  relationTypes: Record<string, number>;
  totalNodes: number;
  totalRelations: number;
}

export interface DashboardSeries {
  labels: string[];
  values: number[];
}

export interface DashboardTrends {
  daily: {
    chunks: DashboardSeries;
    documents: DashboardSeries;
    knowledgeBases: DashboardSeries;
    logins: DashboardSeries;
    messages: DashboardSeries;
    sessions: DashboardSeries;
    users: DashboardSeries;
  };
  monthly: {
    documents: DashboardSeries;
    messages: DashboardSeries;
  };
}

export interface DashboardSnapshot {
  centralNodes: DashboardCentralNode[];
  stats: DashboardStats;
  timestamp: string;
  trends: DashboardTrends;
}

const emptySeries: DashboardSeries = {
  labels: [],
  values: [],
};

const emptySnapshot: DashboardSnapshot = {
  centralNodes: [],
  stats: {
    averageDegree: 0,
    communities: 0,
    edges: 0,
    nodeTypes: {},
    nodes: 0,
    relationTypes: {},
    totalNodes: 0,
    totalRelations: 0,
  },
  timestamp: '',
  trends: {
    daily: {
      chunks: { ...emptySeries },
      documents: { ...emptySeries },
      knowledgeBases: { ...emptySeries },
      logins: { ...emptySeries },
      messages: { ...emptySeries },
      sessions: { ...emptySeries },
      users: { ...emptySeries },
    },
    monthly: {
      documents: { ...emptySeries },
      messages: { ...emptySeries },
    },
  },
};

let cachedDashboardDatabase: null | string | undefined;

function toNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function toRecord(value: unknown): Record<string, number> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, raw]) => [key, toNumber(raw)]),
  );
}

function normalizeCentralNode(raw: any): DashboardCentralNode {
  return {
    degree: toNumber(raw?.degree),
    id: raw?.id == null ? null : String(raw.id),
    labels: Array.isArray(raw?.labels) ? raw.labels.map((item: unknown) => String(item)) : [],
    name: typeof raw?.name === 'string' ? raw.name : '',
    properties:
      raw?.properties && typeof raw.properties === 'object' && !Array.isArray(raw.properties)
        ? raw.properties
        : {},
  };
}

function normalizeSeries(raw: any): DashboardSeries {
  const labels = Array.isArray(raw?.labels) ? raw.labels.map((item: unknown) => String(item)) : [];
  const values = Array.isArray(raw?.values) ? raw.values.map((item: unknown) => toNumber(item)) : [];
  return { labels, values };
}

function normalizeSnapshot(raw: any): DashboardSnapshot {
  const stats = raw?.stats ?? raw ?? {};
  const trends = raw?.trends ?? {};
  return {
    centralNodes: Array.isArray(raw?.central_nodes)
      ? raw.central_nodes.map((item: unknown) => normalizeCentralNode(item))
      : [],
    stats: {
      averageDegree: toNumber(stats.average_degree),
      communities: toNumber(stats.communities),
      edges: toNumber(stats.edges ?? stats.total_relations),
      nodeTypes: toRecord(stats.node_types),
      nodes: toNumber(stats.nodes ?? stats.total_nodes),
      relationTypes: toRecord(stats.relation_types),
      totalNodes: toNumber(stats.total_nodes ?? stats.nodes),
      totalRelations: toNumber(stats.total_relations ?? stats.edges),
    },
    timestamp: typeof raw?.timestamp === 'string' ? raw.timestamp : '',
    trends: {
      daily: {
        chunks: normalizeSeries(trends?.daily?.chunks),
        documents: normalizeSeries(trends?.daily?.documents),
        knowledgeBases: normalizeSeries(trends?.daily?.knowledge_bases),
        logins: normalizeSeries(trends?.daily?.logins),
        messages: normalizeSeries(trends?.daily?.messages),
        sessions: normalizeSeries(trends?.daily?.sessions),
        users: normalizeSeries(trends?.daily?.users),
      },
      monthly: {
        documents: normalizeSeries(trends?.monthly?.documents),
        messages: normalizeSeries(trends?.monthly?.messages),
      },
    },
  };
}

async function resolveDashboardDatabase(): Promise<null | string | undefined> {
  if (cachedDashboardDatabase !== undefined) {
    return cachedDashboardDatabase;
  }

  try {
    const response = await baseRequestClient.get<ApiResponse<{ databases?: DashboardDatabaseItem[] }>>('/kg/databases');
    const payload = response.data as unknown as ApiResponse<{ databases?: DashboardDatabaseItem[] }>;
    const items = payload?.data?.databases ?? [];
    const pick =
      items.find((item) => !item.default && item.name !== 'system') ??
      items.find((item) => item.name !== 'system') ??
      items[0];
    cachedDashboardDatabase = pick?.name;
    return cachedDashboardDatabase;
  } catch {
    cachedDashboardDatabase = null;
    return cachedDashboardDatabase;
  }
}

function withDatabase(path: string, database?: null | string): string {
  if (!database) return path;
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}database=${encodeURIComponent(database)}`;
}

export async function fetchDashboardSnapshot(): Promise<DashboardSnapshot> {
  const database = await resolveDashboardDatabase();

  try {
    const dashboardResponse = await baseRequestClient.get<ApiResponse<unknown>>(withDatabase('/kg/dashboard', database));
    const dashboardPayload = dashboardResponse.data as unknown as ApiResponse<unknown>;
    if (dashboardPayload?.success && dashboardPayload.data) {
      return normalizeSnapshot(dashboardPayload.data);
    }
  } catch {
    // Fallback below.
  }

  try {
    const overviewResponse = await baseRequestClient.get<ApiResponse<unknown>>(withDatabase('/kg/overview', database));
    const overviewPayload = overviewResponse.data as unknown as ApiResponse<unknown>;
    if (overviewPayload?.success && overviewPayload.data) {
      return normalizeSnapshot(overviewPayload.data);
    }
  } catch {
    // Fallback below.
  }

  try {
    const statsResponse = await baseRequestClient.get<ApiResponse<unknown>>(withDatabase('/kg/stats', database));
    const statsPayload = statsResponse.data as unknown as ApiResponse<unknown>;
    if (statsPayload?.success && statsPayload.data) {
      return normalizeSnapshot({ stats: statsPayload.data, central_nodes: [], timestamp: '' });
    }
  } catch {
    // Ignore and fall through to empty snapshot.
  }

  return { ...emptySnapshot };
}

export function topEntries(data: Record<string, number>, limit: number): Array<{ name: string; value: number }> {
  return Object.entries(data)
    .map(([name, value]) => ({ name, value: toNumber(value) }))
    .sort((left, right) => right.value - left.value)
    .slice(0, limit);
}

export function zeroArray(length: number): number[] {
  return Array.from({ length }, () => 0);
}
