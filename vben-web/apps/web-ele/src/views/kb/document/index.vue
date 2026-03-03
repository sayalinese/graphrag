<script setup lang="ts">
import { ref, onMounted, watch, computed, defineAsyncComponent } from "vue";
import { useRoute } from "vue-router";
import { 
  ElMessage, 
  ElMessageBox,
  ElCard,
  ElSelect,
  ElOption,
  ElButton,
  ElIcon,
  ElTable,
  ElTableColumn,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInputNumber,
  ElRadioGroup,
  ElRadio,
  ElDivider,
  ElSwitch,
  ElSlider,
  ElTag,
  ElDrawer,
  ElTabs,
  ElTabPane
} from "element-plus";
import { 
  listKnowledgeBases, 
  listDocuments, 
  deleteDocument, 
  batchDeleteDocuments,
  uploadDocument,
  previewDocumentSplit,
  getDocumentChunks,
  getDocumentContent,
  deduplicateDocument,
  type KnowledgeBaseVO,
  type DocumentVO
} from "../management/utils/api";
import { Plus, Delete, Loading, Refresh, Warning } from "@element-plus/icons-vue";
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import 'highlight.js/styles/atom-one-light.css';

// 引入 VueOffice 组件
import VueOfficeDocx from '@vue-office/docx';
import '@vue-office/docx/lib/index.css';
import VueOfficeExcel from '@vue-office/excel';
import '@vue-office/excel/lib/index.css';

const md = new MarkdownIt({
  html: true,
  breaks: true,
  linkify: true,
  highlight: (str: string, lang: string) => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${
          hljs.highlight(str, { language: lang, ignoreIllegals: true }).value
        }</code></pre>`;
      } catch (__) {}
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`;
  }
});

defineOptions({ name: "KnowledgeDocument" });

// Use DocumentVO directly
type DocRow = DocumentVO;

const tableData = ref<DocRow[]>([]);
const loading = ref(false);
const route = useRoute();

const knowledgeOptions = ref<KnowledgeBaseVO[]>([]);
const selectedKbId = ref<number | undefined>(undefined);
const multipleSelection = ref<DocRow[]>([]);

// 切分块抽屉（调试观测）
const chunksDrawerVisible = ref(false);
const chunksLoading = ref(false);
const chunks = ref<any[]>([]);
const chunksTotal = ref(0);
const chunksLimit = ref(20);
const chunksOffset = ref(0);

const loadChunks = async (reset = false) => {
  if (!currentChunkDocId.value) return;
  chunksLoading.value = true;
  if (reset) {
    chunks.value = [];
    chunksOffset.value = 0;
  }
  try {
    const res = await getDocumentChunks(
      String(currentChunkDocId.value), 
      Math.floor(chunksOffset.value / chunksLimit.value) + 1, 
      chunksLimit.value
    );
    if (reset) {
      chunks.value = res.items;
    } else {
      chunks.value.push(...res.items);
    }
    chunksTotal.value = res.total;
  } catch (e: any) {
    ElMessage.error(e.message || "加载切片失败");
  } finally {
    chunksLoading.value = false;
  }
};

// 当前是否按单个文档过滤（文档切分块查看）
const currentChunkDocId = ref<string | null>(null);
const currentChunkDocName = ref<string>("");
const currentChunkDocContent = ref<string>("");
const currentChunkDocType = ref<string>(""); // 文件类型：pdf, docx, txt 等
const pdfFileUrl = ref<string>(""); // PDF 文件 URL 用于 vue-pdf

// 上传配置弹窗
const uploadConfigVisible = ref(false);
const useMineruUpload = ref(false);
type UploadMode = 'auto' | 'manual';
const uploadMode = ref<UploadMode>('auto');
// 自动模式：固定 600/120
const AUTO_CHUNK_SIZE = 512;
const AUTO_CHUNK_OVERLAP = 120;
// 手动模式参数
const manualChunkSize = ref(600);
const manualChunkOverlap = ref(120);
const uploading = ref(false);

const fileInputRef = ref<HTMLInputElement | null>(null);
// 语义切分控制（默认开启）
const semanticEnabled = ref(true);
const semanticThreshold = ref(0.6);
// 清洗无效块（仅标点/噪声等）
const cleanInvalid = ref(false);

