<script setup lang="ts">
import { nextTick, ref, computed, onMounted } from 'vue';
import {
  ElIcon,
  ElImage,
  ElUpload,
  ElInput,
  ElRadio,
  ElRadioGroup,
  ElDialog,
  ElButton,
  ElTooltip,
  ElAvatar,
} from 'element-plus';
import {
  Location,
  Setting,
  Mute,
  Star,
  Microphone,
  Picture,
  MagicStick,
  Promotion,
  Upload,
  Delete,
  Edit,
  Connection,
  User,
} from '@element-plus/icons-vue';
import { Page } from '@vben/common-ui';
import { useUserStore } from '@vben/stores';
import type { UploadFile } from 'element-plus';
import { type RAGResult, saveScenarioData, getScenarioImageUrl } from '../mock/data';

const userStore = useUserStore();

// --- 类型定义 ---

interface Message {
  id: number;
  type: 'user' | 'assistant';
  content: string;
  timestamp: string;
  loading?: boolean;
  searchTime?: number;
  location?: string;
  images?: RAGResult[];
  conclusion?: string;
  overlayTime?: string; // 图片角标时间（随机生成）
  recallShown?: number; // 本次展示的召回数量（TopN）
  recallTotal?: number; // 召回总数量
  recallRank?: RecallRankItem[]; // 相似度排行（TopN）
  recallExpanded?: boolean; // 相似度排行是否展开（默认折叠）
}

interface RecallRankItem {
  id: number;
  title: string;
  score: number; // 0~1
  source: string;
  time: string; // HH:mm
  thumb?: string; // 缩略图（可选）
}

interface Scenario {
  id: number;
  name: string;
  replyText: string;
  imageUrl: string;
  conclusion: string;
}

// --- 状态定义 ---

// 1. Mock 场景配置
const scenarios = ref<Scenario[]>([
  {
    id: 1,
    name: '筱园食堂',
    replyText: '经视觉分析，当前筱园食堂二楼人流量稀少，超过 90% 的座位处于空闲状态。各餐饮窗口均无需排队，用餐环境安静舒适。',
    imageUrl: '', // 待上传
    conclusion: '当前为非高峰时段，无需等待，推荐即刻前往用餐。',
  },
  {
    id: 2,
    name: '松园食堂',
    replyText:
      '从画面观察，松园食堂就餐区当前较为空：餐桌与座位大多未被占用，视野内未见明显排队与拥堵。整体环境整洁，通道顺畅，属于“人少/不挤”的状态。',
    imageUrl: '', 
    conclusion: '结论：目前人不多，基本无需等待；现在去用餐体验会更舒适。',
  },
  {
    id: 3,
    name: '乒乓球台',
    replyText:
      '视觉检测显示：南操运动场乒乓球区域当前状态良好。画面中可见多张（约 6 张）乒乓球台，未见正在使用的人群，绝大多数处于空闲状态。场地遮阴充足，地面与球台整体完好。',
    imageUrl: '', 
    conclusion: '结论：空位充足，随到随打；建议优先选择树荫下或台面更干净的球台。',
  },
  {
    id: 4,
    name: '图书馆',
    replyText:
      '根据画面俯视观察，图书馆自习区当前有人在学习，但整体不拥挤：分散就座为主，空桌与空位较多，走道通畅，环境安静。',
    imageUrl: '', 
    conclusion: '结论：普遍有人但不满座，想找座位问题不大；建议优先选远离通道的位置更安静。',
  },
]);

const activeScenarioId = ref<number>(1); // 当前选中的场景ID

// 页面初始化：从持久化存储恢复各场景图片（刷新后仍可用、也能被对话引用）
onMounted(() => {
  for (const s of scenarios.value) {
    const saved = getScenarioImageUrl(s.id);
    if (saved) s.imageUrl = saved;
  }
});

// 弹窗控制
const dialogVisible = ref(false);
const currentEditingScenario = ref<Scenario | null>(null);

// 2. 聊天状态
const loading = ref(false);
const inputText = ref('');
const messages = ref<Message[]>([]);
const messagesContainer = ref<HTMLElement>();
let messageIdCounter = 0;

// 头像处理 - 直接复用后端管理平台的头像
const userAvatar = computed(() => {
  // 直接使用后端返回的用户头像
  const avatar = userStore.userInfo?.avatar;
  console.log('User Avatar:', avatar); // 调试日志
  return avatar || ''; // 如果没有头像则返回空字符串，让 ElAvatar 使用默认显示
});

// AI 头像 - 使用更好看的机器人风格
const aiAvatar = 'https://api.dicebear.com/7.x/bottts/svg?seed=VisualAI&backgroundColor=8b5cf6&eyes=shade01&mouth=smile01';

