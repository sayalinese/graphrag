<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { PieChart, BarChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';
import SkinKgPathGraph, {
  type SkinGraphLink,
  type SkinGraphNode,
} from './components/SkinKgPathGraph.vue';
import {
  ArrowLeft,
  Phone,
  FileText,
  AlertTriangle,
  MapPin,
  Activity,
  Eye,
  Layers,
  CircleDot,
} from 'lucide-vue-next';
import '../skin/styles/token.css';

use([
  CanvasRenderer,
  PieChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
]);

/** 图表配色：与 token 品牌 / 中性色一致 */
const chartPalette = ['#2C7A7B', '#57534E', '#A8A29E', '#78716C', '#D6D3D1'];

function truncateLabel(text: string, max = 14) {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

const route = useRoute();
const router = useRouter();
const sessionId = computed(() => route.params.sessionId as string);
const uploadedImageUrl = ref('');

const result = ref({
  riskLevel: 'mid' as 'low' | 'mid' | 'high',
  conclusion: '建议 2 周内到皮肤科就诊',
  analysisTime: new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  }),
  features: [
    { icon: Activity, label: '颜色', value: '偏红，分布不均匀' },
    { icon: Eye, label: '边缘', value: '轻度不规则' },
    { icon: Layers, label: '表面', value: '略有粗糙感' },
    { icon: CircleDot, label: '形态', value: '斑片状' },
  ],
  candidates: [
    {
      name: '湿疹（特应性皮炎）',
      confidence: 65,
      description: '慢性炎症性皮肤病，与免疫、遗传因素相关',
      isTop: true,
    },
    {
      name: '接触性皮炎',
      confidence: 22,
      description: '皮肤接触致敏物质后引起的炎症反应',
      isTop: false,
    },
    {
      name: '银屑病（轻度）',
      confidence: 13,
      description: '慢性自身免疫性皮肤病',
      isTop: false,
    },
  ],
  hospital: {
    name: '重庆医科大学附属第一医院',
    department: '皮肤科',
    distance: '3.2 km',
    phone: '023-89011111',
  },
  graphNodes: [
    { id: 'root', label: '皮损图像', type: 'root' },
    { id: 'f1', label: '颜色异常', type: 'feature' },
    { id: 'f2', label: '边缘不规则', type: 'feature' },
    { id: 'f3', label: '斑片状', type: 'feature' },
    { id: 'd1', label: '湿疹', type: 'disease' },
    { id: 'd2', label: '接触性皮炎', type: 'disease' },
    { id: 'k1', label: '炎症反应', type: 'knowledge' },
    { id: 'k2', label: '免疫相关', type: 'knowledge' },
    { id: 'k3', label: '遗传因素', type: 'knowledge' },
  ] satisfies SkinGraphNode[],
  graphEdges: [
    { source: 'root', target: 'f1' },
    { source: 'root', target: 'f2' },
    { source: 'root', target: 'f3' },
    { source: 'f1', target: 'd1' },
    { source: 'f2', target: 'd1' },
    { source: 'f3', target: 'd2' },
    { source: 'd1', target: 'k1' },
    { source: 'd1', target: 'k2' },
    { source: 'd2', target: 'k2' },
    { source: 'd2', target: 'k3' },
  ] satisfies SkinGraphLink[],
});

const riskConfig = computed(() => ({
  low: {
    tag: '低关注',
    tagClass: 'tag-low',
    barColor: 'var(--skin-risk-low)',
    textColor: 'var(--skin-risk-low-text)',
  },
  mid: {
    tag: '建议关注',
    tagClass: 'tag-mid',
    barColor: 'var(--skin-risk-mid)',
    textColor: 'var(--skin-risk-mid-text)',
  },
  high: {
    tag: '建议尽快就诊',
    tagClass: 'tag-high',
    barColor: 'var(--skin-risk-high)',
    textColor: 'var(--skin-risk-high-text)',
  },
}[result.value.riskLevel]));

