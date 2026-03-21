<script lang="ts" setup>
import type { EchartsUIType } from '@vben/plugins/echarts';

import { computed, onMounted, ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

const props = withDefaults(
  defineProps<{
    labels?: string[];
    primaryLabel?: string;
    primaryValues?: number[];
    secondaryLabel?: string;
    secondaryValues?: number[];
  }>(),
  {
    labels: () => [],
    primaryLabel: '主序列',
    primaryValues: () => [],
    secondaryLabel: '副序列',
    secondaryValues: () => [],
  },
);

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

const labels = computed(() => {
  return props.labels.length > 0
    ? props.labels
    : Array.from({ length: 8 }).map((_item, index) => `分类${index + 1}`);
});

const primaryValues = computed(() => {
  return labels.value.map((_item, index) => props.primaryValues[index] ?? 0);
});

const secondaryValues = computed(() => {
  return labels.value.map((_item, index) => props.secondaryValues[index] ?? 0);
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
        areaStyle: {},
        data: primaryValues.value,
        itemStyle: {
          color: '#5ab1ef',
        },
        name: props.primaryLabel,
        smooth: true,
        type: 'line',
      },
      {
        areaStyle: {},
        data: secondaryValues.value,
        itemStyle: {
          color: '#019680',
        },
        name: props.secondaryLabel,
        smooth: true,
        type: 'line',
      },
    ],
    tooltip: {
      axisPointer: {
        lineStyle: {
          color: '#019680',
          width: 1,
        },
      },
      trigger: 'axis',
    },
    // xAxis: {
    //   axisTick: {
    //     show: false,
    //   },
    //   boundaryGap: false,
    //   data: Array.from({ length: 18 }).map((_item, index) => `${index + 6}:00`),
    //   type: 'category',
    // },
    xAxis: {
      axisTick: {
        show: false,
      },
      boundaryGap: false,
      data: labels.value,
      splitLine: {
        lineStyle: {
          type: 'solid',
          width: 1,
        },
        show: true,
      },
      type: 'category',
    },
    yAxis: [
      {
        axisTick: {
          show: false,
        },
        splitArea: {
          show: true,
        },
        splitNumber: 4,
        type: 'value',
      },
    ],
  });
}

onMounted(() => {
  renderChart();
});

watch([labels, primaryValues, secondaryValues], () => {
  renderChart();
});
</script>

<template>
  <EchartsUI ref="chartRef" />
</template>
