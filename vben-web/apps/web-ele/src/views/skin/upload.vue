<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import './styles/token.css';

const router = useRouter();

// 状态管理
const selectedFiles = ref<File[]>([]);
const previewUrls = ref<string[]>([]);
const isUploading = ref(false);
const uploadProgress = ref(0);
const errorMessage = ref('');

// 文件输入 ref
const fileInputRef = ref<HTMLInputElement | null>(null);

// 是否已选择图片
const hasSelectedImages = computed(() => selectedFiles.value.length > 0);

// 触发文件选择（拍照）
function takePhoto() {
  if (fileInputRef.value) {
    // capture="environment" 会调起后置摄像头
    fileInputRef.value.setAttribute('capture', 'environment');
    fileInputRef.value.click();
  }
}

// 触发文件选择（相册）
function pickFromAlbum() {
  if (fileInputRef.value) {
    // 移除 capture 属性，让用户可以选相册
    fileInputRef.value.removeAttribute('capture');
    fileInputRef.value.click();
  }
}

// 处理文件选择
function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  const files = target.files;
  
  if (!files || files.length === 0) return;
  
  errorMessage.value = '';
  
  // 验证文件
  const validFiles: File[] = [];
  const validUrls: string[] = [];
  
  for (let i = 0; i < files.length && i < 3; i++) {
    const file = files[i];
    
    // 文件类型检查
    if (!file.type.startsWith('image/')) {
      errorMessage.value = '请选择图片文件';
      continue;
    }
    
    // 文件大小检查（10MB）
    if (file.size > 10 * 1024 * 1024) {
      errorMessage.value = '图片不能超过 10MB';
      continue;
    }
    
    validFiles.push(file);
    validUrls.push(URL.createObjectURL(file));
  }
  
  selectedFiles.value = validFiles;
  previewUrls.value = validUrls;
  
  // 清空 input，允许重复选择同一文件
  target.value = '';
}

// 清空所有已选图片并释放 blob URL
function clearImages() {
  previewUrls.value.forEach(url => URL.revokeObjectURL(url));
  selectedFiles.value = [];
  previewUrls.value = [];
}

// 移除某张图片
function removeImage(index: number) {
  URL.revokeObjectURL(previewUrls.value[index]);
  selectedFiles.value.splice(index, 1);
  previewUrls.value.splice(index, 1);
}

// 上传图片（Mock 版本 - 后端接口好了再换回真实版）
async function uploadImages() {
  if (selectedFiles.value.length === 0) {
    errorMessage.value = '请先选择图片';
    return;
  }

  isUploading.value = true;
  uploadProgress.value = 0;
  errorMessage.value = '';

  // 模拟上传进度（每 200ms 增加 10%）
  const progressInterval = setInterval(() => {
    uploadProgress.value += 10;

    if (uploadProgress.value >= 100) {
      clearInterval(progressInterval);

      // 模拟上传成功
      setTimeout(() => {
        const sessionId = `demo_${Date.now()}`;

        // 把图片信息存到 sessionStorage，让推理页能用
        const imageData = {
          urls: previewUrls.value,
          fileNames: selectedFiles.value.map((f) => f.name),
        };
        sessionStorage.setItem(
          `skin_session_${sessionId}`,
          JSON.stringify(imageData),
        );

        // 跳转到推理页
        router.push(`/skin/reasoning/${sessionId}`);
      }, 300);
    }
  }, 200);
}

// 组件卸载时清理预览 URL
onBeforeUnmount(() => {
  previewUrls.value.forEach(url => URL.revokeObjectURL(url));
});
</script>

<template>
  <div class="skin-page">
    <div class="skin-container">
      <!-- 顶部标题 -->
      <header class="hero">
        <h1 class="skin-title">图睿病理</h1>
        <p class="subtitle">皮肤有不舒服？拍张照片，AI 帮你看一下</p>
      </header>

      <!-- 错误提示 -->
      <div v-if="errorMessage" class="error-banner">
        ⚠️ {{ errorMessage }}
      </div>

      <!-- 图片预览区 -->
      <div v-if="hasSelectedImages" class="preview-section">
        <div class="preview-grid">
          <div 
            v-for="(url, index) in previewUrls" 
            :key="index"
            class="preview-item"
          >
            <img :src="url" :alt="`预览图 ${index + 1}`" />
            <button 
              class="remove-btn" 
              @click="removeImage(index)"
              :disabled="isUploading"
            >
              ×
            </button>
          </div>
        </div>
        <p class="preview-hint">
          已选 {{ selectedFiles.length }} 张图片
          {{ selectedFiles.length < 3 ? '（建议多拍几张不同角度）' : '' }}
        </p>
      </div>

      <!-- 上传区（未选择图片时显示）-->
      <div 
        v-else
        class="upload-area" 
        @click="takePhoto"
      >
        <div class="upload-icon">📷</div>
        <p class="upload-text">点击拍照或上传</p>
        <p class="upload-hint">支持 JPG / PNG，10MB 以内</p>
      </div>

      <!-- 隐藏的文件输入 -->
      <input
        ref="fileInputRef"
        type="file"
        accept="image/*"
        multiple
        class="hidden-input"
        @change="handleFileChange"
      />

      <!-- 主操作按钮 -->
      <button
        v-if="!hasSelectedImages"
        class="skin-btn-primary"
        @click="takePhoto"
        :disabled="isUploading"
      >
        📸 现在拍一张
      </button>

      <button
        v-if="!hasSelectedImages"
        class="skin-btn-secondary"
        style="margin-top: 16px"
        @click="pickFromAlbum"
        :disabled="isUploading"
      >
        🖼️ 从相册选一张
      </button>

      <!-- 已选择图片后显示上传按钮 -->
      <button
        v-if="hasSelectedImages"
        class="skin-btn-primary"
        @click="uploadImages"
        :disabled="isUploading"
      >
        <span v-if="!isUploading">开始分析</span>
        <span v-else>上传中 {{ uploadProgress }}%...</span>
      </button>

      <button
        v-if="hasSelectedImages && !isUploading"
        class="skin-btn-secondary"
        style="margin-top: 16px"
        @click="clearImages"
      >
        重新选择
      </button>

      <!-- 拍照小提示 -->
      <details class="tips-card" open>
        <summary class="tips-title">💡 拍照小提示</summary>
        <ul class="tips-list">
          <li>在光线充足的地方拍</li>
          <li>距离皮肤 15 公分左右</li>
          <li>让皮损在画面正中央</li>
          <li>拍 2-3 张不同角度更准确</li>
        </ul>
      </details>

      <!-- 免责声明 -->
      <p class="disclaimer">
        ⚠️ 本应用仅供健康参考，不能替代医生诊断
      </p>
    </div>
  </div>
