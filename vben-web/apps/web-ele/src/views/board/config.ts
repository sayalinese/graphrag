import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

/**
 * Board (视觉RAG看板) 模块页面配置
 */

export const BOARD_ROUTES: RouteRecordRaw[] = [
  {
    path: 'gate',
    name: 'BoardGate',
    component: () => import('./gate/index.vue'),
    meta: {
      title: $t('page.board.gate'),
      icon: 'lucide:home',
      keepAlive: true,
    },
  },
  {
    path: 'app',
    name: 'BoardApp',
    component: () => import('./app/index.vue'),
    meta: {
      title: $t('page.board.app'),
      icon: 'lucide:layout-dashboard',
      keepAlive: true,
    },
  },
  {
    path: 'view_search',
    name: 'BoardViewSearch',
    component: () => import('./view_search/index.vue'),
    meta: {
      title: $t('page.board.viewSearch'),
      icon: 'lucide:search',
      keepAlive: true,
    },
  },
];

/**
 * 视觉RAG相关常量
 */
export const BOARD_CONSTANTS = {
  // 图片上传
  MAX_IMAGE_SIZE: 10 * 1024 * 1024, // 10MB
  ALLOWED_IMAGE_FORMATS: ['.jpg', '.jpeg', '.png', '.webp'],
  
  // RAG检索
  DEFAULT_TOP_K: 5,
  MAX_TOP_K: 20,
  
  // 显示
  GRID_COLUMNS: {
    xs: 1,
    sm: 2,
    md: 3,
    lg: 4,
    xl: 5,
  },
};

