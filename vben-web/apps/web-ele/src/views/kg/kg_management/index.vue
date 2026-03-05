<script lang="ts" setup>
import { ref, onMounted, reactive, nextTick, watch, onUnmounted } from 'vue';
import {
  ElMessage,
  ElMessageBox,
  ElSelect,
  ElOption,
  ElButton,
  ElInput,
  ElForm,
  ElFormItem,
  ElTag,
  ElIcon,
} from 'element-plus';
import {
  Document,
  Delete,
  Download,
  Connection,
  Edit,
  Refresh,
  Search,
  Share,
  Brush,
  Plus
} from '@element-plus/icons-vue';
import ForceGraph3D from '3d-force-graph';
import SpriteText from 'three-spritetext';
import {
  getDatabases,
  getCommunities,
  getVisualizeData,
  updateNode,
  updateRelation,
  clearDatabase,
  exportDatabase,
  cleanupAllOrphanedData,
  getChunksVectorStatus,
  deleteNode,
  deleteRelation
} from './api';

// --- State ---
const loading = ref(false);
const graphContainer = ref<HTMLElement | null>(null);
let graphInstance: any = null;

// Filters
const databases = ref<Array<{ label: string; value: string }>>([]);
const communities = ref<Array<number>>([]);
const selectedDatabase = ref('');
const selectedCommunityId = ref<number | undefined>(undefined);

// Selection for Editing
const selectedElement = ref<any>(null); // Node or Link object
const selectedType = ref<'node' | 'link' | null>(null);
const editForm = reactive<{ properties: Record<string, any> }>({ properties: {} });
const isEditing = ref(false);

// Chunk & Vector Status
const chunksStatus = reactive<{
  orphaned_chunks: number;
  vectorized_chunks: number;
  summary: string;
}>({
  orphaned_chunks: 0,
  vectorized_chunks: 0,
  summary: ''
});

// --- Methods ---

const formatTime = (val: any) => {
  if (!val) return '';
  try {
    const date = new Date(val);
    if (isNaN(date.getTime())) return String(val);
    
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    const hour = date.getHours().toString().padStart(2, '0');
    const minute = date.getMinutes().toString().padStart(2, '0');
    
    return `${year}-${month}-${day} ${hour}:${minute}`;
  } catch (e) {
    return String(val);
  }
};

const loadDatabases = async () => {
  try {
    const res = await getDatabases();
    // 兼容不同的响应结构
    const data = res.data || res;
    const dbList = data.data?.databases || data.databases || [];
    
    if (Array.isArray(dbList)) {
      databases.value = dbList.map((db: any) => ({
        label: db.name || db,
        value: db.name || db
      }));
    }
  } catch (error) {
    console.error('Failed to load databases', error);
  }
};

const loadCommunities = async () => {
  if (!selectedDatabase.value) {
    communities.value = [];
    selectedCommunityId.value = undefined;
    return;
  }
  try {
    const res = await getCommunities(undefined, selectedDatabase.value);
    const data = res.data || res;
    const comms = data.data || data || [];
    if (Array.isArray(comms)) {
      communities.value = comms;
    }
  } catch (error) {
    console.error('Failed to load communities', error);
  }
};

