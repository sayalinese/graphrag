<script lang="ts" setup>
import { onMounted, ref } from 'vue';

import KgChatWindow from './components/KgChatWindow.vue';
import { baseRequestClient } from '#/api/request';

const selectedDocId = ref('');

onMounted(async () => {
  try {
    const res = await baseRequestClient.get<any>('/kg/databases');
    const dbs: Array<{ name: string; default: boolean }> =
      res?.data?.data?.databases || res?.data?.databases || [];
    // 优先选非默认、非 system 的数据库（即项目实际知识库）
    const pick =
      dbs.find((d) => !d.default && d.name !== 'system') ||
      dbs.find((d) => d.name !== 'system');
    if (pick) selectedDocId.value = pick.name;
  } catch {
    // 如果接口不可用，保持空字符串
  }
});
</script>

<template>
  <div class="h-[calc(100vh-80.2px)] overflow-hidden bg-background">
    <div class="h-full w-full">
      <KgChatWindow
        v-model:selected-database="selectedDocId"
      />
    </div>
  </div>
</template>