const topCandidate = computed(
  () =>
    result.value.candidates.find((c) => c.isTop) ?? result.value.candidates[0],
);

const graphCaption = computed(() => {
  const n = result.value.graphNodes.length;
  const e = result.value.graphEdges.length;
  return `基于皮肤病知识图谱 · GraphRAG 推理子图 · ${n} 个节点 · ${e} 条关联`;
});

const donutChartOption = computed(() => {
  const list = result.value.candidates;
  const top = topCandidate.value;
  return {
    color: chartPalette,
    tooltip: {
      trigger: 'item',
      confine: true,
      backgroundColor: 'rgba(28, 25, 23, 0.92)',
      borderWidth: 0,
      textStyle: { color: '#FAFAF9', fontSize: 12 },
      formatter: (p: { name?: string; value?: number; data?: { desc?: string } }) => {
        const name = p.name ?? '';
        const val = typeof p.value === 'number' ? p.value : Number(p.value);
        const desc = p.data?.desc;
        const extra = desc
          ? `<div style="margin-top:6px;max-width:220px;line-height:1.45;opacity:.88;font-size:11px">${desc}</div>`
          : '';
        return `<div style="font-weight:600">${name}</div><div>参考概率 ${val}%</div>${extra}`;
      },
    },
    legend: {
      type: 'scroll',
      bottom: 0,
      left: 'center',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: '#57534E', fontSize: 11 },
      formatter: (name: string) => truncateLabel(name, 16),
    },
    title: top
      ? {
          text: `${top.confidence}%`,
          subtext: truncateLabel(top.name, 18),
          left: 'center',
          top: '38%',
          textAlign: 'center',
          textStyle: {
            fontSize: 26,
            fontWeight: 700,
            color: '#2C7A7B',
            fontFamily:
              'ui-sans-serif, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
          },
          subtextStyle: {
            fontSize: 12,
            color: '#57534E',
            lineHeight: 18,
            width: 160,
            overflow: 'truncate',
            fontFamily:
              'ui-sans-serif, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
          },
        }
      : undefined,
    series: [
      {
        type: 'pie',
        radius: ['46%', '68%'],
        center: ['50%', '42%'],
        animationDuration: 720,
        animationEasing: 'cubicOut',
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#FFFFFF',
          borderWidth: 2,
        },
        label: {
          show: true,
          formatter: '{d}%',
          color: '#1C1917',
          fontSize: 11,
          fontWeight: 600,
        },
        labelLine: { length: 8, length2: 6, smooth: true },
        emphasis: {
          scale: true,
          scaleSize: 4,
          itemStyle: { shadowBlur: 12, shadowColor: 'rgba(44, 122, 123, 0.25)' },
        },
        data: list.map((c, i) => ({
          name: c.name,
          value: c.confidence,
          desc: c.description,
          itemStyle: { color: chartPalette[i % chartPalette.length] },
        })),
      },
    ],
  };
});

const barChartOption = computed(() => {
  const list = [...result.value.candidates].sort(
    (a, b) => b.confidence - a.confidence,
  );
  return {
    color: chartPalette,
    grid: {
      left: 4,
      right: 36,
      top: 8,
      bottom: 8,
      containLabel: true,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      confine: true,
      backgroundColor: 'rgba(28, 25, 23, 0.92)',
      borderWidth: 0,
      textStyle: { color: '#FAFAF9', fontSize: 12 },
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : [params];
        const first = arr[0] as {
          name?: string;
          value?: number;
          dataIndex?: number;
        };
        const idx = first?.dataIndex ?? 0;
        const row = list[idx];
        if (!row) return '';
        return `<div style="font-weight:600">${row.name}</div><div>${row.confidence}%</div><div style="margin-top:6px;max-width:240px;line-height:1.45;opacity:.88;font-size:11px">${row.description}</div>`;
      },
    },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: {
        formatter: '{value}%',
        color: '#A8A29E',
        fontSize: 10,
      },
      splitLine: {
        lineStyle: { type: 'dashed', color: '#F5F5F4' },
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: list.map((c) => truncateLabel(c.name, 12)),
      axisLabel: { color: '#57534E', fontSize: 11, width: 100, overflow: 'truncate' },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        animationDuration: 640,
        animationEasing: 'cubicOut',
        data: list.map((c, i) => ({
          value: c.confidence,
          itemStyle: {
            color: chartPalette[i % chartPalette.length],
            borderRadius: [0, 6, 6, 0],
          },
        })),
        barMaxWidth: 18,
        emphasis: {
          focus: 'series',
          itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.08)' },
        },
      },
    ],
  };
});

