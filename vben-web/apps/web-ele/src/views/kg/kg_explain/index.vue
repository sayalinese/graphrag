<script lang="ts" setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';

import KgChatWindow from '../kg_preview/components/KgChatWindow.vue';
import KgGraph2D from './components/KgGraph2D.vue';

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

function goBack() {
  router.push('/kg/preview');
}

function handleKgHighlight(payload: HighlightPayload) {
  if (!graph2dRef.value) return;
  const payloadGraphNodes = Array.isArray(payload.graph?.nodes)
    ? payload.graph.nodes.length
    : 0;
  const payloadGraphEdges = Array.isArray(payload.graph?.edges)
    ? payload.graph.edges.length
    : (Array.isArray(payload.graph?.links)
      ? payload.graph.links.length
      : 0);

  // console.info('[Explain2D]', {
  //   phase: 'page-forward',
  //   payloadGraphNodes,
  //   payloadGraphEdges,
  //   seedNodeIds: payload.seedNodeIds ?? [],
  //   nodeIds: payload.nodeIds ?? [],
  //   linkIds: payload.linkIds ?? [],
  //   maxDepth: payload.maxDepth ?? 3,
  // });

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
          v-model:doc-id="selectedDocId"
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
