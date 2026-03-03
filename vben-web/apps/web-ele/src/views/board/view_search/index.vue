<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import {
  ElButton,
  ElCard,
  ElCol,
  ElDivider,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElRadio,
  ElRadioGroup,
  ElRow,
  ElSelect,
  ElSkeleton,
  ElSkeletonItem,
  ElSlider,
  ElTag,
  ElTooltip,
} from 'element-plus';
import {
  CopyDocument,
  DataLine,
  Document,
  Refresh,
  Search,
  Setting,
} from '@element-plus/icons-vue';
import { Page } from '@vben/common-ui';

import {
  bm25Search,
  getKBList,
  pgvectorSearch,
  type SearchResult,
  vectorSearch,
} from './api';

// 状态定义
const loading = ref(false);
const kbs = ref<{ id: number; name: string; description?: string }[]>([]);
const results = ref<SearchResult[]>([]);
const searchTime = ref(0);

// 表单数据
const form = reactive({
  kb_id: undefined as number | undefined,
  query: '',
  mode: 'hybrid' as 'hybrid' | 'rerank' | 'vector' | 'bm25',
  top_k: 5,
  threshold: 0.0,
  vector_weight: 0.5,
  bm25_weight: 0.5,
});

// 权重联动
const handleVectorWeightChange = (val: number) => {
  form.bm25_weight = parseFloat((1 - val).toFixed(2));
};
const handleBm25WeightChange = (val: number) => {
  form.vector_weight = parseFloat((1 - val).toFixed(2));
};

// 初始化（mock）
onMounted(async () => {
  try {
    const data = await getKBList();
    kbs.value = data;
    if (data.length > 0) {
      form.kb_id = data[0].id;
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('获取知识库列表失败', error);
    ElMessage.error('获取知识库列表失败');
  }
});

// 搜索处理（mock）
const handleSearch = async () => {
  if (!form.kb_id) {
    ElMessage.warning('请先选择知识库');
    return;
  }
  if (!form.query.trim()) {
    ElMessage.warning('请输入搜索内容');
    return;
  }

  loading.value = true;
  results.value = [];
  const start = performance.now();

  try {
    let data: SearchResult[] = [];

    if (form.mode === 'vector') {
      data = await vectorSearch(form.kb_id, form.query, form.top_k);
    } else if (form.mode === 'bm25') {
      data = await bm25Search(form.kb_id, form.query, form.top_k);
    } else {
      // hybrid or rerank
      data = await pgvectorSearch(form.kb_id, form.query, {
        top_k: form.top_k,
        mode: form.mode as 'hybrid' | 'rerank',
        vector_weight: form.vector_weight,
        bm25_weight: form.bm25_weight,
        threshold: form.threshold,
      });
    }

    results.value = data;
    searchTime.value = Math.round(performance.now() - start);
    if (data.length === 0) {
      ElMessage.info('未找到相关结果（Mock）');
    } else {
      ElMessage.success(`找到 ${data.length} 条结果（Mock），耗时 ${searchTime.value}ms`);
    }
  } catch (error: any) {
    // eslint-disable-next-line no-console
    console.error('搜索失败', error);
    ElMessage.error(error.message || '搜索请求失败');
  } finally {
    loading.value = false;
  }
};

// 重置表单
const reset = () => {
  form.query = '';
  form.mode = 'hybrid';
  form.top_k = 5;
  form.threshold = 0.0;
  form.vector_weight = 0.5;
  form.bm25_weight = 0.5;
  results.value = [];
  searchTime.value = 0;
};

// 复制内容
const handleCopy = (text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('内容已复制');
  });
};

// 高亮关键词
const highlightKeyword = (text: string, keyword: string) => {
  if (!keyword || !text) return text;
  const keywords = keyword.split(/\s+/).filter((k) => k.length > 0);
  let highlighted = text;
  keywords.forEach((k) => {
    const reg = new RegExp(`(${k})`, 'gi');
    highlighted = highlighted.replace(reg, '<span class="highlight">$1</span>');
  });
  return highlighted;
};

// 分数颜色
const getScoreColor = (score: number) => {
  if (score >= 0.8) return 'success';
  if (score >= 0.5) return 'warning';
  return 'info';
};
</script>

