<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  ArrowLeft,
  Phone,
  FileText,
  AlertTriangle,
  MapPin,
  ChevronRight,
  Activity,
  Eye,
  Layers,
  CircleDot,
} from 'lucide-vue-next';
import '../skin/styles/token.css';

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
  ],
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

      <!-- ③ AI 评估（候选诊断）-->
      <section class="section">
        <p class="skin-section-label">AI 评估</p>

        <div class="candidate-list">
          <div
            v-for="(c, idx) in result.candidates"
            :key="c.name"
            class="candidate-item"
            :class="{ 'candidate-item-top': c.isTop }"
          >
            <div class="candidate-header">
              <div class="candidate-left">
                <span class="candidate-rank">#{{ idx + 1 }}</span>
                <div>
                  <p class="candidate-name">{{ c.name }}</p>
                  <p class="candidate-desc">{{ c.description }}</p>
                </div>
              </div>
              <span class="candidate-pct skin-numeric">
                {{ c.confidence }}%
              </span>
            </div>
            <!-- 置信度条 -->
            <div class="conf-track">
              <div
                class="conf-fill"
                :style="{
                  width: `${c.confidence}%`,
                  background: c.isTop
                    ? 'var(--skin-brand)'
                    : 'var(--skin-border)',
                }"
              />
            </div>
          </div>
        </div>

        <p class="notice-text">
          <AlertTriangle :size="13" style="vertical-align:-2px;margin-right:4px" />
          以上仅为参考概率，<strong>不是诊断结论</strong>，请以医生意见为准
        </p>
      </section>

      <!-- ④ 知识图谱推理路径 -->
      <section class="section">
        <p class="skin-section-label">推理依据</p>
        <div class="graph-card skin-card">
          <div class="graph-legend">
            <span class="legend-dot legend-root" />图像特征
            <span class="legend-dot legend-disease" style="margin-left:12px" />关联病种
            <span class="legend-dot legend-knowledge" style="margin-left:12px" />知识节点
          </div>
          <!-- 知识图谱 SVG 可视化 -->
          <div class="graph-svg-wrap">
            <svg viewBox="0 0 320 220" class="graph-svg">
              <!-- 连线（先画线，在节点下方）-->
              <!-- 中心 → 特征 -->
              <line x1="160" y1="50" x2="60" y2="110" stroke="#E7E5E4" stroke-width="1.5"/>
              <line x1="160" y1="50" x2="160" y2="110" stroke="#E7E5E4" stroke-width="1.5"/>
              <line x1="160" y1="50" x2="260" y2="110" stroke="#E7E5E4" stroke-width="1.5"/>
              <!-- 特征 → 疾病 -->
              <line x1="60" y1="110" x2="110" y2="170" stroke="#E7E5E4" stroke-width="1.5"/>
              <line x1="160" y1="110" x2="110" y2="170" stroke="#E7E5E4" stroke-width="1.5"/>
              <line x1="260" y1="110" x2="210" y2="170" stroke="#E7E5E4" stroke-width="1.5"/>
              <!-- 疾病 → 知识 -->
              <line x1="110" y1="170" x2="70" y2="210" stroke="#E7E5E4" stroke-width="1.5" stroke-dasharray="4 2"/>
              <line x1="110" y1="170" x2="150" y2="210" stroke="#E7E5E4" stroke-width="1.5" stroke-dasharray="4 2"/>
              <line x1="210" y1="170" x2="250" y2="210" stroke="#E7E5E4" stroke-width="1.5" stroke-dasharray="4 2"/>

              <!-- 根节点（皮损图像）-->
              <circle cx="160" cy="50" r="22" fill="var(--skin-brand)" />
              <text x="160" y="46" text-anchor="middle" fill="white" font-size="9" font-weight="600">皮损</text>
              <text x="160" y="57" text-anchor="middle" fill="white" font-size="9" font-weight="600">图像</text>

              <!-- 特征节点 -->
              <circle cx="60" cy="110" r="18" fill="white" stroke="var(--skin-brand)" stroke-width="1.5"/>
              <text x="60" y="107" text-anchor="middle" fill="var(--skin-brand)" font-size="8">颜色</text>
              <text x="60" y="117" text-anchor="middle" fill="var(--skin-brand)" font-size="8">异常</text>

              <circle cx="160" cy="110" r="18" fill="white" stroke="var(--skin-brand)" stroke-width="1.5"/>
              <text x="160" y="107" text-anchor="middle" fill="var(--skin-brand)" font-size="8">边缘</text>
              <text x="160" y="117" text-anchor="middle" fill="var(--skin-brand)" font-size="8">不规则</text>

              <circle cx="260" cy="110" r="18" fill="white" stroke="var(--skin-brand)" stroke-width="1.5"/>
              <text x="260" y="107" text-anchor="middle" fill="var(--skin-brand)" font-size="8">斑片</text>
              <text x="260" y="117" text-anchor="middle" fill="var(--skin-brand)" font-size="8">形态</text>

              <!-- 疾病节点 -->
              <rect x="80" y="155" width="60" height="28" rx="6" fill="#1C1917"/>
              <text x="110" y="165" text-anchor="middle" fill="white" font-size="8" font-weight="600">湿疹</text>
              <text x="110" y="175" text-anchor="middle" fill="white" font-size="7">65%</text>

              <rect x="180" y="155" width="60" height="28" rx="6" fill="var(--skin-surface-soft)" stroke="var(--skin-border)" stroke-width="1"/>
              <text x="210" y="165" text-anchor="middle" fill="var(--skin-text-secondary)" font-size="7.5">接触性</text>
              <text x="210" y="175" text-anchor="middle" fill="var(--skin-text-tertiary)" font-size="7">皮炎 22%</text>

              <!-- 知识节点（虚线连接）-->
              <circle cx="70" cy="210" r="14" fill="var(--skin-surface-soft)" stroke="var(--skin-border)" stroke-width="1" stroke-dasharray="3 2"/>
              <text x="70" y="207" text-anchor="middle" fill="var(--skin-text-tertiary)" font-size="7">炎症</text>
              <text x="70" y="215" text-anchor="middle" fill="var(--skin-text-tertiary)" font-size="7">反应</text>

              <circle cx="150" cy="210" r="14" fill="var(--skin-surface-soft)" stroke="var(--skin-border)" stroke-width="1" stroke-dasharray="3 2"/>
              <text x="150" y="207" text-anchor="middle" fill="var(--skin-text-tertiary)" font-size="7">免疫</text>
              <text x="150" y="215" text-anchor="middle" fill="var(--skin-text-tertiary)" font-size="7">相关</text>

              <circle cx="250" cy="210" r="14" fill="var(--skin-surface-soft)" stroke="var(--skin-border)" stroke-width="1" stroke-dasharray="3 2"/>
              <text x="250" y="207" text-anchor="middle" fill="var(--skin-text-tertiary)" font-size="7">遗传</text>
              <text x="250" y="215" text-anchor="middle" fill="var(--skin-text-tertiary)" font-size="7">因素</text>
            </svg>
          </div>
          <p class="graph-caption">
            基于皮肤病知识图谱 · GraphRAG 推理 · 匹配 12 个知识节点
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

