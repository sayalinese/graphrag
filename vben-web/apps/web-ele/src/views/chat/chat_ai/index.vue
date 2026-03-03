<script lang="ts" setup>
import { ref, computed, nextTick } from 'vue';
import { ElButton, ElInput, ElScrollbar, ElUpload } from 'element-plus';
import type { UploadFile, UploadUserFile } from 'element-plus';
import { useUserStore } from '@vben/stores';
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string; // 内容
  time: string;
  pending?: boolean; // 生成中
  error?: boolean; // 出错
  partialContent?: string; // 流式增量
  retryOf?: string; // 重试来源
}

const userStore = useUserStore();
const input = ref('');
const loading = ref(false);
const uploadedFiles = ref<UploadUserFile[]>([]);
const messages = ref<ChatMessage[]>([
  {
    id: 'sys-welcome',
    role: 'system',
    content: `您好，${userStore.userInfo?.realName || '用户'}，可以开始你的提问:`,
    time: new Date().toLocaleTimeString(),
  },
]);

// markdown 渲染
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight(code: string, lang: string) {
    try {
      if (lang && hljs.getLanguage(lang)) {
        return `<pre class="code-block hljs"><code>${hljs.highlight(code, { language: lang }).value}</code></pre>`;
      }
      return `<pre class="code-block hljs"><code>${hljs.highlightAuto(code).value}</code></pre>`;
    } catch (err) {
      return `<pre class="code-block"><code>${md.utils.escapeHtml(code)}</code></pre>`;
    }
  },
});

const scrollRef = ref<InstanceType<typeof ElScrollbar>>();

function scrollToBottom() {
  nextTick(() => {
    const wrap = scrollRef.value?.wrapRef;
    if (wrap) wrap.scrollTop = wrap.scrollHeight;
  });
}

const canSend = computed(() => !!input.value.trim() && !loading.value);

function handleKey(e: Event) {
  if (e instanceof KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }
}

function buildUserMessage(content: string): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role: 'user',
    content,
    time: new Date().toLocaleTimeString(),
  };
}

function buildAssistantMessage(): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '',
    partialContent: '',
    pending: true,
    time: new Date().toLocaleTimeString(),
  };
}

async function send() {
  if (!canSend.value) return;
  const text = input.value.trim();
  input.value = '';
  const userMsg = buildUserMessage(text);
  messages.value.push(userMsg);
  const aiMsg = buildAssistantMessage();
  messages.value.push(aiMsg);
  scrollToBottom();
  loading.value = true;
  try {
  // 后端接入真实流式接口
    for await (const chunk of mockStreamAnswer(text)) {
      aiMsg.partialContent += chunk;
      scrollToBottom();
    }
    aiMsg.content = aiMsg.partialContent || '';
    aiMsg.pending = false;
    aiMsg.partialContent = '';
  } catch (e) {
    aiMsg.content = '请求失败，请稍后重试';
    aiMsg.error = true;
    aiMsg.pending = false;
  } finally {
    loading.value = false;
    scrollToBottom();
  }
}

// 模拟流式回答
async function* mockStreamAnswer(q: string): AsyncGenerator<string> {
  const fake = `你说: ${q}\n\n示例：\n\n\`\`\`ts\nfunction add(a: number, b: number){\n  return a + b;\n}\nconsole.log(add(2,3));\n\`\`\`\n\n以上是 TypeScript 代码块。`;
  const parts = fake.match(/.{1,15}/g) || [];
  for (const p of parts) {
    await new Promise((r) => setTimeout(r, 120));
    yield p;
  }
}


// 上传回调
function handleFileChange(_file: UploadFile, fileList: UploadUserFile[]) {
  uploadedFiles.value = fileList;
}
function handleFileRemove(file: UploadFile) {
  uploadedFiles.value = uploadedFiles.value.filter((f) => f.uid !== file.uid);
}

function clearFiles() {
  uploadedFiles.value = [];
}

function renderMarkdown(text: string) {
  return md.render(text);
}

function messageHtml(m: ChatMessage) {
  const base = m.pending && m.partialContent ? m.partialContent : m.content;
  return renderMarkdown(base);
}
</script>

