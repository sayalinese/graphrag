<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue';
import {
  ElButton,
  ElScrollbar,
  ElMessage,
  ElEmpty,
  ElPopconfirm,
  ElTooltip,
} from 'element-plus';
import type { ChatSessionVO } from '../utils/api';
import { listChatSessions, deleteChatSession } from '../utils/api';

interface Props {
  activeSessionId?: string;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  selectSession: [sessionId: string];
  createSession: [];
  editSession: [session: ChatSessionVO];
}>();

const sessions = ref<ChatSessionVO[]>([]);
const loading = ref(false);
const scrollRef = ref<InstanceType<typeof ElScrollbar>>();

const activeSessionId = computed(() => props.activeSessionId);

onMounted(() => {
  loadSessions();
});

async function loadSessions() {
  loading.value = true;
  try {
    const result = await listChatSessions(50);
    sessions.value = result.sessions || [];
  } catch (error) {
    console.error('Failed to load sessions:', error);
    // @ts-ignore
    if (error.response) {
      // @ts-ignore
      console.error('Response data:', error.response.data);
      // @ts-ignore
      console.error('Response status:', error.response.status);
    }
  } finally {
    loading.value = false;
  }
}

async function handleDeleteSession(session: ChatSessionVO) {
  try {
    await deleteChatSession(session.session_id);
    ElMessage.success('会话已删除');
    loadSessions();
    emit('selectSession', '');
  } catch (error) {
    ElMessage.error('删除失败');
  }
}

function handleSelectSession(sessionId: string) {
  emit('selectSession', sessionId);
}

function handleCreateNew() {
  emit('createSession');
}

function handleEdit(session: ChatSessionVO) {
  emit('editSession', session);
}

defineExpose({
  refresh: loadSessions,
});
</script>

<template>
  <div class="session-list flex flex-col h-full" style="background-color: var(--el-bg-color);">
    <!-- 创建按钮 -->
    <div class="p-3 border-b" style="border-color: var(--el-border-color);">
      <ElButton
        type="primary"
        class="w-full"
        @click="handleCreateNew"
      >
        <i class="i-line-md:plus mr-1" /> 新建会话
      </ElButton>
    </div>

    <!-- 会话列表 -->
    <ElScrollbar ref="scrollRef" class="flex-1">
      <ElEmpty v-if="!sessions.length && !loading" description="暂无会话" :image-size="60" />
      <div v-else class="p-2 space-y-1">
        <div
          v-for="session in sessions"
          :key="session.session_id"
          class="session-item group relative px-3 py-3 rounded-lg cursor-pointer transition-all duration-200 border border-transparent hover:bg-[var(--el-fill-color)]"
          :class="[activeSessionId === session.session_id ? 'bg-[var(--el-color-primary-light-9)] text-[var(--el-color-primary)]' : 'text-[var(--el-text-color-primary)]']"
          @click="handleSelectSession(session.session_id)"
        >
          <!-- 会话名称 -->
          <div class="font-medium text-sm truncate pr-12">
            {{ session.name || '无标题会话' }}
          </div>

          <!-- 角色和时间 -->
          <div class="text-xs mt-1.5 flex items-center justify-between" :class="[activeSessionId === session.session_id ? 'text-[var(--el-color-primary-light-3)]' : 'text-[var(--el-text-color-secondary)]']">
            <span class="truncate max-w-[120px] flex items-center gap-1">
              <i class="i-line-md:account text-[10px]" />
              {{ session.character_name || session.character_key }}
            </span>
            <span class="opacity-70 text-[10px]">{{ new Date(session.updated_at).toLocaleDateString() }}</span>
          </div>

          <!-- 操作按钮（hover 显示） -->
          <div
            class="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-0.5"
            @click.stop
          >
            <ElTooltip content="编辑会话" placement="top" :show-after="500">
              <ElButton
                text
                size="small"
                class="!w-7 !h-7 !p-0 hover:!bg-primary/10"
                @click="handleEdit(session)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-gray-500 hover:text-primary">
                  <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
                  <path d="m15 5 4 4"/>
                </svg>
              </ElButton>
            </ElTooltip>
            <ElPopconfirm
              title="确认删除此会话？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="handleDeleteSession(session)"
            >
              <template #reference>
                <ElButton text size="small" class="!w-7 !h-7 !p-0 hover:!bg-red-50" title="删除会话">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-gray-500 hover:text-red-500">
                    <path d="M3 6h18"/>
                    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
                    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
                    <line x1="10" x2="10" y1="11" y2="17"/>
                    <line x1="14" x2="14" y1="11" y2="17"/>
                  </svg>
                </ElButton>
              </template>
            </ElPopconfirm>
          </div>
        </div>
      </div>
    </ElScrollbar>

    <!-- 加载状态 -->
    <div v-if="loading" class="text-center text-xs py-2 border-t" style="border-color: var(--el-border-color); color: var(--el-text-color-secondary);">
      <i class="i-line-md:loading-twotone-loop animate-spin mr-1" /> 加载中...
    </div>
  </div>
</template>

<style scoped>
.session-list {
  min-width: 200px;
}
</style>
