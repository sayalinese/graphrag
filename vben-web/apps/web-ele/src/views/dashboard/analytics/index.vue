<script lang="ts" setup>
import type { AnalysisOverviewItem } from '@vben/common-ui';
import type { TabOption } from '@vben/types';

import { computed, onMounted, ref } from 'vue';

import {
  AnalysisChartCard,
  AnalysisChartsTabs,
  AnalysisOverview,
} from '@vben/common-ui';
import {
  SvgBellIcon,
  SvgCakeIcon,
  SvgCardIcon,
  SvgDownloadIcon,
} from '@vben/icons';

import AnalyticsTrends from './analytics-trends.vue';
import AnalyticsVisitsData from './analytics-visits-data.vue';
import AnalyticsVisitsSales from './analytics-visits-sales.vue';
import AnalyticsVisitsSource from './analytics-visits-source.vue';
import AnalyticsVisits from './analytics-visits.vue';
import {
  fetchDashboardSnapshot,
  topEntries,
  type DashboardSnapshot,
} from '../api';

const snapshot = ref<DashboardSnapshot | null>(null);

const overviewItems = computed<AnalysisOverviewItem[]>(() => {
  const stats = snapshot.value?.stats;
  return [
    {
      icon: SvgCardIcon,
      title: '节点数',
      totalTitle: '图谱节点总数',
      totalValue: stats?.totalNodes ?? 0,
      value: stats?.nodes ?? 0,
    },
    {
      icon: SvgCakeIcon,
      title: '关系数',
      totalTitle: '图谱关系总数',
      totalValue: stats?.totalRelations ?? 0,
      value: stats?.edges ?? 0,
    },
    {
      icon: SvgDownloadIcon,
      title: '社区数',
      totalTitle: '社区总数',
      totalValue: stats?.communities ?? 0,
      value: stats?.communities ?? 0,
    },
    {
      icon: SvgBellIcon,
      title: '平均度',
      totalTitle: '图谱平均度',
      totalValue: stats?.averageDegree ?? 0,
      value: stats?.averageDegree ?? 0,
    },
  ];
});

const nodeTypeEntries = computed(() => topEntries(snapshot.value?.stats.nodeTypes ?? {}, 12));
const relationTypeEntries = computed(() => topEntries(snapshot.value?.stats.relationTypes ?? {}, 12));
const coreNodeEntries = computed(() => {
  const nodes = snapshot.value?.centralNodes ?? [];
  return nodes.slice(0, 20).map((node, index) => ({
    name: node.name || node.id || `节点${index + 1}`,
    value: node.degree || 0,
  }));
});

const trendLabels = computed(() => snapshot.value?.trends.daily.documents.labels ?? []);
const trendDocumentValues = computed(() => snapshot.value?.trends.daily.documents.values ?? []);
const trendMessageValues = computed(() => snapshot.value?.trends.daily.messages.values ?? []);

const chartTabs: TabOption[] = [
  {
    label: '时间趋势',
    value: 'trends',
  },
  {
    label: '核心节点',
    value: 'visits',
  },
];

onMounted(async () => {
  snapshot.value = await fetchDashboardSnapshot();
});
</script>

<template>
  <div class="p-5">
    <AnalysisOverview :items="overviewItems" />
    <AnalysisChartsTabs :tabs="chartTabs" class="mt-5">
      <template #trends>
        <AnalyticsTrends
          :labels="trendLabels"
          primary-label="文档入库"
          :primary-values="trendDocumentValues"
          secondary-label="对话消息"
          :secondary-values="trendMessageValues"
        />
      </template>
      <template #visits>
        <AnalyticsVisits :items="coreNodeEntries" />
      </template>
    </AnalysisChartsTabs>

    <div class="mt-5 w-full md:flex">
      <AnalysisChartCard class="mt-5 md:mr-4 md:mt-0 md:w-1/3" title="节点类型分布">
        <AnalyticsVisitsData :items="nodeTypeEntries" />
      </AnalysisChartCard>
      <AnalysisChartCard class="mt-5 md:mr-4 md:mt-0 md:w-1/3" title="节点类型占比">
        <AnalyticsVisitsSource :items="nodeTypeEntries.slice(0, 6)" />
      </AnalysisChartCard>
      <AnalysisChartCard class="mt-5 md:mt-0 md:w-1/3" title="关系类型分布">
        <AnalyticsVisitsSales :items="relationTypeEntries.slice(0, 6)" />
      </AnalysisChartCard>
    </div>
  </div>
</template>
