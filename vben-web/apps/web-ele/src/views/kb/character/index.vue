<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue';
import { useAccessStore } from '@vben/stores';
import { useAppConfig } from '@vben/hooks';
import { Page } from '@vben/common-ui';
import {
  ElAvatar,
  ElButton,
  ElDialog,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElTable,
  ElTableColumn,
  ElTag,
  ElEmpty,
  ElUpload,
} from 'element-plus';
import { useCharacterApi, type CharacterVO } from './utils/api';

const { characters, loading, listCharacters, createCharacter, updateCharacter, deleteCharacter, toggleCharacterStatus } =
  useCharacterApi();

const accessStore = useAccessStore();

// 获取 API base URL
const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);
const uploadActionUrl = computed(() => {
  // apiURL 已经包含 /api，所以只需要加 /upload/avatar
  const base = (apiURL || '').replace(/\/$/, '');
  const url = `${base}/upload/avatar`;
  console.log('[Upload] Action URL:', url);
  return url;
});

// 上传请求头
const uploadHeaders = computed(() => {
  const token = accessStore.accessToken;
  console.log('[Upload] Token:', token ? `${token.substring(0, 20)}...` : 'null');
  return token ? { Authorization: `Bearer ${token}` } : {};
});

// 上传成功回调
function handleAvatarSuccess(resp: any) {
  console.log('[Upload] Success response:', resp);
  // 假设后端返回结构为 { code: 0, data: { url: '...' } } 或直接返回 { url: '...' }
  // 根据实际接口调整
  const url = resp?.data?.url || resp?.url;
  if (url) {
    formModel.avatar = url;
    ElMessage.success('头像上传成功');
  } else {
    ElMessage.error('上传失败: 未返回URL');
  }
}

// 上传失败回调
function handleAvatarError(error: any) {
  console.error('[Upload] Error:', error);
  ElMessage.error('上传失败，请检查登录状态或文件格式');
}

// 上传前校验
function beforeAvatarUpload(rawFile: any) {
  const isImage = ['image/jpeg', 'image/png', 'image/webp'].includes(rawFile.type);
  const isLt2M = rawFile.size / 1024 / 1024 < 2;

  if (!isImage) {
    ElMessage.error('头像必须是 JPG/PNG/WEBP 格式!');
    return false;
  }
  if (!isLt2M) {
    ElMessage.error('头像大小不能超过 2MB!');
    return false;
  }
  return true;
}

// 对话框状态
const showCreateDialog = ref(false);
const showDetailDrawer = ref(false);
const editingCharacter = ref<CharacterVO | null>(null);

// 表单模型
const formModel = reactive({
  key: '',
  name: '',
  product: '',
  hobby: '',
  personality: '',
  expertise: [] as string[],
  system_prompt: '',
  avatar: '',
});

// 标签输入状态
const inputVisible = ref(false);
const inputValue = ref('');
const InputRef = ref<InstanceType<typeof ElInput>>();

const handleClose = (tag: string) => {
  formModel.expertise.splice(formModel.expertise.indexOf(tag), 1);
};

const showInput = () => {
  inputVisible.value = true;
  nextTick(() => {
    InputRef.value!.input!.focus();
  });
};

const handleInputConfirm = () => {
  if (inputValue.value) {
    if (!formModel.expertise.includes(inputValue.value)) {
      formModel.expertise.push(inputValue.value);
    }
  }
  inputVisible.value = false;
  inputValue.value = '';
};

// 初始化
onMounted(() => {
  listCharacters();
});

// ============ 角色管理 ============

function handleCreate() {
  editingCharacter.value = null;
  Object.assign(formModel, {
    key: '',
    name: '',
    product: '',
    hobby: '',
    personality: '',
    expertise: [],
    system_prompt: '',
    avatar: '',
  });
  showCreateDialog.value = true;
}

async function handleSave() {
  if (!formModel.key.trim() || !formModel.name.trim()) {
    ElMessage.warning('请输入角色标识和名称');
    return;
  }

  try {
    if (editingCharacter.value && editingCharacter.value.id) {
      await updateCharacter(editingCharacter.value.id, {
        name: formModel.name,
        product: formModel.product,
        hobby: formModel.hobby,
        personality: formModel.personality,
        expertise: formModel.expertise,
        system_prompt: formModel.system_prompt,
        avatar: formModel.avatar,
      });
      ElMessage.success('更新成功');
    } else {
      await createCharacter({
        key: formModel.key,
        name: formModel.name,
        product: formModel.product,
        hobby: formModel.hobby,
        personality: formModel.personality,
        expertise: formModel.expertise,
        system_prompt: formModel.system_prompt,
        avatar: formModel.avatar,
      });
      ElMessage.success('创建成功');
    }
    showCreateDialog.value = false;
    await listCharacters();
  } catch (error) {
    ElMessage.error('操作失败');
  }
}

