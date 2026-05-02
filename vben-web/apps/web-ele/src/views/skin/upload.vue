<script setup lang="ts">
import { useRouter } from 'vue-router';

const router = useRouter();

function goReasoning() {
  // 假登录：直接生成一个 demo session
  const sessionId = `demo_${Date.now()}`;
  router.push(`/skin/reasoning/${sessionId}`);
}
</script>

<template>
  <div class="skin-page">
    <header class="hero">
      <h1>图睿病理</h1>
      <p class="subtitle">皮肤有不舒服？拍张照片，AI 帮你看一下</p>
    </header>

    <div class="upload-area" @click="goReasoning">
      <div class="upload-icon">📷</div>
      <p class="upload-text">点击拍照或上传</p>
      <p class="upload-hint">支持 JPG / PNG，10MB 以内</p>
    </div>

    <button class="btn-primary" @click="goReasoning">
      📸 现在拍一张
    </button>

    <button class="btn-secondary" @click="goReasoning">
      🖼️ 从相册选一张
    </button>

    <div class="tips">
      <p class="tips-title">💡 拍照小提示</p>
      <ul>
        <li>在光线充足的地方拍</li>
        <li>距离皮肤 15 公分左右</li>
        <li>让皮损在画面正中央</li>
      </ul>
    </div>

    <p class="disclaimer">
      ⚠️ 本应用仅供健康参考，不能替代医生诊断
    </p>
  </div>
</template>

<style scoped>
.skin-page {
  min-height: 100vh;
  background: #FAFBFC;
  padding: 32px 20px;
  max-width: 480px;
  margin: 0 auto;
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  color: #111827;
}

.hero {
  margin-bottom: 32px;
  margin-top: 24px;
}

.hero h1 {
  font-size: 32px;
  font-weight: 700;
  color: #2C7A7B;
  margin: 0 0 12px 0;
}

.subtitle {
  font-size: 18px;
  color: #4B5563;
  line-height: 1.6;
  margin: 0;
}

.upload-area {
  border: 2px dashed #D1D5DB;
  border-radius: 16px;
  background: white;
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 24px;
}

.upload-area:hover {
  border-color: #2C7A7B;
  background: #E6FFFA;
}

.upload-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.upload-text {
  font-size: 20px;
  font-weight: 500;
  margin: 0 0 8px 0;
}

.upload-hint {
  font-size: 14px;
  color: #9CA3AF;
  margin: 0;
}

.btn-primary,
.btn-secondary {
  width: 100%;
  min-height: 64px;
  font-size: 20px;
  border-radius: 32px;
  border: none;
  cursor: pointer;
  margin-bottom: 16px;
  font-weight: 500;
  transition: all 0.2s;
  font-family: inherit;
}

.btn-primary {
  background: #2C7A7B;
  color: white;
}

.btn-primary:hover {
  background: #285E5F;
}

.btn-secondary {
  background: white;
  color: #2C7A7B;
  border: 2px solid #2C7A7B;
}

.btn-secondary:hover {
  background: #E6FFFA;
}

.tips {
  background: #FEF3C7;
  border-radius: 12px;
  padding: 20px;
  margin-top: 32px;
}

.tips-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: #92400E;
}

.tips ul {
  margin: 0;
  padding-left: 24px;
  font-size: 16px;
  line-height: 1.8;
  color: #78350F;
}

.disclaimer {
  text-align: center;
  font-size: 14px;
  color: #9CA3AF;
  margin-top: 32px;
  line-height: 1.6;
}
</style>