// --- 辅助函数 ---

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
};

const getCurrentTime = () => {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
};

const getRandomOverlayTime = () => {
  // 随机时间范围：10:00 ~ 16:20
  const min = 10 * 60;
  const max = 16 * 60 + 20;
  const minutes = min + Math.floor(Math.random() * (max - min + 1));
  const hh = Math.floor(minutes / 60)
    .toString()
    .padStart(2, '0');
  const mm = (minutes % 60).toString().padStart(2, '0');
  return `${hh}:${mm}`;
};

const getRandomSearchTime = () => {
  // 随机耗时范围：16s ~ 36s（保留两位小数）
  const min = 16;
  const max = 36;
  return Number((min + Math.random() * (max - min)).toFixed(2));
};

const mockRecallConfig: Record<number, { shown: number; total: number; items: Omit<RecallRankItem, 'id' | 'thumb'>[] }> =
  {
    // 筱园食堂：9/12
    1: {
      shown: 9,
      total: 17,
      items: [
        { title: '筱园·二楼就餐区（近窗）', score: 0.97, source: 'Cam-A2', time: '11:12' },
        { title: '筱园·取餐窗口（主通道）', score: 0.95, source: 'Cam-A1', time: '11:10' },
        { title: '筱园·座位区（东侧）', score: 0.93, source: 'Cam-A3', time: '11:09' },
        { title: '筱园·座位区（西侧）', score: 0.91, source: 'Cam-A4', time: '11:08' },
        { title: '筱园·排队区域（入口）', score: 0.89, source: 'Cam-A0', time: '11:07' },
        { title: '筱园·自助结算区', score: 0.87, source: 'Cam-A5', time: '11:06' },
        { title: '筱园·饮品/小吃档', score: 0.86, source: 'Cam-A6', time: '11:05' },
        { title: '筱园·回收台附近', score: 0.84, source: 'Cam-A7', time: '11:04' },
        { title: '筱园·二楼走道', score: 0.82, source: 'Cam-A8', time: '11:03' },
      ],
    },
    // 松园食堂：9/12（同“食堂”规则）
    2: {
      shown: 9,
      total: 15,
      items: [
        { title: '松园·就餐区（中部）', score: 0.96, source: 'Cam-S2', time: '12:06' },
        { title: '松园·取餐窗口（右侧）', score: 0.94, source: 'Cam-S1', time: '12:05' },
        { title: '松园·座位区（靠墙）', score: 0.92, source: 'Cam-S3', time: '12:04' },
        { title: '松园·入口通道', score: 0.90, source: 'Cam-S0', time: '12:03' },
        { title: '松园·奶茶店区', score: 0.88, source: 'Cam-S4', time: '12:02' },
        { title: '松园·自助结算', score: 0.87, source: 'Cam-S5', time: '12:01' },
        { title: '松园·座位区（左侧）', score: 0.85, source: 'Cam-S6', time: '12:00' },
        { title: '松园·倒餐处', score: 0.83, source: 'Cam-S7', time: '11:59' },
        { title: '松园·就餐区（边缘）', score: 0.81, source: 'Cam-S8', time: '11:58' },
      ],
    },
    // 乒乓球台：3
    3: {
      shown: 3,
      total: 3,
      items: [
        { title: '南操·乒乓球台组 A（树荫）', score: 0.96, source: 'Cam-P1', time: '15:18' },
        { title: '南操·乒乓球台组 B（操场侧）', score: 0.92, source: 'Cam-P2', time: '15:16' },
        { title: '南操·乒乓球台组 C（边缘位）', score: 0.88, source: 'Cam-P3', time: '15:15' },
      ],
    },
    // 图书馆：24（展示Top10）
    4: {
      shown: 10,
      total: 24,
      items: [
        { title: '图书馆·自习区（中区）', score: 0.97, source: 'Cam-L2', time: '14:08' },
        { title: '图书馆·自习区（窗边）', score: 0.95, source: 'Cam-L3', time: '14:07' },
        { title: '图书馆·自习区（东侧）', score: 0.93, source: 'Cam-L4', time: '14:06' },
        { title: '图书馆·自习区（西侧）', score: 0.91, source: 'Cam-L5', time: '14:05' },
        { title: '图书馆·长桌区（靠墙）', score: 0.89, source: 'Cam-L6', time: '14:04' },
        { title: '图书馆·长桌区（中排）', score: 0.87, source: 'Cam-L7', time: '14:03' },
        { title: '图书馆·自习区（边缘）', score: 0.86, source: 'Cam-L8', time: '14:02' },
        { title: '图书馆·走道（主通道）', score: 0.84, source: 'Cam-L1', time: '14:01' },
        { title: '图书馆·自习区（后排）', score: 0.83, source: 'Cam-L9', time: '14:00' },
        { title: '图书馆·入口区域', score: 0.81, source: 'Cam-L0', time: '13:59' },
      ],
    },
  };

