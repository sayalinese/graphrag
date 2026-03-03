<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import {
  ElButton,
  ElCard,
  ElCheckbox,
  ElDivider,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElRadio,
  ElRadioGroup,
  ElTabPane,
  ElTabs,
  ElTag,
} from 'element-plus';
import { Page } from '@vben/common-ui';

defineOptions({ name: 'BoardGate' });

type LoginKind = 'server' | 'admin';
type Mode = 'login' | 'register';

const router = useRouter();

const mode = ref<Mode>('login');
const loginKind = ref<LoginKind>('server');
const submitting = ref(false);

const loginForm = reactive({
  account: '',
  password: '',
  adminCode: '',
  remember: true,
});

const registerForm = reactive({
  account: '',
  password: '',
  confirmPassword: '',
  agree: true,
});

const isAdminLogin = computed(() => loginKind.value === 'admin');

function validateBasicAccount(account: string) {
  return account.trim().length >= 2;
}
function validatePassword(pwd: string) {
  return pwd.trim().length >= 6;
}

async function submitLogin() {
  if (!validateBasicAccount(loginForm.account)) {
    ElMessage.warning('请输入账号（至少2个字符）');
    return;
  }
  if (!validatePassword(loginForm.password)) {
    ElMessage.warning('请输入密码（至少6位）');
    return;
  }
  if (isAdminLogin.value && !loginForm.adminCode.trim()) {
    ElMessage.warning('管理端登录需要填写管理员验证码');
    return;
  }

  submitting.value = true;
  try {
    await new Promise((r) => setTimeout(r, 650));
    localStorage.setItem(
      'board_gate_session',
      JSON.stringify({
        kind: loginKind.value,
        account: loginForm.account.trim(),
        ts: Date.now(),
      }),
    );
    ElMessage.success(loginKind.value === 'admin' ? '管理端登录成功（Mock）' : '服务端登录成功（Mock）');
    await router.push('/board/app');
  } finally {
    submitting.value = false;
  }
}