</template>

<style scoped>
/* 主容器已在 tokens.css 里定义，这里只写页面特有样式 */

.hero {
  margin-bottom: var(--skin-gap-xl);
  margin-top: var(--skin-gap-lg);
}

.skin-title {
  /* tokens.css 里已定义，这里只做微调 */
  margin-bottom: var(--skin-gap-sm);
}

.subtitle {
  font-size: var(--skin-text-base);
  color: var(--skin-text-secondary);
  line-height: var(--skin-leading);
  margin: 0;
}

/* 错误提示 */
.error-banner {
  background: var(--skin-risk-high-soft);
  color: #991B1B;
  padding: var(--skin-gap-md);
  border-radius: var(--skin-radius-md);
  margin-bottom: var(--skin-gap-lg);
  font-size: var(--skin-text-sm);
  border-left: 4px solid var(--skin-risk-high);
}

/* 预览区 */
.preview-section {
  margin-bottom: var(--skin-gap-xl);
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: var(--skin-gap-md);
  margin-bottom: var(--skin-gap-md);
}

.preview-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: var(--skin-radius-md);
  overflow: hidden;
  background: var(--skin-border);
}

.preview-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.remove-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(220, 38, 38, 0.9);
  color: white;
  border: none;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--skin-transition);
}

.remove-btn:hover:not(:disabled) {
  background: rgba(220, 38, 38, 1);
  transform: scale(1.1);
}

.remove-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.preview-hint {
  font-size: var(--skin-text-sm);
  color: var(--skin-text-secondary);
  text-align: center;
  margin: 0;
}

/* 上传区 */
.upload-area {
  border: 2px dashed var(--skin-border);
  border-radius: var(--skin-radius-lg);
  background: var(--skin-surface);
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: var(--skin-transition);
  margin-bottom: var(--skin-gap-lg);
}

.upload-area:hover {
  border-color: var(--skin-brand);
  background: var(--skin-brand-soft);
}

.upload-icon {
  font-size: 64px;
  margin-bottom: var(--skin-gap-md);
}

.upload-text {
  font-size: var(--skin-text-lg);
  font-weight: 500;
  margin: 0 0 var(--skin-gap-xs) 0;
  color: var(--skin-text-primary);
}

.upload-hint {
  font-size: var(--skin-text-xs);
  color: var(--skin-text-muted);
  margin: 0;
}

/* 隐藏文件输入 */
.hidden-input {
  display: none;
}

/* 提示卡片 */
.tips-card {
  background: var(--skin-risk-mid-soft);
  border-radius: var(--skin-radius-md);
  padding: var(--skin-gap-lg);
  margin-top: var(--skin-gap-xl);
  border: none;
}

.tips-title {
  font-size: var(--skin-text-base);
  font-weight: 600;
  color: #92400E;
  cursor: pointer;
  list-style: none;
  margin-bottom: var(--skin-gap-sm);
}

.tips-title::-webkit-details-marker {
  display: none;
}

.tips-list {
  margin: 0;
  padding-left: var(--skin-gap-lg);
  font-size: var(--skin-text-sm);
  line-height: var(--skin-leading);
  color: #78350F;
}

.tips-list li {
  margin-bottom: var(--skin-gap-xs);
}

/* 免责声明 */
.disclaimer {
  text-align: center;
  font-size: var(--skin-text-xs);
  color: var(--skin-text-muted);
  margin-top: var(--skin-gap-xl);
  line-height: var(--skin-leading);
  padding: var(--skin-gap-md);
  background: var(--skin-surface);
  border-radius: var(--skin-radius-sm);
}

/* 按钮间距调整 */
.skin-btn-primary + .skin-btn-secondary {
  margin-top: var(--skin-gap-md);
}
</style>