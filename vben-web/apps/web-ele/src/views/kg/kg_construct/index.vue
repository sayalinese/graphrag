<script lang="ts" setup>
import { ref, onMounted, reactive, nextTick, onUnmounted, watch } from 'vue';
import {
  ElMessage,
  ElNotification,
  ElSteps,
  ElStep,
  ElButton,
  ElInput,
  ElUpload,
  ElSlider,
  ElIcon,
  ElSelect,
  ElOption,
  type UploadFile
} from 'element-plus';
import ForceGraph3D from '3d-force-graph';
import SpriteText from 'three-spritetext';
import {
  uploadDocument,
  detectCommunities,
  generateCommunityReports,
  getGraphStats,
  getVisualizeData,
  clearDatabase,
  checkDatabaseIntegrity,
  repairDatabaseIntegrity,
} from './api';
import { baseRequestClient } from '#/api/request';
import {
  Document,
  FolderOpened,
  VideoPlay,
  Monitor,
  List,
  RefreshRight,
  Cpu,
  Connection
} from '@element-plus/icons-vue';

// --- State ---
const loading = ref(false);
const repairing = ref(false);
const activeTab = ref('text'); // text | file
const activeView = ref('graph'); // graph | logs
const graphContainer = ref<HTMLElement | null>(null);
let graphInstance: any = null;

const stats = reactive({
  nodes: 0,
  edges: 0,
  communities: 0
});

const form = reactive({
  text: '',
  title: '',
  docId: '',
  chunkSize: 500,
  overlap: 50
});

const uploadedFile = ref<File | null>(null); // 用于存储 Excel/CSV 文件

const steps = ref([
  { title: '数据入库', status: 'wait', description: '文本切片与实体抽取' },
  { title: '社区检测', status: 'wait', description: 'Leiden 算法聚类' },
  { title: '报告生成', status: 'wait', description: '生成社区摘要' }
]);

const activeStep = ref(0);
const logs = ref<string[]>([]);

// 数据库筛选相关状态
const selectedDatabase = ref('');
const databaseOptions = ref<Array<{ label: string; value: string }>>([]);
const loadingDocs = ref(false);
const clearBeforeBuild = ref(false);

const integrity = reactive({
  checked: false,
  vectorMissing: false,
  sourceMissing: false,
  neoMissing: false,
  orphanedChunks: false,
  communityMissing: false,
  counts: {
    neo_nodes: 0,
    neo_edges: 0,
    source_docs: 0,
    source_chunks: 0,
    graph_chunks: 0,
    vectors: 0,
    orphaned_chunks: 0,
    entity_nodes: 0,
    vector_coverage: 1.0,
    communities: 0,
  },
});

// --- Methods ---

const addLog = (msg: string) => {
  const time = new Date().toLocaleTimeString();
  logs.value.unshift(`[${time}] ${msg}`);
};

// 获取数据库列表
const fetchDatabases = async () => {
  loadingDocs.value = true;
  try {
    const res = await baseRequestClient.get<any>('/kg/databases');
    const result = res.data as any;
    if (result?.success && Array.isArray(result.data?.databases)) {
      const availableDatabases = result.data.databases.filter((db: any) => {
        const name = String(db?.name || db || '').trim().toLowerCase();
        return Boolean(name) && name !== 'system';
      });

      databaseOptions.value = availableDatabases.map((db: any) => ({
          label: db.name || db,
          value: db.name || db,
        }));

      if (!selectedDatabase.value && databaseOptions.value.length > 0) {
        const defaultDb = availableDatabases.find((db: any) => Boolean(db?.default));
        selectedDatabase.value = (defaultDb?.name || defaultDb) || databaseOptions.value[0].value;
      }
    }
  } catch (error) {
    console.warn('获取数据库列表失败:', error);
  } finally {
    loadingDocs.value = false;
  }
};

const refreshStats = async (database?: string) => {
  try {
    const res = await getGraphStats(database);
    const data = res.data || res;
    if (data.success && data.data) {
      stats.nodes = data.data.nodes || 0;
      stats.edges = data.data.edges || 0;
      stats.communities = data.data.communities || 0;
    }
  } catch (error) {
    console.error(error);
  }
};