// --- 弹窗逻辑 ---

const openConfigDialog = (scenario: Scenario) => {
  // 弹窗内编辑使用拷贝，避免未保存时直接污染列表；保存时再提交
  currentEditingScenario.value = { ...scenario };
  dialogVisible.value = true;
};

// --- 图片上传处理 ---

const handleImageUpload = (file: UploadFile) => {
  if (!file.raw || !currentEditingScenario.value) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    if (currentEditingScenario.value) {
      const imageUrl = e.target?.result as string;
      currentEditingScenario.value.imageUrl = imageUrl;
      
      // 持久化保存图片到 localStorage
      saveScenarioData(currentEditingScenario.value.id, imageUrl);

      // 关键：同步回主场景列表，让对话引用立即生效
      const s = scenarios.value.find((x) => x.id === currentEditingScenario.value?.id);
      if (s) s.imageUrl = imageUrl;
    }
  };
  reader.readAsDataURL(file.raw);
};

const removeImage = () => {
  if (currentEditingScenario.value) {
    currentEditingScenario.value.imageUrl = '';
    saveScenarioData(currentEditingScenario.value.id, '');
    const s = scenarios.value.find((x) => x.id === currentEditingScenario.value?.id);
    if (s) s.imageUrl = '';
  }
};

const saveScenarioConfig = () => {
  if (!currentEditingScenario.value) return;
  const idx = scenarios.value.findIndex((x) => x.id === currentEditingScenario.value?.id);
  if (idx >= 0) {
    scenarios.value[idx] = { ...currentEditingScenario.value };
  }
  // 图片已在上传/删除时持久化，这里兜底再写一次
  saveScenarioData(currentEditingScenario.value.id, currentEditingScenario.value.imageUrl || '');
  dialogVisible.value = false;
};

// --- 搜索/对话逻辑 ---

