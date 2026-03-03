import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

// 系统管理路由：父级 /system，包含角色与菜单管理
const routes: RouteRecordRaw[] = [
  {
    name: 'SystemRoot',
    path: '/system',
    redirect: '/system/role',
    meta: {
      icon: 'carbon:cloud-service-management',
      order: 250,
      title: $t('page.system.title'),
    },
    children: [
      {
        name: 'SystemRole',
        path: 'role',
        component: () => import('#/views/system/role/index.vue'),
        meta: {
          title: $t('page.system.role.list'),
          icon: 'carbon:user-role',
          keepAlive: true,
        },
      },
      {
        name: 'SystemMenu',
        path: 'menu',
        component: () => import('#/views/system/menu/index.vue'),
        meta: {
          title: $t('page.system.menu.name'),
          icon: 'carbon:menu',
          keepAlive: true,
        },
      },
      {
        name: 'SystemUser',
        path: 'user',
        component: () => import('#/views/system/user/index.vue'),
        meta: {
          title: $t('page.system.user.list'),
          icon: 'carbon:user-avatar',
          keepAlive: true,
        },
      },
    ],
  },
];

export default routes;