/* ③ 候选诊断 */
.candidate-list {
  display: flex;
  flex-direction: column;
  gap: var(--skin-gap-2);
}

.candidate-item {
  background: var(--skin-surface);
  border: 1px solid var(--skin-border);
  border-radius: var(--skin-radius-lg);
  padding: var(--skin-gap-4) var(--skin-gap-4) var(--skin-gap-3);
}

.candidate-item-top {
  border-color: var(--skin-brand);
  background: var(--skin-brand-50);
}

.candidate-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: var(--skin-gap-3);
}

.candidate-left {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.candidate-rank {
  font-size: var(--skin-text-xs);
  font-weight: var(--skin-font-bold);
  color: var(--skin-brand);
  background: var(--skin-surface);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--skin-brand-100);
  flex-shrink: 0;
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}

.candidate-name {
  font-size: var(--skin-text-base);
  font-weight: var(--skin-font-semibold);
  color: var(--skin-text-primary);
  margin: 0 0 2px 0;
  letter-spacing: var(--skin-tracking-tight);
}

.candidate-desc {
  font-size: var(--skin-text-xs);
  color: var(--skin-text-tertiary);
  margin: 0;
  line-height: 1.5;
}

.candidate-pct {
  font-size: var(--skin-text-xl);
  font-weight: var(--skin-font-bold);
  color: var(--skin-brand);
  flex-shrink: 0;
  letter-spacing: var(--skin-tracking-tight);
}

.conf-track {
  height: 4px;
  background: var(--skin-border);
  border-radius: 2px;
  overflow: hidden;
}

.conf-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
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

/* ④ 知识图谱 */
.graph-card {
  padding: var(--skin-gap-4);
}

.graph-legend {
  display: flex;
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

.legend-disease {
  background: var(--skin-text-primary);
}

.legend-knowledge {
  background: var(--skin-border);
  border: 1px solid var(--skin-text-muted);
}

.graph-svg-wrap {
  border-radius: var(--skin-radius-md);
  background: var(--skin-bg);
  overflow: hidden;
  border: 1px solid var(--skin-border-soft);
}

.graph-svg {
  width: 100%;
  height: auto;
  display: block;
}

.graph-caption {
  font-size: var(--skin-text-xs);
  color: var(--skin-text-muted);
  text-align: center;
  margin: var(--skin-gap-3) 0 0 0;
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