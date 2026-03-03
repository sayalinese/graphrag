import { defineConfig } from '@vben/vite-config';

import ElementPlus from 'unplugin-element-plus/vite';

export default defineConfig(async () => {
  return {
    application: {},
    vite: {
      plugins: [
        ElementPlus({
          format: 'esm',
        }),
      ],
      server: {
        proxy: {
          '/api': {
            target: 'http://127.0.0.1:5000', // 指向 Flask 后端
            changeOrigin: true,
            ws: true,
            // 不再 rewrite，保持 /api 前缀与 Flask Blueprint 一致
          },
        },
      },
    },
  };
});
