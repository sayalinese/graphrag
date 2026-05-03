<template>
  <div class="skin-kg-graph">
    <div ref="canvasRef" class="skin-kg-graph__canvas" />
    <p class="skin-kg-graph__hint">拖拽节点 · 滚轮缩放 · 悬停查看名称</p>
  </div>
</template>

<script setup lang="ts">
import ForceGraph from 'force-graph';
import {
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  watch,
} from 'vue';

export interface SkinGraphNode {
  id: string;
  label: string;
  type: 'root' | 'feature' | 'disease' | 'knowledge';
}

export interface SkinGraphLink {
  source: string;
  target: string;
}

const props = defineProps<{
  nodes: SkinGraphNode[];
  links: SkinGraphLink[];
}>();

const canvasRef = ref<HTMLDivElement | null>(null);
const graph = shallowRef<any>(null);
let resizeObs: ResizeObserver | null = null;

function nodeFill(n: SkinGraphNode) {
  if (n.type === 'root') return '#2C7A7B';
  if (n.type === 'feature') return '#B2F5EA';
  if (n.type === 'disease') return n.id === 'd1' ? '#1C1917' : '#44403C';
  return '#E7E5E4';
}

function relSize(n: SkinGraphNode) {
  if (n.type === 'root') return 8;
  if (n.type === 'disease') return 6.5;
  if (n.type === 'feature') return 5.2;
  return 4.2;
}

function labelDy(n: SkinGraphNode, globalScale: number) {
  const base = relSize(n);
  return base / globalScale + 10 / globalScale;
}

function syncSize() {
  const g = graph.value;
  const el = canvasRef.value;
  if (!g || !el) return;
  const w = el.clientWidth;
  const h = el.clientHeight;
  if (w > 0 && h > 0) {
    g.width(w);
    g.height(h);
  }
}

function pushGraphData() {
  const g = graph.value;
  if (!g) return;
  g.graphData({
    nodes: props.nodes.map((n) => ({ ...n })),
    links: props.links.map((l) => ({ ...l })),
  });
  g.d3ReheatSimulation?.();
  setTimeout(() => g.zoomToFit?.(400, 36), 100);
}

function initGraph() {
  if (!canvasRef.value || graph.value) return;
  const factory = ForceGraph as unknown as () => any;
  const inst = factory()(canvasRef.value)
    .backgroundColor('transparent')
    .dagMode('td')
    .dagLevelDistance(62)
    .nodeId('id')
    .nodeLabel('label')
    .nodeRelSize((n: SkinGraphNode) => relSize(n))
    .nodeColor((n: SkinGraphNode) => nodeFill(n))
    .linkColor(() => 'rgba(44, 122, 123, 0.3)')
    .linkWidth(1.35)
    .enableNodeDrag(true)
    .enableZoomInteraction(true)
    .enablePanInteraction(true)
    .warmupTicks(50)
    .cooldownTicks(220)
    .onEngineStop(() => {
      setTimeout(() => inst.zoomToFit?.(420, 40), 60);
    })
    .nodeCanvasObjectMode(() => 'after')
    .nodeCanvasObject((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      if (node.x == null || node.y == null) return;
      const n = node as SkinGraphNode & { x: number; y: number };
      if (n.type === 'feature') {
        const r = relSize(n) * 1.05;
        ctx.strokeStyle = '#2C7A7B';
        ctx.lineWidth = 1.35 / globalScale;
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, 2 * Math.PI, false);
        ctx.stroke();
      }
      const fontSize = Math.min(11, 13 / globalScale);
      ctx.font = `500 ${fontSize}px ui-sans-serif, "PingFang SC", "Microsoft YaHei", sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillStyle = 'rgba(28, 25, 23, 0.9)';
      ctx.fillText(n.label, n.x, n.y + labelDy(n, globalScale));
    });

  try {
    inst.d3Force('charge')?.strength?.(-200);
    inst.d3VelocityDecay?.(0.36);
  } catch {
    /* ignore */
  }

  graph.value = inst;
  syncSize();
  pushGraphData();

  resizeObs = new ResizeObserver(() => {
    syncSize();
    graph.value?.zoomToFit?.(220, 40);
  });
  resizeObs.observe(canvasRef.value);
}

onMounted(() => {
  nextTick(() => initGraph());
});

watch(
  () => [props.nodes, props.links] as const,
  () => {
    if (graph.value) pushGraphData();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  resizeObs?.disconnect();
  resizeObs = null;
  if (graph.value) {
    graph.value._destructor?.();
    graph.value = null;
  }
});
</script>

<style scoped>
.skin-kg-graph {
  position: relative;
  width: 100%;
}

.skin-kg-graph__canvas {
  width: 100%;
  height: min(52vh, 320px);
  min-height: 240px;
  border-radius: var(--skin-radius-md, 8px);
  background: var(--skin-bg, #fafaf9);
  border: 1px solid var(--skin-border-soft, #f5f5f4);
  overflow: hidden;
}

.skin-kg-graph__hint {
  margin: var(--skin-gap-2, 8px) 0 0 0;
  font-size: var(--skin-text-xs, 12px);
  color: var(--skin-text-muted, #a8a29e);
  text-align: center;
}
</style>
