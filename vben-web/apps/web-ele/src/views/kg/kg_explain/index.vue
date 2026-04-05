<script lang="ts" setup>
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import KgChatWindow from './components/KgChatWindow.vue';
import KgGraph2D from './components/KgGraph2D.vue';
import { baseRequestClient } from '#/api/request';

interface HighlightPayload {
  seedNodeIds?: string[];
  nodeIds?: string[];
  linkIds?: string[];
  maxDepth?: number;
  graph?: { edges?: any[]; links?: any[]; nodes?: any[] };
}

const router = useRouter();
const graph2dRef = ref<InstanceType<typeof KgGraph2D> | null>(null);
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

function goBack() {
  router.push('/kg/preview');
}

function handleKgHighlight(payload: HighlightPayload) {
  if (!graph2dRef.value) return;

  graph2dRef.value.highlightByWaves({
    ...payload,
    maxDepth: Number.isFinite(payload.maxDepth) ? Number(payload.maxDepth) : 3,
  });
}
</script>

<template>
  <div class="h-[calc(100vh-80.2px)] overflow-hidden bg-[#030b1a] p-3">
    <div class="explain-grid grid h-full grid-cols-1 lg:grid-cols-[38%_62%]">
      <div
        class="min-h-[320px] border-b border-[#16345d] lg:min-h-0 lg:border-b-0 lg:border-r"
      >
        <KgChatWindow
          v-model:selected-database="selectedDocId"
          @kg-highlight="handleKgHighlight"
          @close="goBack"
        />
      </div>

      <div class="relative h-full w-full">
        <KgGraph2D ref="graph2dRef" />
      </div>
    </div>
  </div>
</template>

<style scoped>
@media (max-width: 1024px) {
  .explain-grid {
    grid-template-rows: minmax(300px, 45%) minmax(0, 55%);
  }
}
</style>
