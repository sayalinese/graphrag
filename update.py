import os

filepath = r'C:\Users\16960\Desktop\项目\vben-web\apps\web-ele\src\views\kg\kg_explain\components\KgGraph2D.vue'

new_content = \"\"\"<template>
  <div class=\"kg-graph3d relative h-full w-full overflow-hidden rounded-2xl\">
    <div ref=\"containerRef\" class=\"absolute inset-0 z-0\"></div>
    <div
      v-if=\"!hasGraphData\"
      class=\"pointer-events-none absolute inset-0 z-10 flex items-center justify-center px-6 text-center text-sm text-gray-400\"
    >
      No explainable path yet. Ask a question on the left panel.
    </div>
  </div>
</template>

<script lang=\"ts\" setup>
import ForceGraph3D from '3d-force-graph';
import * as THREE from 'three';
import SpriteText from 'three-spritetext';
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue';    

interface GraphPayload {
  nodes?: any[];
  edges?: any[];
  links?: any[];
}

interface HighlightPayload {
  seedNodeIds?: string[];
  nodeIds?: string[];
  linkIds?: string[];
  maxDepth?: number;
  graph?: GraphPayload;
}

interface ExplainNode {
  id: string;
  label: string;
  category?: string;
  type?: string;
  value: number;
  isPath?: boolean;
  isSeed?: boolean;
  x?: number;
  y?: number;
  z?: number;
}

interface ExplainLink {
  id: string;
  source: string | ExplainNode;
  target: string | ExplainNode;
  sourceId: string;
  targetId: string;
  relationType: string;
  value: number;
  isPath?: boolean;
}

const containerRef = ref<HTMLElement | null>(null);
const renderedGraph = shallowRef<{ nodes: ExplainNode[]; links: ExplainLink[] }>({ nodes: [], links: [] });
const hasGraphData = computed(() => renderedGraph.value.nodes.length > 0);

let graph: any = null;
let resizeObserver: ResizeObserver | null = null;
let zoomTimer: number | null = null;
let rafId: number | null = null;

let highlightActive = false;
const nodeOpacityMap = new Map<string, number>();
const nodeScaleMap = new Map<string, number>();
const linkProgressMap = new Map<string, number>();
let animationToken = 0;

const visibleNodeIds = new Set<string>();
const pathNodeIds = new Set<string>();
const pathLinkIds = new Set<string>();
const seedNodeIds = new Set<string>();

const WAVE_DELAY = 120;
const NODE_FADE_DURATION = 400;
const LINK_DRAW_DURATION = 600;

function clearAnimation() {
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
}

function refreshGraph() {
  if (!graph) return;
  graph.nodeRelabel();
  graph.linkDirectionalParticles(graph.linkDirectionalParticles());
}

function normalizeGraphPayload(payload?: GraphPayload) {
  if (!payload) return { nodes: [], links: [] };
  const rawNodes = Array.isArray(payload.nodes) ? payload.nodes : [];
  const rawLinks = Array.isArray(payload.links) ? payload.links : Array.isArray(payload.edges) ? payload.edges : [];

  const nodes: ExplainNode[] = rawNodes.map((n: any) => {
    return {
      id: String(n.id ?? n.name ?? Math.random().toString(36).slice(2)),
      label: String(n.label ?? n.name ?? n.id ?? 'Unknown'),
      category: String(n.category ?? n.type ?? 'Default'),
      type: String(n.type ?? 'entity'),
      value: Number(n.value) || 1,
    };
  });

  const links: ExplainLink[] = rawLinks.map((l: any, i: number) => {
    const s = String(l.source?.id ?? l.source);
    const t = String(l.target?.id ?? l.target);
    return {
      id: String(l.id ?? \link_\_\_\\),
      source: s,
      target: t,
      sourceId: s,
      targetId: t,
      relationType: String(l.relationType ?? l.type ?? l.label ?? 'RELATED_TO'),
      value: Number(l.value) || 1,
    };
  });

  return { nodes, links };
}

const CATEGORY_COLORS: Record<string, string> = {
  Company: '#3b82f6',
  Person: '#10b981',
  Technology: '#8b5cf6',
  Product: '#f59e0b',
  Location: '#ef4444',
  Default: '#6366f1',
};
function getCategoryColor(category?: string) {
  if (!category) return CATEGORY_COLORS.Default;
  return CATEGORY_COLORS[category] || CATEGORY_COLORS.Default;
}

function getNodeColor(node: ExplainNode) {
  return getCategoryColor(node.category);
}

function buildPathSubgraph(sourceGraph: { nodes: ExplainNode[]; links: ExplainLink[] }, payload: HighlightPayload) {
  const seedSet = new Set(payload.seedNodeIds ?? []);
  const nodeSet = new Set(payload.nodeIds ?? []);
  const linkSet = new Set(payload.linkIds ?? []);

  const keptNodes = sourceGraph.nodes.filter(n => nodeSet.has(n.id) || seedSet.has(n.id));
  const keptLinks = sourceGraph.links.filter(l => linkSet.has(l.id) || (nodeSet.has(l.sourceId) && nodeSet.has(l.targetId)));

  return {
    nodes: keptNodes.map(n => ({ ...n, isSeed: seedSet.has(n.id), isPath: true })),
    links: keptLinks.map(l => ({ ...l, isPath: true })),
    chainNodePaths: []
  };
}