const handleSearch = async () => {
  if (!inputText.value.trim()) return;

  const query = inputText.value;
  
  // 1. 添加用户消息
  messages.value.push({
    id: messageIdCounter++,
    type: 'user',
    content: query,
    timestamp: getCurrentTime(),
  });

  inputText.value = '';
  scrollToBottom();

  // 2. 添加助手Loading消息
  const assistantMsgId = messageIdCounter++;
  messages.value.push({
    id: assistantMsgId,
    type: 'assistant',
    content: '',
    loading: true,
    timestamp: getCurrentTime(),
  });
  
  scrollToBottom();
  loading.value = true;

  try {
    const startTime = performance.now();
    // 模拟网络延迟
    await new Promise(resolve => setTimeout(resolve, 1000));
    void startTime;
    
    // 3. 获取当前激活的 Mock 场景数据
    const activeScenario = scenarios.value.find(s => s.id === activeScenarioId.value);
    
    // 更新助手消息
    const msg = messages.value.find(m => m.id === assistantMsgId);
    if (msg) {
      msg.loading = false;
      msg.searchTime = msg.searchTime ?? getRandomSearchTime();
      msg.location = '七教'; 
      msg.overlayTime = msg.overlayTime || getRandomOverlayTime();
      
      if (activeScenario) {
        // 使用 Mock 配置的数据
        msg.content = activeScenario.replyText;
        msg.conclusion = activeScenario.conclusion;

        // 召回检索 + 相似度排行（写死）
        const recallCfg = mockRecallConfig[activeScenario.id];
        if (recallCfg) {
          msg.recallShown = recallCfg.shown;
          msg.recallTotal = recallCfg.total;
          msg.recallRank = recallCfg.items.map((it, idx) => ({
            id: activeScenario.id * 1000 + idx,
            ...it,
            thumb: activeScenario.imageUrl || undefined,
          }));
          msg.recallExpanded = false;
        } else {
          msg.recallShown = undefined;
          msg.recallTotal = undefined;
          msg.recallRank = undefined;
          msg.recallExpanded = undefined;
        }
        
        // 构造图片结果
        if (activeScenario.imageUrl) {
          msg.images = [{
            id: activeScenario.id,
            imageId: activeScenario.id,
            score: 0.98,
            image: {
              id: activeScenario.id,
              url: activeScenario.imageUrl,
              title: activeScenario.name,
              description: activeScenario.replyText,
              uploadTime: getCurrentTime(),
              tags: ['Mock', activeScenario.name]
            }
          }];
        } else {
           msg.content += '\n(注：未上传场景图片，仅显示文本)';
        }
      } else {
         msg.content = '未激活任何场景配置。';
      }
    }
    scrollToBottom();
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

</script>

<template>
  <!-- 外层容器：高度固定，禁止滚动 -->
  <Page content-class="flex h-[calc(100vh-100px)] p-0 bg-[#eef0f4] overflow-hidden rounded-xl">
    
    <!-- 左侧：Mock 配置面板 (精简版) -->
    <div class="config-panel">
      <div class="panel-header">
        <div class="flex items-center gap-2">
          <div class="p-2 bg-indigo-50 rounded-lg text-indigo-600">
            <el-icon><Connection /></el-icon>
          </div>
          <span class="font-bold text-gray-700">场景控制台</span>
        </div>
      </div>
      
      <div class="scenarios-list">
        <el-radio-group v-model="activeScenarioId" class="w-full flex flex-col gap-3">
          
          <div 
            v-for="scenario in scenarios" 
            :key="scenario.id"
            class="scenario-item"
            :class="{ active: activeScenarioId === scenario.id }"
            @click="activeScenarioId = scenario.id"
          >
            <!-- 场景头部 -->
            <div class="flex items-center justify-between w-full">
              <el-radio :label="scenario.id" size="large" class="!mr-0" @click.stop>
                <span class="font-bold text-gray-800">{{ scenario.name }}</span>
              </el-radio>
              
              <div class="flex items-center gap-2">
                <!-- 状态指示灯 -->
                <div 
                  class="status-indicator" 
                  :class="activeScenarioId === scenario.id ? 'active' : ''"
                >
                  <span class="ping"></span>
                  <span class="dot"></span>
                </div>
                
                <!-- 编辑按钮 -->
                <el-tooltip content="编辑场景配置" placement="top">
                  <el-button 
                    circle 
                    size="small" 
                    @click.stop="openConfigDialog(scenario)"
                    class="edit-btn"
                  >
                    <el-icon><Edit /></el-icon>
                  </el-button>
                </el-tooltip>
              </div>
            </div>

            <!-- 简略信息展示 -->
            <div class="scenario-meta">
              <div class="meta-tag" :class="scenario.imageUrl ? 'bg-green-50 text-green-600' : 'bg-gray-50 text-gray-400'">
                <el-icon size="12" class="mr-1"><Picture /></el-icon>
                {{ scenario.imageUrl ? '已上传图片' : '无图片' }}
              </div>
            </div>
          </div>

        </el-radio-group>
      </div>
    </div>

    <!-- 右侧：手机模拟器 -->
    <div class="phone-wrapper">
      <div class="mobile-container">
        <!-- 装饰背景光斑 -->
        <div class="glow-bg"></div>

        <!-- 1. App Header -->
        <div class="app-header">
          <div class="header-left">
            <div class="location-badge">
              <el-icon class="mr-1 text-xs"><Location /></el-icon>
              <span>七教</span>
            </div>
          </div>
          <div class="header-title">山城视觉智能体</div>
          <div class="header-right">
            <div class="icon-circle">
              <el-icon><Setting /></el-icon>
            </div>
          </div>
        </div>

        <!-- 2. Chat Area -->
        <div ref="messagesContainer" class="chat-area">
          <div v-for="msg in messages" :key="msg.id" class="message-wrapper" :class="msg.type">
            
            <!-- AI 头像 (仅助手消息显示) -->
            <div v-if="msg.type === 'assistant'" class="avatar-col mr-3">
              <div class="ai-avatar-wrapper">
                <div class="ai-avatar-glow"></div>
                <div class="ai-avatar-img">
                  <img :src="aiAvatar" alt="AI" />
                </div>
              </div>
            </div>

            <!-- 消息内容 -->
            <div class="message-content-col" :class="msg.type === 'user' ? 'items-end' : 'items-start'">
              <!-- 用户消息 -->
              <div v-if="msg.type === 'user'" class="user-bubble">{{ msg.content }}</div>
              
              <!-- 助手消息 -->
              <div v-else class="assistant-card">
                <div v-if="msg.loading" class="loading-wrapper">
                  <div class="ai-avatar-pulse"><el-icon><MagicStick /></el-icon></div>
                  <span class="loading-text">正在分析视觉信号...</span>
                </div>
                <div v-else class="result-content">
                  <div v-if="msg.searchTime !== undefined" class="status-row">
                    <div class="status-tag"><el-icon class="mr-1"><MagicStick /></el-icon>智能分析完成 · {{ msg.searchTime }}s</div>
                    <div v-if="msg.recallTotal !== undefined" class="status-tag status-tag-secondary">召回 · {{ msg.recallShown }}/{{ msg.recallTotal }}</div>
                  </div>
                  <div class="text-content">{{ msg.content }}</div>
                  <div v-if="msg.images && msg.images.length > 0 && msg.images[0]" class="visual-card">
                    <el-image :src="msg.images[0].image.url" fit="cover" class="w-full h-full" :preview-src-list="msg.images.map(i => i.image.url)" loading="lazy">
                      <template #error><div class="image-placeholder"><el-icon size="24"><Picture /></el-icon></div></template>
                    </el-image>
                    <div class="visual-overlay">
                      <div class="overlay-badge"><span class="pulse-dot"></span> LIVE FEED</div>
                      <div class="overlay-info">{{ msg.overlayTime }}</div>
                    </div>
                  </div>

                  <!-- 相似度排行（TopN） -->
                  <div v-if="msg.recallRank && msg.recallRank.length" class="retrieval-box">
                    <div class="retrieval-head">
                      <div class="retrieval-title-row">
                        <div class="retrieval-title">相似度排行</div>
                        <button class="retrieval-toggle" type="button" @click="msg.recallExpanded = !msg.recallExpanded">
                          <span class="retrieval-toggle-text">{{ msg.recallExpanded ? '收起' : '展开' }}</span>
                          <span class="retrieval-toggle-chevron" :class="{ open: !!msg.recallExpanded }">▾</span>
                        </button>
                      </div>
                      <div class="retrieval-meta">Top {{ msg.recallShown }}/{{ msg.recallTotal }}</div>
                    </div>
                    <div v-show="msg.recallExpanded" class="retrieval-list">
                      <div v-for="it in msg.recallRank" :key="it.id" class="retrieval-item">
                        <div class="retrieval-left">
                          <div class="retrieval-thumb" v-if="it.thumb">
                            <img :src="it.thumb" alt="thumb" />
                          </div>
                          <div class="retrieval-thumb placeholder" v-else>
                            <el-icon><Picture /></el-icon>
                          </div>
                          <div class="retrieval-info">
                            <div class="retrieval-name">{{ it.title }}</div>
                            <div class="retrieval-sub">{{ it.source }} · {{ it.time }}</div>
                          </div>
                        </div>
                        <div class="retrieval-right">
                          <div class="retrieval-score">{{ Math.round(it.score * 100) }}%</div>
                          <div class="retrieval-bar">
                            <div class="retrieval-bar-in" :style="{ width: `${Math.round(it.score * 100)}%` }"></div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div v-if="msg.conclusion" class="conclusion-box">
                    <div class="conclusion-header"><span class="icon"></span>建议</div>
                    <div class="conclusion-body">{{ msg.conclusion }}</div>
                  </div>
                  <div class="card-footer">
                    <div class="actions">
                      <button class="icon-btn hover:text-yellow-500"><el-icon><Star /></el-icon></button>
                      <button class="icon-btn hover:text-red-500"><el-icon><Mute /></el-icon></button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 用户头像 (仅用户消息显示) -->
            <div v-if="msg.type === 'user'" class="avatar-col ml-3">
              <div class="user-avatar-wrapper">
                <el-avatar 
                  :src="userAvatar" 
                  :icon="User"
                  class="user-avatar-main"
                  shape="circle"
                  :size="44"
                />
              </div>
            </div>

          </div>
        </div>

        <!-- 3. Floating Input Bar -->
        <div class="input-container">
          <div class="input-glass">
            <button class="tool-btn"><el-icon><Microphone /></el-icon></button>
            <input v-model="inputText" placeholder="输入指令..." @keydown.enter="handleSearch"/>
            <button class="send-btn" :class="{ active: inputText.trim() }" @click="handleSearch"><el-icon><Promotion /></el-icon></button>
          </div>
        </div>
      </div>
    </div>

    <!-- 配置弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      title="编辑场景配置"
      width="500px"
      append-to-body
      destroy-on-close
      class="config-dialog"
    >
      <div v-if="currentEditingScenario" class="dialog-content">
        <div class="form-item">
          <div class="label">场景名称</div>
          <div class="font-bold text-lg mb-2">{{ currentEditingScenario.name }}</div>
        </div>

        <div class="form-item">
          <div class="label">场景图片</div>
          <div class="upload-area">
            <div v-if="currentEditingScenario.imageUrl" class="preview-box large">
              <img :src="currentEditingScenario.imageUrl" class="preview-img" />
              <div class="remove-btn" @click="removeImage">
                <el-icon><Delete /></el-icon>
              </div>
            </div>
            <el-upload
              v-else
              class="w-full"
              action="#"
              :auto-upload="false"
              :show-file-list="false"
              :on-change="handleImageUpload"
              drag
            >
              <div class="upload-placeholder large">
                <el-icon class="text-3xl mb-2 text-indigo-400"><Upload /></el-icon>
                <span class="text-sm text-gray-500">点击或拖拽上传图片</span>
              </div>
            </el-upload>
          </div>
        </div>

        <div class="form-item">
          <div class="label">AI 回复文本</div>
          <el-input
            v-model="currentEditingScenario.replyText"
            type="textarea"
            :rows="4"
            placeholder="输入AI回复内容"
            resize="none"
          />
        </div>

        <div class="form-item">
          <div class="label">结论/建议</div>
          <el-input
            v-model="currentEditingScenario.conclusion"
            type="textarea"
            :rows="2"
            placeholder="输入结论建议"
            resize="none"
          />
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">关闭</el-button>
          <el-button type="primary" @click="saveScenarioConfig">保存配置</el-button>
        </span>
      </template>
    </el-dialog>
  </Page>
</template>

<style scoped>
/* --- 布局容器 --- */
/* Page content-class 已经设置了 flex h-full overflow-hidden */

/* --- 左侧 Mock 控制台 (精简版) --- */
.config-panel {
  width: 280px; /* 变窄 */
  height: 100%;
  background: #fff;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  box-shadow: 4px 0 20px rgba(0,0,0,0.02);
  z-index: 10;
}

.panel-header {
  height: 60px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  border-bottom: 1px solid #f3f4f6;
  background: #fff;
}

.scenarios-list {
  flex: 1;
  overflow-y: auto; /* 内部滚动 */
  padding: 16px;
  background: #f9fafb;
}

.scenario-item {
  background: #fff;
  border-radius: 12px;
  padding: 12px;
  border: 2px solid transparent;
  transition: all 0.2s ease;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.scenario-item:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 6px rgba(0,0,0,0.05);
}

.scenario-item.active {
  border-color: #6366f1;
  background: #f5f7ff;
}

.scenario-meta {
  margin-top: 8px;
  margin-left: 28px; /* 对齐文本 */
}

.meta-tag {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

/* 状态指示灯 */
.status-indicator {
  position: relative;
  width: 10px;
  height: 10px;
}
.status-indicator .dot {
  display: block;
  width: 10px;
  height: 10px;
  background: #d1d5db;
  border-radius: 50%;
  transition: background 0.3s;
}
.status-indicator.active .dot {
  background: #10b981;
}
.status-indicator.active .ping {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: #10b981;
  opacity: 0.75;
  animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
}
@keyframes ping {
  75%, 100% { transform: scale(2); opacity: 0; }
}

.edit-btn:hover {
  color: #6366f1;
  border-color: #6366f1;
  background: #eef2ff;
}

/* --- 弹窗样式 --- */
.dialog-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-item .label {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 8px;
}

.upload-area {
  width: 100%;
}

.upload-placeholder.large {
  height: 140px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f9fafb;
}

.preview-box.large {
  height: 180px;
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
}

.preview-img {
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
  background: rgba(0,0,0,0.6);
  color: white;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
}
.remove-btn:hover { background: rgba(0,0,0,0.8); }

/* --- 右侧手机模拟器 --- */
.phone-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eef0f4;
  position: relative;
  overflow: hidden; /* 防止溢出 */
}

/* 保持之前的手机样式 */
.mobile-container {
  width: 100%;
  max-width: 460px;
  height: 90vh; /* 相对高度 */
  max-height: 880px;
  background: #f8f9fc;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px -10px rgba(0,0,0,0.15);
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  z-index: 5;
}

@media (min-width: 768px) {
  .mobile-container {
    border-radius: 32px;
    border: 6px solid #fff;
  }
}

.glow-bg {
  position: absolute;
  top: -20%;
  left: -20%;
  width: 140%;
  height: 60%;
  background: radial-gradient(circle at 50% 50%, rgba(139, 92, 246, 0.08), transparent 70%);
  z-index: 0;
  pointer-events: none;
}

/* Header */
.app-header {
  height: 64px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  border-bottom: 1px solid rgba(255, 255, 255, 0.4);
}

.location-badge {
  display: flex;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
  color: #4b5563;
  background: rgba(255,255,255,0.5);
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid rgba(0,0,0,0.03);
}

.header-title { font-size: 18px; font-weight: 700; color: #111827; letter-spacing: -0.5px; }

.icon-circle {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.03); color: #374151; font-size: 18px;
  transition: all 0.2s; cursor: pointer;
}
.icon-circle:hover { background: rgba(0,0,0,0.06); }

/* Chat Area */
.chat-area {
  flex: 1;
  padding: 84px 16px 100px 16px;
  overflow-y: auto; /* 内部滚动 */
  display: flex;
  flex-direction: column;
  gap: 24px;
  z-index: 1;
  scroll-behavior: smooth;
}

.chat-area::-webkit-scrollbar { display: none; }

.message-wrapper { display: flex; width: 100%; animation: slideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
@keyframes slideIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }

.message-wrapper.user { justify-content: flex-end; }
.message-wrapper.assistant { justify-content: flex-start; }

/* 消息内容容器 */
.message-content-col {
  max-width: 80%;
  display: flex;
  flex-direction: column;
}

.user-bubble {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: #fff;
  padding: 14px 20px;
  border-radius: 24px 24px 4px 24px;
  font-size: 15px;
  line-height: 1.5;
  box-shadow: 0 8px 20px -6px rgba(79, 70, 229, 0.4);
}

.assistant-card {
  width: 100%; background: #fff;
  border-radius: 24px; border-top-left-radius: 4px; padding: 6px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.03), 0 1px 3px rgba(0,0,0,0.02);
}

/* 头像样式 */
.avatar-col {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
}

/* 用户头像美化 */
.user-avatar-wrapper {
  position: relative;
}

.user-avatar-main {
  border: 2px solid #fff;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.25);
}

.user-avatar-main:deep(.el-avatar) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

/* AI 头像美化 - 添加光晕效果 */
.ai-avatar-wrapper {
  position: relative;
  width: 44px;
  height: 44px;
}

.ai-avatar-glow {
  position: absolute;
  top: -3px;
  left: -3px;
  right: -3px;
  bottom: -3px;
  background: linear-gradient(135deg, #667eea, #764ba2, #f093fb, #4facfe);
  background-size: 400% 400%;
  border-radius: 50%;
  animation: gradientShift 3s ease infinite;
  filter: blur(6px);
  opacity: 0.5;
  z-index: 0;
}

@keyframes gradientShift {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}

.ai-avatar-img {
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
  border: 2px solid #fff;
  box-shadow: 0 4px 16px rgba(139, 92, 246, 0.3);
  overflow: hidden;
  padding: 2px;
  z-index: 1;
}

.ai-avatar-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
}

.loading-wrapper { display: flex; align-items: center; gap: 12px; padding: 16px; color: #6b7280; }
.ai-avatar-pulse {
  width: 32px; height: 32px; border-radius: 12px; background: #f3f4f6;
  display: flex; align-items: center; justify-content: center; color: #8b5cf6;
  animation: pulse 2s infinite;
}
@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(139, 92, 246, 0.2); } 70% { box-shadow: 0 0 0 10px rgba(139, 92, 246, 0); } 100% { box-shadow: 0 0 0 0 rgba(139, 92, 246, 0); } }