// --- 预上传切分预览新增状态 ---
const pendingFile = ref<File | null>(null);
const splitPreviewLoading = ref(false);
const splitPreviewData = ref<any | null>(null);
const splitChunks = ref<any[]>([]);
const previewDirty = ref(false);
const previewError = ref("");
const activeChunkIndex = ref<number | null>(null);

function resetPreviewState() {
  pendingFile.value = null;
  splitPreviewLoading.value = false;
  splitPreviewData.value = null;
  splitChunks.value = [];
  previewDirty.value = false;
  previewError.value = "";
  activeChunkIndex.value = null;
}

const openUploadDialog = () => {
  if (!selectedKbId.value) {
    ElMessage.warning('请先选择知识库');
    return;
  }
  useMineruUpload.value = false;
  uploadMode.value = 'auto';
  manualChunkSize.value = AUTO_CHUNK_SIZE;
  manualChunkOverlap.value = AUTO_CHUNK_OVERLAP;
  semanticEnabled.value = true;
  semanticThreshold.value = 0.6;
  cleanInvalid.value = false;
  resetPreviewState();
  uploadConfigVisible.value = true;
};

const onManualSizeChange = (val: number | undefined) => {
  if (val === undefined) return;
  if (manualChunkOverlap.value >= val) {
    manualChunkOverlap.value = Math.max(0, val - 1);
  }
};
const onManualOverlapChange = (val: number | undefined) => {
  if (val === undefined) return;
  if (manualChunkSize.value <= val) {
    manualChunkSize.value = val + 1;
  }
};

const triggerFilePick = () => fileInputRef.value?.click();

const doUploadWithConfig = async (file: File) => {
  if (!selectedKbId.value) return;
  uploading.value = true;
  try {
    await uploadDocument(selectedKbId.value, file, {
      split_mode: uploadMode.value === 'auto' ? 'smart' : 'simple',
      chunk_size: manualChunkSize.value,
      overlap: manualChunkOverlap.value
    });
    ElMessage.success('文件已上传成功！现在正在后台进行向量化处理，请稍候...');
    uploadConfigVisible.value = false;
    await loadDocs();
  } catch (e: any) {
    ElMessage.error(e?.message || '上传失败');
  } finally {
    uploading.value = false;
  }
};

const onFileSelected = async (e: Event) => {
  const t = e.target as HTMLInputElement;
  const f = t.files?.[0];
  if (!f) return;
  pendingFile.value = f;
  previewDirty.value = false;
  await generateSplitPreview();
  if (fileInputRef.value) fileInputRef.value.value = '';
};

async function generateSplitPreview() {
  if (!pendingFile.value) return;
  splitPreviewLoading.value = true;
  splitPreviewData.value = null;
  splitChunks.value = [];
  previewError.value = "";
  try {
    const res = await previewDocumentSplit(pendingFile.value, {
      split_mode: uploadMode.value === 'auto' ? 'smart' : 'simple', // 简单映射
      chunk_size: manualChunkSize.value,
      overlap: manualChunkOverlap.value
    });
    splitPreviewData.value = res;
    splitChunks.value = res.chunks || [];
    previewDirty.value = false;
  } catch (e: any) {
    previewError.value = e.message || "预览失败";
  } finally {
    splitPreviewLoading.value = false;
  }
}

async function confirmUpload() {
  if (!pendingFile.value) {
    ElMessage.warning('请选择文件');
    return;
  }
  // if (previewDirty.value) { ... }
  await doUploadWithConfig(pendingFile.value);
}

watch([
  manualChunkSize,
  manualChunkOverlap,
  semanticEnabled,
  semanticThreshold,
  cleanInvalid,
  uploadMode
], () => {
  if (splitPreviewData.value) previewDirty.value = true;
});

// ===== 向量库去重 =====
const dedupeDialogVisible = ref(false);
const dedupeScopeDoc = ref(false); // 仅对选中文档
const deduping = ref(false);
const canDocScope = computed(() => multipleSelection.value.length === 1);
const selectedDocForDedupe = computed(() => canDocScope.value ? multipleSelection.value[0] : null);

