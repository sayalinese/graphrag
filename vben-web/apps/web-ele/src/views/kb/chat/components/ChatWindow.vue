<script lang="ts" setup>
import { computed, nextTick, ref, onMounted } from 'vue';
import {
  ElButton,
  ElInput,
  ElScrollbar,
  ElEmpty,
  ElAvatar,
  ElSelect,
  ElOption,
  ElTooltip,
  ElTag,
} from 'element-plus';
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import type { ChatMessageVO } from '../utils/api';
import { sendChatMessage, sendChatMessageStream } from '../utils/api';
import { getKBList } from '../../search/api';

interface KBItem {
  id: number;
  name: string;
  description?: string;
}

interface Props {
  sessionId: string;
  characterKey: string;
  maxContextLength?: number;
  userAvatar?: string;
  characterAvatar?: string;
}

const props = withDefaults(defineProps<Props>(), {
  maxContextLength: 10,
});

const emit = defineEmits<{
  messageAdded: [ChatMessageVO];
  characterChanged: [string];
}>();

const input = ref('');
const loading = ref(false);
const messages = ref<ChatMessageVO[]>([]);
const scrollRef = ref<InstanceType<typeof ElScrollbar>>();
const kbList = ref<KBItem[]>([]);
const selectedKbId = ref<number | undefined>(undefined);
const enableWebSearch = ref(false);

onMounted(async () => {
  try {
    const res = await getKBList();
    kbList.value = res;
    if (kbList.value.length > 0) {
      selectedKbId.value = kbList.value[0]?.id;
    }
  } catch (e) {
    console.error('Failed to load KB list', e);
  }
});

// Markdown 渲染器
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight(code: string, lang: string) {
    try {
      if (lang && hljs.getLanguage(lang)) {
        return `<pre class="hljs"><code>${hljs.highlight(code, { language: lang }).value}</code></pre>`;
      }
      return `<pre class="hljs"><code>${hljs.highlightAuto(code).value}</code></pre>`;
    } catch {
      return `<pre><code>${md.utils.escapeHtml(code)}</code></pre>`;
    }
  },
});

const canSend = computed(() => !!input.value.trim() && !loading.value);

function scrollToBottom() {
  nextTick(() => {
    scrollRef.value?.setScrollTop(Number.MAX_SAFE_INTEGER);
  });
}

function handleKeyDown(e: any) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    send();
  }
}

async function send() {
  if (!canSend.value) return;

  const content = input.value.trim();
  input.value = '';

  // 添加用户消息
  const userMsg: ChatMessageVO = {
    id: crypto.randomUUID(),
    session_id: props.sessionId,
    role: 'user',
    content,
    timestamp: new Date().toISOString(),
  };
  messages.value.push(userMsg);
  emit('messageAdded', userMsg);
  scrollToBottom();

  // 添加 AI 消息占位符
  const aiMsg: ChatMessageVO = {
    id: crypto.randomUUID(),
    session_id: props.sessionId,
    role: 'assistant',
    content: '',
    timestamp: new Date().toISOString(),
    pending: true,
  };
  const aiMsgIndex = messages.value.length;
  messages.value.push(aiMsg);
  loading.value = true;
  scrollToBottom();

  try {
    // 尝试流式请求
    let accumulated = '';
    let sources: any[] = [];

    await sendChatMessageStream(
      {
        session_id: props.sessionId,
        content,
        character_id: props.characterKey,
        max_context_length: props.maxContextLength,
        kb_id: selectedKbId.value,
        enable_web_search: enableWebSearch.value,
      },
      (chunk) => {
        if (chunk.type === 'chunk' && chunk.content) {
          accumulated += chunk.content;
          // 直接更新并触发响应式
          messages.value[aiMsgIndex]!.partialContent = accumulated;
          messages.value = [...messages.value];
          scrollToBottom();
        } else if (chunk.type === 'complete') {
          if (chunk.sources) {
            sources = chunk.sources;
          }
          // 最终更新
          const msg = messages.value[aiMsgIndex]!;
          msg.content = accumulated;
          msg.sources = sources;
          msg.pending = false;
          msg.partialContent = undefined;
          messages.value = [...messages.value];
          emit('messageAdded', msg);
          scrollToBottom();
        } else if (chunk.type === 'error') {
          const msg = messages.value[aiMsgIndex]!;
          msg.content = chunk.error || '请求失败，请重试';
          msg.error = true;
          msg.pending = false;
          messages.value = [...messages.value];
          scrollToBottom();
        }
      }
    );
  } catch (error) {
    console.error('[UI] Stream error, falling back:', error);
    // 流式失败，回退到普通请求
    try {
      const result = await sendChatMessage({
        session_id: props.sessionId,
        content,
        character_id: props.characterKey,
        max_context_length: props.maxContextLength,
      });

      const msg = messages.value[aiMsgIndex]!;
      msg.content = result.response;
      msg.sources = result.sources;
      msg.pending = false;
      messages.value = [...messages.value];
      emit('messageAdded', msg);
    } catch (fallbackError) {
      console.error('Chat error:', fallbackError);
      const msg = messages.value[aiMsgIndex]!;
      msg.content = '发送失败，请检查网络';
      msg.error = true;
      msg.pending = false;
      messages.value = [...messages.value];
    }
    scrollToBottom();
  } finally {
    loading.value = false;
  }
}

