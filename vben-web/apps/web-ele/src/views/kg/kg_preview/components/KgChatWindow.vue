<template>
  <div class="kg-chat-window flex flex-col h-full bg-gray-900/80 backdrop-blur-sm text-gray-200">
    <!-- 头部 -->
    <div
      class="chat-header px-5 py-4 border-b border-gray-700/50 flex items-center justify-between bg-gray-900/50 backdrop-blur-sm"
    >
      <div class="flex items-center gap-3">
        <ElTooltip content="折叠面板" placement="bottom">
          <button
            class="p-1.5 rounded-md hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
            @click="$emit('close')"
          >
            <el-icon class="text-lg"><Fold /></el-icon>
          </button>
        </ElTooltip>
        <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500/20 to-blue-600/20 flex items-center justify-center border border-cyan-500/30">
          <el-icon class="text-xl text-cyan-400"><Service /></el-icon>
        </div>
        <button 
          class="flex items-center justify-between gap-1.5 px-3 py-1.5 rounded-md hover:bg-gray-800 transition-colors group w-48 min-w-0"
          @click="() => { showSessionList = true; loadSessions(); }"
        >
          <span class="font-semibold text-base tracking-wide text-gray-200 group-hover:text-cyan-400 transition-colors flex-1 truncate text-left block">
            {{ currentSessionName }}
          </span>
          <el-icon class="text-gray-500 group-hover:text-cyan-400 transition-colors flex-shrink-0"><ArrowDown /></el-icon>
        </button>
      </div>
      <div class="flex items-center gap-2">
        <div class="flex flex-col gap-1.5 items-end">
          <ElSelect
            v-model="selectedStrategy"
            size="small"
            style="width: 100px"
            placeholder="搜索策略"
            class="strategy-select"
            popper-class="strategy-select-dropdown"
            :teleported="true"
            :popper-options="{ modifiers: [{ name: 'offset', options: { offset: [0, 4] } }] }"
          >
            <template #prefix>
              <el-icon class="text-gray-400"><Operation /></el-icon>
            </template>
            <ElOption
              v-for="opt in strategyOptions"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            >
              <div class="flex flex-col py-1">
                <span class="font-medium">{{ opt.label }}</span>
                <span class="text-xs text-gray-500 mt-0.5">{{ opt.desc }}</span>
              </div>
            </ElOption>
          </ElSelect>
          
          <ElSelect
            v-model="selectedDocId"
            size="small"
            style="width: 100px"
            placeholder="选择知识库"
            class="doc-select"
            popper-class="doc-select-dropdown"
            :teleported="true"
            :popper-options="{ modifiers: [{ name: 'offset', options: { offset: [0, 4] } }] }"
          >
            <template #prefix>
              <el-icon class="text-gray-400"><Document /></el-icon>
            </template>
            <ElOption
              v-for="doc in documents"
              :key="doc.name"
              :value="doc.name"
              :label="doc.name"
            >
              <div class="truncate">{{ doc.name }}</div>
            </ElOption>
          </ElSelect>
        </div>
        
        <div class="h-4 w-px bg-gray-700 mx-1"></div>

        <ElTooltip content="清空对话 & 重置上下文" placement="bottom">
          <button
            class="p-1.5 rounded-md hover:bg-gray-800 text-gray-400 hover:text-red-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            :disabled="!hasMessages"
            @click="clearMessages"
          >
            <el-icon class="text-lg"><Delete /></el-icon>
          </button>
        </ElTooltip>
        
      </div>
    </div>

    <!-- 消息列表 -->
    <ElScrollbar ref="scrollRef" class="flex-1 px-2">
      <div class="py-6 px-3 space-y-6">
        <!-- 服务状态提示 -->
        <div
          v-if="serviceStatus === 'offline'"
          class="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-between"
        >
          <div class="flex items-center gap-2 text-red-400 text-sm">
            <el-icon class="text-lg"><Warning /></el-icon>
            <span>GraphRAG 服务未连接</span>
          </div>
          <button 
            class="px-3 py-1 text-xs font-medium bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded transition-colors"
            @click="retryConnection"
          >
            重试连接
          </button>
        </div>

        <div
          v-if="serviceStatus === 'checking'"
          class="flex items-center justify-center py-8 text-gray-500 gap-2"
        >
          <el-icon class="text-xl text-cyan-500 is-loading"><Loading /></el-icon>
          <span class="text-sm">正在连接知识图谱服务...</span>
        </div>

        <!-- 消息 -->
        <div
          v-for="message in messages"
          :key="message.id"
          class="message-item group"
          :class="message.role"
        >
          <!-- 用户消息 -->
          <div
            v-if="message.role === 'user'"
            class="flex justify-end items-start gap-3 pl-12"
          >
            <div class="flex flex-col items-end gap-1 max-w-full">
              <div
                class="user-bubble px-4 py-3 rounded-2xl rounded-tr-sm bg-gradient-to-br from-cyan-600 to-blue-600 text-white shadow-lg shadow-blue-900/20 text-sm leading-relaxed"
              >
                {{ message.content }}
              </div>
              <span class="text-[10px] text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity">
                {{ message.timestamp.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}
              </span>
            </div>
            <!-- 用户头像 -->
            <div class="w-9 h-9 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center flex-shrink-0 shadow-md overflow-hidden">
              <el-icon class="text-gray-400 text-lg"><User /></el-icon>
            </div>
          </div>

          <!-- 助手消息 -->
          <div v-else class="flex items-start gap-3 pr-8">
            <!-- 助手头像 -->
            <div class="w-9 h-9 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center flex-shrink-0 shadow-md overflow-hidden relative group-hover:shadow-cyan-500/20 transition-shadow">
              <div class="absolute inset-0 bg-gradient-to-br from-cyan-500/10 to-purple-500/10"></div>
              <el-icon class="text-cyan-400 text-lg relative z-10"><Service /></el-icon>
            </div>
            
            <div class="flex flex-col gap-1 max-w-full flex-1 min-w-0">
              <div
                class="assistant-bubble px-5 py-4 rounded-2xl rounded-tl-sm bg-gray-800/60 border border-gray-700/50 shadow-sm backdrop-blur-sm"
              >
                <!-- 加载中 -->
                <div v-if="message.loading" class="flex items-center gap-3 py-1">
                  <div class="flex gap-1">
                    <div class="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
                    <div class="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
                    <div class="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
                  </div>
                  <span class="text-xs text-cyan-500 font-medium animate-pulse">{{ message.loadingText || '正在思考...' }}</span>
                </div>

                <!-- 错误 -->
                <div
                  v-else-if="message.error"
                  class="text-red-400 flex items-start gap-2 text-sm"
                >
                  <el-icon class="mt-0.5 flex-shrink-0"><WarningFilled /></el-icon>
                  <span>{{ message.content }}</span>
                </div>

                <!-- 正常内容 -->
                <template v-else>
                  <div
                    class="markdown-body prose prose-invert prose-sm max-w-none"
                    v-html="renderMarkdown(message.content)"
                  />

                  <!-- 底部元数据栏 -->
                  <div class="mt-4 pt-3 border-t border-gray-700/30 flex flex-wrap items-center gap-3">
                    <!-- 策略标签 -->
                    <div
                      v-if="message.strategy"
                      class="flex items-center gap-1.5 px-2 py-1 rounded bg-gray-900/50 border border-gray-700/50"
                    >
                      <el-icon class="text-xs text-gray-500"><Operation /></el-icon>
                      <span class="text-xs font-medium" :class="getStrategyColorClass(message.strategy)">
                        {{ getStrategyLabel(message.strategy) }}
                      </span>
                    </div>
                    
                    <div
                      v-if="message.communities_used"
                      class="flex items-center gap-1.5 px-2 py-1 rounded bg-gray-900/50 border border-gray-700/50"
                    >
                      <el-icon class="text-xs text-gray-500"><Connection /></el-icon>
                      <span class="text-xs text-gray-400">
                        {{ message.communities_used }} 个社区
                      </span>
                    </div>
                  </div>

                  <div v-if="!message.entities?.length" class="mt-3">
                    <button
                      class="px-3 py-1.5 rounded-md text-xs font-medium border border-cyan-500/40 text-cyan-300 hover:text-cyan-200 hover:bg-cyan-900/25 transition-colors flex items-center gap-1.5"
                      @click="triggerDemoHighlight()"
                    >
                      <span>✨</span>
                      <span>路径演示</span>
                    </button>
                  </div>

                  <!-- 附加信息折叠面板 -->
                  <div
                    v-if="
                      message.entities?.length ||
                      message.relations?.length ||
                      message.chunks?.length
                    "
                    class="mt-3 space-y-2"
                  >
                    <!-- 相关实体 -->
                    <div v-if="message.entities?.length" class="rounded-lg bg-gray-900/30 border border-gray-700/30 overflow-hidden">
                      <button 
                        class="w-full px-3 py-2 flex items-center justify-between hover:bg-gray-800/50 transition-colors text-xs font-medium text-gray-400"
                        @click="toggleCollapse(message.id, 'entities')"
                      >
                        <div class="flex items-center gap-2">
                          <el-icon class="text-cyan-500"><DataBoard /></el-icon>
                          <span>相关实体 ({{ message.entities.length }})</span>
                        </div>
                        <el-icon class="transition-transform duration-200" :class="{ 'rotate-180': !isCollapsed(message.id, 'entities') }"><ArrowDown /></el-icon>
                      </button>
                      
                      <div v-show="!isCollapsed(message.id, 'entities')" class="px-3 pb-3 pt-1 border-t border-gray-700/30">
                        <div class="flex flex-wrap gap-1.5">
                          <button
                            v-for="entity in message.entities.slice(0, 20)"
                            :key="entity.name"
                            class="px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 border border-gray-700 text-xs text-gray-300 transition-colors flex items-center gap-1"
                            @click="handleEntityClick(entity)"
                          >
                            {{ entity.name }}
                            <span v-if="entity.type" class="text-[10px] text-gray-500">
                              {{ entity.type }}
                            </span>
                          </button>
                          <button
                            v-if="message.entities.length > 0"
                            class="px-2 py-1 rounded text-xs text-cyan-400 hover:text-cyan-300 hover:bg-cyan-900/20 transition-colors flex items-center gap-1 ml-1"
                            @click="handleHighlightEntities(message.entities!)"
                          >
                            <el-icon><Aim /></el-icon>
                            选择调用节点
                          </button>
                        </div>
                      </div>
                    </div>

                    <!-- 实体关系 -->
                    <div v-if="message.relations?.length" class="rounded-lg bg-gray-900/30 border border-gray-700/30 overflow-hidden">
                      <button 
                        class="w-full px-3 py-2 flex items-center justify-between hover:bg-gray-800/50 transition-colors text-xs font-medium text-gray-400"
                        @click="toggleCollapse(message.id, 'relations')"
                      >
                        <div class="flex items-center gap-2">
                          <el-icon class="text-purple-500"><Share /></el-icon>
                          <span>实体关系 ({{ message.relations.length }})</span>
                        </div>
                        <el-icon class="transition-transform duration-200" :class="{ 'rotate-180': !isCollapsed(message.id, 'relations') }"><ArrowDown /></el-icon>
                      </button>
                      
                      <div v-show="!isCollapsed(message.id, 'relations')" class="px-3 pb-3 pt-1 border-t border-gray-700/30">
                        <div class="space-y-1.5">
                          <div
                            v-for="(rel, idx) in message.relations.slice(0, 15)"
                            :key="idx"
                            class="flex items-center gap-2 text-xs text-gray-400 bg-gray-800/30 px-2 py-1.5 rounded"
                          >
                            <span class="font-medium text-gray-300 flex-shrink-0">{{ rel.source }}</span>
                            <el-icon class="text-gray-600 text-[10px] flex-shrink-0"><ArrowRight /></el-icon>
                            <span class="px-1.5 py-0.5 rounded bg-purple-900/30 text-[10px] text-purple-300 border border-purple-600/30 truncate max-w-[200px]" :title="rel.description || rel.type">
                              {{ rel.description || rel.type }}
                            </span>
                            <el-icon class="text-gray-600 text-[10px] flex-shrink-0"><ArrowRight /></el-icon>
                            <span class="font-medium text-gray-300 flex-shrink-0">{{ rel.target }}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- 原文片段 -->
                    <div v-if="message.chunks?.length" class="rounded-lg bg-gray-900/30 border border-gray-700/30 overflow-hidden">
                      <button 
                        class="w-full px-3 py-2 flex items-center justify-between hover:bg-gray-800/50 transition-colors text-xs font-medium text-gray-400"
                        @click="toggleCollapse(message.id, 'chunks')"
                      >
                        <div class="flex items-center gap-2">
                          <el-icon class="text-yellow-500"><Document /></el-icon>
                          <span>原文片段 ({{ message.chunks.length }})</span>
                        </div>
                        <el-icon class="transition-transform duration-200" :class="{ 'rotate-180': !isCollapsed(message.id, 'chunks') }"><ArrowDown /></el-icon>
                      </button>
                      
                      <div v-show="!isCollapsed(message.id, 'chunks')" class="px-3 pb-3 pt-1 border-t border-gray-700/30">
                        <div class="space-y-2">
                          <div
                            v-for="(chunk, idx) in message.chunks.slice(0, 5)"
                            :key="idx"
                            class="text-xs text-gray-400 p-2.5 rounded bg-gray-800/50 border border-gray-700/50 hover:border-gray-600/50 transition-colors"
                          >
                            <div
                              v-if="chunk.score"
                              class="flex justify-between items-center mb-1.5 pb-1.5 border-b border-gray-700/30"
                            >
                              <span class="text-[10px] text-gray-500">片段 #{{ idx + 1 }}</span>
                              <span class="text-[10px] font-mono text-cyan-500/80">
                                Score: {{ (chunk.score as number).toFixed(3) }}
                              </span>
                            </div>
                            <div class="line-clamp-3 leading-relaxed opacity-90">{{ chunk.text }}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </template>
              </div>
              <span class="text-[10px] text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity pl-1">
                {{ message.timestamp.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}
              </span>
            </div>
          </div>
        </div>

        <!-- 预设问题（仅在没有用户消息时显示） -->
        <div
          v-if="messages.length <= 1"
          class="mt-8 px-4"
        >
          <div class="text-xs font-medium text-gray-500 mb-3 uppercase tracking-wider flex items-center gap-2">
            <el-icon><Sunny /></el-icon>
            <span>你可以试着问：</span>
          </div>
          <div class="grid grid-cols-1 gap-2">
            <button
              v-for="q in presetQuestions"
              :key="q"
              class="text-left px-4 py-3 rounded-xl bg-gray-800/40 hover:bg-gray-800 border border-gray-700/30 hover:border-cyan-500/30 text-sm text-gray-300 hover:text-cyan-100 transition-all duration-200 group flex items-center justify-between"
              @click="usePresetQuestion(q)"
            >
              <span>{{ q }}</span>
              <el-icon class="opacity-0 group-hover:opacity-100 -translate-x-2 group-hover:translate-x-0 transition-all text-cyan-500"><ArrowRight /></el-icon>
            </button>
          </div>
        </div>
      </div>
    </ElScrollbar>

    <!-- 输入区域 -->
    <div
      class="chat-input px-5 py-4 border-t border-gray-700/50 bg-gray-900/30 backdrop-blur-sm"
    >
      <div class="relative">
        <ElInput
          v-model="inputText"
          type="textarea"
          :rows="1"
          :autosize="{ minRows: 1, maxRows: 4 }"
          placeholder="输入你的问题..."
          :disabled="isLoading"
          class="custom-input"
          @keydown="handleKeydown"
        />
        <div class="absolute right-2 bottom-1.5">
          <button
            class="p-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-cyan-900/20"
            :disabled="!canSend"
            @click="handleSend"
          >
            <el-icon v-if="!isLoading" class="text-lg block"><Position /></el-icon>
            <el-icon v-else class="animate-spin text-lg block"><Loading /></el-icon>
          </button>
        </div>
      </div>
      <div class="mt-2 text-[10px] text-gray-500 flex justify-between px-1">
        <span v-if="contextMessageCount > 0" class="flex items-center gap-1">
          <el-icon class="text-cyan-500"><ChatDotSquare /></el-icon>
        </span>
        <span v-else></span>
        <span v-if="isLoading" class="text-cyan-500 animate-pulse">正在生成回答...</span>
      </div>
    </div>

    <!-- 会话列表侧边栏 -->
    <div 
      v-if="showSessionList" 
      class="absolute inset-0 z-50 bg-gray-900/95 backdrop-blur-md flex flex-col transition-all duration-300"
    >
      <div class="p-4 border-b border-gray-700 flex items-center justify-between">
        <span class="font-semibold text-lg">历史会话</span>
        <button @click="showSessionList = false" class="text-gray-400 hover:text-white">
          <el-icon class="text-xl"><Close /></el-icon>
        </button>
      </div>
      
      <div class="p-3">
        <button 
          class="w-full py-2 px-4 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg flex items-center justify-center gap-2 transition-colors"
          @click="createNewSession"
        >
          <el-icon><Plus /></el-icon>
          <span>新对话</span>
        </button>
      </div>

      <ElScrollbar class="flex-1 px-3">
        <div v-if="isSessionLoading" class="flex justify-center py-4">
           <el-icon class="is-loading text-cyan-500"><Loading /></el-icon>
        </div>
        <div v-else class="space-y-2 pb-4">
          <div 
            v-for="session in sessions" 
            :key="session.session_id"
            class="p-3 rounded-lg cursor-pointer transition-colors group relative"
            :class="currentSessionId === session.session_id ? 'bg-gray-800 border border-cyan-500/30' : 'hover:bg-gray-800/50 border border-transparent'"
            @click="switchSession(session.session_id)"
          >
            <div class="font-medium text-sm truncate pr-6">{{ session.name || '未命名会话' }}</div>
            <div class="text-xs text-gray-500 mt-1">{{ new Date(session.updated_at).toLocaleString() }}</div>
            
            <button 
              class="absolute right-2 top-3 text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
              @click.stop="handleDeleteSession(session.session_id, $event)"
            >
              <el-icon><Delete /></el-icon>
            </button>
          </div>
          
          <div v-if="sessions.length === 0" class="text-center text-gray-500 py-8 text-sm">
            暂无历史会话
          </div>
        </div>
      </ElScrollbar>
    </div>
  </div>
</template>


<script lang="ts" setup>
import { computed, nextTick, onMounted, ref, reactive, watch } from 'vue';
import {
  ElScrollbar,
  ElInput,
  ElTooltip,
  ElSelect,
  ElOption,
  ElMessage,
  ElIcon,
} from 'element-plus';
import {
  User,
  Service,
  Operation,
  Delete,
  Fold,
  Warning,
  Loading,
  WarningFilled,
  Connection,
  DataBoard,
  ArrowDown,
  Aim,
  Share,
  ArrowRight,
  Document,
  Sunny,
  Position,
  ChatDotSquare,
  Close,
  Plus,
} from '@element-plus/icons-vue';
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';
import {
  hybridSearch,
  getGraphStats,
  getKgSessions,
  createKgSession,
  getKgSessionMessages,
  deleteKgSession,
  getNeo4jDatabases,
  type KgSession,
  type KgChatMessage,
  type SearchStrategy,
  type EntityInfo,
  type RelationInfo,
  type Neo4jDatabaseInfo,
} from '../utils/api';

const props = defineProps<{
  docId?: string;
}>();

const emit = defineEmits<{
  selectEntity: [entity: EntityInfo];
  highlightEntities: [entities: EntityInfo[]];
  'highlight-knowledge': [data: { entities: EntityInfo[]; relations: any[]; question?: string }];
  'kg-highlight': [payload: {
    seedNodeIds: string[];
    nodeIds: string[];
    linkIds: string[];
    maxDepth: number;
    graph?: { nodes: any[]; edges: any[]; links?: any[] };
  }];
  'update:docId': [docId: string];
  close: [];
}>();

// Markdown 渲染器
const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight: (str: string, lang: string) => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang, ignoreIllegals: true }).value;
      } catch (_) {}
    }
    return '';
  },
});