<template>
  <Page>
    <div class="search-container">
      <el-row :gutter="20">
        <!-- 左侧配置区 -->
        <el-col :xs="24" :sm="24" :md="8" :lg="6" class="mb-4">
          <el-card class="config-card" shadow="never">
            <template #header>
              <div class="flex items-center justify-between">
                <span class="font-medium flex items-center">
                  <el-icon class="mr-1"><Setting /></el-icon>
                  检索配置（Mock）
                </span>
                <el-button link type="primary" @click="reset">
                  <el-icon class="mr-1"><Refresh /></el-icon>
                  重置
                </el-button>
              </div>
            </template>

            <el-form :model="form" label-position="top" size="default">
              <el-form-item label="目标知识库" required>
                <el-select v-model="form.kb_id" placeholder="请选择知识库" class="w-full">
                  <el-option v-for="kb in kbs" :key="kb.id" :label="kb.name" :value="kb.id" />
                </el-select>
              </el-form-item>

              <el-form-item label="检索模式">
                <el-radio-group v-model="form.mode" class="w-full flex flex-col items-start gap-2">
                  <el-radio value="hybrid" border class="!ml-0 !w-full !mr-0">混合检索 (Hybrid)</el-radio>
                  <el-radio value="rerank" border class="!ml-0 !w-full !mr-0">重排序 (Rerank)</el-radio>
                  <el-radio value="vector" border class="!ml-0 !w-full !mr-0">仅向量 (Vector Only)</el-radio>
                  <el-radio value="bm25" border class="!ml-0 !w-full !mr-0">仅关键词 (BM25 Only)</el-radio>
                </el-radio-group>
              </el-form-item>

              <el-divider content-position="center">参数设置</el-divider>

              <el-form-item label="召回数量 (Top K)">
                <div class="flex items-center w-full gap-2">
                  <el-slider v-model="form.top_k" :min="1" :max="20" class="flex-1" />
                  <el-input-number v-model="form.top_k" :min="1" :max="20" size="small" style="width: 90px" />
                </div>
              </el-form-item>

              <el-form-item label="相似度阈值">
                <div class="flex items-center w-full gap-2">
                  <el-slider v-model="form.threshold" :min="0" :max="1" :step="0.01" class="flex-1" />
                  <span class="text-sm w-12 text-right">{{ form.threshold }}</span>
                </div>
              </el-form-item>

              <template v-if="form.mode === 'hybrid' || form.mode === 'rerank'">
                <el-form-item label="向量权重 (Vector Weight)">
                  <div class="flex items-center w-full gap-2">
                    <el-slider
                      v-model="form.vector_weight"
                      :min="0"
                      :max="1"
                      :step="0.1"
                      class="flex-1"
                      @input="handleVectorWeightChange"
                    />
                    <span class="text-sm w-12 text-right">{{ form.vector_weight }}</span>
                  </div>
                </el-form-item>

                <el-form-item label="关键词权重 (BM25 Weight)">
                  <div class="flex items-center w-full gap-2">
                    <el-slider
                      v-model="form.bm25_weight"
                      :min="0"
                      :max="1"
                      :step="0.1"
                      class="flex-1"
                      @input="handleBm25WeightChange"
                    />
                    <span class="text-sm w-12 text-right">{{ form.bm25_weight }}</span>
                  </div>
                </el-form-item>
              </template>
            </el-form>
          </el-card>
        </el-col>

        <!-- 右侧结果区 -->
        <el-col :xs="24" :sm="24" :md="16" :lg="18">
          <el-card class="search-box mb-4" shadow="hover">
            <el-input
              v-model="form.query"
              type="textarea"
              :rows="3"
              placeholder="请输入测试问题（用于模拟视觉RAG文本检索）"
              resize="none"
              maxlength="500"
              show-word-limit
              @keydown.enter.ctrl.prevent="handleSearch"
            />
            <div class="mt-3 flex justify-between items-center">
              <el-button type="primary" :loading="loading" @click="handleSearch">
                <el-icon class="mr-1"><Search /></el-icon>
                开始检索
              </el-button>
            </div>
          </el-card>

          <div v-if="loading" class="space-y-4">
            <el-card v-for="i in 3" :key="i" shadow="never">
              <el-skeleton animated>
                <template #template>
                  <el-skeleton-item variant="text" style="width: 30%" class="mb-2" />
                  <el-skeleton-item variant="p" :rows="3" />
                </template>
              </el-skeleton>
            </el-card>
          </div>

          <div v-else-if="results.length > 0" class="space-y-4">
            <div class="flex justify-between items-center px-1">
              <span class="text-sm text-gray-500">
                耗时: <span class="font-bold text-primary">{{ searchTime }}ms</span>
              </span>
              <span class="text-sm text-gray-500">
                共 <span class="font-bold">{{ results.length }}</span> 条结果
              </span>
            </div>

            <el-card v-for="(item, index) in results" :key="index" class="result-card" shadow="hover">
              <template #header>
                <div class="flex justify-between items-start">
                  <div class="flex items-center gap-2">
                    <el-tag effect="dark" size="small" class="font-mono">#{{ index + 1 }}</el-tag>
                    <el-tag :type="getScoreColor(item.fused_score || item.rerank_score || 0)" effect="plain">
                      Score: {{ (item.fused_score || item.rerank_score || 0).toFixed(4) }}
                    </el-tag>
                    <el-tag v-if="item.rerank_score !== undefined" type="warning" effect="plain" size="small">
                      Rerank: {{ item.rerank_score.toFixed(4) }}
                    </el-tag>
                  </div>
                  <div class="flex gap-2">
                    <el-tooltip content="复制内容" placement="top">
                      <el-button circle size="small" :icon="CopyDocument" @click="handleCopy(item.content)" />
                    </el-tooltip>
                  </div>
                </div>
              </template>

              <div class="content-area prose max-w-none text-sm" v-html="highlightKeyword(item.content, form.query)"></div>

              <div
                class="mt-3 pt-3 border-t border-dashed border-gray-200 dark:border-gray-700 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500"
              >
                <div class="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <div class="flex items-center hover:text-primary transition-colors" title="Chunk ID">
                    <el-icon class="mr-1"><Document /></el-icon>
                    <span class="font-mono">ID: {{ item.id }}</span>
                  </div>
                  <div class="flex items-center" v-if="item.metadata?.source">
                    <el-icon class="mr-1"><DataLine /></el-icon>
                    <el-tooltip :content="item.metadata.source" placement="top" :show-after="200">
                      <span class="truncate max-w-[150px] sm:max-w-[200px] cursor-default">Src: {{ item.metadata.source }}</span>
                    </el-tooltip>
                  </div>
                </div>

                <div class="flex items-center gap-2 ml-auto sm:ml-0">
                  <div
                    v-if="item.vector_score !== undefined"
                    class="flex items-center px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400"
                    title="Vector Similarity Score"
                  >
                    <span class="mr-1 opacity-75 scale-90">Vec</span>
                    <span class="font-mono font-semibold">{{ item.vector_score.toFixed(4) }}</span>
                  </div>
                  <div
                    v-if="item.bm25_score !== undefined"
                    class="flex items-center px-2 py-0.5 rounded bg-orange-50 dark:bg-orange-900/20 text-orange-600 dark:text-orange-400"
                    title="BM25 Keyword Score"
                  >
                    <span class="mr-1 opacity-75 scale-90">BM25</span>
                    <span class="font-mono font-semibold">{{ item.bm25_score.toFixed(4) }}</span>
                  </div>
                </div>
              </div>
            </el-card>
          </div>

          <el-empty v-else description="暂无搜索结果，请在上方输入问题进行检索（Mock）" />
        </el-col>
      </el-row>
    </div>
  </Page>
</template>

<style scoped>
.search-container {
  min-height: 100%;
}

.config-card {
  position: sticky;
  top: 16px;
}

.result-card {
  transition: all 0.3s ease;
  border-left: 4px solid transparent;

  &:hover {
    transform: translateY(-2px);
    border-left-color: var(--el-color-primary);
  }
}

/* 高亮样式 */
::deep(span.highlight) {
  background-color: #fef08a;
  color: #111827;
  font-weight: 600;
  padding: 0 2px;
  border-radius: 2px;
}

::deep(.dark span.highlight) {
  background-color: #713f12;
  color: #fef08a;
}

.prose {
  line-height: 1.6;
  color: var(--el-text-color-regular);
}
</style>



