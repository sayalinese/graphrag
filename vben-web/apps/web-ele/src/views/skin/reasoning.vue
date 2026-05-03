<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import '../skin/styles/token.css';

const route = useRoute();
const router = useRouter();

// 从路由参数获取 session ID
const sessionId = computed(() => route.params.sessionId as string);

// 从 sessionStorage 读取上传时存的图片信息
const uploadedImageUrl = ref<string>('');
const uploadedFileName = ref<string>('');

// 推理步骤定义
interface ReasoningStep {
  id: string;
  title: string;
  status: 'pending' | 'active' | 'done';
  content: string;
  fullContent: string;  // 完整内容（用于打字机效果）
  charIndex: number;    // 当前打字到第几个字
}

const steps = ref<ReasoningStep[]>([
  {
    id: 'receive',
    title: '接收到照片',
    status: 'pending',
    content: '',
    fullContent: '已成功接收 1 张皮损照片，开始预处理...',
    charIndex: 0,
  },
  {
    id: 'detect',
    title: '检测皮损区域',
    status: 'pending',
    content: '',
    fullContent: '识别到皮肤异常区域，位于画面中央，大小约占图片 35%。',
    charIndex: 0,
  },
  {
    id: 'extract',
    title: '提取关键特征',
    status: 'pending',
    content: '',
    fullContent: '观察到以下特征：\n· 颜色：偏红，分布不均匀\n· 边缘：轻度不规则\n· 表面：略有粗糙感\n· 形态：斑片状',
    charIndex: 0,
  },
  {
    id: 'graph',
    title: '比对知识图谱',
    status: 'pending',
    content: '',
    fullContent: '在皮肤病知识图谱中检索匹配，找到 12 个相关疾病节点，正在缩小范围...',
    charIndex: 0,
  },
  {
    id: 'rag',
    title: '调用医学文献',
    status: 'pending',
    content: '',
    fullContent: '检索到 5 篇相关医学文献，提取关键诊断依据...',
    charIndex: 0,
  },
  {
    id: 'conclude',
    title: '生成评估结果',
    status: 'pending',
    content: '',
    fullContent: '综合分析完成，正在生成报告...',
    charIndex: 0,
  },
]);

// 整体进度（百分比）
const overallProgress = computed(() => {
  const doneCount = steps.value.filter(s => s.status === 'done').length;
  return Math.round((doneCount / steps.value.length) * 100);
});

// 预计剩余时间
const remainingSeconds = ref(15);

// 当前进行中的步骤索引
const currentStepIndex = ref(0);

// 定时器引用
let typingTimer: number | null = null;
let stepTimer: number | null = null;
let countdownTimer: number | null = null;

// 启动下一个步骤
function startNextStep() {
  if (currentStepIndex.value >= steps.value.length) {
    // 所有步骤完成，跳转结果页
    setTimeout(() => {
      router.push(`/skin/result/${sessionId.value}`);
    }, 800);
    return;
  }
  
  const step = steps.value[currentStepIndex.value];
  step.status = 'active';
  
  // 开始打字机效果
  typeContent(step);
}

// 打字机效果
function typeContent(step: ReasoningStep) {
  typingTimer = window.setInterval(() => {
    if (step.charIndex < step.fullContent.length) {
      step.content = step.fullContent.substring(0, step.charIndex + 1);
      step.charIndex++;
    } else {
      // 打字完成
      if (typingTimer) clearInterval(typingTimer);
      
      // 短暂停留，然后标记为完成
      setTimeout(() => {
        step.status = 'done';
        currentStepIndex.value++;
        
        // 启动下一个步骤
        setTimeout(() => {
          startNextStep();
        }, 400);
      }, 500);
    }
  }, 40); // 每 40ms 输出一个字符
}

// 倒计时
function startCountdown() {
  countdownTimer = window.setInterval(() => {
    if (remainingSeconds.value > 0) {
      remainingSeconds.value--;
    } else {
      if (countdownTimer) clearInterval(countdownTimer);
    }
  }, 1000);
}

// 返回上一页
function goBack() {
  router.push('/skin/upload');
}

onMounted(() => {
  // 从 sessionStorage 读取图片
  const dataStr = sessionStorage.getItem(`skin_session_${sessionId.value}`);
  if (dataStr) {
    try {
      const data = JSON.parse(dataStr);
      uploadedImageUrl.value = data.urls?.[0] || '';
      uploadedFileName.value = data.fileNames?.[0] || '';
    } catch (e) {
      console.error('解析 session 数据失败', e);
    }
  }
  
  // 启动倒计时和第一个步骤
  startCountdown();
  setTimeout(() => {
    startNextStep();
  }, 600);
});

onBeforeUnmount(() => {
  if (typingTimer) clearInterval(typingTimer);
  if (stepTimer) clearInterval(stepTimer);
  if (countdownTimer) clearInterval(countdownTimer);
});
</script>