const checkIntegrity = async () => {
  if (!selectedDatabase.value) {
    ElMessage.warning('请先选择数据库');
    return;
  }
  try {
    const res = await checkDatabaseIntegrity(selectedDatabase.value);
    const data = res.data || res;
    const payload = data.data || {};
    const status = payload.status || {};
    integrity.checked = true;
    integrity.vectorMissing = Boolean(status.vector_missing);
    integrity.sourceMissing = Boolean(status.source_missing);
    integrity.neoMissing = Boolean(status.neo_missing);
    integrity.orphanedChunks = Boolean(status.orphaned_chunks);
    integrity.communityMissing = Boolean(status.community_missing);
    integrity.counts = {
      neo_nodes: payload.counts?.neo_nodes || 0,
      neo_edges: payload.counts?.neo_edges || 0,
      source_docs: payload.counts?.source_docs || 0,
      source_chunks: payload.counts?.source_chunks || 0,
      graph_chunks: payload.counts?.graph_chunks || 0,
      vectors: payload.counts?.vectors || 0,
      orphaned_chunks: payload.counts?.orphaned_chunks || 0,
      entity_nodes: payload.counts?.entity_nodes || 0,
      vector_coverage: payload.counts?.vector_coverage ?? 1.0,
      communities: payload.counts?.communities || 0,
    };
  } catch (error) {
    ElMessage.error('完整性检测失败');
    console.error(error);
  }
};

const repairIntegrity = async () => {
  if (!selectedDatabase.value) {
    ElMessage.warning('请先选择数据库');
    return;
  }
  repairing.value = true;
  try {
    if (!integrity.checked) {
      await checkIntegrity();
    }

    const targets: string[] = [];
    if (integrity.vectorMissing) targets.push('vector');
    if (integrity.neoMissing) targets.push('neo4j');
    if (integrity.sourceMissing && !targets.includes('neo4j')) targets.push('neo4j');
    if (!targets.length && !integrity.communityMissing) {
      // 全部指标健康，无需修复
      ElMessage.success('数据库生命周期完整，无需修复');
      repairing.value = false;
      return;
    }
    // 先执行向量/Neo4j修复
    if (targets.length > 0) {
      const res = await repairDatabaseIntegrity(selectedDatabase.value, targets);
      const data = res.data || res;
      if (!data.success) throw new Error(data.error || '修复失败');
      const repairedDb = data.data?.database || selectedDatabase.value;
      addLog(`修复完成（目标库：${repairedDb}）`);
    }
    // 社区划分修复
    if (integrity.communityMissing) {
      addLog('社区划分缺失，开始执行 Leiden 社区检测...');
      const cRes = await detectCommunities(true, selectedDatabase.value);
      const cData = cRes.data || cRes;
      if (cData.success) {
        const cd = cData.data || {};
        addLog(`社区检测完成：共 ${cd.total_communities ?? 0} 个社区，模式=${cd.mode_used ?? 'auto'}，模块度=${(cd.modularity ?? 0).toFixed(4)}`);
      } else {
        addLog(`社区检测失败: ${cData.error || '未知错误'}`);
      }
    }
    ElMessage.success(`自动修复任务已执行（目标库：${selectedDatabase.value}）`);
    await checkIntegrity();
    await initGraph();
  } catch (error) {
    ElMessage.error('自动修复失败');
    console.error(error);
  } finally {
    repairing.value = false;
  }
};

const handleClearDatabase = async () => {
  if (!selectedDatabase.value) {
    ElMessage.warning('请先选择数据库');
    return;
  }
  await clearDatabase(selectedDatabase.value);
  await initGraph();
  await checkIntegrity();
};