// 状态
const messages = ref<KgChatMessage[]>([]);
const inputText = ref('');
const isLoading = ref(false);
const scrollRef = ref<InstanceType<typeof ElScrollbar>>();
const selectedStrategy = ref<SearchStrategy>('auto');
const serviceStatus = ref<'checking' | 'online' | 'offline'>('checking');
const graphStatsInfo = ref<{ nodes: number; edges: number; communities?: number } | null>(null);

// 文档选择
const documents = ref<Neo4jDatabaseInfo[]>([]);
const selectedDocId = ref<string>(props.docId || '');

// 监听外部 docId 变化
watch(() => props.docId, (newVal) => {
  if (newVal !== undefined && newVal !== selectedDocId.value) {
    selectedDocId.value = newVal;
  }
});

// 监听内部选择变化，通知父组件
watch(selectedDocId, (newVal) => {
  emit('update:docId', newVal);
});

// 加载 Neo4j 数据库列表
async function loadDocuments() {
  try {
    documents.value = await getNeo4jDatabases();
  } catch (error) {
    console.error('Failed to load neo4j databases:', error);
  }
}

// 会话管理
const sessions = ref<KgSession[]>([]);
const currentSessionId = ref<string>();
const showSessionList = ref(false);
const isSessionLoading = ref(false);

