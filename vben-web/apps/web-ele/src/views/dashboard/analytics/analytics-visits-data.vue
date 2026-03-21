<script lang="ts" setup>
import type { EchartsUIType } from '@vben/plugins/echarts';

import { computed, onMounted, ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

const props = withDefaults(
  defineProps<{
    items?: Array<{ name: string; value: number }>;
  }>(),
  {
    items: () => [],
  },
);

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

const radarItems = computed(() => {
  if (props.items.length > 0) {
    return props.items.slice(0, 6);
  }
  return Array.from({ length: 6 }).map((_item, index) => ({
    name: `类型${index + 1}`,
    value: 0,
  }));
});

const radarIndicators = computed(() => {
  return radarItems.value.map((item) => ({ name: item.name, max: Math.max(item.value, 1) }));
});

const radarValues = computed(() => radarItems.value.map((item) => item.value ?? 0));

function renderChart() {
  if (!chartRef.value) return;
  renderEcharts({
    legend: {
      bottom: 0,
      data: ['节点类型'],
    },
    radar: {
      indicator: radarIndicators.value,
      radius: '60%',
      splitNumber: 4,
    },
    series: [
      {
        areaStyle: {
          opacity: 1,
          shadowBlur: 0,
          shadowColor: 'rgba(0,0,0,.2)',
          shadowOffsetX: 0,
          shadowOffsetY: 10,
        },
        data: [
          {
            itemStyle: {
              color: '#b6a2de',
            },
            name: '节点类型',
            value: radarValues.value,
          },
        ],
        itemStyle: {
          // borderColor: '#fff',
          borderRadius: 10,
          borderWidth: 2,
        },
        symbolSize: 0,
        type: 'radar',
      },
    ],
    tooltip: {},
  });
}

onMounted(() => {
  renderChart();
});

watch([radarIndicators, radarValues], () => {
  renderChart();
});
</script>

<template>
  <EchartsUI ref="chartRef" />
</template>