const initGraph = async () => {
  if (!graphContainer.value) return;
  
  // 销毁旧实例（如果存在）
  if (graphInstance) {
    graphInstance._destructor && graphInstance._destructor();
    graphContainer.value.innerHTML = '';
  }

  try {
    // 传入数据库筛选参数
    const res = await getVisualizeData(200, undefined, undefined, selectedDatabase.value || undefined);
    const data = res.data || res;
    const rawData = (data.success ? data.data : null) || { nodes: [], links: [] };
    
    // 确保数据结构符合 3d-force-graph 要求 (需要 links 字段)
    const gData = {
      nodes: rawData.nodes || [],
      links: rawData.links || rawData.edges || []
    };
    graphInstance = ForceGraph3D()(graphContainer.value)
      .graphData(gData)
      .nodeLabel('label')
      .nodeAutoColorBy('category')
      .nodeThreeObject((node: any) => {
        const sprite = new SpriteText(node.label);
        sprite.color = node.color;
        sprite.textHeight = 8;
        return sprite;
      })
      .linkDirectionalParticles(2)
      .linkDirectionalParticles(2)
      .linkDirectionalParticleSpeed(0.005)
      .backgroundColor('#00000000') // 透明背景
      .width(graphContainer.value.clientWidth)
      .height(graphContainer.value.clientHeight);

    // 自适应大小
    window.addEventListener('resize', handleResize);
  } catch (e) {
    console.error("Graph init failed", e);
  }
};

const handleResize = () => {
  if (graphInstance && graphContainer.value) {
    graphInstance.width(graphContainer.value.clientWidth);
    graphInstance.height(graphContainer.value.clientHeight);
  }
};

const handleFileChange = async (file: UploadFile) => {
  if (!file.raw) return;
  
  const fileName = file.name.toLowerCase();
  const isExcel = fileName.endsWith('.xlsx') || fileName.endsWith('.csv');
  
  if (isExcel) {
    // Schema 映射模式: 直接上传二进制文件
    // 只在标题为空时自动填充，否则保留用户输入
    if (!form.title) {
      form.title = file.name;
    }
    uploadedFile.value = file.raw; // 保存文件对象
    ElMessage.success(`已选择表格文件: ${file.name}, 将使用 Schema 映射模式`);
  } else {
    // LLM 抽取模式: 读取文本内容
    const reader = new FileReader();
    reader.onload = (e) => {
      if (e.target?.result) {
        form.text = e.target.result as string;
        // 只在标题为空时自动填充
        if (!form.title) {
          form.title = file.name;
        }
        uploadedFile.value = null; // 清空文件对象
        ElMessage.success(`已读取文件: ${file.name}`);
      }
    };
    reader.readAsText(file.raw);
  }
};

const handleBuild = async () => {
  if (!selectedDatabase.value) {
    ElMessage.warning('请先选择目标数据库');
    return;
  }
  if (!form.text && !uploadedFile.value) {
    ElMessage.warning('请先输入文本或上传文件');
    return;
  }

  if (clearBeforeBuild.value) {
    try {
      await handleClearDatabase();
      addLog('✓ 已按配置清空目标数据库');
    } catch (e) {
      ElMessage.error('清空数据库失败，已终止构建');
      return;
    }
  }
  
  // 判断数据源类型
  const isSchemaMode = !!uploadedFile.value;
  
  if (isSchemaMode) {
    await handleSchemaBuild();
  } else {
    await handleTextBuild();
  }
};

