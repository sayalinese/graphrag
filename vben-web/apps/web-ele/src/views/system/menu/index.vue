<script setup lang="ts">
import type { MenuItem } from '#/api/system/menu';

import { computed, onMounted, reactive, ref } from 'vue';

import { useAccessStore } from '@vben/stores';

import {
  ElButton,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElRadioGroup,
  ElRadio,
  ElTree,
  ElSelect,
  ElOption,
  ElMessageBox,
  ElMessage,
  ElTag,
} from 'element-plus';
import { IconifyIcon } from '@vben/icons';

import { getMenuRecords, useMenuApi } from '#/api/system/menu';
import { $t } from '#/locales';
import { router } from '#/router';

const accessStore = useAccessStore();
const { listMenus, createMenu, updateMenu, deleteMenu, toggleMenuStatus } =
  useMenuApi();

const menuTree = ref<MenuItem[]>([]);

const drawerVisible = ref(false);
const editing = ref<MenuItem | null>(null);

const formModel = reactive<MenuItem>({
  id: 0,
  type: 'menu',
  title: '',
  path: '',
  status: 1,
});

async function refreshMenuTree() {
  menuTree.value = await listMenus();
}

async function refreshAccessMenus() {
  accessStore.setAccessMenus(await getMenuRecords());
}

function openCreateRoot() {
  editing.value = null;
  Object.assign(formModel, {
    id: 0,
    pid: undefined,
    type: 'catalog',
    title: '',
    path: '',
    status: 1,
  });
  drawerVisible.value = true;
}
function openAppend(parent: MenuItem) {
  // 仅允许根层 catalog 节点添加一级菜单
  if (parent.pid !== undefined || parent.type !== 'catalog') return;
  editing.value = null;
  Object.assign(formModel, {
    id: 0,
    pid: parent.id,
    type: 'menu',
    title: '',
    path: '',
    status: 1,
  });
  drawerVisible.value = true;
}
function openEdit(node: MenuItem) {
  editing.value = node;
  Object.assign(formModel, { ...node });
  drawerVisible.value = true;
}

function normalizeTree(list: MenuItem[]): MenuItem[] {
  return list.map((item) => ({
    ...item,
    children: item.children ? normalizeTree(item.children) : undefined,
  }));
}

// 原始（完整）树数据
const treeData = computed(() => normalizeTree(menuTree.value));

// 仅显示启用的菜单：规则
// 1) 根级(catalog 且无 pid)即使禁用仍显示，方便重新启用
// 2) 非根节点 status=0 时隐藏
function filterVisible(list: MenuItem[]): MenuItem[] {
  return list
    .filter((item) => item.status === 1 || item.pid === undefined)
    .map((item) => ({
      ...item,
      children: item.children ? filterVisible(item.children) : undefined,
    }));
}
const visibleTreeData = computed(() => filterVisible(treeData.value));

function submitForm() {
  if (!formModel.title) {
    ElMessage.error('标题必填');
    return;
  }
  if (
    formModel.type === 'menu' &&
    formModel.path &&
    !formModel.path.startsWith('/')
  ) {
    ElMessage.error('路径必须以 / 开头');
    return;
  }
  const payload = { ...formModel };
  const action = editing.value
    ? updateMenu(editing.value.id, payload)
    : createMenu(payload as Omit<MenuItem, 'id'>);

  action
    .then(async (result) => {
      const target = result || (editing.value ? { ...editing.value, ...payload } : null);
      await refreshMenuTree();
      if (target) syncRouteMenuStatus(target as MenuItem);
      await refreshAccessMenus();
      ElMessage.success(editing.value ? '更新成功' : '创建成功');
      drawerVisible.value = false;
    })
    .catch(() => {
      ElMessage.error(editing.value ? '更新失败' : '创建失败');
    });
}

function deleteNode(node: MenuItem) {
  ElMessageBox.confirm(`确认删除: ${node.title} ?`, '提示', { type: 'warning' })
    .then(async () => {
      await deleteMenu(node.id);
      await refreshMenuTree();
      await refreshAccessMenus();
      ElMessage.success('删除成功');
    })
    .catch(() => {});
}

function toggleStatus(node: MenuItem) {
  const next = node.status === 1 ? 0 : 1;
  ElMessageBox.confirm(
    `确认将 ${node.title} 状态切换为 ${next === 1 ? '启用' : '禁用'}?`,
    '状态切换',
    { type: 'info' },
  )
    .then(async () => {
      const updated = await toggleMenuStatus(node.id);
      await refreshMenuTree();
      ElMessage.success('状态已更新');
      syncRouteMenuStatus(updated || { ...node, status: next });
      if (updated?.children) updated.children.forEach((c) => syncRouteMenuStatus(c));
      await refreshAccessMenus();
    })
    .catch(() => {});
}