// 加载会话列表
async function loadSessions() {
  try {
    sessions.value = await getKgSessions();
  } catch (error) {
    console.error('Failed to load sessions:', error);
  }
}

// 切换会话
async function switchSession(sessionId: string) {
  if (currentSessionId.value === sessionId) return;
  
  try {
    isSessionLoading.value = true;
    const history = await getKgSessionMessages(sessionId);
    
    // 转换消息格式
    messages.value = history.map(msg => ({
      id: generateId(),
      role: msg.role,
      content: msg.content,
      timestamp: new Date(msg.timestamp),
      sources: msg.sources,
      loading: false
    }));
    
    currentSessionId.value = sessionId;
    showSessionList.value = false;
  } catch (error) {
    ElMessage.error('加载会话消息失败');
    console.error(error);
  } finally {
    isSessionLoading.value = false;
  }
}

// 创建新会话
async function createNewSession() {
  currentSessionId.value = undefined;
  messages.value = [];
  showSessionList.value = false;
  // 实际上我们不需要立即调用 API 创建，等到发送第一条消息时再创建
  // 或者在这里创建也可以，看交互设计。
  // 为了简单，这里只重置状态，发送消息时自动创建
}

// 删除会话
async function handleDeleteSession(sessionId: string, event: Event) {
  event.stopPropagation();
  try {
    await deleteKgSession(sessionId);
    sessions.value = sessions.value.filter(s => s.session_id !== sessionId);
    if (currentSessionId.value === sessionId) {
      createNewSession();
    }
    ElMessage.success('会话已删除');
  } catch (error) {
    ElMessage.error('删除会话失败');
  }
}