const initGraph = async () => {
  if (!graphContainer.value) return;
  
  loading.value = true;
  // Clear selection when reloading graph
  selectedElement.value = null;
  selectedType.value = null;

  try {
    const res = await getVisualizeData(200, undefined, selectedCommunityId.value, selectedDatabase.value || undefined);
    const data = res.data || res;
    const rawData = (data.success || data.nodes) ? (data.data || data) : { nodes: [], edges: [] };
    
    const gData = {
      nodes: rawData.nodes || [],
      links: rawData.edges || []
    };

    if (graphInstance) {
      graphInstance.graphData(gData);
    } else {
      graphInstance = ForceGraph3D()(graphContainer.value)
        .graphData(gData)
        .nodeLabel('label')
        .nodeAutoColorBy('category')
        .linkLabel((link: any) => {
          const props = link.properties || {};
          const desc = props.description || props.desc || '';
          const source = typeof link.source === 'object' ? link.source.label : link.source;
          const target = typeof link.target === 'object' ? link.target.label : link.target;
          
          return `
            <div class="p-2 bg-gray-900/90 rounded border border-gray-700 shadow-xl backdrop-blur-sm text-xs">
              <div class="font-bold text-cyan-400 mb-1">${link.label}</div>
              ${desc ? `<div class="text-gray-300 mb-1 max-w-[200px] whitespace-normal">${desc}</div>` : ''}
              <div class="text-gray-500 mt-1 pt-1 border-t border-gray-700/50 flex items-center gap-1">
                <span class="truncate max-w-[80px]">${source}</span>
                <span>→</span>
                <span class="truncate max-w-[80px]">${target}</span>
              </div>
            </div>
          `;
        })
        .nodeThreeObject((node: any) => {
          const sprite = new SpriteText(node.label);
          sprite.color = node.color;
          sprite.textHeight = 8;
          return sprite;
        })
        .linkDirectionalParticles(2)
        .linkDirectionalParticleSpeed(0.005)
        .backgroundColor('#00000000')
        .width(graphContainer.value.clientWidth)
        .height(graphContainer.value.clientHeight)
        .onNodeClick(handleNodeClick)
        .onLinkClick(handleLinkClick)
        .onBackgroundClick(() => {
          selectedElement.value = null;
          selectedType.value = null;
        });
    }
  } catch (e) {
    console.error("Graph init failed", e);
    ElMessage.error('图谱加载失败');
  } finally {
    loading.value = false;
  }
};

const handleNodeClick = (node: any) => {
  console.log('Node clicked:', node);
  selectedElement.value = node;
  selectedType.value = 'node';
  // Copy properties for editing
  // Ensure properties exists
  editForm.properties = node.properties ? { ...node.properties } : {};
  
  // Focus camera on node
  const distance = 40;
  const distRatio = 1 + distance/Math.hypot(node.x, node.y, node.z);
  graphInstance.cameraPosition(
    { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
    node,
    3000
  );
};

const handleLinkClick = (link: any) => {
  console.log('Link clicked:', link);
  selectedElement.value = link;
  selectedType.value = 'link';
  editForm.properties = link.properties ? { ...link.properties } : {};
};

const handleAddProperty = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入属性名', '添加属性', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /^[a-zA-Z_][a-zA-Z0-9_]*$/,
      inputErrorMessage: '属性名只能包含字母、数字和下划线，且不能以数字开头'
    });
    
    if (value) {
      if (editForm.properties[value] !== undefined) {
        ElMessage.warning('属性已存在');
        return;
      }
      editForm.properties[value] = '';
    }
  } catch (e) {
    // Cancelled
  }
};

const handleSaveEdit = async () => {
  if (!selectedElement.value) return;
  
  const currentId = selectedElement.value.id;
  const currentType = selectedType.value;

  isEditing.value = true;
  try {
    if (selectedType.value === 'node') {
      await updateNode(selectedElement.value.id, editForm.properties);
      ElMessage.success('节点属性已更新');
    } else if (selectedType.value === 'link') {
      await updateRelation(selectedElement.value.id, editForm.properties);
      ElMessage.success('关系属性已更新');
    }

    // Refresh graph to ensure data consistency
    await initGraph();

    // Restore selection
    if (currentId && currentType && graphInstance) {
      const { nodes, links } = graphInstance.graphData();
      let target = null;
      if (currentType === 'node') {
        target = nodes.find((n: any) => n.id === currentId);
      } else {
        target = links.find((l: any) => l.id === currentId);
      }
      
      if (target) {
        selectedElement.value = target;
        selectedType.value = currentType;
        editForm.properties = target.properties ? { ...target.properties } : {};
      }
    }

  } catch (error) {
    ElMessage.error('更新失败');
    console.error(error);
  } finally {
    isEditing.value = false;
  }
};

const handleRefresh = async () => {
  await initGraph();
  ElMessage.success('图谱已刷新');
};

