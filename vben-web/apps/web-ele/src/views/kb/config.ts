import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

/**
 * KB (知识库) 模块页面配置
 */

export const KB_ROUTES: RouteRecordRaw[] = [
  {
    path: 'chat',
    name: 'KBChat',
    component: () => import('./chat/index.vue'),
    meta: {
      hideInMenu: true,
      title: $t('page.kb.chat'),
      icon: 'lucide:message-square',
      keepAlive: true,
    },
  },
  {
    path: 'management',
    name: 'KBManagement',
    component: () => import('./management/index.vue'),
    meta: {
      hideInMenu: true,
      title: $t('page.kb.management'),
      icon: 'lucide:database',
      keepAlive: true,
    },
  },
  {
    path: 'document',
    name: 'KBDocument',
    component: () => import('./document/index.vue'),
    meta: {
      hideInMenu: true,
      title: '文档管理',
      icon: 'lucide:file-text',
      keepAlive: true,
    },
  },
  {
    path: 'character',
    name: 'CharacterManagement',
    component: () => import('./character/index.vue'),
    meta: {
      hideInMenu: true,
      title: $t('page.kb.character'),
      icon: 'lucide:users',
      keepAlive: true,
    },
  },
  {
    path: 'search',
    name: 'KBSearch',
    component: () => import('./search/index.vue'),
    meta: {
      hideInMenu: true,
      title: '知识库搜索',
      icon: 'lucide:search',
      keepAlive: true,
    },
  },
];

/**
 * 常用常量
 */
export const KB_CONSTANTS = {
  // 上下文长度范围
  MAX_CONTEXT_LENGTH_MIN: 1,
  MAX_CONTEXT_LENGTH_MAX: 100,
  MAX_CONTEXT_LENGTH_DEFAULT: 10,

  // 分页
  PAGE_SIZE_DEFAULT: 50,

  // 文件上传
  MAX_FILE_SIZE: 100 * 1024 * 1024, // 100MB
  ALLOWED_EXTENSIONS: ['.txt', '.pdf', '.docx', '.md', '.json'],

  // RAG 相关
  RAG_TOP_K_DEFAULT: 3,
  RAG_CONFIDENCE_THRESHOLD_DEFAULT: 0.5,
};