// 折叠状态管理
const collapseState = reactive<Record<string, Record<string, boolean>>>({});

function toggleCollapse(msgId: string, section: string) {
  if (!collapseState[msgId]) {
    collapseState[msgId] = {};
  }
  // 默认是展开的（undefined），点击后变为 true（折叠）
  // 或者默认折叠，点击展开。这里我们设计为默认折叠（true），点击展开（false）
  // 修正：UI上显示折叠面板，通常默认是折叠的。
  // isCollapsed 返回 true 表示折叠。
  // 初始状态：undefined -> 视为折叠(true)
  
  const current = isCollapsed(msgId, section);
  collapseState[msgId][section] = !current;
}

function isCollapsed(msgId: string, section: string): boolean {
  if (!collapseState[msgId]) {
    return true; // 默认折叠
  }
  return collapseState[msgId][section] !== false; // 除非明确设置为 false (展开)，否则折叠
}

// 策略选项
const strategyOptions = [
  { value: 'auto', label: '自动选择', desc: '智能判断搜索方式' },
  { value: 'local', label: 'Local Search', desc: '基于实体关系的精确搜索' },
  { value: 'global', label: 'Global Search', desc: '基于社区摘要的全局搜索' },
  { value: 'both', label: '混合搜索', desc: '同时使用两种搜索方式' },
];

