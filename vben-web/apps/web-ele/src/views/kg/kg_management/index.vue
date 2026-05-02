<script lang="ts" setup>
import { ref, onMounted, reactive, nextTick, watch, onUnmounted } from 'vue';
import {
  ElMessage,
  ElMessageBox,
  ElNotification,
  ElSelect,
  ElOption,
  ElButton,
  ElInput,
  ElForm,
  ElFormItem,
  ElTag,
  ElIcon,
  ElSteps,
  ElStep,
  ElUpload,
  ElSlider,
  type UploadFile,
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
  Plus,
  FolderOpened,
  VideoPlay,
  Monitor,
  List,
  RefreshRight,
  Cpu,
} from '@element-plus/icons-vue';
import ForceGraph3D from '3d-force-graph';
import SpriteText from 'three-spritetext';
import {
  getDatabases,
  getCommunities,
  getVisualizeData,
  getGraphStats,
  updateNode,
  updateRelation,
  clearDatabase,
  exportDatabase,
  cleanupAllOrphanedData,
  getChunksVectorStatus,
  deleteNode,
  deleteRelation,
  uploadDocument,
  detectCommunities,
  generateCommunityReports,
  checkDatabaseIntegrity,
  repairDatabaseIntegrity,
} from './api';
import { baseRequestClient } from '#/api/request';

// ═══ Shared State ═══════════════════════════════════════
const sidebarTab = ref<'construct' | 'manage' | 'edit'>('construct');
const loading = ref(false);
const graphContainer = ref<HTMLElement | null>(null);
let graphInstance: any = null;

// Database
const databases = ref<Array<{ label: string; value: string }>>([]);
const selectedDatabase = ref('');
const loadingDbs = ref(false);

// Stats
const stats = reactive({ nodes: 0, edges: 0, communities: 0 });

// ═══ Construct State ════════════════════════════════════
const repairing = ref(false);
const activeTab = ref('text'); // text | file
const form = reactive({ text: '', title: '', docId: '', chunkSize: 500, overlap: 50 });
const uploadedFile = ref<File | null>(null);
const clearBeforeBuild = ref(false);

const steps = ref([
  { title: '数据入库', status: 'wait', description: '文本切片与实体抽取' },
  { title: '社区检测', status: 'wait', description: 'Leiden 算法聚类' },
  { title: '报告生成', status: 'wait', description: '生成社区摘要' },
]);
const activeStep = ref(0);
const logs = ref<string[]>([]);
const activeView = ref('graph'); // graph | logs

const integrity = reactive({
  checked: false,
  vectorMissing: false,
  sourceMissing: false,
  neoMissing: false,
  orphanedChunks: false,
  communityMissing: false,
  counts: {
    neo_nodes: 0, neo_edges: 0, source_docs: 0, source_chunks: 0,
    graph_chunks: 0, vectors: 0, orphaned_chunks: 0, entity_nodes: 0,
    vector_coverage: 1.0, communities: 0,
  },
});

// ═══ Management State ═══════════════════════════════════
const communities = ref<Array<number>>([]);
const selectedCommunityId = ref<number | undefined>(undefined);
const chunksStatus = reactive({ orphaned_chunks: 0, vectorized_chunks: 0, summary: '' });

// ═══ Edit State ═════════════════════════════════════════
const selectedElement = ref<any>(null);
const selectedType = ref<'node' | 'link' | null>(null);
const editForm = reactive<{ properties: Record<string, any> }>({ properties: {} });
const isEditing = ref(false);

// ═══ Helpers ════════════════════════════════════════════
const addLog = (msg: string) => {
  const time = new Date().toLocaleTimeString();
  logs.value.unshift(`[${time}] ${msg}`);
};

const isDarkMode = () => document.documentElement.classList.contains('dark');

const formatTime = (val: any) => {
  if (!val) return '';
  try {
    const date = new Date(val);
    if (isNaN(date.getTime())) return String(val);
    const y = date.getFullYear();
    const mo = (date.getMonth() + 1).toString().padStart(2, '0');
    const d = date.getDate().toString().padStart(2, '0');
    const h = date.getHours().toString().padStart(2, '0');
    const mi = date.getMinutes().toString().padStart(2, '0');
    return y+'-'+mo+'-'+d+' '+h+':'+mi;
  } catch { return String(val); }
};

const buildLinkTooltip = (link: any) => {
  const dark = isDarkMode();
  const props = link.properties || {};
  const desc = props.description || props.desc || '';
  const source = typeof link.source === 'object' ? link.source.label : link.source;
  const target = typeof link.target === 'object' ? link.target.label : link.target;
  const bg = dark ? 'rgba(15,23,42,0.92)' : 'rgba(255,255,255,0.96)';
  const border = dark ? 'rgba(71,85,105,0.72)' : 'rgba(148,163,184,0.35)';
  const title = dark ? '#67e8f9' : '#0369a1';
  const text = dark ? '#cbd5e1' : '#334155';
  const meta = dark ? '#94a3b8' : '#64748b';
  const div = dark ? 'rgba(71,85,105,0.6)' : 'rgba(203,213,225,0.8)';
  const shadow = dark ? '0 16px 32px rgba(2,6,23,0.42)' : '0 16px 32px rgba(15,23,42,0.12)';
  return '<div style="padding:10px 12px;background:'+bg+';border:1px solid '+border+';border-radius:10px;box-shadow:'+shadow+';backdrop-filter:blur(10px);font-size:12px;">'+
    '<div style="font-weight:700;color:'+title+';margin-bottom:4px;">'+link.label+'</div>'+
    (desc?'<div style="color:'+text+';margin-bottom:4px;max-width:200px;white-space:normal;line-height:1.5;">'+desc+'</div>':'')+
    '<div style="color:'+meta+';margin-top:4px;padding-top:4px;border-top:1px solid '+div+';display:flex;gap:4px;align-items:center;">'+
    '<span style="max-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'+source+'</span>'+
    '<span>&rarr;</span>'+
    '<span style="max-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'+target+'</span>'+
    '</div></div>';
};

// ═══ Database / Graph Methods ═══════════════════════════
const loadDatabases = async () => {
  loadingDbs.value = true;
  try {
    const res = await getDatabases();
    const data = res.data || res;
    const dbList = data.data?.databases || data.databases || [];
    if (Array.isArray(dbList)) {
      databases.value = dbList.map((db: any) => ({ label: db.name || db, value: db.name || db }));
      if (!selectedDatabase.value && databases.value.length > 0) {
        const defaultDb = dbList.find((db: any) => Boolean(db?.default));
        selectedDatabase.value = (defaultDb?.name || defaultDb) || databases.value[0]!.value;
      }
    }
  } catch (error) {
    console.error('Failed to load databases', error);
  } finally {
    loadingDbs.value = false;
  }
};