function renderMarkdown(text: string) {
  return md.render(text);
}

function getMessageHtml(msg: ChatMessageVO) {
  const content = msg.pending && msg.partialContent ? msg.partialContent : msg.content;
  return renderMarkdown(content);
}

// 暴露 loadHistory 给父组件
defineExpose({
  loadHistory: (newMessages: ChatMessageVO[]) => {
    messages.value = newMessages;
    scrollToBottom();
  },
  addMessage: (msg: ChatMessageVO) => {
    messages.value.push(msg);
    scrollToBottom();
  },
});
</script>

<template>
  <div class="kb-chat-window h-full flex flex-col bg-background">
    <!-- 消息区 -->
    <ElScrollbar ref="scrollRef" class="flex-1">
      <div class="p-4 min-h-full">
        <ElEmpty v-if="!messages.length" description="暂无消息" :image-size="100" class="mt-20" />
        <div v-else class="flex flex-col gap-6 pb-4">
          <div
            v-for="msg in messages"
            :key="msg.id"
            class="flex gap-3 max-w-4xl mx-auto w-full group"
            :class="{
              'flex-row-reverse': msg.role === 'user',
            }"
          >
            <!-- 头像 -->
            <div class="flex-shrink-0">
              <ElAvatar
                :size="32"
                :src="msg.role === 'user' ? userAvatar : characterAvatar"
                :class="msg.role === 'user' ? '!bg-primary !text-white' : '!bg-white !border !border-gray-200 !text-primary dark:!bg-zinc-800 dark:!border-zinc-700'"
                @error="() => true"
              >
                <i :class="msg.role === 'user' ? 'i-line-md:person' : 'i-line-md:robot'" class="text-lg" />
              </ElAvatar>
            </div>

            <!-- 消息内容容器 -->
            <div class="flex flex-col gap-1 min-w-0 max-w-[85%]">
              <!-- 角色名和时间 -->
              <div class="text-xs text-muted-foreground flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity" :class="{ 'justify-end': msg.role === 'user' }">
                  <span>{{ msg.role === 'user' ? '我' : 'AI 助手' }}</span>
                  <span>{{ new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}</span>
              </div>

              <!-- 气泡 -->
              <div
                  class="rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm break-words"
                  :class="[
                    msg.role === 'user' 
                      ? 'bg-primary text-white rounded-tr-sm' 
                      : 'bg-white dark:bg-zinc-800 border border-border rounded-tl-sm',
                    msg.error && 'bg-red-50 border-red-200 text-red-600 dark:bg-red-900/20 dark:border-red-800'
                  ]"
              >
                  <!-- Loading -->
                  <div v-if="msg.pending && !msg.partialContent" class="flex items-center gap-2 py-1">
                    <i class="i-line-md:loading-twotone-loop animate-spin" />
                    <span>正在思考...</span>
                  </div>
                  
                  <!-- Content -->
                  <div v-else class="markdown-body" v-html="getMessageHtml(msg)" />
                  
                  <!-- RAG 引用展开按钮 -->
                  <div v-if="msg.sources?.length && !msg.pending" class="mt-2 pt-2 border-t border-border/30">
                    <button
                      class="text-xs text-muted-foreground hover:text-primary flex items-center gap-1 transition-colors"
                      @click="msg.showSources = !msg.showSources"
                    >
                      <svg 
                        xmlns="http://www.w3.org/2000/svg" 
                        width="14" 
                        height="14" 
                        viewBox="0 0 24 24" 
                        fill="none" 
                        stroke="currentColor" 
                        stroke-width="2" 
                        stroke-linecap="round" 
                        stroke-linejoin="round"
                        class="transition-transform"
                        :class="msg.showSources ? 'rotate-90' : ''"
                      >
                        <path d="m9 18 6-6-6-6"/>
                      </svg>
                      <span>参考来源 ({{ msg.sources.length }})</span>
                    </button>
                    
                    <!-- 展开的引用内容 -->
                    <div v-if="msg.showSources" class="mt-2 space-y-2">
                      <div
                        v-for="(source, idx) in msg.sources"
                        :key="idx"
                        class="text-xs bg-muted/30 p-2.5 rounded-lg border border-border/50"
                      >
                        <div class="flex items-center gap-2 mb-1.5">
                          <ElTag
                            v-if="source.relevance_level"
                            :type="
                              source.relevance_level === 'high'
                                ? 'success'
                                : source.relevance_level === 'medium'
                                  ? 'warning'
                                  : 'info'
                            "
                            size="small"
                            effect="plain"
                            class="!h-5 !px-1.5"
                          >
                            {{ source.relevance_level === 'high' ? '高相关' : source.relevance_level === 'medium' ? '中相关' : '低相关' }}
                          </ElTag>
                          <span v-if="source.score" class="text-muted-foreground">
                            匹配度 {{ (source.score * 100).toFixed(0) }}%
                          </span>
                        </div>
                        <div class="text-foreground/80 leading-relaxed line-clamp-3">
                          {{ source.text }}
                        </div>
                        <div v-if="source.metadata?.filename" class="mt-1.5 text-primary/70 flex items-center gap-1">
                          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>
                            <path d="M14 2v4a2 2 0 0 0 2 2h4"/>
                          </svg>
                          {{ source.metadata.filename }}
                        </div>
                      </div>
                    </div>
                  </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ElScrollbar>

    <!-- 输入区 -->
    <div class="p-4 border-t border-border bg-background">
      <!-- 顶部知识库选择栏 -->
      <div class="max-w-4xl mx-auto mb-3 flex items-center gap-3">
        <div class="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/30 border border-border/50">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground">
            <ellipse cx="12" cy="5" rx="9" ry="3"/>
            <path d="M3 5V19A9 3 0 0 0 21 19V5"/>
            <path d="M3 12A9 3 0 0 0 21 12"/>
          </svg>
          <ElSelect 
            v-model="selectedKbId" 
            placeholder="选择知识库" 
            size="small" 
            class="!w-40 kb-select" 
            clearable 
            filterable
          >
            <ElOption v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
          </ElSelect>
        </div>
        
        <ElTooltip content="开启后将尝试搜索互联网补充回答" placement="top">
          <div 
            class="flex items-center gap-1.5 cursor-pointer px-3 py-2 rounded-lg transition-colors select-none border"
            :class="enableWebSearch ? 'bg-primary/10 border-primary/30 text-primary' : 'bg-muted/30 border-border/50 hover:bg-muted/50 text-muted-foreground'"
            @click="enableWebSearch = !enableWebSearch"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/>
              <path d="M2 12h20"/>
            </svg>
            <span class="text-sm">联网搜索</span>
          </div>
        </ElTooltip>
      </div>

      <div class="max-w-4xl mx-auto">
        <div class="relative rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 shadow-sm transition-colors focus-within:border-primary focus-within:ring-1 focus-within:ring-primary">
          
          <ElInput
            v-model="input"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 8 }"
            resize="none"
            placeholder="输入你的问题"
            class="input-textarea-transparent"
            @keydown="handleKeyDown"
            :disabled="loading"
          />
          
          <!-- 底部工具栏 -->
          <div class="flex justify-end items-center px-3 pb-3">
             <!-- 右侧发送按钮 -->
             <ElButton type="primary" size="small" :disabled="!canSend" :loading="loading" @click="send" round>
               发送
               <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="ml-1">
                 <path d="m22 2-7 20-4-9-9-4Z"/>
                 <path d="M22 2 11 13"/>
               </svg>
             </ElButton>
          </div>
        </div>
        <div class="text-center mt-2">

        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-textarea :deep(.el-textarea__inner) {
  padding-right: 5rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  border-radius: 0.75rem;
  box-shadow: var(--el-box-shadow-light);
  transition: all 0.2s;
  background-color: var(--el-fill-color-light);
  border-color: transparent;
}