const openDedupeDialog = () => {
  if (multipleSelection.value.length === 0) {
    ElMessage.warning("请先选择文档");
    return;
  }
  dedupeScopeDoc.value = multipleSelection.value.length === 1;
  dedupeDialogVisible.value = true;
};

const runDedupe = async () => {
  if (!selectedDocForDedupe.value) {
    ElMessage.warning("目前仅支持单文档去重");
    return;
  }
  deduping.value = true;
  try {
    const res = await deduplicateDocument(String(selectedDocForDedupe.value.doc_id));
    ElMessage.success(`去重完成，移除了 ${res.removed_count} 个重复块`);
    dedupeDialogVisible.value = false;
    await loadDocs();
  } catch (e: any) {
    ElMessage.error(e.message || "去重失败");
  } finally {
    deduping.value = false;
  }
};

const handleDelete = (row: DocRow) => {
  if (!row.doc_id) return; // DocumentVO uses doc_id
  ElMessageBox.confirm(`确定要删除文档 ${row.filename} 吗？`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    doDelete(row.doc_id!);
  });
};

const handleSelectionChange = (selection: DocRow[]) => {
  multipleSelection.value = selection;
};

const handleBatchDelete = () => {
  if (multipleSelection.value.length === 0) {
    ElMessage.warning('请先选择要删除的文档');
    return;
  }
  
  ElMessageBox.confirm(`确定要删除所选的 ${multipleSelection.value.length} 个文档吗？`, "批量删除", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    doBatchDelete();
  });
};

async function doBatchDelete() {
  if (!selectedKbId.value) return;
  try {
    const docIds = multipleSelection.value.map(row => row.doc_id).filter(id => id !== undefined) as string[];
    if (docIds.length === 0) return;
    const result = await batchDeleteDocuments(selectedKbId.value, docIds);
    ElMessage.success(`成功删除 ${result.deleted.length} 个文档`);
    if (result.failed.length > 0) {
      ElMessage.warning(`${result.failed.length} 个文档删除失败`);
    }
    await loadDocs();
  } catch (e: any) {
    ElMessage.error(e?.message || "批量删除失败");
  }
}

async function loadKBs() {
  const { knowledge_bases } = await listKnowledgeBases(1000);
  knowledgeOptions.value = knowledge_bases;
}

async function loadDocs() {
  if (!selectedKbId.value) return;
  loading.value = true;
  try {
    const { documents } = await listDocuments(selectedKbId.value);
    tableData.value = documents;
    
    // 如果有向量化中的文档，定时轮询状态更新
    const indexingDocs = documents.filter(d => d.status === 'indexing');
    if (indexingDocs.length > 0) {
      setTimeout(() => loadDocs(), 2000); // 2秒后重新加载
    }
  } finally {
    loading.value = false;
  }
}

async function doDelete(docId: string) {
  if (!selectedKbId.value) return;
  try {
    await deleteDocument(selectedKbId.value, docId);
    ElMessage.success("删除成功");
    await loadDocs();
  } catch (e: any) {
    ElMessage.error(e?.message || "删除失败");
  }
}

watch(
  () => route.query.kb_id,
  val => {
    const kb = Number(val);
    if (kb) selectedKbId.value = kb;
    loadDocs();
  },
  { immediate: true }
);

onMounted(async () => {
  await loadKBs();
  const kbFromQuery = Number(route.query.kb_id);
  if (kbFromQuery) selectedKbId.value = kbFromQuery;
  await loadDocs();
});

const loadMoreChunks = async () => {
  if (chunksLoading.value || chunks.value.length >= chunksTotal.value) return;
  chunksOffset.value += chunksLimit.value;
  await loadChunks(false);
};