// 预设问题
const presetQuestions = [
  '这个故事涉及哪些主要人物？',
  '文档中有哪些重要的组织？',
  '主角与其他角色之间有什么关系？',
  '故事发生在哪些地点？',
];

// 计算属性
const hasMessages = computed(() => messages.value.length > 0);
const canSend = computed(() => inputText.value.trim() && !isLoading.value);
// 计算有效上下文消息数量（排除欢迎消息、加载中消息和错误消息）
const contextMessageCount = computed(() => {
  return messages.value.filter(msg => 
    !msg.loading && 
    !msg.error && 
    msg.content?.trim()
  ).length;
});

// 当前会话名称
const currentSessionName = computed(() => {
  if (!currentSessionId.value) return '新对话';
  const session = sessions.value.find(s => s.session_id === currentSessionId.value);
  return session?.name || '未命名会话';
});

// 生成唯一 ID
function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// 滚动到底部
async function scrollToBottom() {
  await nextTick();
  if (scrollRef.value) {
    const scrollEl = scrollRef.value.wrapRef;
    if (scrollEl) {
      scrollEl.scrollTop = scrollEl.scrollHeight;
    }
  }
}

// 渲染 Markdown
function renderMarkdown(content: string): string {
  return md.render(content);
}

// 流式输出文本
async function streamText(message: KgChatMessage, text: string) {
  message.content = '';
  const delay = 30;
  
  for (const char of text) {
    message.content += char;
    await new Promise(resolve => setTimeout(resolve, delay));
    if (message.content.length % 5 === 0) {
       scrollToBottom();
    }
  }
  await scrollToBottom();
}

// 检查服务状态
async function checkServiceStatus() {
  serviceStatus.value = 'checking';
  try {
    const stats = await getGraphStats();
    graphStatsInfo.value = stats;
    serviceStatus.value = 'online';
  } catch (error) {
    console.warn('GraphRAG service check failed:', error);
    serviceStatus.value = 'offline';
  }
}

