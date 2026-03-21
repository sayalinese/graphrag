import { baseRequestClient } from '#/api/request';

interface ApiResponse<T> {
  data?: T;
  error?: string;
  success?: boolean;
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

export interface DashboardSnapshot {
  centralNodes: DashboardCentralNode[];
  stats: DashboardStats;
  timestamp: string;
}

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
};

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

function normalizeSnapshot(raw: any): DashboardSnapshot {
  const stats = raw?.stats ?? raw ?? {};
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
  };
}

export async function fetchDashboardSnapshot(): Promise<DashboardSnapshot> {
  try {
    const overviewResponse = await baseRequestClient.get<ApiResponse<unknown>>('/kg/overview');
    const overviewPayload = overviewResponse.data as unknown as ApiResponse<unknown>;
    if (overviewPayload?.success && overviewPayload.data) {
      return normalizeSnapshot(overviewPayload.data);
    }
  } catch {
    // Fallback below.
  }

  try {
    const statsResponse = await baseRequestClient.get<ApiResponse<unknown>>('/kg/stats');
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