function computeDepthMap(links: ExplainLink[], seeds: string[], maxDepth: number) {
  const depthMap = new Map<string, number>();
  if (!links.length) return depthMap;
  
  const adjacency = new Map<string, string[]>();
  links.forEach((link) => {
    if (!adjacency.has(link.sourceId)) adjacency.set(link.sourceId, []);
    if (!adjacency.has(link.targetId)) adjacency.set(link.targetId, []);
    adjacency.get(link.sourceId)?.push(link.targetId);
    adjacency.get(link.targetId)?.push(link.sourceId);
  });
  
  const queue: Array<{ id: string; depth: number }> = [];
  seeds.forEach((seed) => {
    depthMap.set(seed, 0);
    queue.push({ id: seed, depth: 0 });
  });

  let head = 0;
  while (head < queue.length) {
    const { id, depth } = queue[head++];
    if (depth >= maxDepth) continue;
    const neighbors = adjacency.get(id) || [];
    for (const neighbor of neighbors) {
      if (!depthMap.has(neighbor)) {
        depthMap.set(neighbor, depth + 1);
        queue.push({ id: neighbor, depth: depth + 1 });
      }
    }
  }
  return depthMap;
}

function attemptZoomToFit() {
  if (zoomTimer !== null) {
    window.clearTimeout(zoomTimer);
  }
  zoomTimer = window.setTimeout(() => {
    if (graph && graph.zoomToFit) {
      graph.zoomToFit(800, 50); 
    }
  }, 300);
}

function updateSize() {
  if (!containerRef.value || !graph) return;
  const { clientWidth, clientHeight } = containerRef.value;
  graph.width(clientWidth).height(clientHeight);
}

function initGraph() {
  if (!containerRef.value) return;

  graph = ForceGraph3D()(containerRef.value)
    .backgroundColor('#060d1d')
    .nodeThreeObject((node: any) => {
      const isPath = pathNodeIds.has(node.id) || Boolean(node.isPath);
      const isSeed = seedNodeIds.has(node.id) || Boolean(node.isSeed);
      
      const targetOpacity = highlightActive ? (nodeOpacityMap.get(node.id) ?? 0.1) : 1;
      const targetScale = highlightActive ? (nodeScaleMap.get(node.id) ?? 0.8) : 1;
      
      const group = new THREE.Group();
      
      const color = getNodeColor(node);
      
      const geometry = new THREE.SphereGeometry(6, 16, 16);
      const material = new THREE.MeshLambertMaterial({
        color,
        transparent: true,
        opacity: targetOpacity,
        depthWrite: targetOpacity >= 1
      });
      const sphere = new THREE.Mesh(geometry, material);
      group.add(sphere);
      
      const labelText = isSeed ? \[SEED] \\ : node.label;
      const sprite = new SpriteText(labelText);
      sprite.color = '#ffffff';
      sprite.textHeight = 4;
      sprite.backgroundColor = \gba(12, 24, 48, \)\;
      sprite.borderColor = color;
      sprite.borderWidth = 0.5;
      sprite.padding = [2, 4];
      sprite.position.set(0, 10, 0);
      sprite.material.depthWrite = false;
      sprite.material.opacity = targetOpacity;
      group.add(sprite);
      
      const scale = isSeed ? targetScale * 1.5 : targetScale;
      group.scale.set(scale, scale, scale);
      
      return group;
    })
    .linkWidth((link: any) => {
        const isPath = pathLinkIds.has(link.id) || Boolean(link.isPath);
        return isPath ? 1.5 : 0.5;
    })
    .linkColor((link: any) => {
        const isPath = pathLinkIds.has(link.id) || Boolean(link.isPath);
        return isPath ? 'rgba(56, 189, 248, 1)' : 'rgba(255, 255, 255, 0.2)';
    })
    .linkDirectionalParticles((link: any) => {
        const isPath = pathLinkIds.has(link.id) || Boolean(link.isPath);
        if (!highlightActive) return isPath ? 2 : 0;
        const progress = linkProgressMap.get(link.id) ?? 0;
        return progress > 0.5 ? 2 : 0;
    })
    .linkDirectionalParticleSpeed(0.005)
    .onEngineStop(() => {
      attemptZoomToFit();
    })
    .graphData({ nodes: [], links: [] });

  const scene = graph.scene();
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
  directionalLight.position.set(1, 1, 1);
  scene.add(ambientLight);
  scene.add(directionalLight);

  updateSize();
  resizeObserver = new ResizeObserver(() => updateSize());
  resizeObserver.observe(containerRef.value);
}