<template>
  <div class="flex h-full flex-col gap-3 p-4">
    <header class="flex items-center justify-between gap-3 border-b pb-3">
      <div class="flex items-center gap-2">
        <div class="text-lg font-semibold">AI 助手</div>
      </div>

    </header>
    <ElScrollbar ref="scrollRef" class="flex-1 rounded border p-3 bg-background">
      <div class="space-y-4">
        <div
          v-for="m in messages"
          :key="m.id"
          class="group flex flex-col gap-1"
          :class="[
            m.role === 'user' ? 'items-end' : 'items-start',
          ]"
        >
          <div class="flex items-center gap-2" v-if="m.role === 'user'">
            <span class="text-xs text-muted-foreground">{{ m.time }}</span>
          </div>
          <div
            class="max-w-[85%] rounded-md px-3 py-2 text-sm shadow-sm ring-1 ring-transparent group-hover:ring-border/50 transition-colors"
            :class="[
              m.role === 'user'
                ? 'bg-primary-500/90 text-white'
                : m.role === 'assistant'
                  ? 'bg-card text-foreground'
                  : 'bg-muted text-foreground',
              m.error && '!bg-red-500 text-white',
            ]"
          >
            <template v-if="m.pending && !m.partialContent">
              <span class="inline-flex items-center gap-1">
                <i class="i-line-md:loading-twotone-loop" /> 正在思考...
              </span>
            </template>
            <template v-else>
              <div v-html="messageHtml(m)" />
            </template>
          </div>
          <div class="flex items-center gap-2 text-xs opacity-0 group-hover:opacity-100 transition-opacity" v-if="m.role !== 'system'">
            <span class="text-muted-foreground">{{ m.time }}</span>
            <span v-if="m.error" class="text-red-500">出错</span>
            <span v-if="m.pending" class="text-primary-500">生成中…</span>
          </div>
        </div>
      </div>
    </ElScrollbar>
  <footer class="chat-footer mt-1 flex flex-col gap-3">
      <ElInput
        v-model="input"
        type="textarea"
        :rows="5"
        placeholder="输入你的问题"
        @keydown="handleKey"
        class="chat-input"
      />
      <div v-if="uploadedFiles.length" class="flex flex-wrap gap-1 text-xs">
        <span
          v-for="f in uploadedFiles"
          :key="f.uid"
          class="rounded bg-muted px-2 py-0.5"
        >{{ f.name }}</span>
        <ElButton link size="small" type="danger" @click="clearFiles">清空</ElButton>
      </div>
      <div class="flex items-center justify-end gap-3">
        <div class="flex gap-2 items-center">
          <ElUpload
            action="#"
            multiple
            :auto-upload="false"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            :show-file-list="false"
            class="inline-block"
          >
            <ElButton
              type="default"
              :disabled="loading"
            >
              <i class="i-line-md:paperclip text-base mr-1" /> 上传
              <span v-if="uploadedFiles.length" class="ml-1 text-xs text-muted-foreground">({{ uploadedFiles.length }})</span>
            </ElButton>
          </ElUpload>
          <ElButton
            type="primary"
            :disabled="!canSend"
            :loading="loading"
            @click="send"
          >发送</ElButton>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.bg-background { background: hsl(var(--background)); }

.code-block {
  position: relative;
  padding: 0.75rem 0.9rem;
  font-size: 0.75rem;
  line-height: 1.4;
  border-radius: 0.5rem;
}

.code-block code { font-family: var(--font-mono, SFMono-Regular, Menlo, monospace); }

.code-block:hover { box-shadow: 0 0 0 1px hsl(var(--border)); }

::v-deep(pre.code-block) {
  color: hsl(var(--foreground));
  background: hsl(var(--muted));
}

::v-deep(.hljs-keyword) { color: #c792ea; }

::v-deep(.hljs-string) { color: #a5e844; }

::v-deep(.hljs-number) { color: #f78c6c; }

::v-deep(.hljs-function) { color: #82aaff; }

::v-deep(.hljs-comment) {
  font-style: italic;
  color: #546e7a;
}


::v-deep(.chat-input .el-textarea__inner) {
  height: 110px; /* 原 140px 调整为 110px 更紧凑 */
  padding: 0.75rem 1rem;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.4; /* 缩短行高 */
  resize: none;
  outline: none;
  background: hsl(var(--muted));
  border: none;
  border-radius: 0.75rem;
  box-shadow: none;
  transition: background .15s;
}

::v-deep(.chat-input .el-textarea__inner:focus) {
  background: hsl(var(--background));
}

::v-deep(.chat-input .el-textarea__inner::placeholder) {
  color: hsl(var(--muted-foreground));
  opacity: .8;
}

:deep(.dark .chat-input .el-textarea__inner) {
  outline: none;
  background: hsl(var(--muted));
  border: none;
}

:deep(.dark .chat-input .el-textarea__inner:focus) {
  background: hsl(var(--background));
}

/* Footer 容器基础样式与联动聚焦效果 */
.chat-footer {
  padding: 0.75rem; /* 原先内部已有间距，外层包一层不至于太挤 */
  background: hsl(var(--muted));
  border: 1px solid hsl(var(--border));
  border-radius: 0.75rem;

  /* background: transparent; 默认透明，避免双层背景 */
  transition: background .15s, box-shadow .15s, border-color .15s;
}

.chat-footer:focus-within {
  background: hsl(var(--muted));
  border-color: hsl(var(--border));
}

.dark .chat-footer {
  border-color: hsl(var(--border));
}

.dark .chat-footer:focus-within {
  background: hsl(var(--muted));
  border-color: hsl(var(--border));
}
</style>
