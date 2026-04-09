<script lang="ts" setup>
import { ref, watch, onMounted } from 'vue'
import { ElOption, ElSelect, ElTooltip, ElIcon, ElInput } from 'element-plus'
import {
  Operation,
  Brush,
  Refresh,
  Loading,
  Search,
  CollectionTag,
  Connection,
  RefreshLeft,
  Fold,
  Document
} from '@element-plus/icons-vue'
import { getNeo4jDatabases } from './utils/api'

interface ParamState {
  searchKeyword: string
  selectedCategory: string
  selectedDatabase: string
  graphLimit: number
  showLabels: boolean
  showEdges: boolean
  nodeSize: number
  autoRotate: boolean
  nodeStyle: string
}

const props = withDefaults(defineProps<{
  modelValue: ParamState
  nodeCount?: number
  edgeCount?: number
}>(), {
  modelValue: () => ({
    searchKeyword: '',
    selectedCategory: '',
    selectedDatabase: '',
    graphLimit: 300,
    showLabels: true,
    showEdges: true,
    nodeSize: 1,
    autoRotate: true,
    nodeStyle: 'style1'
  })
})

const emit = defineEmits<{
  'update:modelValue': [value: ParamState]
  'refresh': []
  'reset': []
  'close': []
}>()

const loading = ref(false)
const localState = ref({ ...props.modelValue })
const styleOptions = [
  { label: '木星', value: 'style1' },
  { label: '海王星', value: 'style2' }
]

const categories = [
  { label: '全部', value: '' },
  { label: 'PERSON', value: 'PERSON' },
  { label: 'ORGANIZATION', value: 'ORGANIZATION' },
  { label: 'LOCATION', value: 'LOCATION' },
  { label: 'PRODUCT', value: 'PRODUCT' },
  { label: 'CONCEPT', value: 'CONCEPT' }
]

// Neo4j 数据库列表
const databaseOptions = ref<Array<{ label: string; value: string }>>([
  { label: '默认数据库', value: '' }
])
const loadingDocs = ref(false)

function sanitizeDatabaseName(value?: string) {
  const normalized = value?.trim() || ''
  return normalized.toLowerCase() === 'system' ? '' : normalized
}

function ensureSelectedDatabaseValid() {
  const selected = sanitizeDatabaseName(localState.value.selectedDatabase)
  const allowed = new Set(databaseOptions.value.map((option) => option.value))
  localState.value.selectedDatabase = allowed.has(selected) ? selected : ''
}

// 获取数据库列表
async function fetchDatabases() {
  loadingDocs.value = true
  try {
    const databases = await getNeo4jDatabases()
    databaseOptions.value = [
      { label: '默认数据库', value: '' },
      ...databases.map((db) => ({
        label: db.name,
        value: db.name
      }))
    ]
    ensureSelectedDatabaseValid()
  } catch (error) {
    console.warn('获取数据库列表失败:', error)
  } finally {
    loadingDocs.value = false
  }
}

watch(() => props.modelValue, (newVal) => {
  localState.value = {
    ...newVal,
    selectedDatabase: sanitizeDatabaseName(newVal.selectedDatabase)
  }
  ensureSelectedDatabaseValid()
}, { deep: true })

watch(localState, (newVal) => {
  emit('update:modelValue', { ...newVal })
}, { deep: true })

watch(() => localState.value.selectedDatabase, (newVal) => {
  const sanitized = sanitizeDatabaseName(newVal)
  if (sanitized !== newVal) {
    localState.value.selectedDatabase = sanitized
  }
})

const handleRefresh = () => {
  loading.value = true
  emit('refresh')
  setTimeout(() => {
    loading.value = false
  }, 1000)
}

const handleReset = () => {
  emit('reset')
}

// 初始化时获取文档列表
onMounted(() => {
  fetchDatabases()
})

</script>

