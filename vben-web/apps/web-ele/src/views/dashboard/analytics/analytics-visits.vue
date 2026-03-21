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

const labels = computed(() => {
  return props.items.length > 0
    ? props.items.map((item) => item.name)
    : Array.from({ length: 6 }).map((_item, index) => `节点${index + 1}`);
});

const values = computed(() => {
  return props.items.length > 0
    ? props.items.map((item) => item.value ?? 0)
    : Array.from({ length: 6 }).map(() => 0);
});

function renderChart() {
  if (!chartRef.value) return;
  renderEcharts({
    grid: {
      bottom: 0,
      containLabel: true,
      left: '1%',
      right: '1%',
      top: '2 %',
    },
    series: [
      {
        barMaxWidth: 80,
        data: values.value,
        type: 'bar',
      },
    ],
    tooltip: {
      axisPointer: {
        lineStyle: {
          // color: '#4f69fd',
          width: 1,
        },
      },
      trigger: 'axis',
    },
    xAxis: {
      data: labels.value,
      type: 'category',
    },
    yAxis: {
      splitNumber: 4,
      type: 'value',
    },
  });
}

onMounted(() => {
  renderChart();
});

watch([labels, values], () => {
  renderChart();
});
</script>

<template>
  <EchartsUI ref="chartRef" />
</template>