function goToReport() {
  router.push(`/skin/report/${sessionId.value}`);
}

function goBack() {
  router.push('/skin/upload');
}

function callHospital() {
  window.location.href = `tel:${result.value.hospital.phone}`;
}

onMounted(() => {
  const dataStr = sessionStorage.getItem(`skin_session_${sessionId.value}`);
  if (dataStr) {
    try {
      const data = JSON.parse(dataStr);
      uploadedImageUrl.value = data.urls?.[0] || '';
    } catch (e) {
      console.error(e);
    }
  }
});
</script>

<template>
  <div class="skin-page">

    <!-- 顶部导航 -->
    <nav class="topbar">
      <button class="icon-btn" @click="goBack" aria-label="返回">
        <ArrowLeft :size="20" />
      </button>
      <span class="topbar-title">检查报告</span>
      <div style="width:40px" />
    </nav>

    <div class="skin-container">

      <!-- ① 风险评估卡（最重要，最大）-->
      <div class="risk-card">
        <div
          class="risk-bar"
          :style="{ background: riskConfig.barColor }"
        />
        <div class="risk-body">
          <div class="risk-meta">
            <span class="risk-tag" :class="riskConfig.tagClass">
              {{ riskConfig.tag }}
            </span>
            <span class="risk-time">
              分析完成 {{ result.analysisTime }}
            </span>
          </div>
          <h1 class="risk-conclusion">{{ result.conclusion }}</h1>
          <p class="risk-desc">
            以下内容由 AI 基于医学知识图谱与影像分析生成，
            <strong>仅供参考，不构成诊断意见</strong>。
          </p>
        </div>
      </div>

      <!-- ② AI 影像观察 -->
      <section class="section">
        <p class="skin-section-label">影像观察</p>

        <!-- 图片区 -->
        <div class="image-wrap">
          <img
            v-if="uploadedImageUrl"
            :src="uploadedImageUrl"
            alt="皮损照片"
            class="skin-img"
          />
          <div v-else class="image-placeholder">
            <span style="font-size:32px">📷</span>
            <span>照片预览</span>
          </div>
        </div>

        <!-- 特征列表 -->
        <div class="feature-list skin-card">
          <div
            v-for="(f, idx) in result.features"
            :key="f.label"
            class="feature-row"
            :class="{ 'feature-row-last': idx === result.features.length - 1 }"
          >
            <span class="feature-icon-wrap">
              <component :is="f.icon" :size="16" />
            </span>
            <span class="feature-label">{{ f.label }}</span>
            <span class="feature-value">{{ f.value }}</span>
          </div>
        </div>
      </section>

      <!-- ③ AI 评估（候选诊断 · ECharts）-->
      <section class="section section-candidates">
        <p class="skin-section-label">AI 评估</p>
        <p class="candidate-section-lead">
          以下为模型输出的<strong>候选病种与参考概率</strong>，环形图为分布占比，条形图便于横向对比。
        </p>

        <div class="candidate-charts-card skin-card">
          <div class="candidate-chart-block">
            <div class="candidate-chart-head">
              <span class="candidate-chart-title">概率分布</span>
              <span class="candidate-chart-sub">环形图 · 合计 100%</span>
            </div>
            <div class="candidate-donut-wrap">
              <VChart
                class="candidate-echart"
                :option="donutChartOption"
                autoresize
              />
            </div>
          </div>

          <div class="candidate-chart-divider" />

          <div class="candidate-chart-block">
            <div class="candidate-chart-head">
              <span class="candidate-chart-title">置信度对比</span>
              <span class="candidate-chart-sub">横向条形图 · 由高到低</span>
            </div>
            <div class="candidate-bar-wrap">
              <VChart
                class="candidate-echart candidate-echart--bar"
                :option="barChartOption"
                autoresize
              />
            </div>
          </div>
        </div>

        <p class="notice-text">
          <AlertTriangle :size="13" style="vertical-align:-2px;margin-right:4px" />
          以上仅为参考概率，<strong>不是诊断结论</strong>，请以医生意见为准
        </p>
      </section>

      <!-- ④ 知识图谱推理路径（force-graph 可交互子图）-->
      <section class="section section-graph">
        <p class="skin-section-label">推理依据</p>
        <p class="graph-section-lead">
          从<strong>影像特征</strong>到<strong>候选病种</strong>再到<strong>知识概念</strong>的可解释子图，
          自上而下为 GraphRAG 常用推理方向（示意数据）。
        </p>
        <div class="graph-card skin-card">
          <div class="graph-legend">
            <span class="legend-dot legend-root" />皮损 / 根节点
            <span class="legend-dot legend-feature" style="margin-left:12px" />影像特征
            <span class="legend-dot legend-disease" style="margin-left:12px" />关联病种
            <span class="legend-dot legend-knowledge" style="margin-left:12px" />知识节点
          </div>
          <SkinKgPathGraph
            :nodes="result.graphNodes"
            :links="result.graphEdges"
          />
          <p class="graph-caption">
            {{ graphCaption }}
          </p>
        </div>
      </section>

      <!-- ⑤ 建议就诊 -->
      <section class="section">
        <p class="skin-section-label">建议就诊</p>
        <div class="hospital-card skin-card">
          <div class="hospital-left">
            <div class="hospital-icon">
              <MapPin :size="18" color="var(--skin-brand)" />
            </div>
            <div>
              <p class="hospital-name">{{ result.hospital.name }}</p>
              <p class="hospital-sub">
                {{ result.hospital.department }}
                <span class="dot-sep">·</span>
                {{ result.hospital.distance }}
              </p>
            </div>
          </div>
          <button class="call-btn" @click="callHospital">
            <Phone :size="15" />
            拨打电话
          </button>
        </div>
      </section>

      <!-- ⑥ 操作按钮 -->
      <div class="action-group">
        <button class="skin-btn-primary" @click="goToReport">
          <FileText :size="18" />
          生成完整报告
        </button>
        <button class="skin-btn-secondary" @click="goBack" style="margin-top:10px">
          重新拍一张
        </button>
      </div>

      <!-- ⑦ 免责（合规，字号不缩小）-->
      <div class="disclaimer">
        <AlertTriangle :size="14" style="flex-shrink:0;margin-top:2px" />
        <p>
          本报告由人工智能基于医学知识图谱生成，<strong>不能替代临床医生诊断</strong>。
          如有疑虑，请尽快到正规医院皮肤科就诊。
        </p>
      </div>

    </div>
  </div>
