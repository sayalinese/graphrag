import type { RouteRecordRaw } from 'vue-router';

import { LOGIN_PATH } from '@vben/constants';
import { preferences } from '@vben/preferences';

import { $t } from '#/locales';

const BasicLayout = () => import('#/layouts/basic.vue');
const AuthPageLayout = () => import('#/layouts/auth.vue');
/** 全局404页面 */
const fallbackNotFoundRoute: RouteRecordRaw = {
  component: () => import('#/views/_core/fallback/not-found.vue'),
  meta: {
    hideInBreadcrumb: true,
    hideInMenu: true,
    hideInTab: true,
    title: '404',
  },
  name: 'FallbackNotFound',
  path: '/:path(.*)*',
};

/** 基本路由，这些路由是必须存在的 */
const coreRoutes: RouteRecordRaw[] = [
  /**
   * C 端皮损识别（图睿病理）
   * 不套任何 Layout，全屏自定义 UI，面向老人和家属用户
   * 使用假登录方案，无需身份认证
   */
  {
    meta: {
      hideInBreadcrumb: true,
      hideInMenu: true,
      hideInTab: true,
      title: '图睿病理',
    },
    name: 'Skin',
    path: '/skin',
    redirect: '/skin/upload',
    children: [
      {
        name: 'SkinUpload',
        path: 'upload',
        component: () => import('#/views/skin/upload.vue'),
        meta: {
          title: '拍照识别',
          hideInBreadcrumb: true,
          hideInMenu: true,
          hideInTab: true,
        },
      },
      {
        name: 'SkinReasoning',
        path: 'reasoning/:sessionId',
        component: () => import('#/views/skin/reasoning.vue'),
        meta: {
          title: 'AI 分析中',
          hideInBreadcrumb: true,
          hideInMenu: true,
          hideInTab: true,
        },
      },
      {
        name: 'SkinResult',
        path: 'result/:sessionId',
        component: () => import('#/views/skin/result.vue'),
        meta: {
          title: '检查报告',
          hideInBreadcrumb: true,
          hideInMenu: true,
          hideInTab: true,
        },
      },
      {
        name: 'SkinReport',
        path: 'report/:sessionId',
        component: () => import('#/views/skin/report.vue'),
        meta: {
          title: '完整报告',
          hideInBreadcrumb: true,
          hideInMenu: true,
          hideInTab: true,
        },
      },
    ],
  },
  /**
   * 根路由
   * 使用基础布局，作为所有页面的父级容器，子级就不必配置BasicLayout。
   * 此路由必须存在，且不应修改
   */
  {
    component: BasicLayout,
    meta: {
      hideInBreadcrumb: true,
      title: 'Root',
    },
    name: 'Root',
    path: '/',
    redirect: preferences.app.defaultHomePath,
    children: [],
  },
  {
    component: AuthPageLayout,
    meta: {
      hideInTab: true,
      title: 'Authentication',
    },
    name: 'Authentication',
    path: '/auth',
    redirect: LOGIN_PATH,
    children: [
      {
        name: 'Login',
        path: 'login',
        component: () => import('#/views/_core/authentication/login.vue'),
        meta: {
          title: $t('page.auth.login'),
        },
      },
      {
        name: 'CodeLogin',
        path: 'code-login',
        component: () => import('#/views/_core/authentication/code-login.vue'),
        meta: {
          title: $t('page.auth.codeLogin'),
        },
      },
      {
        name: 'QrCodeLogin',
        path: 'qrcode-login',
        component: () =>
          import('#/views/_core/authentication/qrcode-login.vue'),
        meta: {
          title: $t('page.auth.qrcodeLogin'),
        },
      },
      {
        name: 'ForgetPassword',
        path: 'forget-password',
        component: () =>
          import('#/views/_core/authentication/forget-password.vue'),
        meta: {
          title: $t('page.auth.forgetPassword'),
        },
      },
      {
        name: 'Register',
        path: 'register',
        component: () => import('#/views/_core/authentication/register.vue'),
        meta: {
          title: $t('page.auth.register'),
        },
      },
    ],
  },
];

export { coreRoutes, fallbackNotFoundRoute };