const handleDeleteElement = async () => {
  if (!selectedElement.value) return;
  
  try {
    await ElMessageBox.confirm(
      `确定要删除该${selectedType.value === 'node' ? '节点' : '关系'}吗？`,
      '警告',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );
    
    loading.value = true;
    if (selectedType.value === 'node') {
      await deleteNode(selectedElement.value.id);
      ElMessage.success('节点已删除');
    } else {
      await deleteRelation(selectedElement.value.id);
      ElMessage.success('关系已删除');
    }
    
    // Refresh graph
    await initGraph();
    
    selectedElement.value = null;
    selectedType.value = null;
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败');
      console.error(error);
    }
  } finally {
    loading.value = false;
  }
};

const handleDeleteDoc = async () => {
  if (!selectedDatabase.value) return;

  try {
    await ElMessageBox.confirm(
      `确定要清空数据库 ${selectedDatabase.value} 吗？该数据库内所有节点与关系将被删除。`,
      '高风险操作确认',
      {
        confirmButtonText: '确定清空',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );

    loading.value = true;
    const res = await clearDatabase(selectedDatabase.value);
    const data = res.data || res;

    if (data.success) {
      const d = data.data || {};
      ElMessage.success(`清空成功：删除节点 ${d.deleted_nodes || 0}，删除关系 ${d.deleted_edges || 0}`);
      selectedCommunityId.value = undefined;
      communities.value = [];
      await initGraph();
    } else {
      throw new Error(data.error || '清空失败');
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清空数据库失败');
      console.error(error);
    }
  } finally {
    loading.value = false;
  }
};

const handleExportDoc = async () => {
  if (!selectedDatabase.value) return;

  try {
    loading.value = true;
    const res = await exportDatabase(selectedDatabase.value);
    const data = res.data || res;

    if (data.success) {
      const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `graph_export_db_${selectedDatabase.value}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      ElMessage.success('数据库导出成功');
    } else {
      throw new Error(data.error || '导出失败');
    }
  } catch (error) {
    ElMessage.error('数据库导出失败');
    console.error(error);
  } finally {
    loading.value = false;
  }
};

const handleCleanupVectors = async () => {
  try {
    if (!selectedDatabase.value) {
      ElMessage.warning('请先选择数据库');
      return;
    }

    await ElMessageBox.confirm(
      '确定要清理孤立数据吗？这将删除所有没有对应关联的向量和Chunk节点。',
      '清理确认',
      {
        confirmButtonText: '确定清理',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );
    
    loading.value = true;
    const res = await cleanupAllOrphanedData(selectedDatabase.value);
    const data = res.data || res;
    
    if (data.success) {
      const stats = data.data || {};
      const messages = [];
      
      if (stats.vectors?.deleted > 0) {
        messages.push(`删除了 ${stats.vectors.deleted} 个孤立向量`);
      }
      if (stats.chunks?.deleted > 0) {
        messages.push(`删除了 ${stats.chunks.deleted} 个孤立Chunk`);
        if (stats.chunks.mentions > 0) {
          messages.push(`${stats.chunks.mentions} 个MENTIONS关系`);
        }
        if (stats.chunks.contains > 0) {
          messages.push(`${stats.chunks.contains} 个CONTAINS关系`);
        }
      }
      
      const msgText = messages.length > 0 
        ? messages.join(', ') 
        : '未发现需要清理的数据';
      
      ElMessage.success(`清理完成: ${msgText}`);
      // 刷新状态
      await loadChunksStatus();
      await initGraph();
    } else {
      throw new Error(data.error || '清理失败');
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清理操作失败');
      console.error(error);
    }
  } finally {
    loading.value = false;
  }
};

const loadChunksStatus = async () => {
  try {
    if (!selectedDatabase.value) {
      chunksStatus.orphaned_chunks = 0;
      chunksStatus.vectorized_chunks = 0;
      chunksStatus.summary = '';
      return;
    }

    const res = await getChunksVectorStatus(selectedDatabase.value);
    const data = res.data || res;
    
    if (data.success) {
      const status = data.data || {};
      chunksStatus.orphaned_chunks = status.orphaned_chunks || 0;
      chunksStatus.vectorized_chunks = status.vectorized_chunks || 0;
      chunksStatus.summary = status.summary || '';
    }
  } catch (error) {
    console.error('Failed to load chunks status:', error);
  }
};


const handleResize = () => {
  if (graphInstance && graphContainer.value) {
    graphInstance.width(graphContainer.value.clientWidth);
    graphInstance.height(graphContainer.value.clientHeight);
  }
};

// Watchers
watch(selectedDatabase, async (newVal) => {
  selectedCommunityId.value = undefined;
  if (newVal) {
    await loadCommunities();
    await loadChunksStatus();
  } else {
    communities.value = [];
    chunksStatus.orphaned_chunks = 0;
    chunksStatus.vectorized_chunks = 0;
    chunksStatus.summary = '';
  }
  initGraph();
});

watch(selectedCommunityId, () => {
  initGraph();
});

// Lifecycle
onMounted(() => {
  loadDatabases();
  loadChunksStatus();
  nextTick(() => {
    initGraph();
  });
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  if (graphInstance) {
    graphInstance._destructor && graphInstance._destructor();
  }
});
</script>

<template>
  <div class="h-[calc(100vh-80px)] w-full flex bg-[#050505] text-gray-200 overflow-hidden font-sans">
    <!-- 左侧控制面板 -->
    <div class="w-[380px] flex-none flex flex-col border-r border-gray-800 bg-[#0f1115] shadow-2xl z-20">
      <!-- 标题栏 -->
      <div class="flex-none p-5 border-b border-gray-800 bg-gradient-to-r from-gray-900 to-gray-800">
        <h2 class="text-lg font-bold flex items-center gap-3 text-white tracking-wide">
          <div class="p-2 bg-cyan-500/20 rounded-lg backdrop-blur-sm">
            <el-icon class="text-cyan-400 text-xl"><Share /></el-icon>
          </div>
          <span>知识图谱管理</span>
        </h2>
      </div>

      <!-- 内容区域 -->
      <div class="flex-1 flex flex-col p-5 space-y-6 overflow-hidden">
        
        <!-- 筛选区域 -->
        <div class="flex-none bg-gray-800/40 rounded-xl p-4 border border-gray-700/50 backdrop-blur-sm">
          <div class="flex items-center gap-2 mb-4">
            <div class="w-1 h-4 bg-cyan-500 rounded-full shadow-[0_0_8px_rgba(6,182,212,0.5)]"></div>
            <h3 class="text-sm font-bold text-gray-300">数据筛选</h3>
          </div>
          
          <div class="space-y-4">
            <div class="space-y-1.5">
              <label class="text-xs font-medium text-gray-500 ml-1">选择数据库</label>
              <el-select
                v-model="selectedDatabase"
                placeholder="请选择数据库..."
                class="w-full custom-select"
                clearable
                filterable
                size="large"
              >
                <template #prefix><el-icon class="text-gray-400"><Document /></el-icon></template>
                <el-option
                  v-for="db in databases"
                  :key="db.value"
                  :label="db.label"
                  :value="db.value"
                />
              </el-select>
            </div>

            <div class="space-y-1.5" :class="{ 'opacity-50 pointer-events-none': !selectedDatabase }">
              <label class="text-xs font-medium text-gray-500 ml-1">社区聚类</label>
              <el-select
                v-model="selectedCommunityId"
                placeholder="选择社区 (Cluster)"
                class="w-full custom-select"
                clearable
                size="large"
              >
                <template #prefix><el-icon class="text-gray-400"><Connection /></el-icon></template>
                <el-option
                  v-for="cId in communities"
                  :key="cId"
                  :label="`Community ${cId}`"
                  :value="cId"
                />
              </el-select>
            </div>
          </div>
        </div>

        <!-- 文档操作区域 -->
        <div class="flex-none bg-gray-800/40 rounded-xl p-4 border border-gray-700/50 backdrop-blur-sm transition-all duration-300">
          <div class="flex items-center gap-2 mb-4">
            <div class="w-1 h-4 bg-purple-500 rounded-full shadow-[0_0_8px_rgba(168,85,247,0.5)]"></div>
            <h3 class="text-sm font-bold text-gray-300">批量操作</h3>
          </div>
          
          <div class="grid grid-cols-2 gap-3">
            <el-button 
              type="primary" 
              plain 
              :icon="Download" 
              class="!w-full !h-10 !rounded-lg !border-gray-600 hover:!border-primary hover:!bg-primary/10" 
              @click="handleExportDoc"
              :loading="loading"
              :disabled="!selectedDatabase"
            >
              导出数据库
            </el-button>
            <el-button 
              type="danger" 
              plain 
              :icon="Delete" 
              class="!w-full !h-10 !rounded-lg !border-gray-600 hover:!border-danger hover:!bg-danger/10" 
              @click="handleDeleteDoc"
              :loading="loading"
              :disabled="!selectedDatabase"
            >
              清空数据库
            </el-button>
            <el-button 
              type="warning" 
              plain 
              :icon="Brush" 
              class="!w-full !h-10 !rounded-lg !border-gray-600 hover:!border-warning hover:!bg-warning/10" 
              @click="handleCleanupVectors"
              :loading="loading"
            >
              清理孤立数据
            </el-button>

            <el-button 
              type="info" 
              plain 
              :icon="Refresh" 
              class="!w-full !h-10 !rounded-lg !border-gray-600 hover:!border-info hover:!bg-info/10" 
              @click="handleRefresh"
              :loading="loading"
            >
              刷新图谱
            </el-button>
          </div>
        </div>

        <!-- 编辑区域 (Flex-1 to fill remaining space) -->
        <div class="flex-1 flex flex-col bg-gray-800/40 rounded-xl p-4 border border-gray-700/50 backdrop-blur-sm overflow-hidden">
          <div class="flex-none flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <div class="w-1 h-4 bg-orange-500 rounded-full shadow-[0_0_8px_rgba(249,115,22,0.5)]"></div>
              <h3 class="text-sm font-bold text-gray-300">编辑</h3>
            </div>
            <el-tag 
              v-if="selectedElement" 
              size="small" 
              effect="dark" 
              class="!bg-gray-900 !border-gray-700 font-mono"
            >
   
            </el-tag>
          </div>

          <div v-if="selectedElement" class="flex-1 flex flex-col overflow-hidden">
            <div class="flex-none mb-3 flex items-center gap-2 text-xs text-cyan-400 bg-cyan-950/30 p-2 rounded border border-cyan-900/50">
              <el-icon><Edit /></el-icon>
              <span>正在编辑: {{ selectedType === 'node' ? '节点' : '关系' }}</span>
            </div>

            <!-- Basic Info Section -->
            <div class="mb-4 p-3 bg-gray-900/50 rounded-lg border border-gray-700/50 space-y-2 flex-none">
               <div class="text-xs text-gray-500 uppercase font-bold">基本信息</div>
               <div class="flex items-center justify-between text-sm">
                 <span class="text-gray-400">ID:</span>
                 <span class="font-mono text-gray-200 truncate max-w-[180px]" :title="selectedElement.id">{{ selectedElement.id }}</span>
               </div>
               <div class="flex items-center justify-between text-sm">
                 <span class="text-gray-400">Label:</span>
                 <span class="text-cyan-400 font-medium">{{ selectedElement.label }}</span>
               </div>
            </div>

            <div class="flex-none mb-2 px-1 flex justify-between items-center">
              <span class="text-xs font-bold text-gray-400 uppercase">属性列表</span>
              <el-button size="small" text bg @click="handleAddProperty">
                <el-icon class="mr-1"><Plus /></el-icon> 添加
              </el-button>
            </div>

            <el-form :model="editForm" label-position="top" size="default" class="custom-form flex-1 flex flex-col overflow-hidden">
              <div class="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-3">
                <div v-for="(value, key) in editForm.properties" :key="key">
                  <el-form-item :label="key" class="!mb-0">
                    <!-- 类型选择框 -->
                    <el-select
                      v-if="key === 'type'"
                      v-model="editForm.properties[key]"
                      filterable
                      allow-create
                      default-first-option
                      placeholder="选择类型"
                      class="w-full"
                    >
                      <el-option label="人物 (PERSON)" value="PERSON" />
                      <el-option label="组织 (ORGANIZATION)" value="ORGANIZATION" />
                      <el-option label="地点 (LOCATION)" value="LOCATION" />
                      <el-option label="物品 (ITEM)" value="ITEM" />
                      <el-option label="技能 (SKILL)" value="SKILL" />
                      <el-option label="事件 (EVENT)" value="EVENT" />
                      <el-option label="概念 (CONCEPT)" value="CONCEPT" />
                      <el-option label="未知 (UNKNOWN)" value="UNKNOWN" />
                    </el-select>

                    <!-- 只读字段 -->
                    <el-input 
                      v-else-if="['created_at', 'doc_id', 'vec_id', 'element_id'].includes(key)" 
                      :model-value="key === 'created_at' ? formatTime(editForm.properties[key]) : editForm.properties[key]" 
                      disabled 
                      class="!opacity-60"
                    />

                    <!-- 普通文本输入 -->
                    <el-input v-else v-model="editForm.properties[key]" />
                  </el-form-item>
                </div>
                
                <div v-if="Object.keys(editForm.properties).length === 0" class="text-gray-500 text-xs text-center py-8 bg-gray-900/50 rounded-lg border border-dashed border-gray-700">
                  该元素没有可编辑的属性
                </div>
              </div>
              
              <div class="flex-none mt-4 pt-2 border-t border-gray-700/30 flex gap-3">
                <el-button 
                  type="primary" 
                  class="flex-1 !h-10 !rounded-lg !font-medium shadow-lg shadow-primary/20" 
                  @click="handleSaveEdit" 
                  :loading="isEditing"
                  :disabled="Object.keys(editForm.properties).length === 0"
                >
                  保存修改
                </el-button>
                <el-button 
                  type="danger" 
                  plain
                  class="!w-10 !h-10 !rounded-lg !px-0" 
                  @click="handleDeleteElement" 
                  :loading="isEditing"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </el-form>
          </div>
          
          <div v-else class="flex-1 flex flex-col items-center justify-center text-gray-500 text-sm py-8 opacity-60">
            <div class="w-16 h-16 rounded-full bg-gray-800/50 flex items-center justify-center mb-3 border border-gray-700/50">
              <el-icon class="text-2xl text-gray-400"><Connection /></el-icon>
            </div>
            <p class="font-medium">点击图谱元素</p>
            <p class="text-xs mt-1 text-gray-600">在右侧视图中选择节点或连线进行编辑</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧图谱区域 -->
    <div class="flex-1 relative bg-[#050505]">
      <div ref="graphContainer" class="w-full h-full"></div>
      
      <div v-if="loading" class="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm z-10">
        <div class="flex flex-col items-center bg-gray-900 p-6 rounded-xl border border-gray-800 shadow-2xl">
          <div class="loading-spinner mb-4"></div>
          <span class="text-cyan-400 font-medium tracking-wider">正在构建图谱...</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Custom Scrollbar */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(75, 85, 99, 0.5);
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: rgba(107, 114, 128, 0.8);
}

/* Loading Spinner */
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(6, 182, 212, 0.3);
  border-radius: 50%;
  border-top-color: #06b6d4;
  animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Element Plus Overrides */
.custom-select :deep(.el-input__wrapper) {
  background-color: rgba(17, 24, 39, 0.8);
  box-shadow: none !important;
  border: 1px solid rgba(75, 85, 99, 0.4);
  transition: all 0.3s;
}
.custom-select :deep(.el-input__wrapper:hover) {
  border-color: rgba(107, 114, 128, 0.8);
  background-color: rgba(31, 41, 55, 0.8);
}
.custom-select :deep(.el-input__wrapper.is-focus) {
  border-color: #06b6d4;
  background-color: rgba(31, 41, 55, 1);
  box-shadow: 0 0 0 1px #06b6d4 !important;
}
.custom-select :deep(.el-input__inner) {
  color: #e5e7eb;
  font-weight: 500;
}

.custom-form :deep(.el-form-item__label) {
  color: #9ca3af;
  font-size: 0.75rem;
  padding-bottom: 4px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.custom-form :deep(.el-input__wrapper) {
  background-color: rgba(17, 24, 39, 0.6);
  box-shadow: none;
  border: 1px solid rgba(75, 85, 99, 0.4);
  border-radius: 6px;
}
.custom-form :deep(.el-input__wrapper.is-focus) {
  border-color: #06b6d4;
  background-color: rgba(17, 24, 39, 0.9);
}
.custom-form :deep(.el-input__inner) {
  color: #e5e7eb;
}
</style>
