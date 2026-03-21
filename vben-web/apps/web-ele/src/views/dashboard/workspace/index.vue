<script lang="ts" setup>
import type {
  WorkbenchProjectItem,
  WorkbenchQuickNavItem,
  WorkbenchTodoItem,
  WorkbenchTrendItem,
} from '@vben/common-ui';

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import {
  AnalysisChartCard,
  WorkbenchHeader,
  WorkbenchProject,
  WorkbenchQuickNav,
  WorkbenchTodo,
  WorkbenchTrends,
} from '@vben/common-ui';
import { preferences } from '@vben/preferences';
import { useUserStore } from '@vben/stores';
import { openWindow } from '@vben/utils';

import AnalyticsVisitsSource from '../analytics/analytics-visits-source.vue';
import {
  fetchDashboardSnapshot,
  topEntries,
  type DashboardSnapshot,
} from '../api';

const userStore = useUserStore();
const snapshot = ref<DashboardSnapshot | null>(null);

// 同样，这里的 url 也可以使用以 http 开头的外部链接
const quickNavItems: WorkbenchQuickNavItem[] = [
  {
    color: '#1fdaca',
    icon: 'ion:home-outline',
    title: '首页',
    url: '/',
  },
  {
    color: '#bf0c2c',
    icon: 'ion:grid-outline',
    title: '仪表盘',
    url: '/dashboard',
  },
  {
    color: '#00d8ff',
    icon: 'ion:bar-chart-outline',
    title: '图表',
    url: '/analytics',
  },
];

const sourceItems = computed(() => topEntries(snapshot.value?.stats.nodeTypes ?? {}, 6));

const projectItems = computed<WorkbenchProjectItem[]>(() => {
  const centralNodes = snapshot.value?.centralNodes ?? [];
  const fallbackDate = snapshot.value?.timestamp?.slice(0, 10) || '0000-00-00';
  if (centralNodes.length === 0) {
    return [
      {
        color: '#5ab1ef',
        content: '当前暂无核心节点数据，已按 0 展示。',
        date: fallbackDate,
        group: '核心节点',
        icon: 'carbon:chart-network',
        title: '0',
        url: '/analytics',
      },
    ];
  }
  return centralNodes.slice(0, 6).map((node, index) => ({
    color: ['#5ab1ef', '#3fb27f', '#e18525', '#bf0c2c', '#00d8ff', '#EBD94E'][index % 6],
    content: `关联度 ${node.degree || 0}`,
    date: fallbackDate,
    group: node.labels[0] || '核心节点',
    icon: 'carbon:chart-network',
    title: node.name || node.id || `节点${index + 1}`,
    url: '/analytics',
  }));
});

const todoItems = computed<WorkbenchTodoItem[]>(() => {
  const stats = snapshot.value?.stats;
  return [
    {
      completed: (stats?.nodes ?? 0) > 0,
      content: `当前节点总数：${stats?.nodes ?? 0}`,
      date: snapshot.value?.timestamp || '-',
      title: '节点总数',
    },
    {
      completed: (stats?.edges ?? 0) > 0,
      content: `当前关系总数：${stats?.edges ?? 0}`,
      date: snapshot.value?.timestamp || '-',
      title: '关系总数',
    },
    {
      completed: (stats?.communities ?? 0) > 0,
      content: `当前社区总数：${stats?.communities ?? 0}`,
      date: snapshot.value?.timestamp || '-',
      title: '社区总数',
    },
    {
      completed: (stats?.averageDegree ?? 0) > 0,
      content: `当前平均度：${stats?.averageDegree ?? 0}`,
      date: snapshot.value?.timestamp || '-',
      title: '平均度',
    },
  ];
});

const trendItems = computed<WorkbenchTrendItem[]>(() => {
  const nodeTypes = topEntries(snapshot.value?.stats.nodeTypes ?? {}, 4);
  const relationTypes = topEntries(snapshot.value?.stats.relationTypes ?? {}, 4);
  const items = [
    ...nodeTypes.map((item, index) => ({
      avatar: `svg:avatar-${(index % 4) + 1}`,
      content: `节点类型 <a>${item.name}</a> 当前数量 <a>${item.value}</a>`,
      date: snapshot.value?.timestamp || '刚刚',
      title: '节点分布',
    })),
    ...relationTypes.map((item, index) => ({
      avatar: `svg:avatar-${(index % 4) + 1}`,
      content: `关系类型 <a>${item.name}</a> 当前数量 <a>${item.value}</a>`,
      date: snapshot.value?.timestamp || '刚刚',
      title: '关系分布',
    })),
  ];
  return items.length > 0
    ? items
    : [
        {
          avatar: 'svg:avatar-1',
          content: '当前暂无类型分布数据，已按 0 展示。',
          date: '刚刚',
          title: '图谱统计',
        },
      ];
});

const router = useRouter();

onMounted(async () => {
  snapshot.value = await fetchDashboardSnapshot();
});

// 这是一个示例方法，实际项目中需要根据实际情况进行调整
// This is a sample method, adjust according to the actual project requirements
function navTo(nav: WorkbenchProjectItem | WorkbenchQuickNavItem) {
  if (nav.url?.startsWith('http')) {
    openWindow(nav.url);
    return;
  }
  if (nav.url?.startsWith('/')) {
    router.push(nav.url).catch((error) => {
      console.error('Navigation failed:', error);
    });
  } else {
    console.warn(`Unknown URL for navigation item: ${nav.title} -> ${nav.url}`);
  }
}
</script>

<template>
  <div class="p-5">
    <WorkbenchHeader
      :avatar="userStore.userInfo?.avatar || preferences.app.defaultAvatar"
    >
      <template #title>
        早安, {{ userStore.userInfo?.realName }}, 开始您一天的工作吧！
      </template>
      <template #description> 今日晴，20℃ - 32℃！ </template>
    </WorkbenchHeader>

    <div class="mt-5 flex flex-col lg:flex-row">
      <div class="mr-4 w-full lg:w-3/5">
        <WorkbenchProject :items="projectItems" title="核心节点" @click="navTo" />
        <WorkbenchTrends :items="trendItems" class="mt-5" title="图谱分布" />
      </div>
      <div class="w-full lg:w-2/5">
        <WorkbenchQuickNav
          :items="quickNavItems"
          class="mt-5 lg:mt-0"
          title="快捷导航"
          @click="navTo"
        />
        <WorkbenchTodo :items="todoItems" class="mt-5" title="图谱状态" />
        <AnalysisChartCard class="mt-5" title="节点类型占比">
          <AnalyticsVisitsSource :items="sourceItems" />
        </AnalysisChartCard>
      </div>
    </div>
  </div>
</template>