.custom-textarea :deep(.el-textarea__inner):hover {
  background-color: var(--el-fill-color);
}

.custom-textarea :deep(.el-textarea__inner):focus {
  background-color: var(--el-bg-color);
  border-color: var(--el-color-primary);
  box-shadow: var(--el-box-shadow);
}

.input-textarea-transparent :deep(.el-textarea__inner) {
  box-shadow: none !important;
  background-color: transparent !important;
  border: none !important;
  padding: 0.75rem 1rem 0 1rem;
}

.kb-select :deep(.el-input__wrapper) {
  box-shadow: none !important;
  background-color: transparent !important;
}

.markdown-body :deep(p) {
  margin: 0.5em 0;
}
.markdown-body :deep(p:first-child) {
  margin-top: 0;
}
.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown-body :deep(pre) {
  margin: 0.5em 0;
  border-radius: 0.5rem;
  background: #282c34;
  padding: 1em;
  overflow-x: auto;
  color: #abb2bf;
}
.markdown-body :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 0.9em;
  background: rgba(175, 184, 193, 0.2);
  padding: 0.2em 0.4em;
  border-radius: 6px;
}
.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}
.markdown-body :deep(li) {
  margin: 0.2em 0;
}
/* Dark mode adjustments for code blocks if needed, but hardcoded dark theme for code blocks is usually fine */
</style>
