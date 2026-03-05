<script lang="ts" setup>
import { onMounted, reactive, ref } from 'vue';
import { ElButton, ElTooltip } from 'element-plus';
import { ChatDotRound, Operation } from '@element-plus/icons-vue';

import KgChatWindow from './components/KgChatWindow.vue';
import Graph from './graph.vue';
import Parameter from './parameter.vue';
import type { EntityInfo } from './utils/api';
import { baseRequestClient } from '#/api/request';

interface KgHighlightPayload {
  seedNodeIds: string[];
  nodeIds: string[];
  linkIds: string[];
  maxDepth?: number;
  graph?: { nodes: any[]; edges: any[] };
}

interface GraphExpose {
  clearHighlight?: () => void;
  fetchGraphData?: () => void;
  getEdges?: () => any[];
  getNodes?: () => any[];
  handleReset?: () => void;
  highlightElements?: (
    nodeIds: string[],
    linkIds: string[],
    options?: { maxDepth?: number; seedNodeIds?: string[] }
  ) => void;
}

const params = reactive({
  searchKeyword: '',
  selectedCategory: '',
  selectedDatabase: '',
  graphLimit: 300,
  showLabels: true,
  showEdges: true,
  nodeSize: 1,
  autoRotate: true,
  nodeStyle: 'style1',
});

const graphRef = ref<GraphExpose>();
const showChat = ref(true);
const showParam = ref(true);
const chatPanelWidth = ref(430);

onMounted(async () => {
  try {
    const res = await baseRequestClient.get<any>('/kg/databases');
    const dbs: Array<{ name: string; default: boolean }> =
      res?.data?.data?.databases || res?.data?.databases || [];
    const pick =
      dbs.find((d) => !d.default && d.name !== 'system') ||
      dbs.find((d) => d.name !== 'system');
    if (pick && !params.selectedDatabase) {
      params.selectedDatabase = pick.name;
    }
  } catch {
    // 保持默认空字符串
  }
});

const handleParamUpdate = (newParams: typeof params) => {
  Object.assign(params, newParams);
};

const handleRefresh = () => {
  graphRef.value?.fetchGraphData?.();
};

const handleReset = () => {
  graphRef.value?.handleReset?.();
};

function normalizeNodeId(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  return '';
}

function normalizeLinkId(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value && typeof value === 'object') {
    const source = normalizeNodeId((value as any).source);
    const target = normalizeNodeId((value as any).target);
    if (source && target) return `${source}-${target}`;
  }
  return '';
}

const buildLayeredHighlight = (seedNodeIds: string[], maxDepth = 3) => {
  const edges = graphRef.value?.getEdges?.() ?? [];
  const adjacency = new Map<string, Set<string>>();

  edges.forEach((edge) => {
    const sourceId = typeof edge.source === 'object' ? (edge.source as any).id : edge.source;
    const targetId = typeof edge.target === 'object' ? (edge.target as any).id : edge.target;
    if (!sourceId || !targetId) return;

    if (!adjacency.has(sourceId)) adjacency.set(sourceId, new Set());
    if (!adjacency.has(targetId)) adjacency.set(targetId, new Set());
    adjacency.get(sourceId)?.add(targetId);
    adjacency.get(targetId)?.add(sourceId);
  });

  const visited = new Set<string>();
  const queue: Array<{ depth: number; id: string }> = [];
  seedNodeIds.forEach((id) => {
    visited.add(id);
    queue.push({ depth: 0, id });
  });

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current.depth >= maxDepth) continue;

    const neighbors = adjacency.get(current.id);
    if (!neighbors) continue;

    neighbors.forEach((neighborId) => {
      if (visited.has(neighborId)) return;
      visited.add(neighborId);
      queue.push({ depth: current.depth + 1, id: neighborId });
    });
  }

  const layeredNodeIds = Array.from(visited);
  const nodeSet = new Set(layeredNodeIds);
  const layeredLinkIds = edges
    .filter((edge) => {
      const sourceId = typeof edge.source === 'object' ? (edge.source as any).id : edge.source;
      const targetId = typeof edge.target === 'object' ? (edge.target as any).id : edge.target;
      return nodeSet.has(sourceId) && nodeSet.has(targetId);
    })
    .map((edge) => {
      const sourceId = typeof edge.source === 'object' ? (edge.source as any).id : edge.source;
      const targetId = typeof edge.target === 'object' ? (edge.target as any).id : edge.target;
      return `${sourceId}-${targetId}`;
    });

  return { layeredNodeIds, layeredLinkIds };
};

