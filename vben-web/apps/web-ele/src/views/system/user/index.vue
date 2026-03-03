<script setup lang="ts">
import type { UserItem } from '#/api/system/user';

import { computed, onMounted, reactive, ref } from 'vue';

import { useAccessStore } from '@vben/stores';

import {
  ElAvatar,
  ElButton,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElRadio,
  ElRadioGroup,
  ElScrollbar,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
  ElUpload,
} from 'element-plus';

import { useUserApi } from '#/api/system/user';
import { $t } from '#/locales';

const { users, listUsers, createUser, updateUser, deleteUser, toggleStatus } =
  useUserApi();

const loading = ref(false);
const drawerVisible = ref(false);
const editing = ref<null | UserItem>(null);

const formModel = reactive<UserItem>({
  id: 0,
  username: '',
  avatar: '',
  email: '',
  permissions: [],
  createTime: '',
  lastVisitTime: '',
  status: 1,
});

// 权限改为仅两类：超级管理员 / 普通管理员
const permissionOptions = computed(() => [
  { label: $t('page.system.user.permissionSuper'), value: 'super' },
  { label: $t('page.system.user.permissionAdmin'), value: 'admin' },
]);

// 显示标签映射
const permissionLabelMap = computed(() => ({
  super: $t('page.system.user.permissionSuper'),
  admin: $t('page.system.user.permissionAdmin'),
}));

function openCreate() {
  editing.value = null;
  Object.assign(formModel, {
    id: 0,
    username: '',
    avatar: '',
    email: '',
    permissions: [],
    createTime: '',
    lastVisitTime: '',
    status: 1,
  });
  drawerVisible.value = true;
}

function openEdit(row: UserItem) {
  editing.value = row;
  Object.assign(formModel, { ...row });
  drawerVisible.value = true;
}

function handleDelete(row: UserItem) {
  ElMessageBox.confirm(
    $t('ui.actionMessage.deleteConfirm', [row.username]),
    $t('common.prompt'),
    { type: 'warning' },
  )
    .then(() => {
      deleteUser(row.id).then(() => {
        ElMessage.success($t('ui.actionMessage.deleteSuccess', [row.username]));
      });
    })
    .catch(() => {});
}

function handleStatusToggle(row: UserItem) {
  const next = row.status === 1 ? 0 : 1;
  ElMessageBox.confirm(
    `${$t('page.system.user.username')} ${row.username} ${$t('common.confirm')} ${next === 1 ? $t('common.enabled') : $t('common.disabled')}?`,
    $t('page.system.user.status'),
    { type: 'info' },
  )
    .then(() => {
      toggleStatus(row.id).then(() => {
        ElMessage.success($t('ui.actionMessage.operationSuccess'));
      });
    })
    .catch(() => {});
}

function submitForm() {
  if (!formModel.username || formModel.username.length < 2) {
    ElMessage.error(
      $t('ui.formRules.minLength', [$t('page.system.user.username'), 2]),
    );
    return;
  }
  loading.value = true;
  setTimeout(() => {
    if (editing.value) {
      updateUser(editing.value.id, { ...formModel }).then(() => {
        ElMessage.success($t('ui.actionMessage.operationSuccess'));
      });
    } else {
      createUser({ ...formModel }).then(() => {
        ElMessage.success($t('ui.actionMessage.operationSuccess'));
      });
    }
    loading.value = false;
    drawerVisible.value = false;
  }, 300);
}

// token store
const accessStore = useAccessStore();

// 上传前校验：类型 + 大小限制 2MB
function beforeAvatarUpload(file: File) {
  const ok = ['image/png', 'image/jpg', 'image/jpeg', 'image/webp'];
  if (!ok.includes(file.type)) {
    ElMessage.error('仅支持 png/jpg/jpeg/webp 格式');
    return false;
  }
  if (file.size / 1024 / 1024 > 2) {
    ElMessage.error('文件大小不能超过 2MB');
    return false;
  }
  return true;
}

// 上传成功回调：后端返回 {code:0,data:{url}}
function handleAvatarUploaded(resp: any) {
  const url = resp?.data?.url || resp?.url;
  if (url) {
    formModel.avatar = url;
    ElMessage.success($t('ui.actionMessage.operationSuccess'));
  } else {
    ElMessage.error('上传失败: 未返回URL');
  }
}

// 上传请求头（ElUpload不会自动加拦截器）
const uploadHeaders = computed(() => {
  const token = accessStore.accessToken;
  return token ? { Authorization: `Bearer ${token}` } : {};
});

const drawerTitle = computed(() =>
  editing.value
    ? $t('ui.actionTitle.edit', [$t('page.system.user.name')])
    : $t('ui.actionTitle.create', [$t('page.system.user.name')]),
);

onMounted(() => {
  listUsers();
});
</script>

