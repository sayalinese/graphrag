<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue';
import {
  ElTable,
  ElTableColumn,
  ElButton,
  ElTag,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElMessageBox,
  ElMessage,
  ElRadioGroup,
  ElRadio,
  ElScrollbar,
} from 'element-plus';
import { useRoleApi } from '#/api/system/role';
import { $t } from '#/locales';

// 简化角色类型
import type { RoleItem } from '#/api/system/role';
const { roles, listRoles, createRole, updateRole, deleteRole, toggleStatus } =
  useRoleApi();

const loading = ref(false);
const drawerVisible = ref(false);
const editing = ref<RoleItem | null>(null);

// 表单模型
const formModel = reactive<RoleItem>({
  id: 0,
  name: '',
  status: 1,
  remark: '',
  permissions: [],
  createTime: '',
});

// 与用户权限保持一致：仅保留 超级管理员 / 普通管理员
const permissionOptions = computed(() => [
  { label: $t('page.system.user.permissionSuper'), value: 'super' },
  { label: $t('page.system.user.permissionAdmin'), value: 'admin' },
]);

function openCreate() {
  editing.value = null;
  Object.assign(formModel, {
    id: 0,
    name: '',
    status: 1,
    remark: '',
    permissions: [],
    createTime: '',
  });
  drawerVisible.value = true;
}

function openEdit(row: RoleItem) {
  editing.value = row;
  Object.assign(formModel, { ...row });
  drawerVisible.value = true;
}

function handleDelete(row: RoleItem) {
  ElMessageBox.confirm(
    $t('ui.actionMessage.deleteConfirm', [row.name]),
    $t('common.prompt'),
    { type: 'warning' },
  )
    .then(() => {
      deleteRole(row.id).then(() => {
        ElMessage.success($t('ui.actionMessage.deleteSuccess', [row.name]));
      });
    })
    .catch(() => {});
}

function handleStatusToggle(row: RoleItem) {
  const next = row.status === 1 ? 0 : 1;
  ElMessageBox.confirm(
    `${$t('system.role.roleName')} ${row.name} ${$t('common.confirm')} ${next === 1 ? $t('common.enabled') : $t('common.disabled')}?`,
    $t('system.role.status'),
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
  if (!formModel.name || formModel.name.length < 2) {
    ElMessage.error('名称至少 2 个字符');
    return;
  }
  loading.value = true;
  setTimeout(() => {
    if (editing.value) {
      updateRole(editing.value.id, { ...formModel }).then(() => {
        ElMessage.success($t('ui.actionMessage.operationSuccess'));
      });
    } else {
      createRole({ ...formModel }).then(() => {
        ElMessage.success($t('ui.actionMessage.operationSuccess'));
      });
    }
    loading.value = false;
    drawerVisible.value = false;
  }, 400);
}

const drawerTitle = computed(() =>
  editing.value
    ? $t('ui.actionTitle.edit', [$t('system.role.name')])
    : $t('ui.actionTitle.create', [$t('system.role.name')]),
);

onMounted(() => {
  listRoles();
});
</script>

<template>
  <div class="space-y-4 p-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-medium">
        {{ $t('page.system.role.list') || $t('page.system.role.name') }}
      </h2>
      <ElButton type="primary" @click="openCreate">
        {{ $t('ui.actionTitle.create', [$t('page.system.role.name')]) }}
      </ElButton>
    </div>

    <ElTable :data="roles" border style="width: 100%" size="small">
      <ElTableColumn
        prop="name"
        :label="$t('page.system.role.roleName')"
        min-width="140"
      />
      <ElTableColumn prop="id" label="ID" width="120" />
      <ElTableColumn :label="$t('page.system.role.status')" width="100">
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
        prop="remark"
        :label="$t('page.system.role.remark')"
        min-width="160"
      />
      <ElTableColumn
        prop="createTime"
        :label="$t('page.system.role.createTime')"
        width="180"
      />
      <ElTableColumn
        :label="$t('page.system.role.operation')"
        fixed="right"
        width="160"
      >
        <template #default="{ row }">
          <div class="flex items-center gap-2">
            <ElButton size="small" @click="openEdit(row)">{{
              $t('common.edit')
            }}</ElButton>
            <ElButton size="small" type="danger" @click="handleDelete(row)">{{
              $t('common.delete')
            }}</ElButton>
          </div>
        </template>
      </ElTableColumn>
    </ElTable>

    <ElDrawer
      v-model="drawerVisible"
      :title="drawerTitle"
      size="480px"
      append-to-body
    >
      <ElScrollbar height="calc(100vh - 140px)">
        <ElForm label-width="88px" label-position="left" class="pr-2">
          <ElFormItem :label="$t('page.system.role.roleName')" required>
            <ElInput v-model="formModel.name" placeholder="请输入角色名称" />
          </ElFormItem>
          <ElFormItem :label="$t('page.system.role.status')">
            <ElRadioGroup v-model="formModel.status">
              <ElRadio :value="1">{{ $t('common.enabled') }}</ElRadio>
              <ElRadio :value="0">{{ $t('common.disabled') }}</ElRadio>
            </ElRadioGroup>
          </ElFormItem>
          <ElFormItem :label="$t('page.system.role.remark')">
            <ElInput
              v-model="formModel.remark"
              type="textarea"
              :rows="3"
              :placeholder="$t('page.system.role.remark')"
            />
          </ElFormItem>
          <ElFormItem :label="$t('page.system.role.setPermissions')">
            <ElSelect
              v-model="formModel.permissions"
              multiple
              collapse-tags
              collapse-tags-tooltip
              :placeholder="$t('page.system.role.setPermissions')"
            >
              <ElOption
                v-for="opt in permissionOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </ElSelect>
          </ElFormItem>
          <div class="flex justify-end gap-3 pt-2">
            <ElButton @click="drawerVisible = false">{{
              $t('common.cancel')
            }}</ElButton>
            <ElButton type="primary" :loading="loading" @click="submitForm">{{
              $t('common.confirm')
            }}</ElButton>
          </div>
        </ElForm>
      </ElScrollbar>
    </ElDrawer>
  </div>
</template>

<style scoped></style>