</template>

<style scoped>
/* 顶部导航 */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--skin-surface);
  border-bottom: 1px solid var(--skin-border);
  position: sticky;
  top: 0;
  z-index: 10;
  backdrop-filter: blur(8px);
}

.topbar-title {
  font-size: var(--skin-text-md);
  font-weight: var(--skin-font-semibold);
  color: var(--skin-text-primary);
  letter-spacing: var(--skin-tracking-tight);
}

.icon-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--skin-radius-md);
  background: transparent;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--skin-text-primary);
  transition: var(--skin-transition-fast);
}

.icon-btn:hover {
  background: var(--skin-surface-soft);
}

/* ① 风险卡 */
.risk-card {
  display: flex;
  background: var(--skin-surface);
  border: 1px solid var(--skin-border);
  border-radius: var(--skin-radius-xl);
  overflow: hidden;
  margin: var(--skin-gap-5) 0 var(--skin-gap-8) 0;
}

.risk-bar {
  width: 4px;
  flex-shrink: 0;
}

.risk-body {
  flex: 1;
  padding: var(--skin-gap-5) var(--skin-gap-6);
}

.risk-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: var(--skin-gap-3);
}

.risk-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: var(--skin-text-xs);
  font-weight: var(--skin-font-semibold);
  letter-spacing: var(--skin-tracking-wide);
}