<template>
  <div class="preview-parameter w-80 h-full overflow-y-auto p-4 flex flex-col backdrop-blur-sm">
    <!-- 标题 -->
    <div class="parameter-header flex justify-between items-center mb-6 pb-4 border-b">
      <div class="flex items-center gap-2">
        <el-icon class="text-lg text-cyan-400"><Operation /></el-icon>
        <span class="parameter-title font-semibold text-base tracking-wide">控制面板</span>
      </div>
      <ElTooltip content="折叠面板" placement="bottom">
        <button 
          class="parameter-close-btn p-1.5 rounded-md transition-colors"
          @click="$emit('close')"
        >
          <el-icon class="text-lg"><Fold /></el-icon>
        </button>
      </ElTooltip>
    </div>

    <!-- 顶部操作栏 -->
    <!-- <div class="flex items-center justify-between gap-3 mb-6"> -->
      <!-- <el-select
        v-model="localState.nodeStyle"
        size="small"
        class="style-select flex-1"
        popper-class="style-select-dropdown"
        :teleported="false"
      >
        <template #prefix>
          <el-icon class="text-gray-400"><Brush /></el-icon>
        </template> -->
        <!-- <el-option
          v-for="option in styleOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        /> -->
      <!-- </el-select> -->
      
      <!-- <button
        @click="handleRefresh"
        :disabled="loading"
        class="px-3 py-1.5 h-8 flex items-center justify-center text-sm font-medium text-cyan-200 rounded-md border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 hover:text-cyan-100 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 disabled:opacity-50 transition-all duration-200"
        :title="loading ? '刷新中…' : '刷新数据'"
      >
        <el-icon v-if="loading" class="text-lg is-loading"><Loading /></el-icon>
        <el-icon v-else class="text-lg"><Refresh /></el-icon>
      </button>
    </div> -->

    <!-- 数据库筛选 -->
    <div class="parameter-focus-card mb-6 group rounded-xl border p-3">
      <label class="parameter-focus-label text-xs font-medium mb-2 block uppercase tracking-wider">数据库</label>
      <ElSelect
        v-model="localState.selectedDatabase"
        class="style-select w-full"
        popper-class="style-select-dropdown"
        :teleported="false"
        :loading="loadingDocs"
        placeholder="选择数据库..."
      >
        <template #prefix>
          <el-icon class="text-gray-500"><Document /></el-icon>
        </template>
        <ElOption
          v-for="db in databaseOptions"
          :key="db.value"
          :label="db.label"
          :value="db.value"
        />
      </ElSelect>
    </div>

    <!-- 搜索 -->
    <div class="mb-6 group">
      <label class="parameter-label text-xs font-medium mb-2 block uppercase tracking-wider group-focus-within:text-cyan-400 transition-colors">搜索节点</label>
      <ElInput
        v-model="localState.searchKeyword"
        placeholder="输入节点名称..."
        class="style-select"
      >
        <template #prefix>
          <el-icon class="text-gray-500"><Search /></el-icon>
        </template>
      </ElInput>
    </div>

    <!-- 分类 -->
    <div class="mb-6 group">
      <label class="parameter-label text-xs font-medium mb-2 block uppercase tracking-wider group-focus-within:text-cyan-400 transition-colors">节点分类</label>
      <ElSelect
        v-model="localState.selectedCategory"
        class="style-select w-full"
        popper-class="style-select-dropdown"
        :teleported="false"
      >
        <template #prefix>
          <el-icon class="text-gray-500"><CollectionTag /></el-icon>
        </template>
        <ElOption
          v-for="cat in categories"
          :key="cat.value"
          :label="cat.label"
          :value="cat.value"
        />
      </ElSelect>
    </div>

    <!-- 图谱加载上限 -->
    <div class="mb-6">
      <div class="flex justify-between items-center mb-3">
        <label class="parameter-label text-xs font-medium uppercase tracking-wider">图谱加载上限</label>
        <span class="parameter-value-chip text-xs font-mono px-2 py-0.5 rounded">{{ localState.graphLimit }}</span>
      </div>
      <input
        v-model.number="localState.graphLimit"
        type="range"
        min="100"
        max="5000"
        step="100"
        class="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
      />
      <p class="parameter-hint mt-2 text-xs">建议 500~2000，过大可能导致 3D 渲染卡顿</p>
    </div>

    <!-- 显示选项 -->
    <div class="parameter-section-card mb-6 p-4 rounded-xl border">
      <h3 class="parameter-label text-xs font-medium mb-3 uppercase tracking-wider">显示选项</h3>
      <div class="space-y-3">
        <label class="flex items-center justify-between text-gray-300 text-sm cursor-pointer group">
          <span class="parameter-option-text transition-colors">显示标签</span>
          <div class="relative inline-flex items-center cursor-pointer">
            <input v-model="localState.showLabels" type="checkbox" class="sr-only peer">
            <div class="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-600"></div>
          </div>
        </label>

        <label class="flex items-center justify-between text-gray-300 text-sm cursor-pointer group">
          <span class="parameter-option-text transition-colors">显示连接</span>
          <div class="relative inline-flex items-center cursor-pointer">
            <input v-model="localState.showEdges" type="checkbox" class="sr-only peer">
            <div class="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-600"></div>
          </div>
        </label>

        <label class="flex items-center justify-between text-gray-300 text-sm cursor-pointer group">
          <span class="parameter-option-text transition-colors">自动旋转</span>
          <div class="relative inline-flex items-center cursor-pointer">
            <input v-model="localState.autoRotate" type="checkbox" class="sr-only peer">
            <div class="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-600"></div>
          </div>
        </label>
      </div>
    </div>

    <!-- 节点大小 -->
    <div class="mb-6">
      <div class="flex justify-between items-center mb-3">
        <label class="parameter-label text-xs font-medium uppercase tracking-wider">节点大小</label>
        <span class="parameter-value-chip text-xs font-mono px-2 py-0.5 rounded">{{ localState.nodeSize.toFixed(1) }}x</span>
      </div>
      <input
        v-model.number="localState.nodeSize"
        type="range"
        min="0.5"
        max="3"
        step="0.1"
        class="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
      />
    </div>

    <!-- 统计 -->
    <div class="parameter-stats-card mb-6 p-4 rounded-xl border">
      <div class="flex items-center gap-2 mb-3">
        <el-icon class="text-cyan-400"><Connection /></el-icon>
        <p class="parameter-title text-sm font-medium">图谱统计</p>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div class="parameter-stat-box p-2 rounded border">
          <div class="parameter-hint text-xs mb-1">节点总数</div>
          <div class="text-cyan-400 font-mono text-lg leading-none">{{ props.nodeCount ?? '--' }}</div>
        </div>
        <div class="parameter-stat-box p-2 rounded border">
          <div class="parameter-hint text-xs mb-1">关系总数</div>
          <div class="text-purple-400 font-mono text-lg leading-none">{{ props.edgeCount ?? '--' }}</div>
        </div>
      </div>
    </div>

    <!-- 按钮 -->
    <div class="parameter-footer mt-auto pt-4 border-t">
      <button
        @click="handleReset"
        class="parameter-reset-btn w-full px-4 py-2.5 text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
      >
        <el-icon><RefreshLeft /></el-icon>
        重置视图
      </button>
    </div>

  </div>