const loadCommunities = async () => {
  if (!selectedDatabase.value) { communities.value = []; selectedCommunityId.value = undefined; return; }
  try {
    const res = await getCommunities(undefined, selectedDatabase.value);
    const data = res.data || res;
    const comms = data.data || data || [];
    if (Array.isArray(comms)) communities.value = comms;
  } catch (error) { console.error('Failed to load communities', error); }
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
  } catch (error) { console.error(error); }
};

const loadChunksStatus = async () => {
  try {
    if (!selectedDatabase.value) { chunksStatus.orphaned_chunks = 0; chunksStatus.vectorized_chunks = 0; chunksStatus.summary = ''; return; }
    const res = await getChunksVectorStatus(selectedDatabase.value);
    const data = res.data || res;
    if (data.success) {
      const s = data.data || {};
      chunksStatus.orphaned_chunks = s.orphaned_chunks || 0;
      chunksStatus.vectorized_chunks = s.vectorized_chunks || 0;
      chunksStatus.summary = s.summary || '';
    }
  } catch (error) { console.error('Failed to load chunks status:', error); }
};

const initGraph = async () => {
  if (!graphContainer.value) return;
  loading.value = true;
  selectedElement.value = null;
  selectedType.value = null;

  try {
    const res = await getVisualizeData(200, undefined, selectedCommunityId.value, selectedDatabase.value || undefined);
    const data = res.data || res;
    const rawData = (data.success || data.nodes) ? (data.data || data) : { nodes: [], edges: [] };
    const gData = { nodes: rawData.nodes || [], links: rawData.links || rawData.edges || [] };

    if (graphInstance) {
      graphInstance.graphData(gData);
    } else {
      graphInstance = ForceGraph3D()(graphContainer.value)
        .graphData(gData)
        .nodeLabel('label')
        .nodeAutoColorBy('category')
        .linkLabel((link: any) => buildLinkTooltip(link))
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
        .onBackgroundClick(() => { selectedElement.value = null; selectedType.value = null; });
    }
  } catch (e) {
    console.error('Graph init failed', e);
    ElMessage.error('图谱加载失败');
  } finally {
    loading.value = false;
  }
};

const handleResize = () => {
  if (graphInstance && graphContainer.value) {
    graphInstance.width(graphContainer.value.clientWidth);
    graphInstance.height(graphContainer.value.clientHeight);
  }
};

const handleRefresh = async () => { await initGraph(); ElMessage.success('图谱已刷新'); };

// ═══ Edit Methods ═══════════════════════════════════════
const handleNodeClick = (node: any) => {
  selectedElement.value = node;
  selectedType.value = 'node';
  editForm.properties = node.properties ? { ...node.properties } : {};
  sidebarTab.value = 'edit';
  const distance = 40;
  const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);
  graphInstance.cameraPosition(
    { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, node, 3000
  );
};

const handleLinkClick = (link: any) => {
  selectedElement.value = link;
  selectedType.value = 'link';
  editForm.properties = link.properties ? { ...link.properties } : {};
  sidebarTab.value = 'edit';
};

const handleAddProperty = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入属性名', '添加属性', {
      confirmButtonText: '确定', cancelButtonText: '取消',
      inputPattern: /^[a-zA-Z_][a-zA-Z0-9_]*$/,
      inputErrorMessage: '属性名只能包含字母、数字和下划线，且不能以数字开头',
    });
    if (value) {
      if (editForm.properties[value] !== undefined) { ElMessage.warning('属性已存在'); return; }
      editForm.properties[value] = '';
    }
  } catch { /* cancelled */ }
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
    await initGraph();
    if (currentId && currentType && graphInstance) {
      const { nodes, links } = graphInstance.graphData();
      const target = currentType === 'node'
        ? nodes.find((n: any) => n.id === currentId)
        : links.find((l: any) => l.id === currentId);
      if (target) {
        selectedElement.value = target;
        selectedType.value = currentType;
        editForm.properties = target.properties ? { ...target.properties } : {};
      }
    }
  } catch (error) { ElMessage.error('更新失败'); console.error(error); }
  finally { isEditing.value = false; }
};

const handleDeleteElement = async () => {
  if (!selectedElement.value) return;
  try {
    await ElMessageBox.confirm(
      '确定要删除该'+(selectedType.value === 'node' ? '节点' : '关系')+'吗？', '警告',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    );
    loading.value = true;
    if (selectedType.value === 'node') { await deleteNode(selectedElement.value.id); ElMessage.success('节点已删除'); }
    else { await deleteRelation(selectedElement.value.id); ElMessage.success('关系已删除'); }
    await initGraph();
    selectedElement.value = null; selectedType.value = null;
  } catch (error) { if (error !== 'cancel') { ElMessage.error('删除失败'); console.error(error); } }
  finally { loading.value = false; }
};

// ═══ Management Methods ═════════════════════════════════
const handleDeleteDoc = async () => {
  if (!selectedDatabase.value) return;
  try {
    await ElMessageBox.confirm(
      '确定要清空数据库 '+selectedDatabase.value+' 吗？该数据库内所有节点与关系将被删除。',
      '高风险操作确认', { confirmButtonText: '确定清空', cancelButtonText: '取消', type: 'warning' }
    );
    loading.value = true;
    const res = await clearDatabase(selectedDatabase.value);
    const data = res.data || res;
    if (data.success) {
      const d = data.data || {};
      ElMessage.success('清空成功：删除节点 '+(d.deleted_nodes||0)+'，删除关系 '+(d.deleted_edges||0));
      selectedCommunityId.value = undefined; communities.value = [];
      await initGraph();
    } else { throw new Error(data.error || '清空失败'); }
  } catch (error) { if (error !== 'cancel') { ElMessage.error('清空数据库失败'); console.error(error); } }
  finally { loading.value = false; }
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
      link.href = url; link.download = 'graph_export_db_'+selectedDatabase.value+'.json';
      document.body.appendChild(link); link.click(); document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      ElMessage.success('数据库导出成功');
    } else { throw new Error(data.error || '导出失败'); }
  } catch (error) { ElMessage.error('数据库导出失败'); console.error(error); }
  finally { loading.value = false; }
};

const handleCleanupVectors = async () => {
  try {
    if (!selectedDatabase.value) { ElMessage.warning('请先选择数据库'); return; }
    await ElMessageBox.confirm(
      '确定要清理孤立数据吗？这将删除所有没有对应关联的向量和Chunk节点。', '清理确认',
      { confirmButtonText: '确定清理', cancelButtonText: '取消', type: 'warning' }
    );
    loading.value = true;
    const res = await cleanupAllOrphanedData(selectedDatabase.value);
    const data = res.data || res;
    if (data.success) {
      const st = data.data || {};
      const messages: string[] = [];
      if (st.vectors?.deleted > 0) messages.push('删除了 '+st.vectors.deleted+' 个孤立向量');
      if (st.chunks?.deleted > 0) {
        messages.push('删除了 '+st.chunks.deleted+' 个孤立Chunk');
        if (st.chunks.mentions > 0) messages.push(st.chunks.mentions+' 个MENTIONS关系');
        if (st.chunks.contains > 0) messages.push(st.chunks.contains+' 个CONTAINS关系');
      }
      ElMessage.success('清理完成: '+(messages.length > 0 ? messages.join(', ') : '未发现需要清理的数据'));
      await loadChunksStatus(); await initGraph();
    } else { throw new Error(data.error || '清理失败'); }
  } catch (error) { if (error !== 'cancel') { ElMessage.error('清理操作失败'); console.error(error); } }
  finally { loading.value = false; }
};