// 根据菜单节点的 status 将对应路由的 meta.hideInMenu 动态更新
function syncRouteMenuStatus(node: MenuItem) {
  if (!node.path) return; // 仅对有 path 的 menu 应用
  const route = router.getRoutes().find((r) => r.path === node.path);
  if (!route) return;
  // 禁用 => 隐藏；启用 => 显示（除非其它逻辑也要求隐藏）
  route.meta.hideInMenu = node.status === 0;
}

const drawerTitle = computed(() =>
  editing.value ? '编辑菜单' : formModel.pid ? '新增子菜单' : '新增根菜单',
);

const menuTypeOptions = [
  { label: '目录', value: 'catalog' },
  { label: '菜单', value: 'menu' },
  { label: '按钮', value: 'button' },
  { label: '内嵌', value: 'embedded' },
  { label: '外链', value: 'link' },
];

onMounted(async () => {
  await refreshMenuTree();
  await refreshAccessMenus();
});
</script>

<template>
  <div class="space-y-4 p-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-medium">{{ $t('page.system.menu.manager') }}</h2>
      <ElButton type="primary" @click="openCreateRoot">{{
        $t('ui.actionTitle.create', [$t('page.system.menu.name')])
      }}</ElButton>
    </div>

    <div class="text-xs text-gray-500 dark:text-gray-400">
      状态含义：启用 = 菜单在导航中显示；禁用 = 菜单在导航中隐藏
    </div>

    <ElTree
      :data="visibleTreeData"
      node-key="id"
      :props="{ label: 'title', children: 'children' }"
      default-expand-all
      class="rounded border px-3 py-2"
    >
      <template #default="{ data }">
        <div class="flex w-full items-center gap-2">
          <IconifyIcon v-if="data.icon" :icon="data.icon" class="text-base" />
          <span class="font-medium">{{ $t(data.title) || data.title }}</span>
          <ElTag
            size="small"
            :type="data.status === 1 ? 'success' : 'info'"
            class="cursor-pointer"
            @click.stop="toggleStatus(data)"
          >
            {{
              data.status === 1 ? $t('common.enabled') : $t('common.disabled')
            }}
          </ElTag>
          <ElTag v-if="data.type" size="small" type="warning">{{
            data.type
          }}</ElTag>
          <div class="ml-auto flex gap-2">
            <ElButton
              size="small"
              @click.stop="openAppend(data)"
              v-if="!data.pid && data.type === 'catalog'"
            >
              {{ $t('ui.actionTitle.create', [$t('page.system.menu.name')]) }}
            </ElButton>
            <ElButton size="small" @click.stop="openEdit(data)">{{
              $t('common.edit')
            }}</ElButton>
            <ElButton
              size="small"
              type="danger"
              @click.stop="deleteNode(data)"
              >{{ $t('common.delete') }}</ElButton
            >
          </div>
        </div>
      </template>
    </ElTree>

    <ElDrawer
      v-model="drawerVisible"
      :title="drawerTitle"
      size="480px"
      append-to-body
    >
      <ElForm label-width="88px" label-position="left">
        <ElFormItem :label="$t('page.system.menu.type')" required>
          <ElSelect
            v-model="formModel.type"
            :disabled="!!editing"
            placeholder="选择类型"
          >
            <ElOption
              v-for="opt in menuTypeOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.system.menu.menuTitle')" required>
          <ElInput
            v-model="formModel.title"
            :placeholder="$t('system.menu.menuTitle')"
          />
        </ElFormItem>
        <ElFormItem
          v-if="['menu', 'embedded', 'catalog'].includes(formModel.type)"
          :label="$t('page.system.menu.path')"
          :required="formModel.type === 'menu'"
        >
          <ElInput
            v-model="formModel.path"
            :placeholder="$t('page.system.menu.path')"
          />
        </ElFormItem>
        <ElFormItem :label="$t('page.system.menu.icon')">
          <ElSelect
            v-model="formModel.icon"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入图标名称"
          >
            <ElOption
              v-for="opt in [
                'carbon:cloud-service-management',
                'carbon:user-role',
                'carbon:menu',
                'carbon:user-avatar',
                'lucide:message-square',
                'lucide:bot-message-square',
                'lucide:settings-2',
                'lucide:network',
                'mdi:view-dashboard-outline',
                'mdi:database-plus-outline',
                'mdi:eye-outline',
                'mdi:cog-outline',
              ]"
              :key="opt"
              :label="opt"
              :value="opt"
            >
              <div class="flex items-center gap-2">
                <IconifyIcon :icon="opt" class="text-base" />
                <span>{{ opt }}</span>
              </div>
            </ElOption>
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.system.menu.status')">
          <ElRadioGroup v-model="formModel.status">
            <ElRadio :value="1">{{ $t('common.enabled') }}</ElRadio>
            <ElRadio :value="0">{{ $t('common.disabled') }}</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <div class="flex justify-end gap-3 pt-2">
          <ElButton @click="drawerVisible = false">{{
            $t('common.cancel')
          }}</ElButton>
          <ElButton type="primary" @click="submitForm">{{
            $t('common.confirm')
          }}</ElButton>
        </div>
      </ElForm>
    </ElDrawer>
  </div>
</template>

<style scoped></style>