</template>

<style scoped>
:global(:root) {
  --kgpp-panel-bg: rgba(255, 255, 255, 0.78);
  --kgpp-panel-text: #334155;
  --kgpp-title: #0f172a;
  --kgpp-border: rgba(148, 163, 184, 0.2);
  --kgpp-muted: #64748b;
  --kgpp-hint: #94a3b8;
  --kgpp-focus-bg: rgba(14, 165, 233, 0.05);
  --kgpp-focus-border: rgba(14, 165, 233, 0.18);
  --kgpp-focus-label: #0f766e;
  --kgpp-section-bg: rgba(248, 250, 252, 0.8);
  --kgpp-section-border: rgba(148, 163, 184, 0.16);
  --kgpp-chip-bg: rgba(14, 165, 233, 0.08);
  --kgpp-chip-text: #0369a1;
  --kgpp-reset-bg: rgba(51, 65, 85, 0.92);
  --kgpp-reset-hover: rgba(30, 41, 59, 0.96);
  --kgpp-close-color: #64748b;
  --kgpp-close-hover-bg: rgba(148, 163, 184, 0.14);
  --kgpp-close-hover-color: #0f172a;
  --kgpp-input-bg: rgba(255, 255, 255, 0.86);
  --kgpp-input-border: rgba(148, 163, 184, 0.36);
  --kgpp-input-text: #0f172a;
  --kgpp-input-placeholder: #94a3b8;
  --kgpp-dropdown-bg: #ffffff;
  --kgpp-dropdown-border: #dbe2ea;
  --kgpp-dropdown-item: #334155;
  --kgpp-dropdown-item-active: #0f172a;
  --kgpp-dropdown-item-bg: rgba(59, 130, 246, 0.08);
}