// ═══ Construct Methods ══════════════════════════════════
const checkIntegrity = async () => {
  if (!selectedDatabase.value) { ElMessage.warning('请先选择数据库'); return; }
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
      neo_nodes: payload.counts?.neo_nodes || 0, neo_edges: payload.counts?.neo_edges || 0,
      source_docs: payload.counts?.source_docs || 0, source_chunks: payload.counts?.source_chunks || 0,
      graph_chunks: payload.counts?.graph_chunks || 0, vectors: payload.counts?.vectors || 0,
      orphaned_chunks: payload.counts?.orphaned_chunks || 0, entity_nodes: payload.counts?.entity_nodes || 0,
      vector_coverage: payload.counts?.vector_coverage ?? 1.0, communities: payload.counts?.communities || 0,
    };
  } catch (error) { ElMessage.error('完整性检测失败'); console.error(error); }
};

const repairIntegrity = async () => {
  if (!selectedDatabase.value) { ElMessage.warning('请先选择数据库'); return; }
  repairing.value = true;
  try {
    if (!integrity.checked) await checkIntegrity();
    const targets: string[] = [];
    if (integrity.vectorMissing) targets.push('vector');
    if (integrity.neoMissing) targets.push('neo4j');
    if (integrity.sourceMissing && !targets.includes('neo4j')) targets.push('neo4j');
    if (!targets.length && !integrity.communityMissing) {
      ElMessage.success('数据库生命周期完整，无需修复'); repairing.value = false; return;
    }
    if (targets.length > 0) {
      const res = await repairDatabaseIntegrity(selectedDatabase.value, targets);
      const data = res.data || res;
      if (!data.success) throw new Error(data.error || '修复失败');
      addLog('修复完成（目标库：'+(data.data?.database || selectedDatabase.value)+')');
    }
    if (integrity.communityMissing) {
      addLog('社区划分缺失，开始执行 Leiden 社区检测...');
      const cRes = await detectCommunities(true, selectedDatabase.value);
      const cData = cRes.data || cRes;
      if (cData.success) {
        const cd = cData.data || {};
        addLog('社区检测完成：共 '+(cd.total_communities??0)+' 个社区');
      } else { addLog('社区检测失败: '+(cData.error||'未知错误')); }
    }
    ElMessage.success('自动修复任务已执行');
    await checkIntegrity(); await initGraph();
  } catch (error) { ElMessage.error('自动修复失败'); console.error(error); }
  finally { repairing.value = false; }
};

const handleClearDatabase = async () => {
  if (!selectedDatabase.value) { ElMessage.warning('请先选择数据库'); return; }
  await clearDatabase(selectedDatabase.value);
  await initGraph(); await checkIntegrity();
};

const handleFileChange = async (file: UploadFile) => {
  if (!file.raw) return;
  const fileName = file.name.toLowerCase();
  const isExcel = fileName.endsWith('.xlsx') || fileName.endsWith('.csv');
  if (isExcel) {
    if (!form.title) form.title = file.name;
    uploadedFile.value = file.raw;
    ElMessage.success('已选择表格文件: '+file.name);
  } else {
    const reader = new FileReader();
    reader.onload = (e) => {
      if (e.target?.result) {
        form.text = e.target.result as string;
        if (!form.title) form.title = file.name;
        uploadedFile.value = null;
        ElMessage.success('已读取文件: '+file.name);
      }
    };
    reader.readAsText(file.raw);
  }
};

const handleBuild = async () => {
  if (!selectedDatabase.value) { ElMessage.warning('请先选择目标数据库'); return; }
  if (!form.text && !uploadedFile.value) { ElMessage.warning('请先输入文本或上传文件'); return; }
  if (clearBeforeBuild.value) {
    try { await handleClearDatabase(); addLog('已按配置清空目标数据库'); }
    catch { ElMessage.error('清空数据库失败，已终止构建'); return; }
  }
  if (uploadedFile.value) await handleSchemaBuild(); else await handleTextBuild();
};

const handleTextBuild = async () => {
  loading.value = true; activeStep.value = 0;
  steps.value.forEach(s => s.status = 'wait'); logs.value = [];
  addLog('[文本模式] 开始 LLM 实体抽取流程...'); addLog('此过程可能需要较长时间，请耐心等待...');
  activeView.value = 'logs';
  try {
    steps.value[0]!.status = 'process';
    addLog('正在入库 (Chunk: '+form.chunkSize+', Overlap: '+form.overlap+')...');
    const uploadRes = await uploadDocument(form.text, form.docId, form.title, selectedDatabase.value || undefined);
    const uploadData = uploadRes.data || uploadRes;
    if (!uploadData.success) throw new Error(uploadData.error || '入库失败');
    addLog('入库成功: '+JSON.stringify(uploadData.data));
    steps.value[0]!.status = 'success'; activeStep.value = 1;
    await refreshStats(selectedDatabase.value); await initGraph();

    steps.value[1]!.status = 'process'; addLog('正在执行社区检测...');
    const detectRes = await detectCommunities(true, selectedDatabase.value);
    const detectData = detectRes.data || detectRes;
    if (!detectData.success) throw new Error(detectData.error || '社区检测失败');
    addLog('社区检测成功'); steps.value[1]!.status = 'success'; activeStep.value = 2;
    await refreshStats(selectedDatabase.value);

    steps.value[2]!.status = 'process'; addLog('正在生成社区报告...');
    const reportRes = await generateCommunityReports(selectedDatabase.value);
    const reportData = reportRes.data || reportRes;
    if (!reportData.success) throw new Error(reportData.error || '报告生成失败');
    steps.value[2]!.status = 'success'; activeStep.value = 3; addLog('构建流程全部完成！');
    ElNotification.success({ title: '构建完成', message: '知识图谱已更新', duration: 3000 });
  } catch (error: any) {
    const msg = error.message || '未知错误';
    if (msg.includes('timeout')) { addLog('请求超时，可能是任务耗时较长'); ElMessage.error('请求超时'); }
    else { addLog('错误: '+msg); ElMessage.error('构建失败: '+msg); }
    steps.value[activeStep.value]!.status = 'error';
  } finally { loading.value = false; await refreshStats(selectedDatabase.value); }
};

