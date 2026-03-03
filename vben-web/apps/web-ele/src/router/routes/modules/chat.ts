import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

const routes: RouteRecordRaw[] = [
  {
    name: 'ChatRoot',
    path: '/chat',
    redirect: '/chat/ai',
    meta: {
      icon: 'lucide:message-square',
      order: 200,
      hideInMenu: true,
      title: $t('page.chat.title'), // 父级面包屑主标题
    },
    children: [
      {
        name: 'ChatAI',
        path: 'ai',
        component: () => import('#/views/chat/chat_ai/index.vue'),
        meta: {
          title: $t('page.chat.title'),
          icon: 'lucide:bot-message-square',
          keepAlive: true,
        },
      },
      {
        name: 'ChatManagement',
        path: 'management',
        component: () => import('#/views/chat/chat_management/index.vue'),
        meta: {
          title: $t('page.chat.management'),
          icon: 'lucide:settings-2',
          keepAlive: true,
        },
      },
    ],
  },
];

export default routes;