.loading-text {
  font-size: 14px; font-weight: 500;
  background: linear-gradient(90deg, #6b7280 0%, #9ca3af 50%, #6b7280 100%);
  background-size: 200% 100%; -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: shimmer 2s infinite linear;
}
@keyframes shimmer { 0% { background-position: 100% 0; } 100% { background-position: -100% 0; } }

.result-content { padding: 16px; }
.status-row { margin-bottom: 12px; }
.status-tag { display: inline-flex; align-items: center; font-size: 12px; color: #8b5cf6; background: rgba(139, 92, 246, 0.08); padding: 4px 10px; border-radius: 12px; font-weight: 600; }
.status-tag-secondary {
  margin-left: 8px;
  color: #0ea5e9;
  background: rgba(14, 165, 233, 0.10);
}

.text-content { font-size: 15px; color: #1f2937; line-height: 1.6; margin-bottom: 16px; }

.visual-card {
  position: relative; width: 100%; height: 200px;
  border-radius: 18px; overflow: hidden; margin-bottom: 20px;
  box-shadow: 0 10px 30px -5px rgba(0,0,0,0.1); transform: translateZ(0);
}

.visual-overlay {
  position: absolute; top: 0; left: 0; width: 100%; height: 100%;
  background: linear-gradient(to bottom, rgba(0,0,0,0) 60%, rgba(0,0,0,0.5) 100%);
  pointer-events: none;
}
.overlay-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(239, 68, 68, 0.9); color: white;
  font-size: 10px; font-weight: 800; padding: 4px 8px; border-radius: 6px;
  display: flex; align-items: center; gap: 6px; box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
}
.pulse-dot { width: 6px; height: 6px; background: white; border-radius: 50%; animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0.5; } }
.overlay-info {
  position: absolute;
  left: 12px;
  bottom: 10px;
  font-size: 10px;
  color: rgba(255,255,255,0.85);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  letter-spacing: 0.3px;
}

/* 相似度排行 */
.retrieval-box {
  margin-top: -6px;
  margin-bottom: 14px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(0,0,0,0.04);
  border-radius: 16px;
  padding: 12px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.04);
}