const handleSchemaBuild = async () => {
  loading.value = true; activeStep.value = 0;
  steps.value.forEach(s => s.status = 'wait'); logs.value = [];
  addLog('[Schema模式] 开始表格数据映射流程...'); activeView.value = 'logs';
  try {
    steps.value[0]!.status = 'process'; addLog('正在上传表格文件...');
    const formData = new FormData();
    formData.append('file', uploadedFile.value!);
    if (form.docId) formData.append('doc_id', form.docId);
    if (form.title) formData.append('title', form.title);
    if (selectedDatabase.value) formData.append('database', selectedDatabase.value);
    const schemaRes = await baseRequestClient.post('/kg/excel/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300000,
    });
    const schemaData = schemaRes.data || schemaRes;
    if (!schemaData.success) throw new Error(schemaData.error || 'Schema解析失败');
    addLog('Schema解析成功: 共 '+schemaData.data.row_count+' 行数据');
    steps.value[0]!.status = 'success'; activeStep.value = 1;
    await refreshStats(selectedDatabase.value); await initGraph();

    steps.value[1]!.status = 'process'; addLog('正在执行社区检测...');
    const detectRes = await detectCommunities(true, selectedDatabase.value);
    const detectData = detectRes.data || detectRes;
    if (!detectData.success) throw new Error(detectData.error || '社区检测失败');
    addLog('社区检测成功'); steps.value[1]!.status = 'success'; activeStep.value = 2;
    await refreshStats(selectedDatabase.value);

    steps.value[2]!.status = 'process'; addLog('正在生成社区报告...');
    const reportRes = await generateCommunityReports(selectedDatabase.value);
    const reportData = reportRes.data || reportRes;
    if (!reportData.success) throw new Error(reportData.error || '报告生成失败');
    steps.value[2]!.status = 'success'; activeStep.value = 3; addLog('[Schema模式] 构建流程全部完成！');
    ElNotification.success({ title: 'Schema映射完成', message: '表格数据已成功导入知识图谱', duration: 3000 });
  } catch (error: any) {
    addLog('错误: '+(error.message||'未知错误'));
    ElMessage.error('Schema映射失败: '+(error.message||'未知错误'));
    steps.value[activeStep.value]!.status = 'error';
  } finally { loading.value = false; await refreshStats(selectedDatabase.value); }
};

// ═══ Watchers & Lifecycle ═══════════════════════════════
watch(selectedDatabase, async (newVal) => {
  selectedCommunityId.value = undefined;
  integrity.checked = false;
  if (newVal) {
    await loadCommunities();
    await loadChunksStatus();
    await refreshStats(newVal);
  } else {
    communities.value = [];
    chunksStatus.orphaned_chunks = 0; chunksStatus.vectorized_chunks = 0; chunksStatus.summary = '';
  }
  initGraph();
});

watch(selectedCommunityId, () => { initGraph(); });

onMounted(() => {
  loadDatabases();
  loadChunksStatus();
  nextTick(() => { initGraph(); });
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  if (graphInstance) { graphInstance._destructor && graphInstance._destructor(); }
});
</script>

