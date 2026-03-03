<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue';
import { useUserStore } from '@vben/stores';
import { Page } from '@vben/common-ui';
import { ElMessage, ElDialog, ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElButton, ElTag, ElTooltip } from 'element-plus';
import ChatWindow from './components/ChatWindow.vue';
import SessionList from './components/SessionList.vue';
import type { ChatSessionVO, CharacterVO } from './utils/api';
import {
  createChatSession,
  updateChatSession,
  getChatSession,
  getChatHistory,
  getAvailableCharacters,
} from './utils/api';


const activeSessionId = ref('');
const currentSession = ref<ChatSessionVO | null>(null);
const characters = ref<CharacterVO[]>([]);
const sessionListRef = ref();
const chatWindowRef = ref();
const isSidebarOpen = ref(true);

const userStore = useUserStore();
const userAvatar = computed(() => userStore.userInfo?.avatar);

const currentCharacterAvatar = computed(() => {
  if (!currentSession.value) return undefined;
  const char = characters.value.find((c) => c.key === currentSession.value?.character_key);
  return char?.avatar;
});


const showCreateDialog = ref(false);
const editingSessionId = ref<string | null>(null);
const createForm = ref({
  name: '',
  character_id: '',
  max_context_length: 10,
});


onMounted(async () => {
  await loadCharacters();
  if (characters.value?.length > 0) {
    createForm.value.character_id = characters.value[0]!.key;
  }
});

// ============ 方法 ============

/**
 * 加载可用角色列表
 */
async function loadCharacters() {
  try {
    characters.value = await getAvailableCharacters();
  } catch (error) {
    console.error('Failed to load characters:', error);
    // @ts-ignore
    if (error.response) {
      // @ts-ignore
      console.error('Response data:', error.response.data);
      // @ts-ignore
      console.error('Response status:', error.response.status);
    } else {
      console.error('Error message:', error);
    }
  }
}

/**
 * 选择会话
 */
async function handleSelectSession(sessionId: string) {
  if (!sessionId) {
    activeSessionId.value = '';
    currentSession.value = null;
    return;
  }

  try {
    activeSessionId.value = sessionId;
    currentSession.value = await getChatSession(sessionId);

    // 加载历史消息
    const history = await getChatHistory(sessionId);
    chatWindowRef.value?.loadHistory(history.messages);
  } catch (error) {
    console.error('Failed to load session:', error);
    ElMessage.error('加载会话失败');
  }
}

/**
 * 创建新会话
 */
async function handleCreateSession() {
  editingSessionId.value = null;
  createForm.value = {
    name: '',
    character_id: characters.value[0]?.key || '',
    max_context_length: 10,
  };
  showCreateDialog.value = true;
}

/**
 * 编辑会话
 */
function handleEditSession(session: ChatSessionVO) {
  editingSessionId.value = session.session_id;
  createForm.value = {
    name: session.name || '',
    character_id: session.character_key,
    max_context_length: session.max_context_length || 10,
  };
  showCreateDialog.value = true;
}

/**
 * 确认保存会话（创建或更新）
 */
async function handleSaveSession() {
  if (!createForm.value.character_id) {
    ElMessage.warning('请选择角色');
    return;
  }

  try {
    if (editingSessionId.value) {
      // 更新模式
      await updateChatSession(editingSessionId.value, {
        name: createForm.value.name,
        max_context_length: createForm.value.max_context_length,
      });
      ElMessage.success('会话更新成功');
      
      // 如果当前正在查看此会话，更新当前会话信息
      if (currentSession.value && currentSession.value.session_id === editingSessionId.value) {
        currentSession.value.name = createForm.value.name;
        currentSession.value.max_context_length = createForm.value.max_context_length;
      }
    } else {
      // 创建模式
      const result = await createChatSession({
        character_id: createForm.value.character_id,
        name: createForm.value.name,
        max_context_length: createForm.value.max_context_length,
      });
      ElMessage.success('会话创建成功');
      handleSelectSession(result.session_id);
    }

    showCreateDialog.value = false;
    // 刷新会话列表
    await sessionListRef.value?.refresh();
  } catch (error) {
    console.error('Failed to save session:', error);
    ElMessage.error(editingSessionId.value ? '更新会话失败' : '创建会话失败');
  }
}

/**
 * 处理消息添加（保存到会话）
 */
function handleMessageAdded() {
  if (currentSession.value) {
    currentSession.value.message_count = (currentSession.value.message_count || 0) + 1;
  }
}

function toggleSidebar() {
  isSidebarOpen.value = !isSidebarOpen.value;
}
</script>