.retrieval-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 8px;
}

.retrieval-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.retrieval-title {
  font-size: 12px;
  font-weight: 800;
  color: #111827;
  letter-spacing: 0.2px;
}

.retrieval-toggle {
  pointer-events: auto;
  border: 1px solid rgba(0,0,0,0.06);
  background: rgba(255,255,255,0.7);
  border-radius: 999px;
  padding: 4px 8px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #4b5563;
  font-size: 11px;
  line-height: 1;
}
.retrieval-toggle:hover {
  border-color: rgba(99, 102, 241, 0.25);
  box-shadow: 0 6px 14px rgba(79, 70, 229, 0.08);
}
.retrieval-toggle-text { font-weight: 700; }
.retrieval-toggle-chevron {
  display: inline-block;
  transform: rotate(-90deg);
  transition: transform 0.18s ease;
  opacity: 0.8;
}
.retrieval-toggle-chevron.open { transform: rotate(0deg); }

.retrieval-meta {
  font-size: 11px;
  color: #6b7280;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.retrieval-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.retrieval-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.retrieval-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.retrieval-thumb {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  overflow: hidden;
  flex-shrink: 0;
  border: 1px solid rgba(0,0,0,0.06);
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
}

.retrieval-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.retrieval-info { min-width: 0; }
.retrieval-name {
  font-size: 12px;
  font-weight: 700;
  color: #111827;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.retrieval-sub {
  margin-top: 2px;
  font-size: 10px;
  color: #6b7280;
}