// 构建对话历史（用于 API 请求）
function buildApiChatHistory(limit = 12) {
  const history = messages.value
    .filter((msg) => {
      if (msg.loading || msg.error) return false;
      if (!msg.content || !msg.content.trim()) return false;
      return msg.role === 'user' || msg.role === 'assistant';
    })
    .map((msg) => ({
      role: msg.role,
      content: msg.content,
    }));

  return history.slice(-limit);
}

function buildDemoEntitiesByQuestion(question: string): EntityInfo[] {
  const normalized = question.toLowerCase();
  const entityPool: Array<{ keywords: string[]; entity: EntityInfo }> = [
    { keywords: ['肺炎', '发热', '呼吸', '咳嗽'], entity: { name: '肺炎', type: 'DISEASE', description: '呼吸系统疾病实体' } },
    { keywords: ['ct', '影像', '检查', '诊断'], entity: { name: 'CT 影像', type: 'PRODUCT', description: '影像诊断相关实体' } },
    { keywords: ['路径', '流程', '规范'], entity: { name: '临床路径', type: 'CONCEPT', description: '临床诊疗流程知识' } },
    { keywords: ['检索', '召回', '多模态'], entity: { name: '多模态检索', type: 'CONCEPT', description: '多模态知识检索能力' } },
    { keywords: ['问答', '知识图谱', '图谱'], entity: { name: '知识图谱问答', type: 'CONCEPT', description: '图谱问答能力节点' } },
    { keywords: ['医院', '协和', '北京'], entity: { name: '北京协和医院', type: 'ORGANIZATION', description: '医疗机构节点' } },
    { keywords: ['医院', '瑞金', '上海'], entity: { name: '上海瑞金医院', type: 'ORGANIZATION', description: '医疗机构节点' } },
    { keywords: ['科室', '呼吸科'], entity: { name: '呼吸科', type: 'DEPARTMENT', description: '医院科室节点' } },
  ];

  const picked: EntityInfo[] = [];
  for (const item of entityPool) {
    const matched = item.keywords.some((keyword) => normalized.includes(keyword));
    if (matched) {
      picked.push(item.entity);
    }
  }

  if (!picked.length) {
    return [
      { name: '知识图谱问答', type: 'CONCEPT', description: '问答中枢节点' },
      { name: '多模态检索', type: 'CONCEPT', description: '检索扩散节点' },
      { name: '临床路径', type: 'CONCEPT', description: '流程知识节点' },
    ];
  }

  return picked.slice(0, 5);
}

function buildDemoRelationsByEntities(entities: EntityInfo[]): RelationInfo[] {
  if (!Array.isArray(entities) || entities.length < 2) return [];
  const relations: RelationInfo[] = [];
  for (let i = 0; i < entities.length - 1; i += 1) {
    const source = entities[i]?.name;
    const target = entities[i + 1]?.name;
    if (!source || !target) continue;
    relations.push({
      source,
      target,
      type: '关联',
      description: `${source} 与 ${target} 存在语义关联`,
    });
  }
  return relations;
}

