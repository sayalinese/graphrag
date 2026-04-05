<script lang="ts" setup>
import { onMounted, ref } from 'vue'
import { 
  ElCard, ElButton, ElMessage, ElDialog, 
  ElTabs, ElTabPane, ElTable, ElTableColumn, ElInput, 
  ElTag, ElSelect, ElOption, ElRow, ElCol, ElIcon, ElSkeleton
} from 'element-plus'
import { 
  Plus, Delete, Edit, Refresh, Connection, 
  Document, DataLine, Link, Odometer 
} from '@element-plus/icons-vue'
import { getNeo4jDatabases } from '../kg_preview/utils/api'

interface DocumentAnalysis {
  doc_id: string
  title: string
  key_nodes: Array<{
    id: string
    name: string
    labels: string[]
    degree: number
  }>
  node_types: Record<string, number>
}

const loading = ref(false)
const docAnalysis = ref<DocumentAnalysis[]>([])
const connectionInfo = ref<any | null>(null)
const selectedDatabase = ref('')
const databaseOptions = ref<Array<{ label: string; value: string }>>([])

// 映射管理相关状态
const showMappingDialog = ref(false)
const mappingLoading = ref(false)
const activeMappingTab = ref('entity')
const mappings = ref({
  entity_types: {} as Record<string, string>,
  relation_types: {} as Record<string, string>
})
const newEntity = ref({ key: '', value: '' })
const newRelation = ref({ key: '', value: '' })

// 预定义的实体类型选项
const entityTypeOptions = [
  'PERSON', 'ORGANIZATION', 'LOCATION', 'PRODUCT', 
  'CONCEPT', 'EVENT', 'DOCUMENT'
]

// 预定义的关系类型选项
const relationTypeOptions = [
  'LOCATED_IN', 'WORKS_FOR', 'OWNS', 'PART_OF', 'KNOWS', 
  'MENTIONS', 'RELATED_TO', 'FOUNDED_BY', 'PARTICIPATES_IN', 
  'PRODUCES', 'FRIEND_OF', 'ENEMY_OF', 'FAMILY_OF', 
  'MASTER_OF', 'STUDENT_OF', 'ALLY_OF', 'RIVAL_OF', 
  'MEMBER_OF', 'LEADER_OF', 'BELONGS_TO', 'HAS_ABILITY', 
  'CREATED_BY'
]

// 获取映射配置
const fetchMappings = async () => {
  try {
    const res = await fetch('/api/kg/mappings')
    const data = await res.json()
    if (data.success) {
      mappings.value = data.data
    }
  } catch (e) {
    console.error('获取映射配置失败', e)
  }
}

// 获取文档分析数据
const fetchDocAnalysis = async () => {
  try {
    loading.value = true
    const params = new URLSearchParams({ limit: '10' })
    if (selectedDatabase.value) params.append('database', selectedDatabase.value)
    const res = await fetch(`/api/kg/documents/analysis?${params}`)
    const data = await res.json()
    if (data.success) {
      docAnalysis.value = data.data
    }
  } catch (e) {
    console.error('获取文档分析失败', e)
  } finally {
    loading.value = false
  }
}

// 加载数据库列表
const fetchDatabases = async () => {
  try {
    const dbs = await getNeo4jDatabases()
    databaseOptions.value = dbs
      .filter(db => db.name.toLowerCase() !== 'system')
      .map(db => ({ label: db.name, value: db.name }))
    if (!selectedDatabase.value && databaseOptions.value.length > 0) {
      selectedDatabase.value = databaseOptions.value[0]!.value
    }
  } catch (e) {
    console.error('获取数据库列表失败', e)
  }
}

const openMappingDialog = () => {
  fetchMappings()
  showMappingDialog.value = true
}

const addEntity = async () => {
  if (!newEntity.value.key || !newEntity.value.value) return
  
  try {
    mappingLoading.value = true
    const res = await fetch('/api/kg/mappings/item', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category: 'entity_type',
        key: newEntity.value.key,
        value: newEntity.value.value
      })
    })
    const data = await res.json()
    if (data.success) {
      mappings.value.entity_types[newEntity.value.key] = newEntity.value.value
      newEntity.value = { key: '', value: '' }
      ElMessage.success('添加成功')
    } else {
      ElMessage.error(data.error || '添加失败')
    }
  } catch (e) {
    ElMessage.error('添加失败')
  } finally {
    mappingLoading.value = false
  }
}