async function submitRegister() {
  if (!validateBasicAccount(registerForm.account)) {
    ElMessage.warning('请输入账号（至少2个字符）');
    return;
  }
  if (!validatePassword(registerForm.password)) {
    ElMessage.warning('请输入密码（至少6位）');
    return;
  }
  if (registerForm.password !== registerForm.confirmPassword) {
    ElMessage.warning('两次密码不一致');
    return;
  }
  if (!registerForm.agree) {
    ElMessage.warning('请勾选同意服务条款');
    return;
  }

  submitting.value = true;
  try {
    await new Promise((r) => setTimeout(r, 800));
    ElMessage.success('注册成功（Mock），请使用服务端登录');
    mode.value = 'login';
    loginKind.value = 'server';
    loginForm.account = registerForm.account.trim();
    loginForm.password = registerForm.password;
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <Page content-class="h-full p-0 overflow-hidden">
    <div class="gate-root">
      <!-- 背景装饰 -->
      <div class="bg-aurora" />
      <div class="bg-grid" />
      <div class="bg-orb orb-1" />
      <div class="bg-orb orb-2" />

      <div class="gate-shell">
        <!-- 左：品牌/卖点 -->
        <section class="brand-panel">
          <div class="brand-top">
            <div class="logo-badge">
              <div class="logo-dot" />
              <div class="logo-text">NANSHAN</div>
            </div>
            <ElTag effect="plain" class="tag-soft">Visual RAG</ElTag>
          </div>

          <div class="brand-main">
            <div class="title">
              视觉RAG智能体
              <span class="title-accent">南山</span>
            </div>
            <div class="subtitle">
              将“图像理解”与“知识检索”融合：更可信的证据链、更快的召回、更可解释的结论。
            </div>

            <div class="pill-row">
              <div class="pill">多模态检索</div>
              <div class="pill">相似度排行</div>
              <div class="pill">召回可视化</div>
              <div class="pill">可控Mock</div>
            </div>
          </div>

          <div class="brand-footer">
            <div class="stat">
              <div class="stat-num">16–36s</div>
              <div class="stat-label">模拟分析耗时</div>
            </div>
            <div class="stat">
              <div class="stat-num">Top-K</div>
              <div class="stat-label">召回与重排</div>
            </div>
            <div class="stat">
              <div class="stat-num">LIVE</div>
              <div class="stat-label">视觉流标记</div>
            </div>
          </div>
        </section>

        <!-- 右：登录/注册 -->
        <section class="form-panel">
          <ElCard class="glass-card" shadow="never">
            <template #header>
              <div class="card-head">
                <div class="card-title">欢迎使用 · 南山</div>
                <div class="card-desc">请选择登录方式或注册服务端账号（Mock）</div>
              </div>
            </template>

            <ElTabs v-model="mode" class="tabs" stretch>
              <ElTabPane label="登录" name="login">
                <div class="seg-row">
                  <ElRadioGroup v-model="loginKind" class="seg">
                    <ElRadio label="server" value="server" border>服务端登录</ElRadio>
                    <ElRadio label="admin" value="admin" border>管理端登录</ElRadio>
                  </ElRadioGroup>
                </div>

                <ElForm label-position="top" size="default" class="mt-3">
                  <ElFormItem :label="loginKind === 'admin' ? '管理员账号' : '账号'">
                    <ElInput v-model="loginForm.account" placeholder="请输入账号" clearable />
                  </ElFormItem>
                  <ElFormItem label="密码">
                    <ElInput v-model="loginForm.password" type="password" show-password placeholder="请输入密码" />
                  </ElFormItem>
                  <ElFormItem v-if="isAdminLogin" label="管理员验证码">
                    <ElInput v-model="loginForm.adminCode" placeholder="请输入验证码（Mock）" clearable />
                  </ElFormItem>
                  <div class="row-between">
                    <ElCheckbox v-model="loginForm.remember">记住我</ElCheckbox>
                    <button class="link-btn" type="button" @click="ElMessage.info('已在规划：找回密码（Mock）')">
                      忘记密码
                    </button>
                  </div>
                  <ElButton
                    type="primary"
                    class="w-full mt-4"
                    :loading="submitting"
                    @click="submitLogin"
                  >
                    进入南山
                  </ElButton>
                  <ElDivider class="my-4">或</ElDivider>
                  <ElButton class="w-full" :disabled="submitting" @click="mode = 'register'">注册服务端账号</ElButton>
                </ElForm>
              </ElTabPane>

              <ElTabPane label="注册" name="register">
                <div class="hint">
                  注册默认仅支持 <b>服务端</b> 使用；管理端账号由平台管理员创建。
                </div>
                <ElForm label-position="top" size="default" class="mt-3">
                  <ElFormItem label="账号">
                    <ElInput v-model="registerForm.account" placeholder="请输入账号" clearable />
                  </ElFormItem>
                  <ElFormItem label="密码">
                    <ElInput v-model="registerForm.password" type="password" show-password placeholder="至少6位" />
                  </ElFormItem>
                  <ElFormItem label="确认密码">
                    <ElInput v-model="registerForm.confirmPassword" type="password" show-password placeholder="再次输入密码" />
                  </ElFormItem>
                  <div class="row-between">
                    <ElCheckbox v-model="registerForm.agree">同意服务条款</ElCheckbox>
                    <button class="link-btn" type="button" @click="ElMessage.info('已在规划：服务条款（Mock）')">
                      查看条款
                    </button>
                  </div>
                  <ElButton
                    type="primary"
                    class="w-full mt-4"
                    :loading="submitting"
                    @click="submitRegister"
                  >
                    创建账号
                  </ElButton>
                  <ElButton class="w-full mt-2" :disabled="submitting" @click="mode = 'login'">
                    返回登录
                  </ElButton>
                </ElForm>
              </ElTabPane>
            </ElTabs>
          </ElCard>

          <div class="mini-note">
            <span class="dot" />
            当前为演示环境：登录/注册不接后端，仅用于流程与 UI 验证
          </div>
        </section>
      </div>
    </div>
  </Page>
</template>

<style scoped>
.gate-root {
  position: relative;
  height: 100%;
  min-height: calc(100vh - 100px);
  overflow: hidden;
  background: radial-gradient(1200px 800px at 20% 10%, rgba(99, 102, 241, 0.20), transparent 55%),
    radial-gradient(1000px 700px at 80% 30%, rgba(236, 72, 153, 0.16), transparent 55%),
    radial-gradient(900px 600px at 30% 90%, rgba(34, 197, 94, 0.14), transparent 55%),
    linear-gradient(180deg, #f7f8ff 0%, #f2f6ff 35%, #eef2ff 100%);
}

.bg-aurora {
  position: absolute;
  inset: -40%;
  background: conic-gradient(from 120deg, rgba(99, 102, 241, 0.28), rgba(236, 72, 153, 0.18), rgba(34, 197, 94, 0.18), rgba(99, 102, 241, 0.28));
  filter: blur(60px);
  opacity: 0.55;
  animation: drift 10s ease-in-out infinite alternate;
}
@keyframes drift {
  0% { transform: translate3d(-2%, -1%, 0) rotate(-2deg); }
  100% { transform: translate3d(2%, 1%, 0) rotate(2deg); }
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(0,0,0,0.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0,0,0,0.04) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(circle at 50% 40%, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.20) 55%, transparent 80%);
  pointer-events: none;
}

.bg-orb {
  position: absolute;
  width: 520px;
  height: 520px;
  border-radius: 50%;
  filter: blur(40px);
  opacity: 0.35;
  pointer-events: none;
}
.orb-1 { left: -180px; top: -160px; background: radial-gradient(circle at 30% 30%, rgba(99,102,241,0.9), transparent 60%); }
.orb-2 { right: -220px; bottom: -200px; background: radial-gradient(circle at 30% 30%, rgba(236,72,153,0.8), transparent 60%); }

.gate-shell {
  position: relative;
  height: 100%;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 22px;
  padding: 28px;
  max-width: 1200px;
  margin: 0 auto;
  align-items: center;
}

@media (max-width: 980px) {
  .gate-shell {
    grid-template-columns: 1fr;
    padding: 18px;
  }
}

.brand-panel {
  border-radius: 22px;
  padding: 22px;
  background: rgba(255,255,255,0.55);
  border: 1px solid rgba(255,255,255,0.55);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 18px 60px rgba(15, 23, 42, 0.10);
}

.brand-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.10);
  border: 1px solid rgba(99, 102, 241, 0.18);
}
.logo-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 0 0 6px rgba(99,102,241,0.12);
}
.logo-text {
  font-weight: 900;
  letter-spacing: 1px;
  color: #111827;
  font-size: 12px;
}

