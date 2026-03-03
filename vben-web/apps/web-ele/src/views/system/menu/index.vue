<script setup lang="ts">
import { ref, reactive, computed } from 'vue';
import { router } from '#/router';
import { $t } from '#/locales';
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

interface MenuItem {
  id: number;
  pid?: number;
  type: 'catalog' | 'menu' | 'button' | 'embedded' | 'link';
  title: string; // 直接使用已经解析后的标题（简化）
  path?: string;
  icon?: string;
  status: 0 | 1;
  children?: MenuItem[];
}

let idSeed = 100;
const menuTree = ref<MenuItem[]>([
  {
    id: 1,
    type: 'catalog',
    title: 'page.system.title',
    icon: 'carbon:cloud-service-management',
    status: 1,
    children: [
      {
        id: 11,
        pid: 1,
        type: 'menu',
        title: 'page.system.role.list',
        path: '/system/role',
        icon: 'carbon:user-role',
        status: 1,
      },
      {
        id: 12,
        pid: 1,
        type: 'menu',
        title: 'page.system.menu.manager',
        path: '/system/menu',
        icon: 'carbon:menu',
        status: 1,
      },
      {
        id: 13,
        pid: 1,
        type: 'menu',
        title: 'page.system.user.list',
        path: '/system/user',
        icon: 'carbon:user-avatar',
        status: 1,
      },
    ],
  },
  {
    id: 2,
    type: 'catalog',
    title: 'page.kg.title',
    icon: 'lucide:network',
    status: 1,
    children: [
      {
        id: 21,
        pid: 2,
        type: 'menu',
        title: 'page.kg.dashboard',
        path: '/kg/dashboard',
        icon: 'mdi:view-dashboard-outline',
        status: 1,
      },
      {
        id: 22,
        pid: 2,
        type: 'menu',
        title: 'page.kg.construct',
        path: '/kg/construct',
        icon: 'mdi:database-plus-outline',
        status: 1,
      },
      {
        id: 23,
        pid: 2,
        type: 'menu',
        title: 'page.kg.preview',
        path: '/kg/preview',
        icon: 'mdi:eye-outline',
        status: 1,
      },
      {
        id: 24,
        pid: 2,
        type: 'menu',
        title: 'page.kg.management',
        path: '/kg/management',
        icon: 'mdi:cog-outline',
        status: 1,
      },
    ],
  },
  {
    id: 3,
    type: 'catalog',
    title: 'page.chat.title',
    path: '/chat',
    icon: 'lucide:message-square',
    status: 1,
    children: [
      {
        id: 31,
        pid: 3,
        type: 'menu',
        title: 'page.chat.title',
        path: '/chat/ai',
        icon: 'lucide:bot-message-square',
        status: 1,
      },
      {
        id: 32,
        pid: 3,
        type: 'menu',
        title: 'page.chat.management',
        path: '/chat/management',
        icon: 'lucide:settings-2',
        status: 1,
      },
    ],
  },
]);

const drawerVisible = ref(false);
const editing = ref<MenuItem | null>(null);

const formModel = reactive<MenuItem>({
  id: 0,
  type: 'menu',
  title: '',
  path: '',
  status: 1,
});

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
  if (editing.value) {
    const target = findNode(editing.value.id, menuTree.value);
    if (target) {
      Object.assign(target, { ...formModel });
    }
    ElMessage.success('更新成功');
    // 同步路由隐藏状态（编辑可能修改路径或标题，这里仅按最新 status 与 path 应用）
    if (target) syncRouteMenuStatus(target);
  } else {
    const newItem: MenuItem = { ...formModel, id: ++idSeed };
    if (newItem.pid) {
      const parent = findNode(newItem.pid, menuTree.value);
      if (parent) {
        parent.children = parent.children || [];
        parent.children.push(newItem);
      }
    } else {
      menuTree.value.push(newItem);
    }
    ElMessage.success('创建成功');
    syncRouteMenuStatus(newItem);
  }
  drawerVisible.value = false;
}

function findNode(id: number, list: MenuItem[]): MenuItem | null {
  for (const item of list) {
    if (item.id === id) return item;
    if (item.children) {
      const found = findNode(id, item.children);
      if (found) return found;
    }
  }
  return null;
}

function deleteNode(node: MenuItem) {
  ElMessageBox.confirm(`确认删除: ${node.title} ?`, '提示', { type: 'warning' })
    .then(() => {
      removeNode(node.id, menuTree.value);
      ElMessage.success('删除成功');
    })
    .catch(() => {});
}

function removeNode(id: number, list: MenuItem[]): boolean {
  const idx = list.findIndex((i) => i.id === id);
  if (idx > -1) {
    list.splice(idx, 1);
    return true;
  }
  for (const item of list) {
    if (item.children && removeNode(id, item.children)) return true;
  }
  return false;
}

function toggleStatus(node: MenuItem) {
  const next = node.status === 1 ? 0 : 1;
  ElMessageBox.confirm(
    `确认将 ${node.title} 状态切换为 ${next === 1 ? '启用' : '禁用'}?`,
    '状态切换',
    { type: 'info' },
  )
    .then(() => {
      node.status = next;
      // 如果是根级 catalog 且被禁用，则其子级全部禁用
      if (node.pid === undefined && node.type === 'catalog' && next === 0) {
        disableChildren(node);
      }
      ElMessage.success('状态已更新');
      // 同步前端路由菜单可见性
      syncRouteMenuStatus(node);
      if (node.children) node.children.forEach((c) => syncRouteMenuStatus(c));
    })
    .catch(() => {});
}

function disableChildren(parent: MenuItem) {
  if (!parent.children) return;
  parent.children.forEach((child) => {
    child.status = 0;
    disableChildren(child);
  });
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