// 原有文本/LLM 流程
const handleTextBuild = async () => {

  loading.value = true;
  activeStep.value = 0;
  steps.value.forEach(s => s.status = 'wait');
  logs.value = [];
  addLog('[文本模式] 开始 LLM 实体抽取流程...');
  addLog('⏳ 此过程可能需要较长时间，请耐心等待...');

  try {
    // 1. 数据入库
    steps.value[0].status = 'process';
    addLog(`正在入库 (Chunk: ${form.chunkSize}, Overlap: ${form.overlap})...`);
    addLog('⏳ 这可能需要 1-5 分钟，请勿关闭页面');
    
    const uploadRes = await uploadDocument(form.text, form.docId, form.title, selectedDatabase.value || undefined);
    // 兼容处理：baseRequestClient 可能返回完整响应对象或直接返回数据
    const uploadData = uploadRes.data || uploadRes;
    
    if (!uploadData.success) {
      throw new Error(uploadData.error || '入库失败');
    }
    
    addLog(`✓ 入库成功: ${JSON.stringify(uploadData.data)}`);
    
    steps.value[0].status = 'success';
    activeStep.value = 1;
    await refreshStats(selectedDatabase.value || undefined);
    await initGraph(); // 刷新图谱

    // 2. 社区检测
    steps.value[1].status = 'process';
    addLog('正在执行社区检测...');
    addLog('⏳ 这可能需要 1-5 分钟，请勿关闭页面');
    const detectRes = await detectCommunities(true, selectedDatabase.value);
    const detectData = detectRes.data || detectRes;
    
    if (!detectData.success) {
      throw new Error(detectData.error || '社区检测失败');
    }
    
    addLog('✓ 社区检测成功');
    steps.value[1].status = 'success';
    activeStep.value = 2;
    await refreshStats(selectedDatabase.value || undefined);

    // 3. 报告生成
    steps.value[2].status = 'process';
    addLog('正在生成社区报告...');
    addLog('⏳ 这可能需要 1-5 分钟，请勿关闭页面');
    const reportRes = await generateCommunityReports(selectedDatabase.value);
    const reportData = reportRes.data || reportRes;
    
    if (!reportData.success) {
      throw new Error(reportData.error || '报告生成失败');
    }
    
    steps.value[2].status = 'success';
    activeStep.value = 3;
    addLog('✓ 构建流程全部完成！');
    
    ElNotification.success({
      title: '构建完成',
      message: '知识图谱已更新',
      duration: 3000
    });

  } catch (error: any) {
    const errorMsg = error.message || '未知错误';
    if (errorMsg.includes('timeout')) {
      addLog(': 请求超时，可能是任务耗时较长');
      ElMessage.error('请求超时 - 任务可能仍在后台处理中，请稍后查看结果');
    } else {
      addLog(`错误: ${errorMsg}`);
      ElMessage.error(`构建失败: ${errorMsg}`);
    }
    steps.value[activeStep.value].status = 'error';
  } finally {
    loading.value = false;
    await refreshStats(selectedDatabase.value || undefined);
  }
};

// 新增: Schema 映射流程 (Excel/CSV)
const handleSchemaBuild = async () => {
  loading.value = true;
  activeStep.value = 0;
  steps.value.forEach(s => s.status = 'wait');
  logs.value = [];
  addLog('[Schema模式] 开始表格数据映射流程...');
  addLog('📊 正在解析 Excel/CSV 结构...');

  try {
    // Step 1: 上传并解析表格,获取 Schema
    steps.value[0].status = 'process';
    addLog('正在上传表格文件并解析列结构...');
    
    const formData = new FormData();
    formData.append('file', uploadedFile.value!);
    if (form.docId) formData.append('doc_id', form.docId);
    if (form.title) formData.append('title', form.title);
    if (selectedDatabase.value) formData.append('database', selectedDatabase.value);
    
    const schemaRes = await baseRequestClient.post('/kg/excel/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000
    });
    
    const schemaData = schemaRes.data || schemaRes;
    if (!schemaData.success) {
      throw new Error(schemaData.error || 'Schema解析失败');
    }
    
    addLog(`✓ Schema解析成功: 共 ${schemaData.data.row_count} 行数据`);
    addLog(`  - 实体列: ${schemaData.data.entity_columns.join(', ')}`);
    addLog(`  - 关系列: ${schemaData.data.relation_columns.join(', ')}`);
    
    steps.value[0].status = 'success';
    activeStep.value = 1;
    await refreshStats(selectedDatabase.value || undefined);
    await initGraph();

    // Step 2: 社区检测 (复用原有逻辑)
    steps.value[1].status = 'process';
    addLog('正在执行社区检测...');
    const detectRes = await detectCommunities(true, selectedDatabase.value);
    const detectData = detectRes.data || detectRes;
    
    if (!detectData.success) {
      throw new Error(detectData.error || '社区检测失败');
    }
    
    addLog('✓ 社区检测成功');
    steps.value[1].status = 'success';
    activeStep.value = 2;
    await refreshStats(selectedDatabase.value || undefined);

    // Step 3: 报告生成 (复用原有逻辑)
    steps.value[2].status = 'process';
    addLog('正在生成社区报告...');
    const reportRes = await generateCommunityReports(selectedDatabase.value);
    const reportData = reportRes.data || reportRes;
    
    if (!reportData.success) {
      throw new Error(reportData.error || '报告生成失败');
    }
    
    steps.value[2].status = 'success';
    activeStep.value = 3;
    addLog('✓ [Schema模式] 构建流程全部完成！');
    
    ElNotification.success({
      title: 'Schema映射完成',
      message: '表格数据已成功导入知识图谱',
      duration: 3000
    });

  } catch (error: any) {
    const errorMsg = error.message || '未知错误';
    addLog(`❌ 错误: ${errorMsg}`);
    ElMessage.error(`Schema映射失败: ${errorMsg}`);
    steps.value[activeStep.value].status = 'error';
  } finally {
    loading.value = false;
    await refreshStats(selectedDatabase.value || undefined);
  }
};