.tag-soft {
  border-radius: 999px;
  border-color: rgba(0,0,0,0.06);
  background: rgba(255,255,255,0.6);
}

.brand-main { margin-top: 16px; }
.title {
  font-size: 34px;
  line-height: 1.15;
  font-weight: 900;
  color: #0f172a;
  letter-spacing: -0.6px;
}
.title-accent {
  margin-left: 8px;
  background: linear-gradient(90deg, #4f46e5, #8b5cf6, #ec4899);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.subtitle {
  margin-top: 10px;
  font-size: 14px;
  color: #475569;
  line-height: 1.7;
  max-width: 520px;
}

.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}
.pill {
  padding: 9px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.7);
  border: 1px solid rgba(0,0,0,0.06);
  font-size: 12px;
  color: #0f172a;
  font-weight: 700;
}

.brand-footer {
  margin-top: 22px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.stat {
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255,255,255,0.7);
  border: 1px solid rgba(0,0,0,0.06);
}
.stat-num {
  font-weight: 900;
  color: #111827;
  letter-spacing: -0.2px;
}
.stat-label {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.form-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.glass-card {
  border-radius: 22px;
  border: 1px solid rgba(255,255,255,0.55);
  background: rgba(255,255,255,0.70);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 18px 60px rgba(15, 23, 42, 0.12);
}

.card-head { display: flex; flex-direction: column; gap: 4px; }
.card-title { font-size: 16px; font-weight: 900; color: #0f172a; }
.card-desc { font-size: 12px; color: #64748b; }

.seg-row { margin-top: 2px; }
.seg :deep(.el-radio.is-bordered) {
  width: 100%;
  justify-content: center;
  border-radius: 12px;
}
.seg :deep(.el-radio-group) { width: 100%; }
.seg :deep(.el-radio) { margin-right: 0 !important; }

.row-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: -4px;
}

.link-btn {
  background: transparent;
  border: none;
  color: #4f46e5;
  font-weight: 700;
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}
.link-btn:hover { text-decoration: underline; }

.hint {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(99,102,241,0.08);
  border: 1px solid rgba(99,102,241,0.14);
  color: #334155;
  font-size: 12px;
  line-height: 1.5;
}

.mini-note {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
  padding-left: 6px;
}
.mini-note .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 6px rgba(34,197,94,0.12);
}
</style>