const handleSelectEntity = (entity: EntityInfo) => {
  params.searchKeyword = entity.name || '';
};

function mapEntitiesToNodeIds(entities: EntityInfo[]): string[] {
  const nodes = graphRef.value?.getNodes?.() ?? [];
  if (!nodes.length) return [];

  let targetNodeIds = entities
    .map((e) => (e.neo_id !== undefined ? String(e.neo_id) : ''))
    .filter(Boolean)
    .filter((id) => nodes.some((n) => n.id === id));

  if (!targetNodeIds.length) {
    targetNodeIds = entities
      .map((e) => {
        const hit = nodes.find(
          (n) =>
            n.label === e.name ||
            n.id === e.name ||
            n.label?.toLowerCase?.() === e.name?.toLowerCase?.()
        );
        return hit?.id;
      })
      .filter((id): id is string => Boolean(id));
  }

  return Array.from(new Set(targetNodeIds));
}

const handleHighlightEntities = (entities: EntityInfo[]) => {
  if (!entities?.length) return;

  params.searchKeyword = '';
  params.selectedCategory = '';

  const targetNodeIds = mapEntitiesToNodeIds(entities);
  if (!targetNodeIds.length) {
    graphRef.value?.clearHighlight?.();
    return;
  }

  const { layeredNodeIds, layeredLinkIds } = buildLayeredHighlight(targetNodeIds, 3);
  graphRef.value?.highlightElements?.(layeredNodeIds, layeredLinkIds, {
    seedNodeIds: targetNodeIds,
    maxDepth: 3,
  });
};

const handleHighlightKnowledge = (data: {
  entities: EntityInfo[];
  relations: any[];
  question?: string;
}) => {
  handleHighlightEntities(data.entities || []);
};

const handleKgHighlight = (payload: KgHighlightPayload) => {
  if (!payload || !graphRef.value) return;

  params.searchKeyword = '';
  params.selectedCategory = '';

  const maxDepth = Number.isFinite(payload.maxDepth) ? Number(payload.maxDepth) : 3;
  const nodes = graphRef.value.getNodes?.() ?? [];
  const edges = graphRef.value.getEdges?.() ?? [];
  const existingNodeIdSet = new Set(nodes.map((node) => normalizeNodeId(node.id)));

  const normalizedSeedNodeIds = Array.from(
    new Set(
      (payload.seedNodeIds || [])
        .map(normalizeNodeId)
        .filter((id) => existingNodeIdSet.has(id))
    )
  );

  const normalizedNodeIds = Array.from(
    new Set(
      (payload.nodeIds || [])
        .map(normalizeNodeId)
        .filter((id) => existingNodeIdSet.has(id))
    )
  );

  const edgeIdSet = new Set(
    edges.flatMap((edge) => {
      const source = normalizeNodeId(
        typeof edge.source === 'object' ? (edge.source as any).id : edge.source
      );
      const target = normalizeNodeId(
        typeof edge.target === 'object' ? (edge.target as any).id : edge.target
      );
      return [`${source}-${target}`, `${target}-${source}`];
    })
  );

  let normalizedLinkIds = Array.from(
    new Set(
      (payload.linkIds || [])
        .map(normalizeLinkId)
        .filter((id) => edgeIdSet.has(id))
    )
  );

  const seeds = normalizedSeedNodeIds.length
    ? normalizedSeedNodeIds
    : normalizedNodeIds.length
      ? [normalizedNodeIds[0]!]
      : [];

  let finalNodeIds = normalizedNodeIds;
  let finalLinkIds = normalizedLinkIds;

  if (!finalNodeIds.length && seeds.length) {
    const layered = buildLayeredHighlight(seeds, maxDepth);
    finalNodeIds = layered.layeredNodeIds;
    finalLinkIds = layered.layeredLinkIds;
  }

  if (finalNodeIds.length && !finalLinkIds.length) {
    const nodeSet = new Set(finalNodeIds);
    finalLinkIds = edges
      .filter((edge) => {
        const source = normalizeNodeId(
          typeof edge.source === 'object' ? (edge.source as any).id : edge.source
        );
        const target = normalizeNodeId(
          typeof edge.target === 'object' ? (edge.target as any).id : edge.target
        );
        return nodeSet.has(source) && nodeSet.has(target);
      })
      .map((edge) => {
        const source = normalizeNodeId(
          typeof edge.source === 'object' ? (edge.source as any).id : edge.source
        );
        const target = normalizeNodeId(
          typeof edge.target === 'object' ? (edge.target as any).id : edge.target
        );
        return `${source}-${target}`;
      });
  }

  if (!finalNodeIds.length) {
    graphRef.value.clearHighlight?.();
    return;
  }

  graphRef.value.highlightElements?.(finalNodeIds, finalLinkIds, {
    seedNodeIds: seeds,
    maxDepth,
  });
};

