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
  ElTabs,
  ElTabPane,
  ElSwitch,
  ElCard,
} from 'element-plus';
import { useCharacterApi, type CharacterVO, listExpertConfigs, updateExpertConfig, type ExpertConfigVO } from './utils/api';

const { characters, loading, listCharacters, createCharacter, updateCharacter, deleteCharacter, toggleCharacterStatus } =
  useCharacterApi();

const accessStore = useAccessStore();

// 获取 API base URL
const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);
const uploadActionUrl = computed(() => {
  const base = (apiURL || '').replace(/\/$/, '');
  return `${base}/upload/avatar`;
});

// 上传请求头
const uploadHeaders = computed(() => {
  const token = accessStore.accessToken;
  return token ? { Authorization: `Bearer ${token}` } : {};
});

function handleAvatarSuccess(resp: any) {
  const url = resp?.data?.url || resp?.url;
  if (url) {
    formModel.avatar = url;
    ElMessage.success('头像上传成功');
  } else {
    ElMessage.error('上传失败: 未返回URL');
  }
}

function handleAvatarError() {
  ElMessage.error('上传失败，请检查登录状态或文件格式');
}

function beforeAvatarUpload(rawFile: any) {
  const isImage = ['image/jpeg', 'image/png', 'image/webp'].includes(rawFile.type);
  const isLt2M = rawFile.size / 1024 / 1024 < 2;
  if (!isImage) { ElMessage.error('头像必须是 JPG/PNG/WEBP 格式!'); return false; }
  if (!isLt2M) { ElMessage.error('头像大小不能超过 2MB!'); return false; }
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

const inputVisible = ref(false);
const inputValue = ref('');
const InputRef = ref<InstanceType<typeof ElInput>>();

const handleClose = (tag: string) => {
  formModel.expertise.splice(formModel.expertise.indexOf(tag), 1);
};
const showInput = () => {
  inputVisible.value = true;
  nextTick(() => { InputRef.value!.input!.focus(); });
};
const handleInputConfirm = () => {
  if (inputValue.value && !formModel.expertise.includes(inputValue.value)) {
    formModel.expertise.push(inputValue.value);
  }
  inputVisible.value = false;
  inputValue.value = '';
};

// ── 多专家配置 ────────────────────────────────
const activeTab = ref('characters');
const expertConfigs = ref<ExpertConfigVO[]>([]);
const expertLoading = ref(false);
const editingExpert = ref<ExpertConfigVO | null>(null);
const showExpertDialog = ref(false);
const expertForm = reactive({
  title: '',
  description: '',
  running_detail: '',
  enabled: true,
});

const KEY_LABELS: Record<string, { icon: string; color: string; badge: string }> = {
  evidence: { icon: '🔍', color: '#0ea5e9', badge: '第1步' },
  pathology: { icon: '🧬', color: '#10b981', badge: '第2步' },
  reviewer:  { icon: '📋', color: '#f59e0b', badge: '第3步' },
};

async function loadExpertConfigs() {
  expertLoading.value = true;
  try {
    expertConfigs.value = await listExpertConfigs();
  } catch {
    ElMessage.error('加载专家配置失败');
  } finally {
    expertLoading.value = false;
  }
}

function handleEditExpert(cfg: ExpertConfigVO) {
  editingExpert.value = cfg;
  Object.assign(expertForm, {
    title: cfg.title,
    description: cfg.description,
    running_detail: cfg.running_detail,
    enabled: cfg.enabled,
  });
  showExpertDialog.value = true;
}

async function handleSaveExpert() {
  if (!editingExpert.value) return;
  if (!expertForm.title.trim()) { ElMessage.warning('专家名称不能为空'); return; }
  try {
    const updated = await updateExpertConfig(editingExpert.value.key, {
      title: expertForm.title.trim(),
      description: expertForm.description,
      running_detail: expertForm.running_detail,
      enabled: expertForm.enabled,
    });
    const idx = expertConfigs.value.findIndex(c => c.key === editingExpert.value!.key);
    if (idx !== -1 && updated) expertConfigs.value[idx] = updated;
    showExpertDialog.value = false;
    ElMessage.success('保存成功');
    await loadExpertConfigs();
  } catch {
    ElMessage.error('保存失败');
  }
}

async function handleToggleExpert(cfg: ExpertConfigVO) {
  try {
    await updateExpertConfig(cfg.key, { enabled: !cfg.enabled });
    cfg.enabled = !cfg.enabled;
    ElMessage.success(cfg.enabled ? '已启用' : '已禁用');
  } catch {
    ElMessage.error('操作失败');
  }
}

// ─────────────────────────────────────────────
onMounted(() => {
  listCharacters();
  loadExpertConfigs();
});

function handleCreate() {
  editingCharacter.value = null;
  Object.assign(formModel, { key: '', name: '', product: '', hobby: '', personality: '', expertise: [], system_prompt: '', avatar: '' });
  showCreateDialog.value = true;
}

async function handleSave() {
  if (!formModel.key.trim() || !formModel.name.trim()) {
    ElMessage.warning('请输入角色标识和名称');
    return;
  }
  try {
    if (editingCharacter.value?.id) {
      await updateCharacter(editingCharacter.value.id, {
        name: formModel.name, product: formModel.product, hobby: formModel.hobby,
        personality: formModel.personality, expertise: formModel.expertise,
        system_prompt: formModel.system_prompt, avatar: formModel.avatar,
      });
      ElMessage.success('更新成功');
    } else {
      await createCharacter({
        key: formModel.key, name: formModel.name, product: formModel.product,
        hobby: formModel.hobby, personality: formModel.personality,
        expertise: formModel.expertise, system_prompt: formModel.system_prompt, avatar: formModel.avatar,
      });
      ElMessage.success('创建成功');
    }
    showCreateDialog.value = false;
    await listCharacters();
  } catch {
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
  ElMessageBox.confirm(`删除角色"${row.name}"？`, '确认删除', { type: 'warning' })
    .then(async () => {
      if (row.id) {
        await deleteCharacter(row.id);
        ElMessage.success('删除成功');
        await listCharacters();
      }
    }).catch(() => {});
}

function handleViewDetail(row: CharacterVO) {
  editingCharacter.value = row;
  showDetailDrawer.value = true;
}

async function handleToggleStatus(row: CharacterVO) {
  if (row.id) await toggleCharacterStatus(row.id);
}
</script>

<template>
  <Page title="角色与专家管理">
    <template #extra>
      <ElButton v-if="activeTab === 'characters'" type="primary" @click="handleCreate">
        <i class="i-line-md:plus mr-1" /> 创建角色
      </ElButton>
    </template>

    <ElTabs v-model="activeTab" class="mb-0">
      <!-- ── Tab 1: AI 角色 ───────────────────────── -->
      <ElTabPane label="AI 角色" name="characters">
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
                <ElButton link :type="row.is_active ? 'warning' : 'success'" size="small" @click="handleToggleStatus(row)">
                  {{ row.is_active ? '禁用' : '启用' }}
                </ElButton>
                <ElButton link type="primary" size="small" @click="handleViewDetail(row)">详情</ElButton>
                <ElButton link type="primary" size="small" @click="handleEdit(row)">编辑</ElButton>
                <ElButton link type="danger" size="small" @click="handleDelete(row)">删除</ElButton>
              </template>
            </ElTableColumn>
          </ElTable>
          <ElEmpty v-if="!loading && characters.length === 0" description="暂无角色" />
        </div>
      </ElTabPane>

      <!-- ── Tab 2: 多专家配置 ────────────────────── -->
      <ElTabPane label="多专家配置" name="experts">
        <div class="space-y-3" v-loading="expertLoading">
          <div
            v-for="cfg in expertConfigs"
            :key="cfg.key"
            class="bg-card rounded-lg border p-4 flex items-start gap-4"
            :class="{ 'opacity-50': !cfg.enabled }"
          >
            <!-- 图标+步骤标 -->
            <div class="flex flex-col items-center gap-1 shrink-0 w-14">
              <span class="text-3xl">{{ KEY_LABELS[cfg.key]?.icon || '🤖' }}</span>
              <span
                class="text-xs px-1.5 py-0.5 rounded font-medium"
                :style="{ background: (KEY_LABELS[cfg.key]?.color || '#6366f1') + '22', color: KEY_LABELS[cfg.key]?.color || '#6366f1' }"
              >
                {{ KEY_LABELS[cfg.key]?.badge || '' }}
              </span>
            </div>

            <!-- 信息 -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="font-semibold text-base">{{ cfg.title }}</span>
                <ElTag size="small" :type="cfg.enabled ? 'success' : 'info'">
                  {{ cfg.enabled ? '启用' : '禁用' }}
                </ElTag>
              </div>
              <p class="text-sm text-muted-foreground mb-1.5 line-clamp-2">{{ cfg.description }}</p>
              <p class="text-xs text-muted-foreground/70">
                <span class="font-medium">运行提示：</span>{{ cfg.running_detail }}
              </p>
            </div>

            <!-- 操作 -->
            <div class="flex flex-col gap-2 shrink-0">
              <ElButton size="small" type="primary" plain @click="handleEditExpert(cfg)">编辑</ElButton>
              <ElButton
                size="small"
                :type="cfg.enabled ? 'warning' : 'success'"
                plain
                @click="handleToggleExpert(cfg)"
              >
                {{ cfg.enabled ? '禁用' : '启用' }}
              </ElButton>
            </div>
          </div>

          <!-- 综合专家（固定，不可编辑） -->
          <div class="bg-card rounded-lg border border-dashed p-4 flex items-start gap-4 opacity-70">
            <div class="flex flex-col items-center gap-1 shrink-0 w-14">
              <span class="text-3xl">🧩</span>
              <span class="text-xs px-1.5 py-0.5 rounded font-medium" style="background:#6366f122;color:#6366f1">固定</span>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="font-semibold text-base">综合专家</span>
                <ElTag size="small" type="info">不可编辑</ElTag>
              </div>
              <p class="text-sm text-muted-foreground">综合以上专家意见，输出最终结构化回答。该专家为系统内置，始终执行。</p>
            </div>
          </div>
        </div>
      </ElTabPane>
    </ElTabs>

    <!-- 创建/编辑角色对话框 -->
    <ElDialog v-model="showCreateDialog" :title="editingCharacter ? '编辑角色' : '创建新角色'" width="600px">
      <ElForm :model="formModel" label-width="100px">
        <ElFormItem label="角色标识" required>
          <ElInput v-model="formModel.key" placeholder="英文标识，如 student" :disabled="!!editingCharacter" />
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
                <ElButton type="primary" plain>上传图片</ElButton>
              </ElUpload>
            </div>
            <div v-if="formModel.avatar" class="flex justify-center p-2 border rounded bg-gray-50 dark:bg-gray-800 w-fit">
              <ElAvatar :size="64" :src="formModel.avatar" shape="square">{{ formModel.avatar }}</ElAvatar>
            </div>
          </div>
        </ElFormItem>
        <ElFormItem label="专业领域">
          <div class="flex flex-wrap gap-2">
            <ElTag v-for="(tag, index) in formModel.expertise" :key="index" closable @close="handleClose(tag)">
              {{ tag }}
            </ElTag>
            <ElInput
              v-if="inputVisible"
              ref="InputRef"
              v-model="inputValue"
              size="small"
              class="w-auto"
              placeholder="输入专业领域并回车"
              @keyup.enter="handleInputConfirm"
              @blur="inputVisible = false"
            />
            <ElButton v-else size="small" @click="showInput">
              <i class="i-line-md:plus" /> 添加
            </ElButton>
          </div>
        </ElFormItem>
        <ElFormItem label="系统提示词">
          <ElInput v-model="formModel.system_prompt" type="textarea" :rows="4" placeholder="定义角色行为的系统提示" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="showCreateDialog = false">取消</ElButton>
        <ElButton type="primary" @click="handleSave">{{ editingCharacter ? '更新' : '创建' }}</ElButton>
      </template>
    </ElDialog>

    <!-- 编辑专家对话框 -->
    <ElDialog v-model="showExpertDialog" title="编辑专家配置" width="600px">
      <ElForm :model="expertForm" label-width="100px" v-if="editingExpert">
        <ElFormItem label="专家名称">
          <ElInput v-model="expertForm.title" placeholder="如：证据专家" />
        </ElFormItem>
        <ElFormItem label="启用状态">
          <ElSwitch v-model="expertForm.enabled" active-text="启用" inactive-text="禁用" />
        </ElFormItem>
        <ElFormItem label="运行提示">
          <ElInput v-model="expertForm.running_detail" placeholder="专家执行时显示给用户的提示文字" />
        </ElFormItem>
        <ElFormItem label="角色指令">
          <ElInput
            v-model="expertForm.description"
            type="textarea"
            :rows="6"
            placeholder="向 LLM 下达的该专家角色指令，描述其专责和分析视角"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="showExpertDialog = false">取消</ElButton>
        <ElButton type="primary" @click="handleSaveExpert">保存</ElButton>
      </template>
    </ElDialog>

    <!-- 角色详情侧边栏 -->
    <ElDrawer v-model="showDetailDrawer" title="角色详情" size="40%">
      <div v-if="editingCharacter" class="space-y-4">
        <div class="flex items-start gap-4">
          <div class="text-5xl">{{ editingCharacter.avatar || '👤' }}</div>
          <div class="flex-1 space-y-2">
            <div><span class="text-muted-foreground text-sm">名称:</span><div class="font-semibold">{{ editingCharacter.name }}</div></div>
            <div><span class="text-muted-foreground text-sm">标识符:</span><div class="font-mono text-sm">{{ editingCharacter.key }}</div></div>
            <div>
              <span class="text-muted-foreground text-sm">状态:</span>
              <ElTag :type="editingCharacter.is_active ? 'success' : 'info'">{{ editingCharacter.is_active ? '启用' : '禁用' }}</ElTag>
            </div>
          </div>
        </div>
        <div class="space-y-3 text-sm">
          <div><span class="text-muted-foreground">产品线:</span><div class="mt-1">{{ editingCharacter.product || '-' }}</div></div>
          <div><span class="text-muted-foreground">爱好:</span><div class="mt-1">{{ editingCharacter.hobby || '-' }}</div></div>
          <div><span class="text-muted-foreground">性格特点:</span><div class="mt-1">{{ editingCharacter.personality || '-' }}</div></div>
          <div>
            <span class="text-muted-foreground">专业领域:</span>
            <div class="mt-1 flex flex-wrap gap-1">
              <ElTag v-for="(exp, idx) in editingCharacter.expertise" :key="idx" size="small">{{ exp }}</ElTag>
            </div>
          </div>
        </div>
        <div>
          <span class="text-muted-foreground text-sm">系统提示词:</span>
          <div class="mt-2 p-3 bg-muted rounded text-xs font-mono whitespace-pre-wrap break-words">{{ editingCharacter.system_prompt || '-' }}</div>
        </div>
        <div v-if="editingCharacter.created_at" class="text-xs text-muted-foreground space-y-1 pt-4 border-t">
          <div>创建: {{ new Date(editingCharacter.created_at).toLocaleString() }}</div>
          <div v-if="editingCharacter.updated_at">更新: {{ new Date(editingCharacter.updated_at).toLocaleString() }}</div>
        </div>
      </div>
    </ElDrawer>
  </Page>
</template>