function handleEdit(row: CharacterVO) {
  editingCharacter.value = row;
  Object.assign(formModel, row);
  showCreateDialog.value = true;
}

function handleDelete(row: CharacterVO) {
  if (!row.id) return;
  ElMessageBox.confirm(`删除角色"${row.name}"？`, '确认删除', {
    type: 'warning',
  })
    .then(async () => {
      if (row.id) {
        await deleteCharacter(row.id);
        ElMessage.success('删除成功');
      }
    })
    .catch(() => {});
}

function handleViewDetail(row: CharacterVO) {
  editingCharacter.value = row;
  showDetailDrawer.value = true;
}

async function handleToggleStatus(row: CharacterVO) {
  if (row.id) {
    await toggleCharacterStatus(row.id);
  }
}
</script>

<template>
  <Page title="AI 角色管理">
    <template #extra>
      <ElButton type="primary" @click="handleCreate">
        <i class="i-line-md:plus mr-1" /> 创建角色
      </ElButton>
    </template>

    <!-- 角色列表 -->
    <div class="bg-card rounded-lg shadow-sm p-4">
      <ElTable :data="characters" stripe v-loading="loading" class="w-full">
        <ElTableColumn prop="avatar" label="头像" width="80">
          <template #default="{ row }">
            <ElAvatar :src="row.avatar" shape="square" :size="40" @error="() => true">
              {{ (row.avatar && row.avatar.length < 10) ? row.avatar : '👤' }}
            </ElAvatar>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="name" label="角色名称" width="120" />
        <ElTableColumn prop="key" label="标识符" width="120" />
        <ElTableColumn prop="product" label="产品线" width="120" />
        <ElTableColumn prop="personality" label="性格特点" />
        <ElTableColumn prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <ElTag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <ElButton
              link
              :type="row.is_active ? 'warning' : 'success'"
              size="small"
              @click="handleToggleStatus(row)"
            >
              {{ row.is_active ? '禁用' : '启用' }}
            </ElButton>
            <ElButton link type="primary" size="small" @click="handleViewDetail(row)">
              详情
            </ElButton>
            <ElButton link type="primary" size="small" @click="handleEdit(row)">
              编辑
            </ElButton>
            <ElButton link type="danger" size="small" @click="handleDelete(row)">
              删除
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>

      <ElEmpty v-if="!loading && characters.length === 0" description="暂无角色" />
    </div>

    <!-- 创建/编辑对话框 -->
    <ElDialog
      v-model="showCreateDialog"
      :title="editingCharacter ? '编辑角色' : '创建新角色'"
      width="600px"
    >
      <ElForm :model="formModel" label-width="100px">
        <ElFormItem label="角色标识" required :disabled="!!editingCharacter">
          <ElInput v-model="formModel.key" placeholder="英文标识，如 student" />
        </ElFormItem>
        <ElFormItem label="角色名称" required>
          <ElInput v-model="formModel.name" placeholder="如：学生、教师" />
        </ElFormItem>
        <ElFormItem label="产品线">
          <ElInput v-model="formModel.product" placeholder="所属产品线" />
        </ElFormItem>
        <ElFormItem label="爱好">
          <ElInput v-model="formModel.hobby" placeholder="角色的爱好特征" />
        </ElFormItem>
        <ElFormItem label="性格特点">
          <ElInput v-model="formModel.personality" placeholder="性格描述" />
        </ElFormItem>
        <ElFormItem label="头像">
          <div class="w-full">
            <div class="flex gap-2 mb-2">
              <ElInput v-model="formModel.avatar" placeholder="emoji 表情或 URL" class="flex-1" />
              <ElUpload
                :action="uploadActionUrl"
                :show-file-list="false"
                :headers="uploadHeaders"
                :on-success="handleAvatarSuccess"
                :on-error="handleAvatarError"
                :before-upload="beforeAvatarUpload"
                accept="image/png,image/jpeg,image/webp"
                name="file"
              >
                <ElButton type="primary" plain>
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mr-1">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" x2="12" y1="3" y2="15"/>
                  </svg>
                  上传图片
                </ElButton>
              </ElUpload>
            </div>
            <div v-if="formModel.avatar" class="flex justify-center p-2 border rounded bg-gray-50 dark:bg-gray-800 w-fit">
              <ElAvatar :size="64" :src="formModel.avatar" shape="square">
                {{ formModel.avatar }}
              </ElAvatar>
            </div>
          </div>
        </ElFormItem>
        <ElFormItem label="专业领域">
          <div class="flex flex-wrap gap-2">
            <ElTag
              v-for="(tag, index) in formModel.expertise"
              :key="index"
              closable
              @close="handleClose(tag)"
              class="cursor-pointer"
            >
              {{ tag }}
            </ElTag>
            <ElInput
              v-if="inputVisible"
              ref="InputRef"
              v-model="inputValue"
              size="small"
              class="w-auto"
              placeholder="输入专业领域并回车添加"
              @keyup.enter="handleInputConfirm"
              @blur="inputVisible = false"
            />
            <ElButton
              v-else
              size="small"
              @click="showInput"
              class="bg-transparent text-primary"
            >
              <i class="i-line-md:plus" /> 添加专业领域
            </ElButton>
          </div>
        </ElFormItem>
        <ElFormItem label="系统提示词">
          <ElInput
            v-model="formModel.system_prompt"
            type="textarea"
            :rows="4"
            placeholder="定义角色行为的系统提示"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <div class="flex justify-end gap-2">
          <ElButton @click="showCreateDialog = false">取消</ElButton>
          <ElButton type="primary" @click="handleSave">
            {{ editingCharacter ? '更新' : '创建' }}
          </ElButton>
        </div>
      </template>
    </ElDialog>

    <!-- 角色详情侧边栏 -->
    <ElDrawer v-model="showDetailDrawer" title="角色详情" size="40%">
      <div v-if="editingCharacter" class="space-y-4">
        <!-- 头像和基本信息 -->
        <div class="flex items-start gap-4">
          <div class="text-5xl">{{ editingCharacter.avatar || '👤' }}</div>
          <div class="flex-1 space-y-2">
            <div>
              <span class="text-muted-foreground text-sm">名称:</span>
              <div class="font-semibold">{{ editingCharacter.name }}</div>
            </div>
            <div>
              <span class="text-muted-foreground text-sm">标识符:</span>
              <div class="font-mono text-sm">{{ editingCharacter.key }}</div>
            </div>
            <div>
              <span class="text-muted-foreground text-sm">状态:</span>
              <ElTag :type="editingCharacter.is_active ? 'success' : 'info'">
                {{ editingCharacter.is_active ? '启用' : '禁用' }}
              </ElTag>
            </div>
          </div>
        </div>

        <!-- 详细信息 -->
        <div class="space-y-3 text-sm">
          <div>
            <span class="text-muted-foreground">产品线:</span>
            <div class="mt-1">{{ editingCharacter.product || '-' }}</div>
          </div>
          <div>
            <span class="text-muted-foreground">爱好:</span>
            <div class="mt-1">{{ editingCharacter.hobby || '-' }}</div>
          </div>
          <div>
            <span class="text-muted-foreground">性格特点:</span>
            <div class="mt-1">{{ editingCharacter.personality || '-' }}</div>
          </div>
          <div>
            <span class="text-muted-foreground">专业领域:</span>
            <div class="mt-1 flex flex-wrap gap-1">
              <ElTag
                v-for="(exp, idx) in editingCharacter.expertise"
                :key="idx"
                size="small"
              >
                {{ exp }}
              </ElTag>
            </div>
          </div>
        </div>

        <!-- 系统提示词 -->
        <div>
          <span class="text-muted-foreground text-sm">系统提示词:</span>
          <div class="mt-2 p-3 bg-muted rounded text-xs font-mono whitespace-pre-wrap break-words">
            {{ editingCharacter.system_prompt || '-' }}
          </div>
        </div>

        <!-- 时间戳 -->
        <div v-if="editingCharacter.created_at" class="text-xs text-muted-foreground space-y-1 pt-4 border-t">
          <div>创建: {{ new Date(editingCharacter.created_at).toLocaleString() }}</div>
          <div v-if="editingCharacter.updated_at">
            更新: {{ new Date(editingCharacter.updated_at).toLocaleString() }}
          </div>
        </div>
      </div>
    </ElDrawer>
  </Page>
</template>