</script>

<template>
  <div class="relative h-[calc(100vh-80.2px)] overflow-hidden bg-[#0a0a0a]">
    <div class="absolute inset-0 min-w-0">
      <Graph
        ref="graphRef"
        :search-keyword="params.searchKeyword"
        :selected-category="params.selectedCategory"
        :selected-database="params.selectedDatabase"
        :graph-limit="params.graphLimit"
        :show-labels="params.showLabels"
        :show-edges="params.showEdges"
        :node-size="params.nodeSize"
        :auto-rotate="params.autoRotate"
        :node-style="params.nodeStyle"
      />

      <div v-if="!showParam" class="absolute left-4 top-4 z-10">
        <ElTooltip content="显示控制面板" placement="right">
          <ElButton
            type="info"
            circle
            size="large"
            class="!border-gray-700 !bg-gray-800/80 !text-gray-200 hover:!bg-gray-700 backdrop-blur-md shadow-lg"
            @click="showParam = true"
          >
            <el-icon class="text-xl"><Operation /></el-icon>
          </ElButton>
        </ElTooltip>
      </div>

      <div v-if="!showChat" class="absolute right-4 top-4 z-10">
        <ElTooltip content="显示问答面板" placement="left">
          <ElButton
            type="primary"
            circle
            size="large"
            class="shadow-lg shadow-blue-900/20"
            @click="showChat = true"
          >
            <el-icon class="text-xl"><ChatDotRound /></el-icon>
          </ElButton>
        </ElTooltip>
      </div>
    </div>

    <transition name="slide-left">
      <div
        v-show="showParam"
        class="absolute bottom-0 left-0 top-0 z-20 h-full border-r border-gray-800/50 bg-transparent shadow-2xl"
      >
        <Parameter
          :model-value="params"
          @update:model-value="handleParamUpdate"
          @refresh="handleRefresh"
          @reset="handleReset"
          @close="showParam = false"
        />
      </div>
    </transition>

    <transition name="slide-right">
      <div
        v-show="showChat"
        class="absolute bottom-0 right-0 top-0 z-20 h-full border-l border-gray-800/50 bg-[#08162f]/70 shadow-2xl backdrop-blur-md"
        :style="{ width: `${chatPanelWidth}px` }"
      >
        <div class="flex h-full flex-col">
          <div class="flex-1 min-h-0 px-3 pb-3 pt-3">
            <KgChatWindow
              v-model:doc-id="params.selectedDatabase"
              @select-entity="handleSelectEntity"
              @highlight-entities="handleHighlightEntities"
              @highlight-knowledge="handleHighlightKnowledge"
              @kg-highlight="handleKgHighlight"
              @close="showChat = false"
            />
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
:deep(html),
:deep(body) {
  margin: 0;
  padding: 0;
  overflow: hidden;
}

.slide-left-enter-active,
.slide-left-leave-active {
  width: 20rem;
  opacity: 1;
  overflow: hidden;
  transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.slide-left-enter-from,
.slide-left-leave-to {
  width: 0;
  opacity: 0;
  transform: translateX(-20px);
}

.slide-right-enter-active,
.slide-right-leave-active {
  opacity: 1;
  overflow: hidden;
  transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.slide-right-enter-from,
.slide-right-leave-to {
  width: 0 !important;
  opacity: 0;
  transform: translateX(20px);
}
</style>