// 行操作：查看该文档的切分块
const openDocChunks = async (row: DocRow) => {
  if (!row.doc_id || !selectedKbId.value) return;
  currentChunkDocId.value = row.doc_id;
  currentChunkDocName.value = row.filename;
  currentChunkDocType.value = row.file_type || '';
  
  // 对于 PDF, Word, Excel, DOC，生成访问 URL（使用文件服务端点）
  if (['pdf', 'docx', 'xlsx', 'xls', 'doc'].includes(currentChunkDocType.value)) {
    pdfFileUrl.value = `/api/kb/${selectedKbId.value}/document/${row.doc_id}/file`;
  }
  
  // 获取文档原文内容（仅对非二进制文件，或者作为后备）
  if (!['pdf', 'docx', 'xlsx', 'xls', 'doc'].includes(currentChunkDocType.value)) {
    try {
      currentChunkDocContent.value = await getDocumentContent(selectedKbId.value, row.doc_id);
    } catch (e: any) {
      ElMessage.warning('获取原文内容失败：' + (e.message || '未知错误'));
      currentChunkDocContent.value = '[原文预览加载失败]';
    }
  } else {
    // 对于二进制文件，清空内容，避免显示旧数据
    currentChunkDocContent.value = '';
  }
  
  chunksDrawerVisible.value = true;
  chunksOffset.value = 0;
  await loadChunks(true);
};
</script>

