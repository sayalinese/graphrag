import { defineConfig } from '@vben/vite-config';

import ElementPlus from 'unplugin-element-plus/vite';

export default defineConfig(async () => {
  // 根据环境变量切换HMR：本机开发用localhost，外网用ngrok域名
  const isNgrokMode = process.env.NGROK_MODE === 'true';
  const ngrokDomain = process.env.NGROK_DOMAIN || 'localhost';
  
  return {
    application: {},
    vite: {
      plugins: [
        ElementPlus({
          format: 'esm',
        }),
      ],
      server: {
        allowedHosts: true,
        hmr: isNgrokMode
          ? {
              protocol: 'wss',
              host: ngrokDomain,
              port: 443,
            }
          : {
              protocol: 'ws',
              host: '127.0.0.1',
              port: 5777,
            },
        proxy: {
          '/api': {
            target: 'http://127.0.0.1:5000',
            changeOrigin: true,
            ws: true,
            timeout: 300000,
            proxyTimeout: 300000,
            keepAlive: true,
          },
        },
      },
      preview: {
        port: 5777,
        host: '0.0.0.0',
        allowedHosts: true,
        proxy: {
          '/api': {
            target: 'http://127.0.0.1:5000',
            changeOrigin: true,
            ws: true,
            timeout: 300000,
            proxyTimeout: 300000,
            keepAlive: true,
          },
        },
      },
    },
  };
});