const removeEntity = async (key: string) => {
  try {
    const res = await fetch(`/api/kg/mappings/item?category=entity_type&key=${encodeURIComponent(key)}`, {
      method: 'DELETE'
    })
    const data = await res.json()
    if (data.success) {
      delete mappings.value.entity_types[key]
      ElMessage.success('删除成功')
    } else {
      ElMessage.error(data.error || '删除失败')
    }
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const addRelation = async () => {
  if (!newRelation.value.key || !newRelation.value.value) return
  
  try {
    mappingLoading.value = true
    const res = await fetch('/api/kg/mappings/item', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category: 'relation_type',
        key: newRelation.value.key,
        value: newRelation.value.value
      })
    })
    const data = await res.json()
    if (data.success) {
      mappings.value.relation_types[newRelation.value.key] = newRelation.value.value
      newRelation.value = { key: '', value: '' }
      ElMessage.success('添加成功')
    } else {
      ElMessage.error(data.error || '添加失败')
    }
  } catch (e) {
    ElMessage.error('添加失败')
  } finally {
    mappingLoading.value = false
  }
}

const removeRelation = async (key: string) => {
  try {
    const res = await fetch(`/api/kg/mappings/item?category=relation_type&key=${encodeURIComponent(key)}`, {
      method: 'DELETE'
    })
    const data = await res.json()
    if (data.success) {
      delete mappings.value.relation_types[key]
      ElMessage.success('删除成功')
    } else {
      ElMessage.error(data.error || '删除失败')
    }
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// 辅助函数：获取类别颜色
const getCategoryColor = (category: string): string => {
  const colorMap: Record<string, string> = {
    PERSON: '#1abc9c', // 绿色青
    ORGANIZATION: '#3498db', // 蓝色
    LOCATION: '#9b59b6', // 紫色
    PRODUCT: '#e67e22', // 橙色
    CONCEPT: '#2ecc71', // 绿色
    EVENT: '#f1c40f', // 黄色
    DOCUMENT: '#e74c3c', // 红色
    Chunk: '#607d8b',   // 蓝灰色
    unknown: '#7f8c8d'
  }
  return colorMap[category] ?? '#7f8c8d'
}

// 辅助函数：获取类别中文名
const getCategoryLabel = (category: string): string => {
  const fallbackMap: Record<string, string> = {
    PERSON: '人物',
    ORGANIZATION: '组织机构',
    LOCATION: '地点',
    PRODUCT: '产品',
    CONCEPT: '概念',
    EVENT: '事件',
    DOCUMENT: '文档',
    SKILL: '技能',
    Chunk: '文本分块',
    unknown: '未知类型'
  }
  
  if (mappings.value && mappings.value.entity_types) {
    for (const [cnName, enType] of Object.entries(mappings.value.entity_types)) {
      if (enType === category) return cnName
    }
  }
  
  return fallbackMap[category] || category
}

// 获取连接信息
const fetchConnectionInfo = async () => {
  try {
    const res = await fetch('/api/kg/connection')
    const data = await res.json()
    if (data.success) {
      connectionInfo.value = data.data
    }
  } catch (e) {
    // 静默失败即可
  }
}

// 获取状态指示器颜色
const getStatusColor = (status: string): string => {
  const colorMap: Record<string, string> = {
    'online': '#10b981',
    'offline': '#6b7280',
    'starting': '#f59e0b',
    'stopping': '#f59e0b',
    'stopped': '#6b7280'
  }
  return colorMap[status?.toLowerCase()] || '#9ca3af'
}

const refreshData = () => {
  fetchConnectionInfo()
  fetchDocAnalysis()
}

// 初始化
onMounted(async () => {
  await fetchDatabases()
  refreshData()
  fetchMappings()
})
</script>

<template>
  <div class="p-6 bg-gray-50 min-h-screen dark:bg-gray-900 transition-colors">
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-800 dark:text-white flex items-center gap-2">
          <el-icon class="text-blue-500"><DataLine /></el-icon>
          知识图谱仪表盘
        </h1>
        <p class="text-gray-500 text-sm mt-1 ml-8">实时监控图谱状态与文档知识分布</p>
      </div>
      <div class="flex gap-3 items-center">
         <ElSelect
           v-model="selectedDatabase"
           placeholder="选择数据库"
           size="small"
           class="w-36"
           @change="fetchDocAnalysis"
         >
           <ElOption v-for="db in databaseOptions" :key="db.value" :label="db.label" :value="db.value" />
         </ElSelect>
         <el-button :icon="Refresh" circle @click="refreshData" />
         <el-button type="primary" :icon="Edit" @click="openMappingDialog">映射管理</el-button>
      </div>
    </div>

    <!-- Main Content -->
    <el-row :gutter="20">
      <!-- Left: Document Analysis List -->
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" class="border-none mb-4 bg-white dark:bg-gray-800">
          <template #header>
            <div class="flex justify-between items-center">
              <span class="font-bold text-lg flex items-center gap-2">
                <el-icon><Odometer /></el-icon> 文档知识洞察
              </span>
              <el-tag type="info" effect="plain" round>{{ docAnalysis.length }} 篇</el-tag>
            </div>
          </template>
          
          <!-- List of Docs -->
          <div v-if="docAnalysis.length > 0" class="space-y-4">
             <div v-for="doc in docAnalysis" :key="doc.doc_id" 
                  class="p-4 rounded-lg border border-gray-100 hover:border-blue-200 hover:shadow-sm transition-all bg-gray-50 dark:bg-gray-700/50 dark:border-gray-700">
                <div class="flex justify-between items-start mb-3">
                  <div>
                    <div class="font-bold text-gray-800 dark:text-gray-100 text-lg">{{ doc.title }}</div>
                    <div class="text-xs text-gray-400 font-mono mt-1">ID: {{ doc.doc_id }}</div>
                  </div>
                </div>
                
                <el-row :gutter="20">
                  <!-- Key Nodes -->
                  <el-col :span="12">
                    <div class="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wider">关键实体 (Top 5)</div>
                    <div class="flex flex-wrap gap-2">
                      <el-tag 
                        v-for="node in doc.key_nodes" 
                        :key="node.id" 
                        size="small" 
                        effect="light"
                        :color="getCategoryColor(node.labels[0]) + '20'"
                        :style="{ color: getCategoryColor(node.labels[0]), borderColor: getCategoryColor(node.labels[0]) + '40' }"
                        class="border"
                      >
                        {{ node.name }} <span class="opacity-60 ml-1 text-xs">({{ node.degree }})</span>
                      </el-tag>
                      <span v-if="doc.key_nodes.length === 0" class="text-xs text-gray-400 italic">暂无关键实体</span>
                    </div>
                  </el-col>
                  
                  <!-- Type Distribution -->
                  <el-col :span="12">
                    <div class="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wider">类型分布</div>
                    <div class="flex flex-wrap gap-x-4 gap-y-2">
                      <div v-for="(count, type) in doc.node_types" :key="type" class="flex items-center gap-1.5">
                        <span class="w-2 h-2 rounded-full" :style="{ background: getCategoryColor(type) }"></span>
                        <span class="text-xs text-gray-600 dark:text-gray-300">{{ getCategoryLabel(type) }}</span>
                        <span class="text-xs font-bold text-gray-400 bg-gray-100 dark:bg-gray-600 px-1 rounded">{{ count }}</span>
                      </div>
                      <span v-if="Object.keys(doc.node_types).length === 0" class="text-xs text-gray-400 italic">暂无类型数据</span>
                    </div>
                  </el-col>
                </el-row>
             </div>
          </div>
          <el-skeleton v-else-if="loading" :rows="5" animated />
          <div v-else class="text-center py-10 text-gray-400">
            <el-icon class="text-4xl mb-2"><Document /></el-icon>
            <p>暂无文档分析数据</p>
          </div>
        </el-card>
      </el-col>

      <!-- Right: System Info -->
      <el-col :xs="24" :lg="8">
         <!-- Connection Details -->
         <el-card shadow="never" class="mb-4 border-none bg-white dark:bg-gray-800">
            <template #header>
              <div class="font-bold flex items-center gap-2">
                <el-icon><Link /></el-icon> 连接详情
              </div>
            </template>
            <div class="space-y-3 text-sm">
               <div class="flex justify-between py-2 border-b border-gray-100 dark:border-gray-700">
                <span class="text-gray-500">状态</span>
                <div class="flex items-center gap-2">
                  <span class="w-2 h-2 rounded-full" :style="{ background: getStatusColor(connectionInfo?.databases?.[0]?.currentStatus || 'offline') }"></span>
                  <span class="font-mono">{{ connectionInfo?.databases?.[0]?.currentStatus || 'Unknown' }}</span>
                </div>
              </div>
              <div class="flex justify-between py-2 border-b border-gray-100 dark:border-gray-700">
                <span class="text-gray-500">版本</span>
                <span class="font-mono">{{ connectionInfo?.version || '-' }}</span>
              </div>
              <div class="flex justify-between py-2 border-b border-gray-100 dark:border-gray-700">
                <span class="text-gray-500">版本类型</span>
                <span class="font-mono">{{ connectionInfo?.edition || '-' }}</span>
              </div>
              <div class="flex justify-between py-2 border-b border-gray-100 dark:border-gray-700">
                <span class="text-gray-500">数据库名</span>
                <span class="font-mono">{{ connectionInfo?.databases?.[0]?.name || '-' }}</span>
              </div>
              <div class="flex justify-between py-2">
                <span class="text-gray-500">地址</span>
                <span class="font-mono text-xs">{{ connectionInfo?.databases?.[0]?.address || '-' }}</span>
              </div>
            </div>
         </el-card>
      </el-col>
    </el-row>

    <!-- 映射管理对话框 -->
    <el-dialog
      v-model="showMappingDialog"
      title="知识图谱映射管理"
      width="800px"
      destroy-on-close
    >
      <div class="mb-4 text-gray-500 text-sm">
        配置 LLM 提取的中文实体/关系类型到 Neo4j 英文类型的映射规则。
      </div>
      
      <el-tabs v-model="activeMappingTab">
        <!-- 实体映射 Tab -->
        <el-tab-pane label="实体类型映射" name="entity">
          <div class="flex gap-2 mb-4">
            <el-input v-model="newEntity.key" placeholder="中文名称 (如: 角色)" style="width: 200px" />
            <el-select v-model="newEntity.value" placeholder="对应实体类型" style="width: 200px" filterable allow-create>
              <el-option v-for="opt in entityTypeOptions" :key="opt" :label="opt" :value="opt" />
            </el-select>
            <el-button type="primary" :icon="Plus" @click="addEntity">添加规则</el-button>
          </div>
          
          <el-table :data="Object.entries(mappings.entity_types).map(([k,v]) => ({key: k, value: v}))" height="400" border stripe>
            <el-table-column prop="key" label="中文名称" />
            <el-table-column prop="value" label="Neo4j 类型">
              <template #default="{ row }">
                <el-tag>{{ row.value }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center">
              <template #default="{ row }">
                <el-button type="danger" link :icon="Delete" @click="removeEntity(row.key)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 关系映射 Tab -->
        <el-tab-pane label="关系类型映射" name="relation">
          <div class="flex gap-2 mb-4">
            <el-input v-model="newRelation.key" placeholder="中文关系 (如: 朋友)" style="width: 200px" />
            <el-select v-model="newRelation.value" placeholder="对应关系类型" style="width: 200px" filterable allow-create>
              <el-option v-for="opt in relationTypeOptions" :key="opt" :label="opt" :value="opt" />
            </el-select>
            <el-button type="primary" :icon="Plus" @click="addRelation">添加规则</el-button>
          </div>
          
          <el-table :data="Object.entries(mappings.relation_types).map(([k,v]) => ({key: k, value: v}))" height="400" border stripe>
            <el-table-column prop="key" label="中文关系" />
            <el-table-column prop="value" label="Neo4j 类型">
              <template #default="{ row }">
                <el-tag type="success">{{ row.value }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center">
              <template #default="{ row }">
                <el-button type="danger" link :icon="Delete" @click="removeRelation(row.key)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showMappingDialog = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 移除旧的样式，使用 Tailwind 类 */
</style>