<template>
  <div class="p-4">
    <ElCard>
      <template #header>
        <div class="flex justify-between items-center">
          <div>
            <h2 class="text-lg font-medium text-gray-800">文档管理</h2>
            <p class="text-sm text-gray-500 mt-1">管理知识库中的各类文档文件</p>
          </div>
        </div>
      </template>

      <!-- 顶部工具：选择知识库 + 上传 -->
      <div class="flex items-center mb-4 gap-3 justify-between">
        <div class="flex items-center gap-3">
          <ElSelect v-model="selectedKbId" placeholder="请选择知识库" style="width: 260px" @change="loadDocs">
            <ElOption v-for="kb in knowledgeOptions" :key="kb.id" :label="kb.name" :value="kb.id!" />
          </ElSelect>
          <ElButton type="primary" :disabled="!selectedKbId" @click="openUploadDialog">
            <ElIcon class="mr-1"><Plus /></ElIcon> 上传文档
          </ElButton>
          
          <input
            ref="fileInputRef"
            type="file"
            accept=".pdf,.doc,.docx,.xlsx,.xls,.txt,.md,.html,.htm"
            style="display:none"
            @change="onFileSelected"
          />
          
          <ElButton 
            type="danger" 
            :disabled="multipleSelection.length === 0"
            @click="handleBatchDelete"
          >
            <ElIcon class="mr-1"><Delete /></ElIcon> 批量删除
          </ElButton>

          <ElButton 
            :disabled="!selectedKbId"
            @click="openDedupeDialog"
          >
            清理/去重
          </ElButton>
        </div>

        <ElButton 
          :disabled="!selectedKbId"
          @click="loadDocs"
          :loading="loading"
        >
          <ElIcon class="mr-1"><Refresh /></ElIcon> 刷新
        </ElButton>
      </div>

      <ElTable
        :data="tableData"
        v-loading="loading"
        class="w-full"
        border
        @selection-change="handleSelectionChange"
      >
        <ElTableColumn type="selection" width="55" />
        <ElTableColumn prop="doc_id" label="ID" width="140" />
        <ElTableColumn prop="filename" label="文件名" min-width="240" />
        <ElTableColumn prop="status" label="状态" width="120">
          <template #default="{ row }">
            <ElTag 
              :type="row.status === 'completed' ? 'success' : (row.status === 'failed' ? 'danger' : 'info')"
            >
              {{ row.status === 'completed' ? '已完成' : (row.status === 'failed' ? '失败' : row.status === 'indexing' ? '向量化中...' : '处理中...') }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="created_at" label="上传时间" width="200">
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '-' }}
          </template>
        </ElTableColumn>
        <ElTableColumn prop="updated_at" label="更新时间" width="200">
          <template #default="{ row }">
            {{ row.updated_at ? new Date(row.updated_at).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '-' }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <ElButton size="small" @click="openDocChunks(row)">
              切片
            </ElButton>
            <ElButton type="danger" size="small" @click="handleDelete(row)">
              删除
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <!-- 上传配置弹窗 -->
    <ElDialog v-model="uploadConfigVisible" title="上传文档" width="800px" :close-on-click-modal="false">
      <div class="flex gap-5 h-[500px]">
        <!-- 左侧配置 -->
        <div class="w-[320px] shrink-0 flex flex-col gap-4 overflow-y-auto pr-2">
          <ElForm label-width="100px" label-position="left">
            <ElFormItem label="文件">
              <div class="flex gap-2 flex-wrap items-center">
                <ElButton type="primary" :disabled="uploading" @click="triggerFilePick" plain size="small">
                  {{ pendingFile ? '重新选择' : '选择文件' }}
                </ElButton>
                <div v-if="pendingFile" class="text-xs text-gray-500 max-w-[180px] truncate">
                  {{ pendingFile.name }}
                </div>
              </div>
            </ElFormItem>

            <ElFormItem label="切分模式">
              <ElRadioGroup v-model="uploadMode">
                <ElRadio label="auto" value="auto">自动 (Smart)</ElRadio>
                <ElRadio label="manual" value="manual">手动 (Simple)</ElRadio>
              </ElRadioGroup>
            </ElFormItem>

            <template v-if="uploadMode === 'manual'">
              <ElFormItem label="块大小">
                <ElInputNumber v-model="manualChunkSize" :min="50" :max="2000" :step="50" @change="onManualSizeChange" size="small" />
              </ElFormItem>
              <ElFormItem label="重叠大小">
                <ElInputNumber v-model="manualChunkOverlap" :min="0" :max="500" :step="10" @change="onManualOverlapChange" size="small" />
              </ElFormItem>
            </template>

            <ElDivider content-position="left">高级设置</ElDivider>
            
            <ElFormItem label="语义切分">
              <ElSwitch v-model="semanticEnabled" />
            </ElFormItem>
            <ElFormItem label="语义阈值" v-if="semanticEnabled">
              <ElSlider v-model="semanticThreshold" :min="0.1" :max="1.0" :step="0.05" size="small" />
            </ElFormItem>
            <ElFormItem label="清洗无效块">
              <ElSwitch v-model="cleanInvalid" />
            </ElFormItem>
          </ElForm>

          <div class="mt-auto">
             <ElButton type="primary" class="w-full" :disabled="!pendingFile || uploading" :loading="uploading" @click="confirmUpload">
                {{ uploading ? '正在入库...' : '确认上传并入库' }}
             </ElButton>
          </div>
        </div>

        <!-- 右侧预览 -->
        <div class="flex-1 border-l border-gray-200 pl-5 flex flex-col overflow-hidden">
          <div class="mb-2 font-bold flex justify-between items-center">
            <span>切分预览</span>
            <ElTag v-if="splitPreviewData" size="small" type="success">预计 {{ splitChunks.length }} 块</ElTag>
          </div>
          
          <div v-if="splitPreviewLoading" class="flex-1 flex items-center justify-center text-gray-400">
            <ElIcon class="is-loading mr-1"><Loading /></ElIcon> 生成预览中...
          </div>
          <div v-else-if="previewError" class="flex-1 flex items-center justify-center text-red-500">
            {{ previewError }}
          </div>
          <div v-else-if="!pendingFile" class="flex-1 flex items-center justify-center text-gray-300">
            请先选择文件
          </div>
          <div v-else class="flex-1 overflow-y-auto bg-gray-50 dark:bg-[#121212] p-4 rounded border border-gray-200 dark:border-gray-700">
            <div 
              v-for="(chunk, idx) in splitChunks" 
              :key="idx"
              class="mb-3 p-3 rounded-lg border cursor-pointer transition-all"
              :class="[
                activeChunkIndex === idx 
                  ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/10' 
                  : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-[#1e1e1e] hover:bg-gray-50 dark:hover:bg-gray-900/50'
              ]"
              @click="activeChunkIndex = idx"
            >
              <div class="flex justify-between items-center mb-2 pb-2 border-b border-gray-100 dark:border-gray-700/50">
                <span class="text-xs font-mono text-gray-400">#{{ idx + 1 }}</span>
                <span class="text-xs text-gray-400">{{ chunk.length }} chars</span>
              </div>
              <div 
                class="markdown-body text-xs leading-relaxed text-gray-800 dark:text-gray-200 break-words"
                v-html="md.render(chunk.content || '')"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </ElDialog>

    <!-- 切分块查看抽屉 -->
    <ElDrawer v-model="chunksDrawerVisible" title="文档预览" size="90%">
      <div class="h-full flex flex-col">
        <div class="mb-4 flex justify-between items-center pb-3 border-b border-gray-200 dark:border-gray-700">
          <div>
            <span class="font-medium">文档：{{ currentChunkDocName }}</span>
            <span class="text-gray-500 ml-4">共 {{ chunksTotal }} 块</span>
          </div>
        </div>
        
        <!-- 左右分屏布局 -->
        <div class="flex-1 flex gap-4 overflow-hidden">
          <!-- 左侧：原文预览 -->
          <div class="w-1/2 flex flex-col border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <div class="px-4 py-3 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 font-medium text-sm flex justify-between items-center">
              <span>📄 原文预览 ({{ currentChunkDocType }})</span>
            </div>
            <div class="flex-1 overflow-hidden bg-white dark:bg-[#1e1e1e]">
              <!-- PDF 显示 -->
              <div v-if="currentChunkDocType === 'pdf'" class="h-full w-full relative group">
                <iframe 
                  :src="pdfFileUrl" 
                  class="w-full h-full border-none"
                  type="application/pdf"
                ></iframe>
                <div class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <a :href="pdfFileUrl" target="_blank" class="px-3 py-1 bg-blue-500 text-white text-xs rounded hover:bg-blue-600 no-underline">
                    在新窗口打开
                  </a>
                </div>
              </div>
              <!-- Word 文档 - 使用 VueOfficeDocx 预览 -->
              <div v-else-if="currentChunkDocType === 'docx'" class="h-full overflow-hidden">
                <VueOfficeDocx 
                  :src="pdfFileUrl"
                  class="h-full w-full"
                  @error="() => ElMessage.error('Word 预览失败，请尝试下载查看')"
                />
              </div>
              <!-- Excel 文档 - 使用 VueOfficeExcel 预览 -->
              <div v-else-if="['xlsx', 'xls'].includes(currentChunkDocType)" class="h-full overflow-hidden">
                <VueOfficeExcel 
                  :src="pdfFileUrl"
                  class="h-full w-full"
                  @error="() => ElMessage.error('Excel 预览失败，请尝试下载查看')"
                />
              </div>
              <!-- DOC 文档 - 提示不支持 -->
              <div v-else-if="currentChunkDocType === 'doc'" class="h-full flex flex-col items-center justify-center p-4 text-gray-500">
                <ElIcon class="text-4xl mb-2"><Warning /></ElIcon>
                <p>暂不支持 .doc 格式在线预览</p>
                <p class="text-xs mt-1">请下载后查看，或转换为 .docx 格式上传</p>
                <a :href="pdfFileUrl" target="_blank" class="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 no-underline text-sm">
                  下载文件
                </a>
              </div>
              <!-- TXT 文件 -->
              <div v-else-if="currentChunkDocType === 'txt'">
                <pre class="text-sm text-gray-800 dark:text-gray-200 font-mono bg-gray-100 dark:bg-gray-800 p-3 rounded overflow-x-auto">{{ currentChunkDocContent }}</pre>
              </div>
              <!-- Markdown 文件 -->
              <div v-else-if="currentChunkDocType === 'md' || currentChunkDocType === 'markdown'">
                <div 
                  class="markdown-body text-sm leading-relaxed text-gray-800 dark:text-gray-200"
                  v-html="md.render(currentChunkDocContent)"
                ></div>
              </div>
              <!-- 默认显示为原始文本 -->
              <div v-else>
                <pre class="text-sm text-gray-800 dark:text-gray-200 font-mono bg-gray-100 dark:bg-gray-800 p-3 rounded overflow-x-auto">{{ currentChunkDocContent }}</pre>
              </div>
            </div>
          </div>
          
          <!-- 右侧：切块预览 -->
          <div class="w-1/2 flex flex-col border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <div class="px-4 py-3 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 font-medium text-sm">
              ✂️ 切块预览 ({{ chunks.length }}/{{ chunksTotal }})
            </div>
            <div v-loading="chunksLoading" class="flex-1 overflow-y-auto p-4 bg-gray-50 dark:bg-[#121212]">
              <div 
                v-for="(item, index) in chunks" 
                :key="index"
                class="mb-4 p-4 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-[#1e1e1e] shadow-sm transition-colors hover:shadow-md"
              >
                <div class="flex justify-between items-center mb-3 pb-2 border-b border-gray-100 dark:border-gray-700/50">
                  <span class="text-xs font-mono text-gray-400 bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">Chunk #{{ chunksOffset + index + 1 }}</span>
                  <span class="text-xs text-gray-400">{{ item.content?.length || 0 }} chars</span>
                </div>
                <div 
                  class="markdown-body text-sm leading-relaxed text-gray-800 dark:text-gray-200 break-words"
                  v-html="md.render(item.content || '')"
                ></div>
              </div>
              <div v-if="chunks.length < chunksTotal" class="text-center mt-4 mb-2">
                <ElButton text bg size="small" @click="loadMoreChunks" :loading="chunksLoading">加载更多</ElButton>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ElDrawer>

    <!-- 去重弹窗 -->
    <ElDialog v-model="dedupeDialogVisible" title="文档去重" width="400px">
      <div class="py-2">
        <p>确定要对选中的文档进行去重吗？</p>
        <p class="text-xs text-gray-500 mt-2">
          去重操作将计算文档内所有切片的相似度，并移除重复内容。此操作不可逆。
        </p>
        <div v-if="selectedDocForDedupe" class="mt-3 font-bold">
          目标文档：{{ selectedDocForDedupe.filename }}
        </div>
      </div>
      <template #footer>
        <ElButton @click="dedupeDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="deduping" @click="runDedupe">开始去重</ElButton>
      </template>
    </ElDialog>

  </div>
</template>

<style lang="less">
/* Markdown Body Styles */
.markdown-body {
  h1, h2, h3, h4, h5, h6 {
    font-weight: 600;
    line-height: 1.25;
    margin-top: 1em;
    margin-bottom: 16px;
    color: #1f2937;
  }
  .dark & h1, .dark & h2, .dark & h3, .dark & h4, .dark & h5, .dark & h6 {
    color: #e5e7eb;
  }

  h1 { font-size: 1.5em; padding-bottom: 0.3em; border-bottom: 1px solid #e5e7eb; }
  h2 { font-size: 1.25em; padding-bottom: 0.3em; border-bottom: 1px solid #e5e7eb; }
  h3 { font-size: 1.1em; }
  
  .dark & h1, .dark & h2 { border-bottom-color: #374151; }

  p { margin-bottom: 10px; }
  
  ul, ol { padding-left: 2em; margin-bottom: 10px; }
  ul { list-style-type: disc; }
  ol { list-style-type: decimal; }

  blockquote {
    margin: 0 0 10px;
    padding: 0 1em;
    color: #6b7280;
    border-left: 0.25em solid #d1d5db;
  }
  .dark & blockquote {
    color: #9ca3af;
    border-left-color: #4b5563;
  }

  pre {
    background-color: #f3f4f6;
    border-radius: 6px;
    padding: 12px;
    overflow: auto;
    margin-bottom: 10px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    font-size: 0.9em;
  }
  .dark & pre {
    background-color: #1f2937;
  }

  code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    background-color: rgba(175, 184, 193, 0.2);
    padding: 0.2em 0.4em;
    border-radius: 6px;
    font-size: 85%;
  }
  pre code {
    background-color: transparent;
    padding: 0;
    border-radius: 0;
    font-size: 100%;
    color: inherit;
  }
  
  table {
    border-spacing: 0;
    border-collapse: collapse;
    margin-bottom: 10px;
    width: 100%;
    overflow: auto;
  }
  table th, table td {
    padding: 6px 13px;
    border: 1px solid #d0d7de;
  }
  .dark & table th, .dark & table td {
    border-color: #374151;
  }
  table tr:nth-child(2n) {
    background-color: #f6f8fa;
  }
  .dark & table tr:nth-child(2n) {
    background-color: #1f2937;
  }
}
</style>