function applyRenderedGraph(graphData: any) {
  renderedGraph.value = graphData;

  visibleNodeIds.clear();
  pathNodeIds.clear();
  pathLinkIds.clear();
  seedNodeIds.clear();

  graphData.nodes.forEach((node: any) => {
    visibleNodeIds.add(node.id);
    if (node.isPath) pathNodeIds.add(node.id);
    if (node.isSeed) seedNodeIds.add(node.id);
  });
  graphData.links.forEach((link: any) => {
    if (link.isPath) pathLinkIds.add(link.id);
  });

  if (!graph) return;

  graph.graphData({
    nodes: graphData.nodes.map((n: any) => ({ ...n })),
    links: graphData.links.map((l: any) => ({ ...l })),
  });
  
  graph.d3ReheatSimulation?.();
  refreshGraph();
  attemptZoomToFit();
}

function clearHighlight() {
  clearAnimation();
  highlightActive = false;
  nodeOpacityMap.clear();
  nodeScaleMap.clear();
  linkProgressMap.clear();
  refreshGraph();
}

function setGraphData(payload: GraphPayload) {
  clearHighlight();
  const normalized = normalizeGraphPayload(payload);
  const annotated = {
    nodes: normalized.nodes.map((node) => ({ ...node, isPath: false, isSeed: false })),
    links: normalized.links.map((link) => ({ ...link, isPath: false })),
  };
  applyRenderedGraph(annotated);
}

function highlightByWaves(payload: HighlightPayload) {
  clearAnimation();

  const sourceGraph = normalizeGraphPayload(payload.graph);

  if (!sourceGraph.nodes.length && !sourceGraph.links.length) {
    clearHighlight();
    return;
  }

  const pathResult = buildPathSubgraph(sourceGraph, payload);
  applyRenderedGraph({ nodes: pathResult.nodes, links: pathResult.links });

  if (!pathResult.nodes.length) {
    clearHighlight();
    return;
  }

  highlightActive = true;
  nodeOpacityMap.clear();
  nodeScaleMap.clear();
  linkProgressMap.clear();

  pathResult.nodes.forEach((node) => {
    nodeOpacityMap.set(node.id, 0.1);
    nodeScaleMap.set(node.id, node.isSeed ? 1.1 : 0.8);
  });
  pathResult.links.forEach((link) => linkProgressMap.set(link.id, 0));

  const maxDepth = Number.isFinite(payload.maxDepth) ? Math.max(1, Number(payload.maxDepth)) : 3;
  const seeds = pathResult.nodes.filter((n) => n.isSeed).map((n) => n.id);
  const depthMap = computeDepthMap(pathResult.links, seeds, maxDepth);
  pathResult.nodes.forEach((n) => {
    if (!depthMap.has(n.id)) depthMap.set(n.id, maxDepth);
  });

  const linkDepthMap = new Map<string, number>();
  pathResult.links.forEach((link) => {
    const sd = depthMap.get(link.sourceId) ?? maxDepth;
    const td = depthMap.get(link.targetId) ?? maxDepth;
    linkDepthMap.set(link.id, Math.max(sd, td));
  });

  const startAt = performance.now();
  animationToken += 1;
  const currentToken = animationToken;

  const animate = () => {
    if (currentToken !== animationToken) return;
    const now = performance.now();
    let isAnimating = false;

    pathResult.nodes.forEach((node) => {
      const depth = depthMap.get(node.id) ?? 0;
      const elapsed = now - startAt - depth * WAVE_DELAY;
      const progress = Math.min(Math.max(elapsed / NODE_FADE_DURATION, 0), 1);
      if (progress < 1) isAnimating = true;
      const eased = 1 - (1 - progress) ** 3;
      nodeOpacityMap.set(node.id, 0.1 + eased * 0.9);
      nodeScaleMap.set(node.id, (node.isSeed ? 1.1 : 0.8) + eased * 0.2);
    });

    pathResult.links.forEach((link) => {
      const depth = linkDepthMap.get(link.id) ?? 0;
      const elapsed = now - startAt - depth * WAVE_DELAY;
      const progress = Math.min(Math.max(elapsed / LINK_DRAW_DURATION, 0), 1);
      if (progress < 1) isAnimating = true;
      linkProgressMap.set(link.id, 1 - (1 - progress) ** 3);
    });

    refreshGraph();
    if (isAnimating) {
      rafId = requestAnimationFrame(animate);
      return;
    }
    rafId = null;
    attemptZoomToFit();
  };

  rafId = requestAnimationFrame(animate);
}

onMounted(() => {
  initGraph();
});

onBeforeUnmount(() => {
  clearAnimation();
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (zoomTimer !== null) {
    window.clearTimeout(zoomTimer);
    zoomTimer = null;
  }
  if (graph?._destructor) graph._destructor();
  graph = null;
});

defineExpose({
  setGraphData,
  clearHighlight,
  highlightByWaves,
});
</script>

<style scoped>
.kg-graph3d {
  background:
    radial-gradient(circle at 20% 10%, rgba(56, 189, 248, 0.08), transparent 35%),
    radial-gradient(circle at 80% 80%, rgba(14, 116, 144, 0.12), transparent 40%),
    #060d1d;
}
</style>\"\"\"

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(\"updated file!!!\")