// 发送消息
async function handleSend() {
  const question = inputText.value.trim();
  if (!question || isLoading.value) return;

  // 发送前抓取历史上下文（不包含本轮问题）
  const apiChatHistory = buildApiChatHistory(12);

  if (!currentSessionId.value) {
    try {
      const session = await createKgSession(question.slice(0, 20));
      currentSessionId.value = session.session_id;
      await loadSessions();
    } catch (e) {
      console.error('Failed to create session:', e);
    }
  }

  const userMessage: KgChatMessage = {
    id: generateId(),
    role: 'user',
    content: question,
    timestamp: new Date(),
  };
  messages.value.push(userMessage);

  const assistantMessage: KgChatMessage = {
    id: generateId(),
    role: 'assistant',
    content: '',
    timestamp: new Date(),
    loading: true,
    loadingText: '正在分析问题...',
    strategy: selectedStrategy.value,
  };
  messages.value.push(assistantMessage);

  inputText.value = '';
  isLoading.value = true;
  await scrollToBottom();

  const loadingStages = [
    '正在分析问题意图...',
    '正在检索知识图谱实体...',
    '正在构建可解释链路...',
    '正在生成最终回答...'
  ];
  let stageIndex = 0;
  const loadingInterval = setInterval(() => {
    const lastMsg = messages.value[messages.value.length - 1];
    if (lastMsg && lastMsg.loading) {
      if (stageIndex < loadingStages.length) {
        lastMsg.loadingText = loadingStages[stageIndex++];
      }
    } else {
      clearInterval(loadingInterval);
    }
  }, 800);

  try {
    const activeDatabase = selectedDocId.value || props.docId || '';
    if (!activeDatabase) {
      throw new Error('请先选择知识库（database）');
    }

    const searchResult = await hybridSearch(
      question,
      selectedStrategy.value,
      20,
      apiChatHistory,
      currentSessionId.value,
      undefined,
      activeDatabase
    );

    const lastMessage = messages.value[messages.value.length - 1];
    if (lastMessage && lastMessage.role === 'assistant') {
      lastMessage.loading = false;
      lastMessage.strategy = searchResult.strategy_used || selectedStrategy.value;
      const apiEntities = searchResult.local_result?.entities || [];
      const apiRelations = searchResult.local_result?.relations || [];

      const explainEntities =
        apiEntities.length > 0 ? apiEntities : buildDemoEntitiesByQuestion(question);
      const explainRelations =
        apiRelations.length > 0
          ? apiRelations
          : buildDemoRelationsByEntities(explainEntities);

      lastMessage.entities = explainEntities;
      lastMessage.relations = explainRelations;
      lastMessage.chunks = searchResult.local_result?.chunks || [];
      lastMessage.communities_used = searchResult.global_result?.communities_used;

      emit('highlight-knowledge', {
        entities: lastMessage.entities,
        relations: lastMessage.relations,
        question,
      });

      // Emit kg-highlight for explain view
      // Important: Deep clone to avoid reactive proxy issues when passed to another view
      const graphNodes = JSON.parse(JSON.stringify(explainEntities.map(e => ({
        id: e.name,
        label: e.name,
        ...e,
        value: 1 // Default value
      }))));
      
      const graphEdges = JSON.parse(JSON.stringify(explainRelations.map((r, idx) => ({
        ...r,
        id: `rel_${idx}`,
        source: r.source,
        target: r.target,
        relationType: r.type,
        description: r.description // Ensure description is passed
      }))));

      // Log for debugging
      console.log('KgChatWindow: Emitting kg-highlight', { 
        nodeCount: graphNodes.length, 
        edgeCount: graphEdges.length,
        sampleNode: graphNodes[0] 
      });

      emit('kg-highlight', {
        seedNodeIds: graphNodes.map((n:any) => n.id),
        nodeIds: graphNodes.map((n:any) => n.id),
        linkIds: graphEdges.map((e:any) => e.id),
        maxDepth: 1,
        graph: {
          nodes: graphNodes,
          edges: graphEdges,
          links: graphEdges // Dual compatibility
        }
      });

      await streamText(lastMessage, searchResult.answer || '未能生成回答');
    }
  } catch (error: any) {
    console.error('GraphRAG search failed:', error);
    const fallbackQuestion = question || '知识图谱问答演示';
    const fallbackEntities = buildDemoEntitiesByQuestion(fallbackQuestion);
    const fallbackRelations = buildDemoRelationsByEntities(fallbackEntities);

    const fallbackNodes = fallbackEntities.map((e) => ({
      ...e,
      id: e.name,
      label: e.name,
      value: 1,
    }));
    const fallbackEdges = fallbackRelations.map((r, idx) => ({
      ...r,
      id: `fallback_rel_${idx}`,
      source: r.source,
      target: r.target,
      relationType: r.type,
      description: r.description,
    }));

    emit('kg-highlight', {
      seedNodeIds: fallbackNodes.map((n) => n.id),
      nodeIds: fallbackNodes.map((n) => n.id),
      linkIds: fallbackEdges.map((e) => e.id),
      maxDepth: 1,
      graph: {
        nodes: fallbackNodes,
        edges: fallbackEdges,
        links: fallbackEdges,
      },
    });

    const lastMessage = messages.value[messages.value.length - 1];
    if (lastMessage && lastMessage.role === 'assistant') {
      lastMessage.loading = false;
      lastMessage.error = error.message || '请求失败';
      lastMessage.content = `抱歉，搜索过程中出现错误：${error.message || '未知错误'}。请检查后端服务是否正常运行。`;
    }
  } finally {
    clearInterval(loadingInterval);
    isLoading.value = false;
    await scrollToBottom();
  }
}
// 使用预设问题
function usePresetQuestion(question: string) {
  inputText.value = question;
  handleSend();
}

// 点击实体
function handleEntityClick(entity: EntityInfo) {
  emit('selectEntity', entity);
}

// 高亮所有实体
function handleHighlightEntities(entities: EntityInfo[]) {
  emit('highlightEntities', entities);
}

function triggerDemoHighlight() {
  const latestUserQuestion = [...messages.value].reverse().find((msg) => msg.role === 'user')?.content || '';
  const question = latestUserQuestion || inputText.value.trim() || '知识图谱问答演示';
  const demoEntities = buildDemoEntitiesByQuestion(question);

  emit('highlight-knowledge', {
    entities: demoEntities,
    relations: [],
    question,
  });

  // Emit kg-highlight for explain view as well during demo
  const graphNodes = demoEntities.map(e => ({
    id: e.name,
    label: e.name,
    ...e,
    value: 1
  }));

  emit('kg-highlight', {
    seedNodeIds: graphNodes.map(n => n.id),
    nodeIds: graphNodes.map(n => n.id),
    linkIds: [],
    maxDepth: 1,
    graph: {
      nodes: graphNodes,
      edges: [],
      links: []
    }
  });

  ElMessage.success('已触发演示点亮，可观察节点按层级逐步出现');
}

// 清空对话（含上下文）
function clearMessages() {
  messages.value = [];
  ElMessage.success('对话已清空，上下文已重置');
  // 重新添加欢迎消息
  addWelcomeMessage();
}

// 键盘事件
function handleKeydown(event: KeyboardEvent | Event) {
  const keyEvent = event as KeyboardEvent;
  if (keyEvent.key === 'Enter' && !keyEvent.shiftKey) {
    event.preventDefault();
    handleSend();
  }
}

// 获取策略标签颜色
function getStrategyColorClass(strategy: SearchStrategy | undefined): string {
  switch (strategy) {
    case 'local':
      return 'text-green-400';
    case 'global':
      return 'text-yellow-400';
    case 'both':
      return 'text-cyan-400';
    default:
      return 'text-gray-400';
  }
}

