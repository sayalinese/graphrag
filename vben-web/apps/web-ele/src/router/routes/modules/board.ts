import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';
import { $t } from '#/locales';
import { BOARD_ROUTES } from '#/views/board/config';

const boardRoutes: RouteRecordRaw[] = [
  {
    name: 'BoardRoot',
    path: '/board',
    component: BasicLayout,
    redirect: '/board/gate',
    meta: {
      title: $t('page.board.title'),
      icon: 'lucide:image',
      order: 320,
      hideInMenu: true,
    },
    children: BOARD_ROUTES,
  },
];

export default boardRoutes;
