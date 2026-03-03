import { useAppConfig } from '@vben/hooks';
import { preferences } from '@vben/preferences';
import { RequestClient } from '@vben/request';
import { useAccessStore } from '@vben/stores';
import { ElMessage } from 'element-plus';

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);

function formatToken(token: string | null) {
  return token ? `Bearer ${token}` : undefined;
}

export const http = new RequestClient({
  baseURL: apiURL,
  responseReturn: 'data',
});

http.addRequestInterceptor({
  fulfilled: async (config) => {
    const accessStore = useAccessStore();
    config.headers = config.headers || {};
    const token = formatToken(accessStore.accessToken);
    if (token) {
      config.headers.Authorization = token;
    }
    config.headers['Accept-Language'] = preferences.app.locale;
    return config;
  },
});

http.addResponseInterceptor({
  fulfilled: async (response) => {
    const data = response?.data ?? response;
    if (data && typeof data === 'object' && 'success' in data) {
      if ((data as { success?: boolean }).success === false) {
        const message = (data as { error?: string }).error || '请求失败';
        ElMessage.error(message);
        throw new Error(message);
      }
    }
    return data;
  },
  rejected: async (error) => {
    const message =
      error?.response?.data?.error ||
      error?.response?.data?.message ||
      error.message ||
      '请求失败';
    ElMessage.error(message);
    throw error;
  },
});
