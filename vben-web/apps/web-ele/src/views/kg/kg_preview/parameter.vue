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
  <div class="w-80 h-full overflow-y-auto p-4 flex flex-col text-gray-200 bg-gray-900/80 backdrop-blur-sm">
    <!-- 标题 -->
    <div class="flex justify-between items-center mb-6 pb-4 border-b border-gray-700/50">
      <div class="flex items-center gap-2">
        <el-icon class="text-lg text-cyan-400"><Operation /></el-icon>
        <span class="font-semibold text-base tracking-wide">控制面板</span>
      </div>
      <ElTooltip content="折叠面板" placement="bottom">
        <button 
          class="p-1.5 rounded-md hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
          @click="$emit('close')"
        >
          <el-icon class="text-lg"><Fold /></el-icon>
        </button>
      </ElTooltip>
    </div>

    <!-- 顶部操作栏 -->
    <div class="flex items-center justify-between gap-3 mb-6">
      <el-select
        v-model="localState.nodeStyle"
        size="small"
        class="style-select flex-1"
        popper-class="style-select-dropdown"
        :teleported="false"
      >
        <template #prefix>
          <el-icon class="text-gray-400"><Brush /></el-icon>
        </template>
        <el-option
          v-for="option in styleOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      
      <button
        @click="handleRefresh"
        :disabled="loading"
        class="px-3 py-1.5 h-8 flex items-center justify-center text-sm font-medium text-cyan-200 rounded-md border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 hover:text-cyan-100 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 disabled:opacity-50 transition-all duration-200"
        :title="loading ? '刷新中…' : '刷新数据'"
      >
        <el-icon v-if="loading" class="text-lg is-loading"><Loading /></el-icon>
        <el-icon v-else class="text-lg"><Refresh /></el-icon>
      </button>
    </div>

    <!-- 数据库筛选 -->
    <div class="mb-6 group rounded-xl border border-cyan-500/15 bg-cyan-500/5 p-3">
      <label class="text-cyan-300 text-xs font-medium mb-2 block uppercase tracking-wider">数据库</label>
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
      <label class="text-gray-400 text-xs font-medium mb-2 block uppercase tracking-wider group-focus-within:text-cyan-400 transition-colors">搜索节点</label>
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
      <label class="text-gray-400 text-xs font-medium mb-2 block uppercase tracking-wider group-focus-within:text-cyan-400 transition-colors">节点分类</label>
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
        <label class="text-gray-400 text-xs font-medium uppercase tracking-wider">图谱加载上限</label>
        <span class="text-cyan-400 text-xs font-mono bg-cyan-500/10 px-2 py-0.5 rounded">{{ localState.graphLimit }}</span>
      </div>
      <input
        v-model.number="localState.graphLimit"
        type="range"
        min="100"
        max="5000"
        step="100"
        class="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
      />
      <p class="mt-2 text-xs text-gray-500">建议 500~2000，过大可能导致 3D 渲染卡顿</p>
    </div>

    <!-- 显示选项 -->
    <div class="mb-6 p-4 bg-gray-800/30 rounded-xl border border-gray-700/30">
      <h3 class="text-gray-400 text-xs font-medium mb-3 uppercase tracking-wider">显示选项</h3>
      <div class="space-y-3">
        <label class="flex items-center justify-between text-gray-300 text-sm cursor-pointer group">
          <span class="group-hover:text-white transition-colors">显示标签</span>
          <div class="relative inline-flex items-center cursor-pointer">
            <input v-model="localState.showLabels" type="checkbox" class="sr-only peer">
            <div class="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-600"></div>
          </div>
        </label>

        <label class="flex items-center justify-between text-gray-300 text-sm cursor-pointer group">
          <span class="group-hover:text-white transition-colors">显示连接</span>
          <div class="relative inline-flex items-center cursor-pointer">
            <input v-model="localState.showEdges" type="checkbox" class="sr-only peer">
            <div class="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-600"></div>
          </div>
        </label>

        <!-- <label class="flex items-center justify-between text-gray-300 text-sm cursor-pointer group">
          <span class="group-hover:text-white transition-colors">自动旋转</span>
          <div class="relative inline-flex items-center cursor-pointer">
            <input v-model="localState.autoRotate" type="checkbox" class="sr-only peer">
            <div class="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-600"></div>
          </div>
        </label> -->
      </div>
    </div>

    <!-- 节点大小 -->
    <div class="mb-6">
      <div class="flex justify-between items-center mb-3">
        <label class="text-gray-400 text-xs font-medium uppercase tracking-wider">节点大小</label>
        <span class="text-cyan-400 text-xs font-mono bg-cyan-500/10 px-2 py-0.5 rounded">{{ localState.nodeSize.toFixed(1) }}x</span>
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
    <div class="mb-6 p-4 bg-gradient-to-br from-gray-800/50 to-gray-900/50 rounded-xl border border-gray-700/50">
      <div class="flex items-center gap-2 mb-3">
        <el-icon class="text-cyan-400"><Connection /></el-icon>
        <p class="text-gray-300 text-sm font-medium">图谱统计</p>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div class="bg-gray-800/50 p-2 rounded border border-gray-700/30">
          <div class="text-gray-500 text-xs mb-1">节点总数</div>
          <div class="text-cyan-400 font-mono text-lg leading-none">--</div>
        </div>
        <div class="bg-gray-800/50 p-2 rounded border border-gray-700/30">
          <div class="text-gray-500 text-xs mb-1">关系总数</div>
          <div class="text-purple-400 font-mono text-lg leading-none">--</div>
        </div>
      </div>
    </div>

    <!-- 按钮 -->
    <div class="mt-auto pt-4 border-t border-gray-700/50">
      <button
        @click="handleReset"
        class="w-full px-4 py-2.5 text-sm font-medium text-white bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors flex items-center justify-center gap-2"
      >
        <el-icon><RefreshLeft /></el-icon>
        重置视图
      </button>
    </div>

  </div>
</template>

<style scoped>
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
  background: rgba(31, 41, 55, 0.5);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 0.5rem;
  box-shadow: none;
  color: #f3f4f6;
}

.style-select :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(6, 182, 212, 0.5);
  box-shadow: 0 0 0 1px rgba(6, 182, 212, 0.5);
}

.style-select :deep(.el-input__inner) {
  color: inherit;
  font-size: 0.875rem;
}

.style-select-dropdown {
  background: #1f2937 !important;
  border: 1px solid #374151 !important;
}

.style-select-dropdown .el-select-dropdown__item {
  color: #d1d5db;
}

.style-select-dropdown .el-select-dropdown__item.hover,
.style-select-dropdown .el-select-dropdown__item.selected {
  background: #374151;
  color: #fff;
}
</style>