.tag-low {
  background: var(--skin-risk-low-soft);
  color: var(--skin-risk-low-text);
}

.tag-mid {
  background: var(--skin-risk-mid-soft);
  color: var(--skin-risk-mid-text);
}

.tag-high {
  background: var(--skin-risk-high-soft);
  color: var(--skin-risk-high-text);
}

.risk-time {
  font-size: var(--skin-text-xs);
  color: var(--skin-text-muted);
  font-variant-numeric: tabular-nums;
}

.risk-conclusion {
  font-size: var(--skin-text-2xl);
  font-weight: var(--skin-font-bold);
  color: var(--skin-text-primary);
  letter-spacing: var(--skin-tracking-tight);
  line-height: var(--skin-leading-tight);
  margin: 0 0 var(--skin-gap-3) 0;
}

.risk-desc {
  font-size: var(--skin-text-sm);
  color: var(--skin-text-secondary);
  line-height: var(--skin-leading-relaxed);
  margin: 0;
}

/* ② 影像观察 */
.image-wrap {
  border-radius: var(--skin-radius-lg);
  overflow: hidden;
  aspect-ratio: 16 / 10;
  background: var(--skin-surface-soft);
  margin-bottom: var(--skin-gap-3);
  border: 1px solid var(--skin-border);
}

.skin-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--skin-text-muted);
  font-size: var(--skin-text-sm);
}

/* 特征列表 */
.feature-list {
  padding: 0 var(--skin-gap-4);
}

.feature-row {
  display: flex;
  align-items: center;
  gap: var(--skin-gap-3);
  padding: var(--skin-gap-3) 0;
  border-bottom: 1px solid var(--skin-border-soft);
}

.feature-row-last {
  border-bottom: none;
}

.feature-icon-wrap {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: var(--skin-brand-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--skin-brand);
  flex-shrink: 0;
}

.feature-label {
  font-size: var(--skin-text-sm);
  font-weight: var(--skin-font-medium);
  color: var(--skin-text-primary);
  width: 48px;
  flex-shrink: 0;
}

.feature-value {
  font-size: var(--skin-text-sm);
  color: var(--skin-text-secondary);
  flex: 1;
}

/* ③ 候选诊断 · 图表 */
.section-candidates .skin-section-label {
  margin-bottom: var(--skin-gap-2);
}

.candidate-section-lead {
  font-size: var(--skin-text-xs);
  color: var(--skin-text-tertiary);
  line-height: var(--skin-leading-relaxed);
  margin: 0 0 var(--skin-gap-4) 0;
}

.candidate-charts-card {
  padding: var(--skin-gap-4);
  overflow: hidden;
}

.candidate-chart-block {
  margin: 0;
}

.candidate-chart-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--skin-gap-3);
  margin-bottom: var(--skin-gap-2);
}

.candidate-chart-title {
  font-size: var(--skin-text-sm);
  font-weight: var(--skin-font-semibold);
  color: var(--skin-text-primary);
  letter-spacing: var(--skin-tracking-tight);
}

.candidate-chart-sub {
  font-size: var(--skin-text-xs);
  color: var(--skin-text-muted);
  flex-shrink: 0;
}