<template>
  <div class="kg-page h-[calc(100vh-78.2px)] flex overflow-hidden">
    <!-- ═══ 左侧边栏 ═══ -->
    <div class="kg-sidebar w-[380px] flex-none flex flex-col border-r z-20">
      <!-- 顶部: 数据库选择 (共享) -->
      <div class="kg-sidebar__header flex-none p-4 border-b space-y-3">
        <h2 class="text-lg font-bold flex items-center gap-3 tracking-wide">
          <div class="p-2 bg-cyan-500/20 rounded-lg backdrop-blur-sm">
            <el-icon class="text-cyan-400 text-xl"><Share /></el-icon>
          </div>
          <span>知识图谱工作台</span>
        </h2>
        <div class="space-y-1.5">
          <label class="text-xs font-medium text-gray-500 ml-1 uppercase">目标数据库</label>
          <el-select v-model="selectedDatabase" placeholder="请选择数据库..." class="w-full custom-select" clearable filterable size="large" :loading="loadingDbs">
            <template #prefix><el-icon class="text-gray-400"><Document /></el-icon></template>
            <el-option v-for="db in databases" :key="db.value" :label="db.label" :value="db.value" />
          </el-select>
        </div>
      </div>

      <!-- Tab 切换 -->
      <div class="kg-tab-bar flex-none flex border-b">
        <button class="kg-tab flex-1 py-2.5 text-sm font-medium transition-colors" :class="{ 'is-active': sidebarTab === 'construct' }" @click="sidebarTab = 'construct'">
          <el-icon class="mr-1 align-text-bottom"><Cpu /></el-icon>构建
        </button>
        <button class="kg-tab flex-1 py-2.5 text-sm font-medium transition-colors" :class="{ 'is-active': sidebarTab === 'manage' }" @click="sidebarTab = 'manage'">
          <el-icon class="mr-1 align-text-bottom"><Share /></el-icon>管理
        </button>
        <button class="kg-tab flex-1 py-2.5 text-sm font-medium transition-colors" :class="{ 'is-active': sidebarTab === 'edit' }" @click="sidebarTab = 'edit'">
          <el-icon class="mr-1 align-text-bottom"><Edit /></el-icon>编辑
          <span v-if="selectedElement" class="ml-1 w-2 h-2 rounded-full bg-cyan-400 inline-block"></span>
        </button>
      </div>

      <!-- Tab 内容 -->
      <div class="flex-1 flex flex-col overflow-hidden">
        <!-- ── 构建 Tab ── -->
        <div v-show="sidebarTab === 'construct'" class="flex-1 flex flex-col overflow-y-auto p-4 space-y-5">
          <!-- 数据源切换 -->
          <div class="space-y-3">
            <label class="text-xs font-medium text-gray-500 uppercase">数据源</label>
            <div class="kg-source-switch p-1 rounded-lg flex gap-1">
              <button class="kg-source-btn flex-1 py-1.5 text-sm rounded-md transition-colors" :class="{ 'is-active': activeTab === 'text' }" @click="activeTab = 'text'">文本输入</button>
              <button class="kg-source-btn flex-1 py-1.5 text-sm rounded-md transition-colors" :class="{ 'is-active': activeTab === 'file' }" @click="activeTab = 'file'">文件上传</button>
            </div>

            <div v-if="activeTab === 'text'" class="space-y-4">
              <div class="grid grid-cols-2 gap-2">
                <div class="space-y-1"><label class="text-xs font-medium text-gray-500 uppercase">文档标题</label>
                  <el-input v-model="form.title" placeholder="请输入标题" class="custom-input" :prefix-icon="Document" clearable /></div>
                <div class="space-y-1"><label class="text-xs font-medium text-gray-500 uppercase">文档 ID</label>
                  <el-input v-model="form.docId" placeholder="ID (可选)" class="custom-input" :prefix-icon="Connection" clearable /></div>
              </div>
              <div class="space-y-1">
                <div class="flex items-center justify-between">
                  <label class="text-xs font-medium text-gray-500 uppercase">文本内容</label>
                  <span class="text-xs text-gray-600 font-mono">{{ form.text.length }}/5000</span>
                </div>
                <div class="kg-text-shell relative border rounded-lg transition-all overflow-hidden">
                  <el-input v-model="form.text" type="textarea" :rows="10" placeholder="在此输入或粘贴需要构建图谱的源文本..." class="custom-textarea" resize="none" maxlength="5000" />
                </div>
              </div>
            </div>
            <div v-else class="space-y-4">
              <div class="grid grid-cols-2 gap-2">
                <div class="space-y-1"><label class="text-xs font-medium text-gray-500 uppercase">文档标题</label>
                  <el-input v-model="form.title" placeholder="请输入标题" class="custom-input" :prefix-icon="Document" clearable /></div>
                <div class="space-y-1"><label class="text-xs font-medium text-gray-500 uppercase">文档 ID</label>
                  <el-input v-model="form.docId" placeholder="ID (可选)" class="custom-input" :prefix-icon="Connection" clearable /></div>
              </div>
              <div class="kg-upload-zone h-40 border-2 border-dashed rounded-lg flex flex-col items-center justify-center transition-colors">
                <el-upload class="w-full h-full flex flex-col items-center justify-center" :auto-upload="false" :show-file-list="false" :on-change="handleFileChange" accept=".txt,.md,.json,.xlsx,.csv" drag>
                  <el-icon class="text-4xl mb-2"><FolderOpened /></el-icon>
                  <div class="text-sm">点击或拖拽文件至此</div>
                  <div class="text-xs mt-1 text-gray-600">支持 .txt, .md, .json, .xlsx, .csv</div>
                </el-upload>
              </div>
            </div>
          </div>

          <label class="flex items-center justify-between text-xs text-gray-400 pt-3 border-t">
            <span>构建前清空目标数据库</span>
            <input v-model="clearBeforeBuild" type="checkbox" class="accent-cyan-500" />
          </label>

          <!-- 一致性检测 -->
          <div class="space-y-3 pt-3 border-t">
            <label class="text-xs font-medium text-gray-500 uppercase">一致性检测</label>
            <div class="flex items-center gap-3 flex-wrap">
              <span class="inline-flex items-center gap-2 text-xs text-gray-300">
                <span class="h-2.5 w-2.5 rounded-full" :class="integrity.checked ? (integrity.vectorMissing ? 'bg-red-500' : 'bg-green-500') : 'bg-gray-600'"></span>向量</span>
              <span class="inline-flex items-center gap-2 text-xs text-gray-300">
                <span class="h-2.5 w-2.5 rounded-full" :class="integrity.checked ? ((integrity.sourceMissing || integrity.neoMissing) ? 'bg-red-500' : 'bg-green-500') : 'bg-gray-600'"></span>源数据/Neo4j</span>
              <span class="inline-flex items-center gap-2 text-xs text-gray-300">
                <span class="h-2.5 w-2.5 rounded-full" :class="integrity.checked ? (integrity.orphanedChunks ? 'bg-orange-500' : 'bg-green-500') : 'bg-gray-600'"></span>孤立Chunk</span>
              <span class="inline-flex items-center gap-2 text-xs text-gray-300">
                <span class="h-2.5 w-2.5 rounded-full" :class="integrity.checked ? (integrity.communityMissing ? 'bg-red-500' : 'bg-green-500') : 'bg-gray-600'"></span>社区划分</span>
            </div>
            <div class="text-[11px] text-gray-500" v-if="integrity.checked">
              N: {{ integrity.counts.neo_nodes }} / E: {{ integrity.counts.neo_edges }} / Chunk: {{ integrity.counts.source_chunks }} / Vec: {{ integrity.counts.vectors }}
              <div v-if="integrity.counts.entity_nodes > 0" class="mt-1">
                <span :class="integrity.vectorMissing ? 'text-yellow-400' : 'text-green-400'">
                  实体向量覆盖率: {{ (integrity.counts.vector_coverage * 100).toFixed(1) }}% ({{ integrity.counts.vectors }}/{{ integrity.counts.entity_nodes }})
                </span>
              </div>
              <div class="mt-1" :class="integrity.communityMissing ? 'text-red-400' : 'text-green-400'">
                社区数量: {{ integrity.counts.communities }}<span v-if="integrity.communityMissing"> ⚠️ 缺失</span>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <el-button size="small" @click="checkIntegrity">检测</el-button>
              <el-button size="small" type="warning" :loading="repairing" @click="repairIntegrity">自动修复</el-button>
            </div>
          </div>

          <!-- 切片策略 -->
          <div class="space-y-4 pt-3 border-t">
            <label class="text-xs font-medium text-gray-500 uppercase">切片策略</label>
            <div>
              <div class="flex justify-between text-xs mb-1"><span class="text-gray-400">Chunk Size</span><span class="text-cyan-400">{{ form.chunkSize }}</span></div>
              <el-slider v-model="form.chunkSize" :min="100" :max="2000" :step="50" size="small" />
            </div>
            <div>
              <div class="flex justify-between text-xs mb-1"><span class="text-gray-400">Overlap</span><span class="text-cyan-400">{{ form.overlap }}</span></div>
              <el-slider v-model="form.overlap" :min="0" :max="500" :step="10" size="small" />
            </div>
          </div>

          <!-- 构建按钮 -->
          <div class="flex-none pt-3 border-t">
            <el-button type="primary" class="w-full !h-9 !text-sm !bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 border-none" :loading="loading" :icon="VideoPlay" @click="handleBuild">
              开始自动化构建
            </el-button>
          </div>
        </div>

        <!-- ── 管理 Tab ── -->
        <div v-show="sidebarTab === 'manage'" class="flex-1 flex flex-col overflow-y-auto p-4 space-y-5">
          <!-- 社区筛选 -->
          <div class="kg-section rounded-xl p-4 border backdrop-blur-sm space-y-4">
            <div class="flex items-center gap-2 mb-2">
              <div class="w-1 h-4 bg-cyan-500 rounded-full shadow-[0_0_8px_rgba(6,182,212,0.5)]"></div>
              <h3 class="text-sm font-bold text-gray-300">数据筛选</h3>
            </div>
            <div class="space-y-1.5" :class="{ 'opacity-50 pointer-events-none': !selectedDatabase }">
              <label class="text-xs font-medium text-gray-500 ml-1">社区聚类</label>
              <el-select v-model="selectedCommunityId" placeholder="选择社区 (Cluster)" class="w-full custom-select" clearable size="large">
                <template #prefix><el-icon class="text-gray-400"><Connection /></el-icon></template>
                <el-option v-for="cId in communities" :key="cId" :label="'Community '+cId" :value="cId" />
              </el-select>
            </div>
          </div>

          <!-- 批量操作 -->
          <div class="kg-section rounded-xl p-4 border backdrop-blur-sm">
            <div class="flex items-center gap-2 mb-4">
              <div class="w-1 h-4 bg-purple-500 rounded-full shadow-[0_0_8px_rgba(168,85,247,0.5)]"></div>
              <h3 class="text-sm font-bold text-gray-300">批量操作</h3>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <el-button type="primary" plain :icon="Download" class="!w-full !h-10 !rounded-lg !border-gray-600 hover:!border-primary hover:!bg-primary/10" @click="handleExportDoc" :loading="loading" :disabled="!selectedDatabase">导出数据库</el-button>
              <el-button type="danger" plain :icon="Delete" class="!w-full !h-10 !rounded-lg !border-gray-600 hover:!border-danger hover:!bg-danger/10" @click="handleDeleteDoc" :loading="loading" :disabled="!selectedDatabase">清空数据库</el-button>
              <el-button type="warning" plain :icon="Brush" class="!w-full !h-10 !rounded-lg !border-gray-600 hover:!border-warning hover:!bg-warning/10" @click="handleCleanupVectors" :loading="loading">清理孤立数据</el-button>
              <el-button type="info" plain :icon="Refresh" class="!w-full !h-10 !rounded-lg !border-gray-600 hover:!border-info hover:!bg-info/10" @click="handleRefresh" :loading="loading">刷新图谱</el-button>
            </div>
          </div>

          <!-- Chunk状态 -->
          <div v-if="chunksStatus.summary" class="kg-section rounded-xl p-4 border backdrop-blur-sm">
            <div class="flex items-center gap-2 mb-3">
              <div class="w-1 h-4 bg-green-500 rounded-full"></div>
              <h3 class="text-sm font-bold text-gray-300">Chunk 状态</h3>
            </div>
            <div class="text-xs text-gray-400 space-y-1">
              <div>向量化: {{ chunksStatus.vectorized_chunks }}</div>
              <div>孤立: {{ chunksStatus.orphaned_chunks }}</div>
              <div class="text-[11px]">{{ chunksStatus.summary }}</div>
            </div>
          </div>
        </div>

        <!-- ── 编辑 Tab ── -->
        <div v-show="sidebarTab === 'edit'" class="flex-1 flex flex-col overflow-hidden p-4">
          <div v-if="selectedElement" class="flex-1 flex flex-col overflow-hidden space-y-3">
            <div class="kg-edit-notice flex-none flex items-center gap-2 text-xs p-2 rounded border">
              <el-icon><Edit /></el-icon>
              <span>正在编辑: {{ selectedType === 'node' ? '节点' : '关系' }}</span>
              <el-tag v-if="selectedElement" size="small" effect="dark" class="kg-tag font-mono ml-auto">
                {{ selectedType === 'node' ? 'NODE' : 'LINK' }}
              </el-tag>
            </div>

            <!-- 基本信息 -->
            <div class="kg-info-card p-3 rounded-lg border space-y-2 flex-none">
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

            <div class="flex-none flex justify-between items-center">
              <span class="text-xs font-bold text-gray-400 uppercase">属性列表</span>
              <el-button size="small" text bg @click="handleAddProperty"><el-icon class="mr-1"><Plus /></el-icon> 添加</el-button>
            </div>

            <el-form :model="editForm" label-position="top" size="default" class="custom-form flex-1 flex flex-col overflow-hidden">
              <div class="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-3">
                <div v-for="(value, key) in editForm.properties" :key="key">
                  <el-form-item :label="String(key)" class="!mb-0">
                    <el-select v-if="key === 'type'" v-model="editForm.properties[key]" filterable allow-create default-first-option placeholder="选择类型" class="w-full">
                      <el-option label="人物 (PERSON)" value="PERSON" />
                      <el-option label="组织 (ORGANIZATION)" value="ORGANIZATION" />
                      <el-option label="地点 (LOCATION)" value="LOCATION" />
                      <el-option label="物品 (ITEM)" value="ITEM" />
                      <el-option label="技能 (SKILL)" value="SKILL" />
                      <el-option label="事件 (EVENT)" value="EVENT" />
                      <el-option label="概念 (CONCEPT)" value="CONCEPT" />
                      <el-option label="未知 (UNKNOWN)" value="UNKNOWN" />
                    </el-select>
                    <el-input v-else-if="['created_at', 'doc_id', 'vec_id', 'element_id'].includes(String(key))" :model-value="key === 'created_at' ? formatTime(editForm.properties[key]) : editForm.properties[key]" disabled class="!opacity-60" />
                    <el-input v-else v-model="editForm.properties[key]" />
                  </el-form-item>
                </div>
                <div v-if="Object.keys(editForm.properties).length === 0" class="kg-info-card text-gray-500 text-xs text-center py-8 rounded-lg border border-dashed">该元素没有可编辑的属性</div>
              </div>
              <div class="flex-none mt-4 pt-2 border-t border-gray-700/30 flex gap-3">
                <el-button type="primary" class="flex-1 !h-10 !rounded-lg !font-medium shadow-lg shadow-primary/20" @click="handleSaveEdit" :loading="isEditing" :disabled="Object.keys(editForm.properties).length === 0">保存修改</el-button>
                <el-button type="danger" plain class="!w-10 !h-10 !rounded-lg !px-0" @click="handleDeleteElement" :loading="isEditing"><el-icon><Delete /></el-icon></el-button>
              </div>
            </el-form>
          </div>

          <div v-else class="flex-1 flex flex-col items-center justify-center text-sm py-8 opacity-60">
            <div class="kg-empty-icon w-16 h-16 rounded-full flex items-center justify-center mb-3 border">
              <el-icon class="text-2xl text-gray-400"><Connection /></el-icon>
            </div>
            <p class="font-medium">点击图谱元素</p>
            <p class="text-xs mt-1 text-gray-600">在右侧视图中选择节点或连线进行编辑</p>
          </div>
        </div>

      </div><!-- end flex-1 tab-content -->
    </div><!-- end sidebar -->

    <!-- ═══ 右侧主区域 ═══ -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 顶部状态栏 -->
      <div class="kg-topbar h-14 border-b flex items-center px-6 justify-between">
        <el-steps :active="activeStep" finish-status="success" simple class="!bg-transparent flex-1 max-w-xl">
          <el-step v-for="step in steps" :key="step.title" :title="step.title" />
        </el-steps>
        <div class="flex gap-6 text-sm">
          <div class="flex flex-col items-end"><span class="text-gray-500 text-xs">Nodes</span><span class="font-mono font-bold text-cyan-400">{{ stats.nodes }}</span></div>
          <div class="flex flex-col items-end"><span class="text-gray-500 text-xs">Edges</span><span class="font-mono font-bold text-purple-400">{{ stats.edges }}</span></div>
          <div class="flex flex-col items-end"><span class="text-gray-500 text-xs">Communities</span><span class="font-mono font-bold text-green-400">{{ stats.communities }}</span></div>
        </div>
      </div>

      <!-- 主视图区域 -->
      <div class="flex-1 relative">
        <!-- 视图切换浮层 -->
        <div class="absolute top-4 left-4 z-10 flex gap-2 items-center">
          <button class="kg-view-btn px-3 py-1.5 rounded-md text-sm backdrop-blur-md border transition-all" :class="{ 'is-active': activeView === 'graph' }" @click="activeView = 'graph'">
            <el-icon class="mr-1 align-text-bottom"><Connection /></el-icon>图谱预览
          </button>
          <button class="kg-view-btn px-3 py-1.5 rounded-md text-sm backdrop-blur-md border transition-all" :class="{ 'is-active': activeView === 'logs' }" @click="activeView = 'logs'">
            <el-icon class="mr-1 align-text-bottom"><List /></el-icon>执行日志
          </button>
          <button class="kg-icon-btn px-3 py-1.5 rounded-md text-sm backdrop-blur-md border transition-all" @click="initGraph">
            <el-icon><RefreshRight /></el-icon>
          </button>
        </div>

        <!-- Graph View -->
        <div v-show="activeView === 'graph'" class="kg-graph-view w-full h-full" ref="graphContainer"></div>

        <!-- Logs View -->
        <div v-show="activeView === 'logs'" class="kg-logs-view w-full h-full p-6 overflow-y-auto font-mono text-sm">
          <div v-if="logs.length === 0" class="h-full flex items-center justify-center text-gray-600">
            <div class="text-center"><el-icon class="text-4xl mb-2"><Monitor /></el-icon><p>等待任务开始...</p></div>
          </div>
          <div v-else class="space-y-2">
            <div v-for="(log, i) in logs" :key="i" class="kg-log-row border-l-2 pl-3 py-1 transition-colors">
              <span class="text-gray-500 mr-2">{{ log.split(']')[0] }}]</span>
              <span :class="log.includes('错误') ? 'text-red-400' : 'text-gray-300'">{{ log.split(']')[1] }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading Overlay -->
    <div v-if="loading" class="kg-loading-overlay absolute inset-0 flex items-center justify-center backdrop-blur-sm z-30">
      <div class="kg-loading-card flex flex-col items-center p-6 rounded-xl border shadow-2xl">
        <div class="loading-spinner mb-4"></div>
        <span class="text-cyan-400 font-medium tracking-wider">正在处理...</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
:global(:root) {
  --kg-page-bg: radial-gradient(circle at top left, rgba(59,130,246,0.05), transparent 26%), linear-gradient(180deg, #f7f8fa, #eef2f7 72%);
  --kg-sidebar-bg: linear-gradient(180deg, rgba(250,251,253,0.96), rgba(244,247,251,0.96));
  --kg-sidebar-border: rgba(148,163,184,0.18);
  --kg-header-bg: linear-gradient(90deg, rgba(248,250,252,0.92), rgba(238,242,247,0.98));
  --kg-title: #0f172a;
  --kg-section-bg: rgba(255,255,255,0.74);
  --kg-section-border: rgba(148,163,184,0.18);
  --kg-info-bg: rgba(248,250,252,0.88);
  --kg-info-border: rgba(148,163,184,0.2);
  --kg-tag-bg: rgba(226,232,240,0.92);
  --kg-tag-border: rgba(148,163,184,0.28);
  --kg-tag-text: #334155;
  --kg-edit-bg: rgba(14,165,233,0.08);
  --kg-edit-border: rgba(14,165,233,0.2);
  --kg-edit-text: #0369a1;
  --kg-empty-bg: rgba(248,250,252,0.8);
  --kg-empty-border: rgba(148,163,184,0.2);
  --kg-graph-bg: linear-gradient(180deg, rgba(247,249,252,0.96), rgba(239,244,250,1));
  --kg-overlay-bg: rgba(241,245,249,0.72);
  --kg-overlay-card-bg: rgba(255,255,255,0.9);
  --kg-overlay-card-border: rgba(148,163,184,0.22);
  --kg-input-bg: rgba(255,255,255,0.82);
  --kg-input-border: rgba(148,163,184,0.32);
  --kg-input-border-hover: rgba(100,116,139,0.44);
  --kg-input-focus-bg: #ffffff;
  --kg-input-text: #334155;
  --kg-label: #64748b;
  --kg-tab-bg: transparent;
  --kg-tab-active-bg: rgba(14,165,233,0.1);
  --kg-tab-active-border: #06b6d4;
  --kg-tab-active-text: #0369a1;
  --kg-tab-text: #64748b;
  --kg-switch-bg: rgba(226,232,240,0.72);
  --kg-switch-active-bg: rgba(255,255,255,0.94);
  --kg-switch-active-text: #0f172a;
  --kg-switch-shadow: 0 8px 18px rgba(15,23,42,0.08);
  --kg-shell-bg: rgba(255,255,255,0.72);
  --kg-shell-hover: rgba(255,255,255,0.88);
  --kg-upload-bg: rgba(248,250,252,0.68);
  --kg-upload-hover: rgba(239,246,255,0.9);
  --kg-btn-bg: rgba(255,255,255,0.8);
  --kg-btn-active-bg: rgba(14,165,233,0.1);
  --kg-btn-active-border: rgba(14,165,233,0.32);
  --kg-btn-active-text: #0369a1;
  --kg-logs-bg: rgba(248,250,252,0.94);
  --kg-log-hover: rgba(226,232,240,0.58);
}

:global(.dark) {
  --kg-page-bg: #050505;
  --kg-sidebar-bg: #0f1115;
  --kg-sidebar-border: rgba(31,41,55,0.9);
  --kg-header-bg: linear-gradient(to right, rgb(17,24,39), rgb(31,41,55));
  --kg-title: #ffffff;
  --kg-section-bg: rgba(31,41,55,0.4);
  --kg-section-border: rgba(55,65,81,0.5);
  --kg-info-bg: rgba(17,24,39,0.5);
  --kg-info-border: rgba(55,65,81,0.5);
  --kg-tag-bg: rgb(17,24,39);
  --kg-tag-border: rgb(55,65,81);
  --kg-tag-text: #e5e7eb;
  --kg-edit-bg: rgba(8,47,73,0.3);
  --kg-edit-border: rgba(8,47,73,0.5);
  --kg-edit-text: #22d3ee;
  --kg-empty-bg: rgba(31,41,55,0.5);
  --kg-empty-border: rgba(55,65,81,0.5);
  --kg-graph-bg: #050505;
  --kg-overlay-bg: rgba(0,0,0,0.6);
  --kg-overlay-card-bg: rgb(17,24,39);
  --kg-overlay-card-border: rgba(31,41,55,0.9);
  --kg-input-bg: rgba(17,24,39,0.8);
  --kg-input-border: rgba(75,85,99,0.4);
  --kg-input-border-hover: rgba(107,114,128,0.8);
  --kg-input-focus-bg: rgba(31,41,55,1);
  --kg-input-text: #e5e7eb;
  --kg-label: #9ca3af;
  --kg-tab-active-bg: rgba(6,182,212,0.15);
  --kg-tab-active-border: #06b6d4;
  --kg-tab-active-text: #67e8f9;
  --kg-tab-text: #6b7280;
  --kg-switch-bg: rgba(31,41,55,0.5);
  --kg-switch-active-bg: rgba(55,65,81,1);
  --kg-switch-active-text: #ffffff;
  --kg-switch-shadow: 0 8px 18px rgba(0,0,0,0.2);
  --kg-shell-bg: rgba(17,24,39,0.3);
  --kg-shell-hover: rgba(17,24,39,0.5);
  --kg-upload-bg: rgba(31,41,55,0.2);
  --kg-upload-hover: rgba(31,41,55,0.3);
  --kg-btn-bg: rgba(17,24,39,0.5);
  --kg-btn-active-bg: rgba(6,182,212,0.2);
  --kg-btn-active-border: rgba(6,182,212,0.5);
  --kg-btn-active-text: #67e8f9;
  --kg-logs-bg: #0c0c0c;
  --kg-log-hover: rgba(17,24,39,0.5);
}

/* Layout */
.kg-page { background: var(--kg-page-bg); color: var(--kg-input-text); }
.kg-sidebar { background: var(--kg-sidebar-bg); border-right-color: var(--kg-sidebar-border) !important; }
.kg-sidebar__header { background: var(--kg-header-bg); border-bottom-color: var(--kg-sidebar-border) !important; }
.kg-sidebar__header h2 { color: var(--kg-title) !important; }

/* Tabs */
.kg-tab-bar { background: var(--kg-header-bg); border-bottom-color: var(--kg-sidebar-border) !important; }
.kg-tab { color: var(--kg-tab-text); border-bottom: 2px solid transparent; }
.kg-tab:hover { color: var(--kg-input-text); }
.kg-tab.is-active { color: var(--kg-tab-active-text); border-bottom-color: var(--kg-tab-active-border); background: var(--kg-tab-active-bg); }

/* Sections */
.kg-section { background: var(--kg-section-bg); border-color: var(--kg-section-border) !important; }
.kg-info-card { background: var(--kg-info-bg); border-color: var(--kg-info-border) !important; }
.kg-tag { background: var(--kg-tag-bg) !important; border-color: var(--kg-tag-border) !important; color: var(--kg-tag-text) !important; }
.kg-edit-notice { background: var(--kg-edit-bg); border-color: var(--kg-edit-border) !important; color: var(--kg-edit-text); }
.kg-empty-icon { background: var(--kg-empty-bg); border-color: var(--kg-empty-border) !important; }

/* Source switch */
.kg-source-switch { background: var(--kg-switch-bg); }
.kg-source-btn { color: var(--kg-label); }
.kg-source-btn:hover { color: var(--kg-input-text); }
.kg-source-btn.is-active { background: var(--kg-switch-active-bg); color: var(--kg-switch-active-text); box-shadow: var(--kg-switch-shadow); }

/* Text shell / Upload */
.kg-text-shell { background: var(--kg-shell-bg); border-color: var(--kg-input-border) !important; }
.kg-text-shell:hover, .kg-text-shell:focus-within { background: var(--kg-shell-hover); }
.kg-upload-zone { background: var(--kg-upload-bg); border-color: var(--kg-input-border) !important; color: var(--kg-label); }
.kg-upload-zone:hover { background: var(--kg-upload-hover); border-color: rgba(6,182,212,0.4) !important; }

/* Graph / Logs */
.kg-topbar { background: var(--kg-header-bg); border-bottom-color: var(--kg-sidebar-border) !important; }
.kg-graph-view { background: var(--kg-graph-bg); }
.kg-logs-view { background: var(--kg-logs-bg); }
.kg-log-row { border-left-color: var(--kg-sidebar-border) !important; }
.kg-log-row:hover { background: var(--kg-log-hover); }

/* View buttons */
.kg-view-btn, .kg-icon-btn { background: var(--kg-btn-bg); border-color: var(--kg-input-border) !important; color: var(--kg-label); }
.kg-view-btn:hover, .kg-icon-btn:hover { color: var(--kg-input-text); }
.kg-view-btn.is-active { background: var(--kg-btn-active-bg); border-color: var(--kg-btn-active-border) !important; color: var(--kg-btn-active-text); }

/* Loading */
.kg-loading-overlay { background: var(--kg-overlay-bg); }
.kg-loading-card { background: var(--kg-overlay-card-bg); border-color: var(--kg-overlay-card-border) !important; }

.loading-spinner { width: 40px; height: 40px; border: 3px solid rgba(6,182,212,0.3); border-radius: 50%; border-top-color: #06b6d4; animation: spin 1s ease-in-out infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Scrollbar */
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background-color: rgba(75,85,99,0.5); border-radius: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background-color: rgba(107,114,128,0.8); }

/* Element Plus Overrides */
.custom-select :deep(.el-input__wrapper) { background-color: var(--kg-input-bg); box-shadow: none !important; border: 1px solid var(--kg-input-border); transition: all 0.3s; }
.custom-select :deep(.el-input__wrapper:hover) { border-color: var(--kg-input-border-hover); }
.custom-select :deep(.el-input__wrapper.is-focus) { border-color: #06b6d4; background-color: var(--kg-input-focus-bg); box-shadow: 0 0 0 1px #06b6d4 !important; }
.custom-select :deep(.el-input__inner) { color: var(--kg-input-text); font-weight: 500; }

.custom-input :deep(.el-input__wrapper) { background-color: var(--kg-input-bg); box-shadow: none; border: 1px solid var(--kg-input-border); }
.custom-input :deep(.el-input__wrapper.is-focus) { border-color: #06b6d4; box-shadow: 0 0 0 1px #06b6d4; }

.custom-textarea :deep(.el-textarea__inner) { background-color: transparent; box-shadow: none; border: none; color: var(--kg-input-text); padding: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.custom-textarea :deep(.el-textarea__inner:focus) { box-shadow: none; }

.custom-form :deep(.el-form-item__label) { color: var(--kg-label); font-size: 0.75rem; padding-bottom: 4px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
.custom-form :deep(.el-input__wrapper) { background-color: var(--kg-input-bg); box-shadow: none; border: 1px solid var(--kg-input-border); border-radius: 6px; }
.custom-form :deep(.el-input__wrapper.is-focus) { border-color: #06b6d4; background-color: var(--kg-input-focus-bg); box-shadow: 0 0 0 1px #06b6d4; }

:deep(.el-upload-dragger) { background-color: transparent; border: none; }
</style>