<template>
  <Page title="" auto-content-height>
    <div class="flex h-full overflow-hidden">
      <!-- 左侧：会话列表 -->
      <div 
        class="flex-shrink-0 h-full flex flex-col transition-all duration-300 ease-in-out border-r"
        :class="[isSidebarOpen ? 'w-72 opacity-100' : 'w-0 opacity-0']"
        style="background-color: var(--el-bg-color-overlay); border-color: var(--el-border-color);"
      >
        <div class="flex items-center justify-between px-4 py-3 flex-shrink-0">
          <span class="font-medium">会话列表</span>
          <ElTooltip content="收起侧边栏" placement="right">
            <div 
              class="w-7 h-7 rounded-md hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer transition-colors flex items-center justify-center"
              @click="toggleSidebar"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="opacity-60">
                <rect width="18" height="18" x="3" y="3" rx="2"/>
                <path d="M9 3v18"/>
                <path d="m16 15-3-3 3-3"/>
              </svg>
            </div>
          </ElTooltip>
        </div>
        <SessionList
          ref="sessionListRef"
          :activeSessionId="activeSessionId"
          @selectSession="handleSelectSession"
          @createSession="handleCreateSession"
          @editSession="handleEditSession"
          class="flex-1 min-h-0"
        />
      </div>

      <!-- 右侧：聊天区 -->
      <div class="flex-1 h-full flex flex-col" style="background-color: var(--el-bg-color-overlay);">
        <div v-if="currentSession" class="h-full flex flex-col">
          <!-- 聊天头部 -->
          <div class="h-14 px-4 flex items-center justify-between flex-shrink-0" style="background-color: var(--el-fill-color-lighter);">
             <div class="font-medium flex items-center gap-2">
                <ElTooltip v-if="!isSidebarOpen" content="展开侧边栏" placement="bottom">
                  <div 
                    class="w-7 h-7 mr-2 rounded-md hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer transition-colors flex items-center justify-center"
                    @click="toggleSidebar"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="opacity-60">
                      <rect width="18" height="18" x="3" y="3" rx="2"/>
                      <path d="M9 3v18"/>
                      <path d="m14 9 3 3-3 3"/>
                    </svg>
                  </div>
                </ElTooltip>
                <span class="text-lg">{{ currentSession.name || '未命名会话' }}</span>
                <ElTag size="small" effect="plain">{{ currentSession.character_name || currentSession.character_key }}</ElTag>
             </div>
          </div>
          
          <div class="flex-1 overflow-hidden relative">
            <ChatWindow
              ref="chatWindowRef"
              :sessionId="activeSessionId"
              :characterKey="currentSession.character_key"
              :maxContextLength="currentSession.max_context_length || 10"
              :userAvatar="userAvatar"
              :characterAvatar="currentCharacterAvatar"
              @messageAdded="handleMessageAdded"
            />
          </div>
        </div>
        <div v-else class="h-full flex flex-col">
           <!-- 空状态头部，也需要显示切换按钮 -->
           <div class="h-14 px-4 flex items-center flex-shrink-0" style="background-color: var(--el-fill-color-lighter);">
              <ElTooltip v-if="!isSidebarOpen" content="展开侧边栏" placement="bottom">
                  <div 
                    class="w-7 h-7 rounded-md hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer transition-colors flex items-center justify-center"
                    @click="toggleSidebar"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="opacity-60">
                      <rect width="18" height="18" x="3" y="3" rx="2"/>
                      <path d="M9 3v18"/>
                      <path d="m14 9 3 3-3 3"/>
                    </svg>
                  </div>
              </ElTooltip>
           </div>
           <div class="flex-1 flex items-center justify-center text-muted-foreground" style="background-color: var(--el-fill-color-lighter);">
            <div class="text-center">
              <div class="text-6xl mb-4 opacity-20">💬</div>
              <p class="text-lg font-medium">选择一个会话开始对话</p>
              <p class="text-sm opacity-60 mt-2">或创建一个新的会话</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建/编辑会话对话框 -->
    <ElDialog v-model="showCreateDialog" :title="editingSessionId ? '编辑会话' : '创建新会话'" width="500px">
      <ElForm :model="createForm" label-width="100px">
        <ElFormItem label="会话名称">
          <ElInput v-model="createForm.name" placeholder="可选，留空自动命名" />
        </ElFormItem>
        <ElFormItem label="选择角色" required>
          <ElSelect v-model="createForm.character_id" placeholder="请选择角色" class="w-full" :disabled="!!editingSessionId">
            <ElOption
              v-for="char in characters"
              :key="char.key"
              :label="char.name"
              :value="char.key"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="上下文长度">
          <ElInput v-model.number="createForm.max_context_length" type="number" min="1" max="100" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <div class="flex justify-end gap-2">
          <ElButton @click="showCreateDialog = false">取消</ElButton>
          <ElButton type="primary" @click="handleSaveSession">{{ editingSessionId ? '保存' : '创建' }}</ElButton>
        </div>
      </template>
    </ElDialog>
  </Page>
</template>

<style scoped>
/* Removed kb-chat-page style as Page component handles height */
</style>