<template>
  <div class="space-y-4 p-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-medium">
        {{ $t('page.system.user.list') || $t('page.system.user.name') }}
      </h2>
      <ElButton type="primary" @click="openCreate">
        {{ $t('ui.actionTitle.create', [$t('page.system.user.name')]) }}
      </ElButton>
    </div>

    <ElTable :data="users" border style="width: 100%" size="small">
      <ElTableColumn prop="id" label="ID" width="80" />
      <ElTableColumn :label="$t('page.system.user.avatar')" width="80">
        <template #default="{ row }">
          <ElAvatar :size="32" :src="row.avatar" v-if="row.avatar" />
          <ElAvatar :size="32" v-else>{{ row.username?.[0] || '?' }}</ElAvatar>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="username"
        :label="$t('page.system.user.username')"
        min-width="140"
      />
      <ElTableColumn
        prop="email"
        :label="$t('page.system.user.email')"
        min-width="180"
      />
      <ElTableColumn
        :label="$t('page.system.user.permissions')"
        min-width="180"
      >
        <template #default="{ row }">
          <div class="flex flex-wrap gap-1">
            <ElTag
              v-for="p in row.permissions"
              :key="p"
              type="info"
              size="small"
            >
              {{ (permissionLabelMap as any)[p] || p }}
            </ElTag>
          </div>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="createTime"
        :label="$t('page.system.user.createTime')"
        width="180"
      />
      <ElTableColumn
        prop="lastVisitTime"
        :label="$t('page.system.user.lastVisitTime')"
        width="190"
      />
      <ElTableColumn :label="$t('page.system.user.status')" width="100">
        <template #default="{ row }">
          <ElTag
            :type="row.status === 1 ? 'success' : 'info'"
            class="cursor-pointer"
            @click="handleStatusToggle(row)"
          >
            {{
              row.status === 1 ? $t('common.enabled') : $t('common.disabled')
            }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn
        :label="$t('page.system.user.operation')"
        fixed="right"
        width="160"
      >
        <template #default="{ row }">
          <div class="flex items-center gap-2">
            <ElButton size="small" @click="openEdit(row)">
              {{ $t('common.edit') }}
            </ElButton>
            <ElButton size="small" type="danger" @click="handleDelete(row)">
              {{ $t('common.delete') }}
            </ElButton>
          </div>
        </template>
      </ElTableColumn>
    </ElTable>

    <ElDrawer
      v-model="drawerVisible"
      :title="drawerTitle"
      size="520px"
      append-to-body
    >
      <ElScrollbar height="calc(100vh - 140px)">
        <ElForm label-width="96px" label-position="left" class="pr-2">
          <ElFormItem :label="$t('page.system.user.username')" required>
            <ElInput
              v-model="formModel.username"
              :placeholder="$t('page.system.user.username')"
            />
          </ElFormItem>
          <ElFormItem :label="$t('page.system.user.avatar')">
            <ElUpload
              action="/api/upload/avatar"
              :show-file-list="false"
              :before-upload="beforeAvatarUpload"
              :on-success="handleAvatarUploaded"
              :headers="uploadHeaders"
              accept="image/png,image/jpg,image/jpeg,image/webp"
            >
              <ElButton>
                {{
                  formModel.avatar
                    ? $t('common.edit')
                    : $t('ui.actionTitle.create', [
                        $t('page.system.user.avatar'),
                      ])
                }}
              </ElButton>
            </ElUpload>
            <div v-if="formModel.avatar" class="mt-2">
              <ElAvatar :size="48" :src="formModel.avatar" />
            </div>
          </ElFormItem>
          <ElFormItem :label="$t('page.system.user.email')">
            <ElInput
              v-model="formModel.email"
              type="email"
              :placeholder="$t('page.system.user.email')"
            />
          </ElFormItem>
          <ElFormItem :label="$t('page.system.user.permissions')">
            <ElSelect
              v-model="formModel.permissions"
              multiple
              collapse-tags
              collapse-tags-tooltip
              :placeholder="$t('page.system.user.permissions')"
            >
              <ElOption
                v-for="opt in permissionOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </ElSelect>
          </ElFormItem>
          <ElFormItem :label="$t('page.system.user.status')">
            <ElRadioGroup v-model="formModel.status">
              <ElRadio :value="1">{{ $t('common.enabled') }}</ElRadio>
              <ElRadio :value="0">{{ $t('common.disabled') }}</ElRadio>
            </ElRadioGroup>
          </ElFormItem>
          <div class="flex justify-end gap-3 pt-2">
            <ElButton @click="drawerVisible = false">
              {{ $t('common.cancel') }}
            </ElButton>
            <ElButton type="primary" :loading="loading" @click="submitForm">
              {{ $t('common.confirm') }}
            </ElButton>
          </div>
        </ElForm>
      </ElScrollbar>
    </ElDrawer>
  </div>
</template>

<style scoped></style>
