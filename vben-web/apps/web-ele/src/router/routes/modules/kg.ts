import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

const routes: RouteRecordRaw[] = [
  {
    name: 'KgRoot',
    path: '/kg',
    redirect: '/kg/preview',
    meta: {
      icon: 'lucide:network',
      order: 300,
      title: $t('page.kg.title'),
    },
    children: [
      {
        name: 'KgDashboard',
        path: 'dashboard',
        component: () => import('#/views/kg/kg_dashboard/index.vue'),
        meta: {
          title: $t('page.kg.dashboard'),
          icon: 'mdi:view-dashboard-outline',
          keepAlive: true,
        },
      },
      {
        name: 'KgPreview',
        path: 'preview',
        component: () => import('#/views/kg/kg_preview/index.vue'),
        meta: {
          title: $t('page.kg.preview'),
          icon: 'mdi:eye-outline',
          keepAlive: true,
        },
      },
      {
        name: 'KgExplain',
        path: 'explain',
        component: () => import('#/views/kg/kg_explain/index.vue'),
        meta: {
          title: '医疗诊断',
          icon: 'mdi:graph-outline',
          keepAlive: true,
        },
      },
      {
        name: 'KgConstruct',
        path: 'construct',
        component: () => import('#/views/kg/kg_construct/index.vue'),
        meta: {
          title: $t('page.kg.construct'),
          icon: 'mdi:database-plus-outline',
          keepAlive: true,
        },
      },
      {
        name: 'KgManagement',
        path: 'management',
        component: () => import('#/views/kg/kg_management/index.vue'),
        meta: {
          title: $t('page.kg.management'),
          icon: 'mdi:cog-outline',
          keepAlive: true,
        },
      },
      {
        name: 'KgCharacter',
        path: 'character',
        component: () => import('#/views/kb/character/index.vue'),
        meta: {
          title: $t('page.kg.character'),
          icon: 'lucide:users',
          keepAlive: true,
        },
      },
    ],
  },
];

export default routes;
