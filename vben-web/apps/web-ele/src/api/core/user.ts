import type { UserInfo } from '@vben/types';

import { requestClient } from '#/api/request';

/**
 * 获取用户信息
 */
export async function getUserInfoApi() {
  const res = await requestClient.get<any>('/user/info');
  return res.user;
}