<template>
  <div class="skin-page">
    <!-- 顶部固定区：缩略图 + 状态 -->
    <div class="header-fixed">
      <button class="back-btn" @click="goBack" aria-label="返回">
        ←
      </button>
      
      <div v-if="uploadedImageUrl" class="header-thumb">
        <img :src="uploadedImageUrl" alt="您的照片" />
      </div>
      <div v-else class="header-thumb header-thumb-placeholder">
        📷
      </div>
      
      <div class="header-info">
        <p class="header-title">正在分析您的照片</p>
        <p class="header-subtitle">
          <span v-if="overallProgress < 100">
            预计还需 {{ remainingSeconds }} 秒
          </span>
          <span v-else>分析完成</span>
        </p>
      </div>
      
      <!-- 圆形进度条 -->
      <div class="progress-circle">
        <svg viewBox="0 0 36 36" class="progress-svg">
          <path
            class="progress-bg"
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          />
          <path
            class="progress-fill"
            :stroke-dasharray="`${overallProgress}, 100`"
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          />
        </svg>
        <div class="progress-text">{{ overallProgress }}%</div>
      </div>
    </div>

    <!-- 步骤流 -->
    <div class="skin-container steps-container">
      <div
        v-for="(step, idx) in steps"
        :key="step.id"
        class="step-card"
        :class="`step-${step.status}`"
      >
        <!-- 步骤头部 -->
        <div class="step-header">
          <!-- 状态图标 -->
          <div class="status-icon" :class="`icon-${step.status}`">
            <svg v-if="step.status === 'done'" viewBox="0 0 24 24" class="check-icon">
              <path 
                fill="none" 
                stroke="currentColor" 
                stroke-width="3" 
                stroke-linecap="round" 
                stroke-linejoin="round"
                d="M5 12l5 5L20 7"
              />
            </svg>
            <div v-else-if="step.status === 'active'" class="pulse-dot"></div>
            <div v-else class="pending-dot"></div>
          </div>
          
          <!-- 步骤标题 -->
          <span class="step-title">{{ step.title }}</span>
          
          <!-- 步骤序号 -->
          <span class="step-number">{{ idx + 1 }}/{{ steps.length }}</span>
        </div>

        <!-- 步骤内容（打字机效果）-->
        <div v-if="step.content || step.status === 'active'" class="step-content">
          <span class="content-text">{{ step.content }}</span>
          <span 
            v-if="step.status === 'active'" 
            class="cursor"
          >▍</span>
        </div>
      </div>

      <!-- 完成提示 -->
      <div v-if="overallProgress === 100" class="finish-banner">
        ✨ 分析完成，正在生成报告...
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 顶部固定区 */
.header-fixed {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--skin-surface);
  border-bottom: 1px solid var(--skin-border);
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: var(--skin-shadow-card);
}

.back-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--skin-bg);
  border: none;
  font-size: 24px;
  color: var(--skin-text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--skin-transition);
}

.back-btn:hover {
  background: var(--skin-border);
}

.header-thumb {
  width: 56px;
  height: 56px;
  border-radius: var(--skin-radius-md);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--skin-border);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.header-thumb-placeholder {
  font-size: 28px;
}

.header-info {
  flex: 1;
  min-width: 0;
}

.header-title {
  font-size: var(--skin-text-base);
  font-weight: 600;
  margin: 0 0 4px 0;
  color: var(--skin-text-primary);
}

.header-subtitle {
  font-size: var(--skin-text-xs);
  color: var(--skin-text-muted);
  margin: 0;
}

/* 圆形进度条 */
.progress-circle {
  position: relative;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
}

.progress-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.progress-bg {
  fill: none;
  stroke: var(--skin-border);
  stroke-width: 3;
}

.progress-fill {
  fill: none;
  stroke: var(--skin-brand);
  stroke-width: 3;
  stroke-linecap: round;
  transition: stroke-dasharray 0.4s ease;
}

.progress-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: var(--skin-brand);
}

/* 步骤容器 */
.steps-container {
  padding: 24px 20px 80px;
}

/* 步骤卡片 */
.step-card {
  background: var(--skin-surface);
  border-radius: var(--skin-radius-lg);
  padding: 16px 20px;
  margin-bottom: 12px;
  box-shadow: var(--skin-shadow-card);
  transition: var(--skin-transition);
  border: 2px solid transparent;
}

.step-pending {
  opacity: 0.5;
}

.step-active {
  border-color: var(--skin-brand);
  box-shadow: 0 0 0 4px rgba(44, 122, 123, 0.08), var(--skin-shadow-card);
}

.step-done {
  background: var(--skin-risk-low-soft);
}

/* 步骤头部 */
.step-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 状态图标 */
.status-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: var(--skin-transition);
}

.icon-pending {
  background: var(--skin-bg);
  border: 2px solid var(--skin-border);
}

.icon-active {
  background: var(--skin-brand-soft);
  border: 2px solid var(--skin-brand);
}

.icon-done {
  background: var(--skin-risk-low);
  color: white;
}

.check-icon {
  width: 20px;
  height: 20px;
}

.pending-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--skin-text-muted);
}

.pulse-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--skin-brand);
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { 
    transform: scale(1); 
    opacity: 1; 
  }
  50% { 
    transform: scale(1.4); 
    opacity: 0.5; 
  }
}

/* 步骤标题 */
.step-title {
  flex: 1;
  font-size: var(--skin-text-base);
  font-weight: 600;
  color: var(--skin-text-primary);
}

.step-number {
  font-size: var(--skin-text-xs);
  color: var(--skin-text-muted);
  font-variant-numeric: tabular-nums;
}

/* 步骤内容 */
.step-content {
  margin-top: 12px;
  padding-left: 44px;
  font-size: var(--skin-text-sm);
  color: var(--skin-text-secondary);
  line-height: var(--skin-leading);
  white-space: pre-line;
}

.content-text {
  display: inline;
}

.cursor {
  display: inline-block;
  margin-left: 2px;
  color: var(--skin-brand);
  font-weight: bold;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* 完成提示 */
.finish-banner {
  margin-top: 24px;
  padding: 20px;
  background: var(--skin-brand-soft);
  border-radius: var(--skin-radius-lg);
  text-align: center;
  font-size: var(--skin-text-base);
  font-weight: 500;
  color: var(--skin-brand);
  animation: fadeIn 0.5s ease;
}

@keyframes fadeIn {
  from { 
    opacity: 0; 
    transform: translateY(10px); 
  }
  to { 
    opacity: 1; 
    transform: translateY(0); 
  }
}
</style>