onMounted(() => {
  refreshStats(selectedDatabase.value || undefined);
  fetchDatabases();
  nextTick(() => {
    initGraph();
  });
});

watch(selectedDatabase, async () => {
  integrity.checked = false;
  await refreshStats(selectedDatabase.value || undefined);
  await initGraph();
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
});
</script>

<template>
  <div class="h-[calc(100vh-78.2px)] flex bg-[#0a0a0a] text-gray-200 overflow-hidden">
    <!-- 左侧配置面板 -->
    <div class="w-[360px] flex flex-col border-r border-gray-800 bg-gray-900/50 backdrop-blur-sm">
      <div class="p-4 border-b border-gray-800">
        <h2 class="text-lg font-semibold flex items-center gap-2">
          <el-icon class="text-cyan-400"><Cpu /></el-icon>
          构建控制台
        </h2>
      </div>

      <div class="flex-1 overflow-y-auto p-4 space-y-6">
        <!-- 数据源选择 -->
        <div class="space-y-3">
          <label class="text-xs font-medium text-gray-500 uppercase">数据源</label>
          <div class="bg-gray-800/50 p-1 rounded-lg flex gap-1">
            <button 
              class="flex-1 py-1.5 text-sm rounded-md transition-colors"
              :class="activeTab === 'text' ? 'bg-gray-700 text-white shadow' : 'text-gray-400 hover:text-gray-300'"
              @click="activeTab = 'text'"
            >
              文本输入
            </button>
            <button 
              class="flex-1 py-1.5 text-sm rounded-md transition-colors"
              :class="activeTab === 'file' ? 'bg-gray-700 text-white shadow' : 'text-gray-400 hover:text-gray-300'"
              @click="activeTab = 'file'"
            >
              文件上传
            </button>
          </div>

          <div v-if="activeTab === 'text'" class="space-y-4">
            <!-- 标题与ID输入 -->
            <div class="grid grid-cols-2 gap-2">
              <div class="space-y-1">
                <label class="text-xs font-medium text-gray-500 uppercase">文档标题</label>
                <el-input
                  v-model="form.title"
                  placeholder="请输入标题"
                  class="custom-input"
                  :prefix-icon="Document"
                  clearable
                />
              </div>
              <div class="space-y-1">
                <label class="text-xs font-medium text-gray-500 uppercase">文档 ID</label>
                <el-input
                  v-model="form.docId"
                  placeholder="ID (可选)"
                  class="custom-input"
                  :prefix-icon="Connection"
                  clearable
                />
              </div>
            </div>

            <!-- 文本内容输入 (美化版) -->
            <div class="space-y-1">
              <div class="flex items-center justify-between">
                <label class="text-xs font-medium text-gray-500 uppercase">文本内容</label>
                <span class="text-xs text-gray-600 font-mono">{{ form.text.length }}/5000</span>
              </div>
              
              <div class="relative border border-gray-700 rounded-lg bg-gray-900/30 hover:border-gray-600 focus-within:border-cyan-500/50 focus-within:bg-gray-900/50 transition-all overflow-hidden group">
                <el-input
                  v-model="form.text"
                  type="textarea"
                  :rows="12"
                  placeholder="在此输入或粘贴需要构建图谱的源文本..."
                  class="custom-textarea"
                  resize="none"
                  maxlength="5000"
                />
              </div>
            </div>
          </div>
          <div v-else class="space-y-4">
            <!-- 标题与ID输入 -->
            <div class="grid grid-cols-2 gap-2">
              <div class="space-y-1">
                <label class="text-xs font-medium text-gray-500 uppercase">文档标题</label>
                <el-input
                  v-model="form.title"
                  placeholder="请输入标题"
                  class="custom-input"
                  :prefix-icon="Document"
                  clearable
                />
              </div>
              <div class="space-y-1">
                <label class="text-xs font-medium text-gray-500 uppercase">文档 ID</label>
                <el-input
                  v-model="form.docId"
                  placeholder="ID (可选)"
                  class="custom-input"
                  :prefix-icon="Connection"
                  clearable
                />
              </div>
            </div>

            <!-- 文件上传区 -->
            <div class="h-48 border-2 border-dashed border-gray-700 rounded-lg flex flex-col items-center justify-center text-gray-500 hover:border-cyan-500/50 hover:bg-gray-800/30 transition-colors">
              <el-upload
                class="w-full h-full flex flex-col items-center justify-center"
                :auto-upload="false"
                :show-file-list="false"
                :on-change="handleFileChange"
                accept=".txt,.md,.json,.xlsx,.csv"
                drag
              >
                <el-icon class="text-4xl mb-2"><FolderOpened /></el-icon>
                <div class="text-sm">点击或拖拽文件至此</div>
                <div class="text-xs mt-1 text-gray-600">支持 .txt, .md, .json, .xlsx, .csv</div>
              </el-upload>
            </div>
          </div>
        </div>

        <div class="space-y-3 pt-3 border-t border-gray-800">
          <label class="text-xs font-medium text-gray-500 uppercase">目标数据库</label>
          <el-select
            v-model="selectedDatabase"
            placeholder="请选择数据库"
            class="w-full custom-select"
            filterable
            :loading="loadingDocs"
            clearable
          >
            <el-option
              v-for="db in databaseOptions"
              :key="db.value"
              :label="db.label"
              :value="db.value"
            />
          </el-select>

          <label class="flex items-center justify-between text-xs text-gray-400">
            <span>构建前清空目标数据库</span>
            <input v-model="clearBeforeBuild" type="checkbox" class="accent-cyan-500" />
          </label>
        </div>

        <div class="space-y-3 pt-3 border-t border-gray-800">
          <label class="text-xs font-medium text-gray-500 uppercase">一致性检测</label>
          <div class="flex items-center gap-3">
            <span class="inline-flex items-center gap-2 text-xs text-gray-300">
              <span class="h-2.5 w-2.5 rounded-full" :class="integrity.checked ? (integrity.vectorMissing ? 'bg-red-500' : 'bg-green-500') : 'bg-gray-600'"></span>
              向量
            </span>
            <span class="inline-flex items-center gap-2 text-xs text-gray-300">
              <span class="h-2.5 w-2.5 rounded-full" :class="integrity.checked ? ((integrity.sourceMissing || integrity.neoMissing) ? 'bg-red-500' : 'bg-green-500') : 'bg-gray-600'"></span>
              源数据/Neo4j
            </span>
            <span class="inline-flex items-center gap-2 text-xs text-gray-300">
              <span class="h-2.5 w-2.5 rounded-full" :class="integrity.checked ? (integrity.orphanedChunks ? 'bg-orange-500' : 'bg-green-500') : 'bg-gray-600'"></span>
              孤立Chunk
            </span>
            <span class="inline-flex items-center gap-2 text-xs text-gray-300">
              <span class="h-2.5 w-2.5 rounded-full" :class="integrity.checked ? (integrity.communityMissing ? 'bg-red-500' : 'bg-green-500') : 'bg-gray-600'"></span>
              社区划分
            </span>
          </div>
          <div class="text-[11px] text-gray-500" v-if="integrity.checked">
            N: {{ integrity.counts.neo_nodes }} / E: {{ integrity.counts.neo_edges }} / Chunk: {{ integrity.counts.source_chunks }} / GraphChunk: {{ integrity.counts.graph_chunks }} / Vec: {{ integrity.counts.vectors }}
            <div v-if="integrity.counts.entity_nodes > 0" class="mt-1">
              <span :class="integrity.vectorMissing ? 'text-yellow-400' : 'text-green-400'">
                实体向量覆盖率: {{ (integrity.counts.vector_coverage * 100).toFixed(1) }}%
                ({{ integrity.counts.vectors }}/{{ integrity.counts.entity_nodes }})
              </span>
            </div>
            <div class="mt-1" :class="integrity.communityMissing ? 'text-red-400' : 'text-green-400'">
              社区数量: {{ integrity.counts.communities }}
              <span v-if="integrity.communityMissing">⚠️ 社区划分缺失</span>
            </div>
            <div v-if="integrity.counts.orphaned_chunks > 0" class="text-orange-400 mt-1">
              ⚠️ 检测到 {{ integrity.counts.orphaned_chunks }} 个孤立Chunk（没有对应向量或Document）
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <el-button size="small" @click="checkIntegrity">检测</el-button>
            <el-button size="small" type="warning" :loading="repairing" @click="repairIntegrity">自动修复</el-button>
          </div>
        </div>



        <!-- 高级配置 -->
        <div class="space-y-4 pt-4 border-t border-gray-800">
          <label class="text-xs font-medium text-gray-500 uppercase">切片策略</label>
          
          <div>
            <div class="flex justify-between text-xs mb-1">
              <span class="text-gray-400">Chunk Size</span>
              <span class="text-cyan-400">{{ form.chunkSize }}</span>
            </div>
            <el-slider v-model="form.chunkSize" :min="100" :max="2000" :step="50" size="small" />
          </div>

          <div>
            <div class="flex justify-between text-xs mb-1">
              <span class="text-gray-400">Overlap</span>
              <span class="text-cyan-400">{{ form.overlap }}</span>
            </div>
            <el-slider v-model="form.overlap" :min="0" :max="500" :step="10" size="small" />
          </div>
        </div>
      </div>

      <div class="p-4 border-t border-gray-800 bg-gray-900/80">
        <el-button 
          type="primary" 
          class="w-full !h-9 !text-sm !bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 border-none" 
          :loading="loading"
          :icon="VideoPlay"
          @click="handleBuild"
        >
          开始自动化构建
        </el-button>
      </div>
    </div>

    <!-- 右侧可视化与反馈 -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 顶部状态栏 -->
      <div class="h-16 border-b border-gray-800 flex items-center px-6 justify-between bg-gray-900/30">
        <el-steps :active="activeStep" finish-status="success" simple class="!bg-transparent flex-1 max-w-2xl">
          <el-step v-for="step in steps" :key="step.title" :title="step.title" />
        </el-steps>
        
        <div class="flex gap-6 text-sm">
          <div class="flex flex-col items-end">
            <span class="text-gray-500 text-xs">Nodes</span>
            <span class="font-mono font-bold text-cyan-400">{{ stats.nodes }}</span>
          </div>
          <div class="flex flex-col items-end">
            <span class="text-gray-500 text-xs">Edges</span>
            <span class="font-mono font-bold text-purple-400">{{ stats.edges }}</span>
          </div>
          <div class="flex flex-col items-end">
            <span class="text-gray-500 text-xs">Communities</span>
            <span class="font-mono font-bold text-green-400">{{ stats.communities }}</span>
          </div>
        </div>
      </div>

      <!-- 主视图区域 -->
      <div class="flex-1 relative">
        <!-- 视图切换 Tabs -->
        <div class="absolute top-4 left-4 z-10 flex gap-2 items-center">
          <button 
            class="px-3 py-1.5 rounded-md text-sm backdrop-blur-md border border-gray-700 transition-all"
            :class="activeView === 'graph' ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50' : 'bg-gray-900/50 text-gray-400 hover:bg-gray-800'"
            @click="activeView = 'graph'"
          >
            <el-icon class="mr-1 align-text-bottom"><Connection /></el-icon> 图谱预览
          </button>
          <button 
            class="px-3 py-1.5 rounded-md text-sm backdrop-blur-md border border-gray-700 transition-all"
            :class="activeView === 'logs' ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50' : 'bg-gray-900/50 text-gray-400 hover:bg-gray-800'"
            @click="activeView = 'logs'"
          >
            <el-icon class="mr-1 align-text-bottom"><List /></el-icon> 执行日志
          </button>
          
          <!-- 数据库筛选 -->
          <el-select
            v-model="selectedDatabase"
            placeholder="筛选数据库"
            size="small"
            class="doc-filter-select"
            :loading="loadingDocs"
            style="width: 160px;"
            @change="initGraph"
          >
            <el-option
              v-for="db in databaseOptions"
              :key="db.value"
              :label="db.label"
              :value="db.value"
            />
          </el-select>
          
          <button 
            class="px-3 py-1.5 rounded-md text-sm backdrop-blur-md border border-gray-700 transition-all hover:text-white"
            @click="initGraph"
          >
            <el-icon><RefreshRight /></el-icon>
          </button>
        </div>

        <!-- Graph View -->
        <div v-show="activeView === 'graph'" class="w-full h-full bg-gradient-to-b from-gray-900 to-black" ref="graphContainer"></div>

        <!-- Logs View -->
        <div v-show="activeView === 'logs'" class="w-full h-full bg-[#0c0c0c] p-6 overflow-y-auto font-mono text-sm">
          <div v-if="logs.length === 0" class="h-full flex items-center justify-center text-gray-600">
            <div class="text-center">
              <el-icon class="text-4xl mb-2"><Monitor /></el-icon>
              <p>等待任务开始...</p>
            </div>
          </div>
          <div v-else class="space-y-2">
            <div v-for="(log, i) in logs" :key="i" class="border-l-2 border-gray-800 pl-3 py-1 hover:bg-gray-900/50 transition-colors">
              <span class="text-gray-500 mr-2">{{ log.split(']')[0] }}]</span>
              <span :class="log.includes('错误') ? 'text-red-400' : 'text-gray-300'">{{ log.split(']')[1] }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-input :deep(.el-input__wrapper) {
  background-color: rgba(31, 41, 55, 0.5);
  box-shadow: none;
  border: 1px solid rgba(75, 85, 99, 0.5);
}
.custom-input :deep(.el-input__wrapper.is-focus) {
  border-color: #06b6d4;
  box-shadow: 0 0 0 1px #06b6d4;
}

.custom-textarea :deep(.el-textarea__inner) {
  background-color: transparent;
  box-shadow: none;
  border: none;
  color: #e5e7eb;
  padding: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
.custom-textarea :deep(.el-textarea__inner:focus) {
  box-shadow: none;
}

:deep(.el-upload-dragger) {
  background-color: transparent;
  border: none;
}

.doc-filter-select :deep(.el-input__wrapper) {
  background-color: rgba(17, 24, 39, 0.8);
  box-shadow: none;
  border: 1px solid rgba(75, 85, 99, 0.5);
  backdrop-filter: blur(8px);
}
.doc-filter-select :deep(.el-input__wrapper:hover) {
  border-color: rgba(6, 182, 212, 0.5);
}
.doc-filter-select :deep(.el-input__inner) {
  color: #9ca3af;
  font-size: 12px;
}
.doc-filter-select :deep(.el-input__inner::placeholder) {
  color: #6b7280;
}
</style>
