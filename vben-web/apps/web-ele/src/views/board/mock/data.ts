/**
 * 视觉RAG Mock数据 - 支持持久化存储
 */

export interface ImageItem {
  id: number;
  url: string;
  title: string;
  description?: string;
  tags?: string[];
  uploadTime: string;
  similarity?: number;
  isUserUploaded?: boolean; // 标记是否为用户上传
}

export interface RAGResult {
  id: number;
  imageId: number;
  image: ImageItem;
  score: number;
  reasoning?: string;
  matchedFeatures?: string[];
}

// 本地存储 Key
const STORAGE_KEY = 'board_user_images';
const STORAGE_SCENARIOS_KEY = 'board_scenarios_data';

// 默认Mock图片数据
const defaultMockImages: ImageItem[] = [
  {
    id: 1,
    url: 'https://picsum.photos/400/300?random=1',
    title: '医学影像 - 胸部X光',
    description: '正常胸部X光片，心肺未见异常',
    tags: ['医学', 'X光', '胸部'],
    uploadTime: '2024-01-15 10:30:00',
  },
  {
    id: 2,
    url: 'https://picsum.photos/400/300?random=2',
    title: '病理切片 - 肝脏组织',
    description: '肝脏组织病理切片，显示正常肝细胞结构',
    tags: ['病理', '肝脏', '组织'],
    uploadTime: '2024-01-15 11:20:00',
  },
  {
    id: 3,
    url: 'https://picsum.photos/400/300?random=3',
    title: 'CT扫描 - 头部横断面',
    description: '头部CT扫描，未见明显异常密度影',
    tags: ['CT', '头部', '扫描'],
    uploadTime: '2024-01-15 14:45:00',
  },
  {
    id: 4,
    url: 'https://picsum.photos/400/300?random=4',
    title: 'MRI影像 - 膝关节',
    description: '膝关节MRI影像，软骨及韧带结构清晰',
    tags: ['MRI', '膝关节', '骨科'],
    uploadTime: '2024-01-16 09:15:00',
  },
  {
    id: 5,
    url: 'https://picsum.photos/400/300?random=5',
    title: '超声影像 - 心脏',
    description: '心脏超声检查，心室壁运动正常',
    tags: ['超声', '心脏', '超声心动'],
    uploadTime: '2024-01-16 10:30:00',
  },
  {
    id: 6,
    url: 'https://picsum.photos/400/300?random=6',
    title: '内窥镜 - 胃部',
    description: '胃镜检查图像，胃黏膜光滑',
    tags: ['内窥镜', '胃部', '消化'],
    uploadTime: '2024-01-16 13:20:00',
  },
  {
    id: 7,
    url: 'https://picsum.photos/400/300?random=7',
    title: '细胞学 - 血液涂片',
    description: '血液细胞涂片，红细胞白细胞形态正常',
    tags: ['细胞学', '血液', '检验'],
    uploadTime: '2024-01-17 08:45:00',
  },
  {
    id: 8,
    url: 'https://picsum.photos/400/300?random=8',
    title: '皮肤镜 - 色素痣',
    description: '皮肤镜下色素痣图像，边界清晰',
    tags: ['皮肤镜', '皮肤科', '色素'],
    uploadTime: '2024-01-17 11:10:00',
  },
];

function safeGetItem(key: string) {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSetItem(key: string, value: string) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // ignore
  }
}

function safeRemoveItem(key: string) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

// 获取持久化的图片数据（包括默认和用户上传的）
export function getMockImages(): ImageItem[] {
  try {
    // 尝试从 localStorage 获取用户上传的图片
    const stored = safeGetItem(STORAGE_KEY);
    const userImages: ImageItem[] = stored ? JSON.parse(stored) : [];
    
    // 合并默认图片和用户图片
    const allImages = [...defaultMockImages, ...userImages];
    return allImages;
  } catch (error) {
    console.error('Failed to load images from localStorage:', error);
    return defaultMockImages;
  }
}

// 保存用户上传的图片
export function saveUserImage(image: ImageItem): void {
  try {
    const stored = safeGetItem(STORAGE_KEY);
    const userImages: ImageItem[] = stored ? JSON.parse(stored) : [];
    
    // 确保 ID 不重复
    const maxId = Math.max(...defaultMockImages.map(i => i.id), ...userImages.map(i => i.id));
    image.id = maxId + 1;
    image.isUserUploaded = true;
    
    userImages.push(image);
    safeSetItem(STORAGE_KEY, JSON.stringify(userImages));
  } catch (error) {
    console.error('Failed to save image to localStorage:', error);
  }
}

// 保存场景配置（包括上传的图片）
export function saveScenarioData(scenarioId: number, imageUrl: string): void {
  try {
    const stored = safeGetItem(STORAGE_SCENARIOS_KEY);
    const scenariosData: Record<number, string> = stored ? JSON.parse(stored) : {};
    
    scenariosData[scenarioId] = imageUrl;
    safeSetItem(STORAGE_SCENARIOS_KEY, JSON.stringify(scenariosData));
  } catch (error) {
    console.error('Failed to save scenario data to localStorage:', error);
  }
}

// 获取场景配置
export function getScenarioImageUrl(scenarioId: number): string | null {
  try {
    const stored = safeGetItem(STORAGE_SCENARIOS_KEY);
    const scenariosData: Record<number, string> = stored ? JSON.parse(stored) : {};
    return scenariosData[scenarioId] || null;
  } catch (error) {
    console.error('Failed to get scenario data from localStorage:', error);
    return null;
  }
}

// 清除所有用户数据
export function clearAllUserData(): void {
  try {
    safeRemoveItem(STORAGE_KEY);
    safeRemoveItem(STORAGE_SCENARIOS_KEY);
  } catch (error) {
    console.error('Failed to clear localStorage:', error);
  }
}

// 导出默认 mockImages （保持向后兼容）
export const mockImages = getMockImages();

// Mock检索结果
export const mockSearchResults = (query: string, topK: number = 5): RAGResult[] => {
  // 获取最新的图片数据（包括用户上传的）
  const allImages = getMockImages();
  
  // 简单的mock逻辑：根据查询关键词匹配
  const results: RAGResult[] = allImages
    .map((image) => {
      // 计算相似度（mock）
      let score = 0.5 + Math.random() * 0.5;
      
      // 如果标题或标签包含查询词，提高分数
      const queryLower = query.toLowerCase();
      if (image.title.toLowerCase().includes(queryLower)) {
        score = Math.min(0.95, score + 0.3);
      }
      
      const matchedTags = image.tags?.filter(tag => 
        tag.toLowerCase().includes(queryLower) || queryLower.includes(tag.toLowerCase())
      ) || [];
      
      if (matchedTags.length > 0) {
        score = Math.min(0.98, score + 0.2 * matchedTags.length);
      }
      
      return {
        id: image.id * 100,
        imageId: image.id,
        image,
        score,
        reasoning: `与查询"${query}"的匹配分析：${
          matchedTags.length > 0 
            ? `匹配标签: ${matchedTags.join(', ')}`
            : '基于图像特征和语义相似度计算'
        }`,
        matchedFeatures: matchedTags,
      };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);
  
  return results;
};

// Mock统计数据
export interface BoardStats {
  totalImages: number;
  totalQueries: number;
  avgResponseTime: number;
  accuracy: number;
}

export const mockStats: BoardStats = {
  totalImages: 1250,
  totalQueries: 3680,
  avgResponseTime: 234, // ms
  accuracy: 89, // 百分比值
};

