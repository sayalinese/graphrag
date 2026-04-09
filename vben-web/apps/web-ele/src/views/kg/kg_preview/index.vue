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
  <div class="kg-preview-page relative h-[calc(100vh-80.2px)] overflow-hidden">
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
        <div class="preview-db-card w-60 rounded-xl border p-3 backdrop-blur-md">
          <div class="preview-db-card__label mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.2em]">
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
            class="preview-panel-toggle backdrop-blur-md"
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
        class="preview-panel-shell absolute bottom-0 left-0 top-0 z-20 h-full border-r bg-transparent shadow-2xl"
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
:global(:root) {
  --kgp-page-bg:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.06), transparent 24%),
    linear-gradient(180deg, #f7f8fa, #eef2f7 72%);
  --kgp-float-bg: rgba(255, 255, 255, 0.84);
  --kgp-float-border: rgba(148, 163, 184, 0.25);
  --kgp-float-shadow: 0 18px 40px rgba(15, 23, 42, 0.12);
  --kgp-float-label: #475569;
  --kgp-toggle-bg: rgba(255, 255, 255, 0.88);
  --kgp-toggle-border: rgba(148, 163, 184, 0.24);
  --kgp-toggle-text: #334155;
  --kgp-panel-border: rgba(148, 163, 184, 0.2);
}

:global(.dark) {
  --kgp-page-bg: #0a0a0a;
  --kgp-float-bg: rgba(2, 6, 23, 0.78);
  --kgp-float-border: rgba(6, 182, 212, 0.2);
  --kgp-float-shadow: 0 18px 40px rgba(0, 0, 0, 0.28);
  --kgp-float-label: rgba(103, 232, 249, 0.85);
  --kgp-toggle-bg: rgba(31, 41, 55, 0.8);
  --kgp-toggle-border: rgba(55, 65, 81, 0.9);
  --kgp-toggle-text: #e5e7eb;
  --kgp-panel-border: rgba(31, 41, 55, 0.7);
}

.kg-preview-page {
  background: var(--kgp-page-bg);
}

.preview-db-card {
  background: var(--kgp-float-bg);
  border-color: var(--kgp-float-border) !important;
  box-shadow: var(--kgp-float-shadow);
}

.preview-db-card__label {
  color: var(--kgp-float-label);
}

.preview-panel-toggle {
  background: var(--kgp-toggle-bg) !important;
  border-color: var(--kgp-toggle-border) !important;
  color: var(--kgp-toggle-text) !important;
  box-shadow: var(--kgp-float-shadow);
}

.preview-panel-toggle:hover {
  opacity: 0.92;
}

.preview-panel-shell {
  border-right-color: var(--kgp-panel-border) !important;
}

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