.candidate-donut-wrap {
  width: 100%;
  height: min(52vw, 280px);
  min-height: 240px;
}

.candidate-bar-wrap {
  width: 100%;
  height: 168px;
  min-height: 140px;
}

.candidate-echart {
  width: 100%;
  height: 100%;
}

.candidate-echart--bar {
  min-height: 140px;
}

.candidate-chart-divider {
  height: 1px;
  background: var(--skin-border-soft);
  margin: var(--skin-gap-4) 0;
}

.notice-text {
  font-size: var(--skin-text-xs);
  color: var(--skin-text-tertiary);
  margin-top: var(--skin-gap-3);
  padding: var(--skin-gap-3) var(--skin-gap-4);
  background: var(--skin-surface-soft);
  border-radius: var(--skin-radius-md);
  text-align: center;
}

/* ④ 知识图谱（force-graph）*/
.section-graph .skin-section-label {
  margin-bottom: var(--skin-gap-2);
}

.graph-section-lead {
  font-size: var(--skin-text-xs);
  color: var(--skin-text-tertiary);
  line-height: var(--skin-leading-relaxed);
  margin: 0 0 var(--skin-gap-4) 0;
}

.graph-card {
  padding: var(--skin-gap-4);
}

.graph-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: var(--skin-text-xs);
  color: var(--skin-text-tertiary);
  margin-bottom: var(--skin-gap-3);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-root {
  background: var(--skin-brand);
}

.legend-feature {
  background: #99f6e4;
  border: 1px solid var(--skin-brand);
}

.legend-disease {
  background: var(--skin-text-primary);
}

.legend-knowledge {
  background: var(--skin-border);
  border: 1px solid var(--skin-text-muted);
}

.graph-caption {
  font-size: var(--skin-text-xs);
  color: var(--skin-text-muted);
  text-align: center;
  margin: var(--skin-gap-4) 0 0 0;
}

/* ⑤ 医院 */
.hospital-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--skin-gap-4);
}

.hospital-left {
  display: flex;
  align-items: flex-start;
  gap: var(--skin-gap-3);
  flex: 1;
  min-width: 0;
}

.hospital-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--skin-radius-md);
  background: var(--skin-brand-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.hospital-name {
  font-size: var(--skin-text-base);
  font-weight: var(--skin-font-semibold);
  color: var(--skin-text-primary);
  margin: 0 0 3px 0;
  line-height: 1.4;
}

.hospital-sub {
  font-size: var(--skin-text-xs);
  color: var(--skin-text-tertiary);
  margin: 0;
}

.dot-sep {
  margin: 0 4px;
  color: var(--skin-border);
}

.call-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 var(--skin-gap-4);
  height: 40px;
  background: var(--skin-brand);
  color: white;
  border: none;
  border-radius: var(--skin-radius-md);
  font-size: var(--skin-text-sm);
  font-weight: var(--skin-font-medium);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  font-family: inherit;
  transition: var(--skin-transition-fast);
}

.call-btn:hover {
  background: var(--skin-brand-hover);
}

/* ⑥ 操作按钮组 */
.action-group {
  margin-top: var(--skin-gap-8);
  display: flex;
  flex-direction: column;
}

/* ⑦ 免责声明 */
.disclaimer {
  display: flex;
  align-items: flex-start;
  gap: var(--skin-gap-2);
  margin-top: var(--skin-gap-6);
  margin-bottom: var(--skin-gap-8);
  padding: var(--skin-gap-4);
  background: var(--skin-surface-soft);
  border-radius: var(--skin-radius-md);
  border-left: 3px solid var(--skin-risk-mid);
  color: var(--skin-text-secondary);
  font-size: var(--skin-text-sm);
  line-height: var(--skin-leading-relaxed);
}

.disclaimer p {
  margin: 0;
}

/* 通用区块间距 */
.section {
  margin-bottom: var(--skin-gap-8);
}
</style>