.retrieval-right {
  width: 110px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.retrieval-score {
  font-size: 11px;
  font-weight: 800;
  color: #4f46e5;
}

.retrieval-bar {
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.10);
  overflow: hidden;
}
.retrieval-bar-in {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 60%, #22c55e 120%);
}

.conclusion-box {
  background: linear-gradient(135deg, #fdfbf7 0%, #fff7ed 100%);
  border: 1px solid rgba(245, 158, 11, 0.15); border-radius: 16px; padding: 14px; margin-bottom: 12px;
}
.conclusion-header { font-size: 12px; font-weight: 700; color: #b45309; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
.conclusion-body { font-size: 14px; color: #4b5563; line-height: 1.5; font-weight: 500; }

.card-footer { display: flex; justify-content: flex-end; align-items: center; padding-top: 8px; border-top: 1px dashed rgba(0,0,0,0.05); }
.actions { display: flex; gap: 8px; }
.icon-btn { background: transparent; border: none; color: #9ca3af; cursor: pointer; padding: 4px; font-size: 16px; transition: color 0.2s; }

/* Floating Input */
.input-container {
  position: absolute; bottom: 0; left: 0; right: 0;
  padding: 16px 20px 24px 20px; z-index: 200;
  background: linear-gradient(to top, rgba(248,249,252,1) 0%, rgba(248,249,252,0) 100%);
}
.input-glass {
  background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.8); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
  border-radius: 40px; height: 60px; display: flex; align-items: center; padding: 0 8px 0 16px; gap: 12px;
  transition: transform 0.2s, box-shadow 0.2s;
}
.input-glass:focus-within {
  box-shadow: 0 12px 40px rgba(99, 102, 241, 0.15); transform: translateY(-2px); border-color: rgba(99, 102, 241, 0.3);
}
.tool-btn {
  width: 36px; height: 36px; border-radius: 50%; border: none; background: #f3f4f6; color: #4b5563;
  display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s;
}
.tool-btn:hover { background: #e5e7eb; color: #111827; }
input { flex: 1; border: none; background: transparent; outline: none; font-size: 15px; color: #1f2937; height: 100%; }
input::placeholder { color: #9ca3af; }
.send-btn {
  width: 44px; height: 44px; border-radius: 50%; border: none; background: #e5e7eb; color: #9ca3af;
  display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); transform: scale(0.9);
}
.send-btn.active { background: #4f46e5; color: white; transform: scale(1); box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3); }
.image-placeholder { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; background: #f3f4f6; color: #d1d5db; }
</style>
