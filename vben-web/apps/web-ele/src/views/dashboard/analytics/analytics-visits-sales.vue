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

const roseItems = computed(() => {
  if (props.items.length > 0) {
    return [...props.items].sort((a, b) => a.value - b.value);
  }
  return Array.from({ length: 4 }).map((_item, index) => ({
    name: `类型${index + 1}`,
    value: 0,
  }));
});

function renderChart() {
  if (!chartRef.value) return;
  renderEcharts({
    series: [
      {
        animationDelay() {
          return Math.random() * 400;
        },
        animationEasing: 'exponentialInOut',
        animationType: 'scale',
        center: ['50%', '50%'],
        color: ['#5ab1ef', '#b6a2de', '#67e0e3', '#2ec7c9'],
        data: roseItems.value,
        name: '关系类型',
        radius: '80%',
        roseType: 'radius',
        type: 'pie',
      },
    ],

    tooltip: {
      trigger: 'item',
    },
  });
}

onMounted(() => {
  renderChart();
});

watch(roseItems, () => {
  renderChart();
});
</script>

<template>
  <EchartsUI ref="chartRef" />
</template>