// 获取策略显示名称
function getStrategyLabel(strategy: SearchStrategy | undefined): string {
  switch (strategy) {
    case 'local':
      return 'Local';
    case 'global':
      return 'Global';
    case 'both':
      return 'Hybrid';
    case 'auto':
      return 'Auto';
    default:
      return '';
  }
}

// 添加欢迎消息
function addWelcomeMessage() {
  let statsInfo = '';
  if (graphStatsInfo.value) {
    statsInfo = `\n\n**图谱状态**: ${graphStatsInfo.value.nodes || 0} 个节点, ${graphStatsInfo.value.edges || 0} 条边`;
    if (graphStatsInfo.value.communities) {
      statsInfo += `, ${graphStatsInfo.value.communities} 个社区`;
    }
  }

  messages.value.push({
    id: generateId(),
    role: 'assistant',
    content: `你好！我是知识图谱问答助手。我可以基于图谱中的实体、关系和社区知识回答你的问题。

**搜索策略说明：**
- **Local Search**: 基于具体实体和关系的精确搜索
- **Global Search**: 基于社区知识摘要的全局搜索
- **自动选择**: 根据问题类型自动判断

**💡 上下文功能**：我会记住我们的对话历史，你可以使用代词如"他"、"这个"来指代之前提到的内容。点击清空按钮可重置对话上下文。${statsInfo}

请输入你的问题，或选择下方的预设问题开始体验。`,
    timestamp: new Date(),
  });
}

// 重试连接
async function retryConnection() {
  await checkServiceStatus();
  if (serviceStatus.value === 'online') {
    ElMessage.success('服务连接成功！');
  }
}

// 初始化
onMounted(async () => {
  await checkServiceStatus();
  await loadDocuments();
  addWelcomeMessage();
});
</script>



<style scoped>
.kg-chat-window {
  min-width: 320px;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.6;
  color: #e5e7eb;
}

.markdown-body :deep(p) {
  margin: 0.5em 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.markdown-body :deep(li) {
  margin: 0.25em 0;
}

.markdown-body :deep(code) {
  background-color: rgba(31, 41, 55, 0.5);
  padding: 0.125em 0.375em;
  border-radius: 4px;
  font-size: 0.875em;
  color: #e5e7eb;
}

.markdown-body :deep(pre) {
  background-color: #111827;
  padding: 1em;
  border-radius: 8px;
  overflow-x: auto;
  border: 1px solid rgba(55, 65, 81, 0.5);
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.markdown-body :deep(strong) {
  font-weight: 600;
  color: #fff;
}

.markdown-body :deep(a) {
  color: #22d3ee;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

/* 自定义输入框样式 */
.custom-input :deep(.el-textarea__inner) {
  background-color: rgba(31, 41, 55, 0.5);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 0.75rem;
  padding: 12px 48px 12px 16px;
  color: #f3f4f6;
  box-shadow: none;
  transition: all 0.2s;
}

.custom-input :deep(.el-textarea__inner:focus) {
  background-color: rgba(31, 41, 55, 0.8);
  border-color: rgba(6, 182, 212, 0.5);
  box-shadow: 0 0 0 1px rgba(6, 182, 212, 0.5);
}

.custom-input :deep(.el-textarea__inner::placeholder) {
  color: #6b7280;
}

/* 策略选择器样式 */
.strategy-select :deep(.el-input__wrapper) {
  background-color: transparent;
  box-shadow: none !important;
  padding: 0;
}

.strategy-select :deep(.el-input__inner) {
  color: #9ca3af;
  font-size: 12px;
  font-weight: 500;
}

.strategy-select :deep(.el-input__suffix) {
  display: none;
}

/* 文档选择器样式 */
.doc-select :deep(.el-input__wrapper) {
  background-color: transparent;
  box-shadow: none !important;
  padding: 0;
}

.doc-select :deep(.el-input__inner) {
  color: #9ca3af;
  font-size: 12px;
  font-weight: 500;
}

.doc-select :deep(.el-input__suffix) {
  display: none;
}
</style>

<style>
/* 策略选择器下拉框样式 - 全局样式确保 teleported 时生效 */
.strategy-select-dropdown {
  background: #1f2937 !important;
  border: 1px solid #374151 !important;
  padding: 4px !important;
  z-index: 9999 !important;
}

.strategy-select-dropdown .el-select-dropdown__item {
  color: #d1d5db;
  border-radius: 4px;
  margin-bottom: 2px;
  height: auto;
  padding: 8px 12px;
}

.strategy-select-dropdown .el-select-dropdown__item.hover,
.strategy-select-dropdown .el-select-dropdown__item.is-hovering,
.strategy-select-dropdown .el-select-dropdown__item.selected {
  background: #374151;
  color: #fff;
}

/* 文档选择器下拉框样式 */
.doc-select-dropdown {
  background: #1f2937 !important;
  border: 1px solid #374151 !important;
  padding: 4px !important;
  z-index: 9999 !important;
  max-height: 300px;
}

.doc-select-dropdown .el-select-dropdown__item {
  color: #d1d5db;
  border-radius: 4px;
  margin-bottom: 2px;
  height: auto;
  padding: 8px 12px;
}

.doc-select-dropdown .el-select-dropdown__item.hover,
.doc-select-dropdown .el-select-dropdown__item.is-hovering,
.doc-select-dropdown .el-select-dropdown__item.selected {
  background: #374151;
  color: #fff;
}
</style>
