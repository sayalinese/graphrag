<script lang="ts" setup>
import { onMounted, reactive, ref } from 'vue';
import { ElButton, ElIcon, ElOption, ElSelect, ElTooltip } from 'element-plus';
import { Document, Operation } from '@element-plus/icons-vue';

import Graph from './graph.vue';
import Parameter from './parameter.vue';
import { getNeo4jDatabases } from './utils/api';

interface GraphExpose {
  clearHighlight?: () => void;
  fetchGraphData?: () => void;
  getEdges?: () => any[];
  getNodes?: () => any[];
  handleReset?: () => void;
  graphData?: { value: { nodes: any[]; edges: any[] } };
  nodeCount?: { value: number };
  edgeCount?: { value: number };
  highlightElements?: (
    nodeIds: string[],
    linkIds: string[],
    options?: {
      maxDepth?: number;
      seedNodeIds?: string[];
      graph?: { nodes?: any[]; edges?: any[]; links?: any[] };
    }
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
const showParam = ref(true);
const loadingDatabases = ref(false);
const databaseOptions = ref<Array<{ label: string; value: string }>>([])
const graphNodeCount = ref(0);
const graphEdgeCount = ref(0);

function handleGraphStatsChanged(payload: { nodeCount: number; edgeCount: number }) {
  graphNodeCount.value = payload.nodeCount;
  graphEdgeCount.value = payload.edgeCount;
}

function sanitizeDatabaseName(value?: string) {
  const normalized = value?.trim() || '';
  return normalized.toLowerCase() === 'system' ? '' : normalized;
}

function ensureSelectedDatabaseValid() {
  const selected = sanitizeDatabaseName(params.selectedDatabase);
  const allowed = new Set(databaseOptions.value.map((option) => option.value));
  params.selectedDatabase = allowed.has(selected) ? selected : databaseOptions.value[0]?.value || '';
}

async function fetchDatabases() {
  loadingDatabases.value = true;
  try {
    const databases = await getNeo4jDatabases();
    databaseOptions.value = databases.map((db) => ({
      label: db.name,
      value: db.name,
    }));
    ensureSelectedDatabaseValid();
  } catch {
    databaseOptions.value = [];
    params.selectedDatabase = '';
  } finally {
    loadingDatabases.value = false;
  }
}

onMounted(async () => {
  await fetchDatabases();
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
        @stats-changed="handleGraphStatsChanged"
      />

      <div v-if="!showParam" class="absolute left-4 top-4 z-[200]">
        <div class="w-60 rounded-xl border border-cyan-500/20 bg-slate-950/78 p-3 shadow-2xl shadow-black/30 backdrop-blur-md">
          <div class="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.2em] text-cyan-300/85">
            <el-icon class="text-sm"><Document /></el-icon>
            <span>数据库</span>
          </div>
          <ElSelect
            v-model="params.selectedDatabase"
            class="w-full"
            placeholder="选择数据库"
            popper-class="doc-select-dropdown"
            :loading="loadingDatabases"
            :teleported="true"
          >
            <ElOption
              v-for="database in databaseOptions"
              :key="database.value"
              :label="database.label"
              :value="database.value"
            />
          </ElSelect>
        </div>
      </div>

      <div v-if="!showParam" class="absolute left-4 top-24 z-50">
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

    </div>

    <transition name="slide-left">
      <div
        v-show="showParam"
        class="absolute bottom-0 left-0 top-0 z-20 h-full border-r border-gray-800/50 bg-transparent shadow-2xl"
      >
        <Parameter
          :model-value="params"
          :node-count="graphNodeCount"
          :edge-count="graphEdgeCount"
          @update:model-value="handleParamUpdate"
          @refresh="handleRefresh"
          @reset="handleReset"
          @close="showParam = false"
        />
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

</style>

