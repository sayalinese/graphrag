import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';
import { $t } from '#/locales';
import { KB_ROUTES } from '#/views/kb/config';

const kbRoutes: RouteRecordRaw[] = [
  {
    name: 'KBRoot',
    path: '/kb',
    component: BasicLayout,
    redirect: '/kb/chat',
    meta: {
      title: $t('page.kb.title'),
      icon: 'lucide:book-open',
      order: 310,
      hideInMenu: true,
    },
    children: KB_ROUTES,
  },
];

export default kbRoutes;