:global(.dark) {
  --kgpp-panel-bg: rgba(17, 24, 39, 0.8);
  --kgpp-panel-text: #e5e7eb;
  --kgpp-title: #f8fafc;
  --kgpp-border: rgba(55, 65, 81, 0.6);
  --kgpp-muted: #9ca3af;
  --kgpp-hint: #6b7280;
  --kgpp-focus-bg: rgba(6, 182, 212, 0.08);
  --kgpp-focus-border: rgba(6, 182, 212, 0.15);
  --kgpp-focus-label: #67e8f9;
  --kgpp-section-bg: rgba(31, 41, 55, 0.3);
  --kgpp-section-border: rgba(55, 65, 81, 0.3);
  --kgpp-chip-bg: rgba(6, 182, 212, 0.1);
  --kgpp-chip-text: #22d3ee;
  --kgpp-reset-bg: #374151;
  --kgpp-reset-hover: #4b5563;
  --kgpp-close-color: #9ca3af;
  --kgpp-close-hover-bg: rgba(31, 41, 55, 0.8);
  --kgpp-close-hover-color: #ffffff;
  --kgpp-input-bg: rgba(31, 41, 55, 0.5);
  --kgpp-input-border: rgba(75, 85, 99, 0.5);
  --kgpp-input-text: #f3f4f6;
  --kgpp-input-placeholder: #6b7280;
  --kgpp-dropdown-bg: #1f2937;
  --kgpp-dropdown-border: #374151;
  --kgpp-dropdown-item: #d1d5db;
  --kgpp-dropdown-item-active: #ffffff;
  --kgpp-dropdown-item-bg: #374151;
}

.preview-parameter {
  background: var(--kgpp-panel-bg);
  color: var(--kgpp-panel-text);
  border-right: 1px solid var(--kgpp-border);
}

.parameter-header,
.parameter-footer {
  border-color: var(--kgpp-border) !important;
}

.parameter-title {
  color: var(--kgpp-title);
}

.parameter-close-btn {
  color: var(--kgpp-close-color);
}

.parameter-close-btn:hover {
  background: var(--kgpp-close-hover-bg);
  color: var(--kgpp-close-hover-color);
}

.parameter-focus-card {
  background: var(--kgpp-focus-bg);
  border-color: var(--kgpp-focus-border) !important;
}

.parameter-focus-label {
  color: var(--kgpp-focus-label);
}

.parameter-label,
.parameter-hint {
  color: var(--kgpp-muted);
}

.parameter-section-card,
.parameter-stats-card,
.parameter-stat-box {
  background: var(--kgpp-section-bg);
  border-color: var(--kgpp-section-border) !important;
}

.parameter-value-chip {
  background: var(--kgpp-chip-bg);
  color: var(--kgpp-chip-text);
}

.parameter-option-text {
  color: var(--kgpp-panel-text);
}

.group:hover .parameter-option-text {
  color: var(--kgpp-title);
}

.parameter-reset-btn {
  background: var(--kgpp-reset-bg);
  color: #ffffff;
}

.parameter-reset-btn:hover {
  background: var(--kgpp-reset-hover);
}

input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #06b6d4;
  cursor: pointer;
  border: 2px solid #1f2937;
  box-shadow: 0 0 0 2px rgba(6, 182, 212, 0.3);
  transition: transform 0.1s;
}

input[type="range"]::-webkit-slider-thumb:hover {
  transform: scale(1.1);
}

.style-select :deep(.el-input__wrapper) {
  padding: 4px 12px;
  background: var(--kgpp-input-bg);
  border: 1px solid var(--kgpp-input-border);
  border-radius: 0.5rem;
  box-shadow: none;
  color: var(--kgpp-input-text);
}

.style-select :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(6, 182, 212, 0.5);
  box-shadow: 0 0 0 1px rgba(6, 182, 212, 0.5);
}

.style-select :deep(.el-input__inner) {
  color: inherit;
  font-size: 0.875rem;
}

.style-select :deep(.el-input__inner::placeholder) {
  color: var(--kgpp-input-placeholder);
}

:global(.style-select-dropdown) {
  background: var(--kgpp-dropdown-bg) !important;
  border: 1px solid var(--kgpp-dropdown-border) !important;
}

:global(.style-select-dropdown .el-select-dropdown__item) {
  color: var(--kgpp-dropdown-item);
}

:global(.style-select-dropdown .el-select-dropdown__item.hover),
:global(.style-select-dropdown .el-select-dropdown__item.selected) {
  background: var(--kgpp-dropdown-item-bg);
  color: var(--kgpp-dropdown-item-active);
}
</style>
