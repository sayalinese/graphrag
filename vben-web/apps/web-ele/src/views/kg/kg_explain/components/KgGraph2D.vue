<template>
  <div class="kg-graph2d relative h-full w-full overflow-hidden rounded-2xl">
    <div ref="containerRef" class="absolute inset-0 z-0"></div>
    <div
      v-if="!hasGraphData"
      class="pointer-events-none absolute inset-0 z-10 flex items-center justify-center px-6 text-center text-sm text-gray-400"
    >
      No explainable path yet. Ask a question on the left panel.
    </div>
  </div>
</template>

<script lang="ts" setup>
import ForceGraph from 'force-graph';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

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
  name?: string;
  raw?: any;
  value: number;
  isPath?: boolean;
  isSeed?: boolean;
  x?: number;
  y?: number;
}

interface ExplainLink {
  id: string;
  source: string | ExplainNode;
  target: string | ExplainNode;
  sourceId: string;
  targetId: string;
  relationType: string;
  relationText: string;
  raw?: any;
  value: number;
  isPath?: boolean;
}

interface NormalizedGraph {
  nodes: ExplainNode[];
  links: ExplainLink[];
}

interface PathBuildResult {
  nodes: ExplainNode[];
  links: ExplainLink[];
  sourceMode: string;
  chainNodePaths: string[][];
}

const NODE_FADE_DURATION = 380;
const LINK_DRAW_DURATION = 450;
const WAVE_DELAY = 220;

const containerRef = ref<HTMLDivElement | null>(null);
const renderedGraph = ref<NormalizedGraph>({ nodes: [], links: [] });
const hasGraphData = computed(() => renderedGraph.value.nodes.length > 0);

const visibleNodeIds = new Set<string>();
const pathNodeIds = new Set<string>();
const pathLinkIds = new Set<string>();
const seedNodeIds = new Set<string>();

const nodeOpacityMap = new Map<string, number>();
const nodeScaleMap = new Map<string, number>();
const linkProgressMap = new Map<string, number>();

let graph: any = null;
let resizeObserver: ResizeObserver | null = null;
let animationToken = 0;
let rafId: number | null = null;
let highlightActive = false;

let zoomRequestId = 0;
let zoomAppliedId = 0;
let zoomReason = '';
let zoomTimer: number | null = null;

function normalizeNodeId(value: unknown): string {
  if (typeof value === 'string') return value.trim();
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    const candidate = obj.id ?? obj.nodeId ?? obj.uid ?? obj.neo_id ?? obj.elementId ?? obj.name;
    if (typeof candidate === 'string') return candidate.trim();
    if (typeof candidate === 'number' && Number.isFinite(candidate)) return String(candidate);
  }
  return '';
}

function normalizeNodeLabel(rawNode: any, fallbackId: string): string {
  return String(rawNode?.name ?? rawNode?.label ?? rawNode?.title ?? rawNode?.id ?? fallbackId);
}

function normalizeNumber(value: unknown, fallback = 1): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function normalizeEdgeType(rawEdge: any): string {
  return String(rawEdge?.type ?? rawEdge?.rel ?? rawEdge?.relationship ?? rawEdge?.label ?? '').trim();
}

function normalizeEdgeLabel(rawEdge: any): string {
  return String(rawEdge?.description ?? rawEdge?.type ?? rawEdge?.rel ?? rawEdge?.label ?? rawEdge?.name ?? '').trim();
}

function resolveEndpoint(rawEdge: any, keys: string[]): { id: string; label: string } {
  for (const key of keys) {
    const endpoint = rawEdge?.[key];
    const id = normalizeNodeId(endpoint);
    if (!id) continue;
    let label = id;
    if (endpoint && typeof endpoint === 'object') {
      label = String((endpoint as any).name ?? (endpoint as any).label ?? id);
    }
    return { id, label };
  }
  return { id: '', label: '' };
}

function normalizeGraphPayload(payload?: GraphPayload): NormalizedGraph {
  const rawNodes = Array.isArray(payload?.nodes) ? payload.nodes : [];
  const rawEdges = Array.isArray(payload?.edges) ? payload.edges : Array.isArray(payload?.links) ? payload.links : [];

  const nodeMap = new Map<string, ExplainNode>();
  rawNodes.forEach((rawNode) => {
    const nodeId = normalizeNodeId(rawNode?.id ?? rawNode?.name ?? rawNode?.uid ?? rawNode?.nodeId ?? rawNode?.neo_id);
    if (!nodeId) return;
    if (nodeMap.has(nodeId)) return;
    nodeMap.set(nodeId, {
      id: nodeId,
      label: normalizeNodeLabel(rawNode, nodeId),
      name: typeof rawNode?.name === 'string' ? rawNode.name : undefined,
      raw: rawNode,
      value: normalizeNumber(rawNode?.value ?? rawNode?.weight, 1),
    });
  });

  const links: ExplainLink[] = [];
  const usedLinkIds = new Set<string>();
  rawEdges.forEach((rawEdge, index) => {
    const source = resolveEndpoint(rawEdge, ['source', 'from', 'start', 'startNode', 'sourceId', 'fromId']);
    const target = resolveEndpoint(rawEdge, ['target', 'to', 'end', 'endNode', 'targetId', 'toId']);
    if (!source.id || !target.id) return;

    if (!nodeMap.has(source.id)) nodeMap.set(source.id, { id: source.id, label: source.label || source.id, value: 1 });
    if (!nodeMap.has(target.id)) nodeMap.set(target.id, { id: target.id, label: target.label || target.id, value: 1 });

    const explicitId = normalizeNodeId(rawEdge?.id);
    let linkId = explicitId || `${source.id}->${target.id}#${index}`;
    if (!linkId) return;

    if (usedLinkIds.has(linkId)) {
      let suffix = 1;
      let candidate = `${linkId}#${suffix}`;
      while (usedLinkIds.has(candidate)) {
        suffix += 1;
        candidate = `${linkId}#${suffix}`;
      }
      linkId = candidate;
    }
    usedLinkIds.add(linkId);

    links.push({
      id: linkId,
      source: source.id,
      target: target.id,
      sourceId: source.id,
      targetId: target.id,
      relationType: normalizeEdgeType(rawEdge),
      relationText: normalizeEdgeLabel(rawEdge),
      raw: rawEdge,
      value: normalizeNumber(rawEdge?.value ?? rawEdge?.weight, 1),
    });
  });

  return { nodes: Array.from(nodeMap.values()), links };
}

function relationStyle(link: ExplainLink): { alpha: number; dash: number[]; width: number } {
  const relationKey = (link.relationType || link.relationText || '').toLowerCase();
  const baseWidth = 1.8 + Math.min(1.8, Math.max(0, normalizeNumber(link.value, 1) * 0.35));
  if (relationKey.includes('recommend') || relationKey.includes('guideline')) return { width: baseWidth + 1, dash: [], alpha: 0.96 };
  if (relationKey.includes('support') || relationKey.includes('evidence')) return { width: baseWidth + 0.8, dash: [3, 2], alpha: 0.92 };
  if (relationKey.includes('diagn')) return { width: baseWidth + 0.5, dash: [8, 3], alpha: 0.9 };
  if (relationKey.includes('treat')) return { width: baseWidth + 0.6, dash: [2, 2], alpha: 0.9 };
  return { width: baseWidth, dash: [], alpha: 0.88 };
}

function trimLabel(text: string, maxLength = 22): string {
  if (!text) return '';
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function buildPathSubgraph(base: NormalizedGraph, payload: HighlightPayload): PathBuildResult {
  const existingNodeIds = new Set(base.nodes.map((node) => node.id));
  const maxDepth = Number.isFinite(payload.maxDepth) ? Math.max(1, Number(payload.maxDepth)) : 3;
  const requestedSeedIds = new Set((payload.seedNodeIds ?? []).map((i) => normalizeNodeId(i)).filter((id) => id && existingNodeIds.has(id)));

  const selected = new Map<string, ExplainLink>();
  if (requestedSeedIds.size > 0 && base.links.length > 0) {
    const adjacency = new Map<string, Array<{ edge: ExplainLink; next: string }>>();
    base.links.forEach((link) => {
      if (!adjacency.has(link.sourceId)) adjacency.set(link.sourceId, []);
      if (!adjacency.has(link.targetId)) adjacency.set(link.targetId, []);
      adjacency.get(link.sourceId)?.push({ edge: link, next: link.targetId });
      adjacency.get(link.targetId)?.push({ edge: link, next: link.sourceId });
    });

    const visited = new Set<string>();
    const queue: Array<{ id: string; depth: number }> = [];
    requestedSeedIds.forEach((seed) => {
      queue.push({ id: seed, depth: 0 });
      visited.add(seed);
    });

    while (queue.length > 0) {
      const current = queue.shift()!;
      if (current.depth >= maxDepth) continue;
      const neighbors = adjacency.get(current.id) ?? [];
      neighbors.forEach(({ edge, next }) => {
        selected.set(edge.id, edge);
        if (!visited.has(next)) {
          visited.add(next);
          queue.push({ id: next, depth: current.depth + 1 });
        }
      });
    }
  }

  if (selected.size === 0 && base.links.length > 0) {
    base.links.forEach((link) => selected.set(link.id, link));
  }

  let nodes: ExplainNode[] = [];
  const selectedLinks = Array.from(selected.values());

  if (selectedLinks.length === 0 && base.nodes.length > 0) {
    nodes = base.nodes.map((n) => ({ ...n, isPath: true, isSeed: requestedSeedIds.has(n.id) }));
  } else {
    const nodeSet = new Set<string>();
    selectedLinks.forEach((l) => {
      nodeSet.add(l.sourceId);
      nodeSet.add(l.targetId);
    });
    nodes = base.nodes
      .filter((n) => nodeSet.has(n.id))
      .map((n) => ({ ...n, isPath: true, isSeed: requestedSeedIds.has(n.id) }));
  }

  if (!nodes.some((n) => n.isSeed) && nodes.length) nodes[0]!.isSeed = true;

  const links = selectedLinks.map((l) => ({ ...l, isPath: true, relationText: l.relationText || l.relationType || '' }));
  const chains: string[][] = [];

  return { nodes, links, sourceMode: 'seed.expand', chainNodePaths: chains };
}

function clearAnimation() {
  animationToken += 1;
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
}

function refreshGraph() {
  graph?.refresh?.();
}

function attemptZoomToFit(_reason: string, requestId = zoomRequestId) {
  if (!graph) return;
  if (requestId <= zoomAppliedId) return;

  const graphData = graph.graphData?.() ?? { nodes: [] };
  const graphNodes = Array.isArray(graphData.nodes) ? graphData.nodes : [];
  const idSet = new Set(graphNodes.map((n: any) => normalizeNodeId(n?.id)).filter(Boolean));
  const matched = Array.from(visibleNodeIds).filter((id) => idSet.has(id));

  zoomAppliedId = requestId;
  if (!matched.length) return;

  const matchedSet = new Set(matched);
  graph.zoomToFit(650, 70, (node: any) => matchedSet.has(normalizeNodeId(node?.id)));
}

function requestZoomToFit(reason: string, delayMs = 220) {
  if (!graph) return;
  zoomRequestId += 1;
  zoomReason = reason;

  if (zoomTimer !== null) window.clearTimeout(zoomTimer);
  const reqId = zoomRequestId;

  zoomTimer = window.setTimeout(() => {
    attemptZoomToFit(`delayed:${reason}`, reqId);
    zoomTimer = null;
  }, delayMs);
}

function toRgba(hexColor: string, alpha: number): string {
  const normalized = hexColor.replace('#', '');
  const pure = normalized.length === 3 ? normalized.split('').map((c) => `${c}${c}`).join('') : normalized;
  const intValue = Number.parseInt(pure, 16);
  const r = (intValue >> 16) & 255;
  const g = (intValue >> 8) & 255;
  const b = intValue & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function nodeColor(node: ExplainNode): string {
  if (node.isSeed) return '#22d3ee';
  if (node.isPath) return '#60a5fa';
  return '#64748b';
}

function getFontSize(globalScale: number, min = 10, max = 18) {
  const safeScale = Math.max(0.25, Math.min(3, globalScale || 1));
  const size = 11 / safeScale;
  return Math.max(min, Math.min(max, size));
}

function drawRelationLabel(ctx: CanvasRenderingContext2D, label: string, x: number, y: number, alpha: number, globalScale: number) {
  if (!label) return;
  if (globalScale < 0.35) return;

  const text = trimLabel(label, 24);
  const fontSize = getFontSize(globalScale, 10, 16);
  ctx.font = `600 ${fontSize}px sans-serif`;
  const textWidth = ctx.measureText(text).width;
  const paddingX = 5;
  const paddingY = 2;
  const rectX = x - textWidth / 2 - paddingX;
  const rectY = y - fontSize / 2 - paddingY;
  const rectW = textWidth + paddingX * 2;
  const rectH = fontSize + paddingY * 2;

  ctx.save();
  ctx.globalAlpha = Math.min(0.92, alpha + 0.06);
  ctx.fillStyle = 'rgba(10, 25, 47, 0.84)';
  ctx.fillRect(rectX, rectY, rectW, rectH);
  ctx.strokeStyle = 'rgba(34, 211, 238, 0.45)';
  ctx.lineWidth = 0.8;
  ctx.strokeRect(rectX, rectY, rectW, rectH);
  ctx.fillStyle = 'rgba(229, 231, 235, 0.95)';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, rectX + paddingX, y);
  ctx.restore();
}

function drawLink(link: any, ctx: CanvasRenderingContext2D, globalScale: number) {
  const source = link.source as ExplainNode;
  const target = link.target as ExplainNode;
  if (!source || !target) return;
  if (!Number.isFinite(source.x) || !Number.isFinite(source.y)) return;
  if (!Number.isFinite(target.x) || !Number.isFinite(target.y)) return;

  const linkId = String(link.id ?? '');
  const isPath = pathLinkIds.has(linkId) || Boolean(link.isPath);
  const progress = highlightActive ? (linkProgressMap.get(linkId) ?? 0) : 1;
  const style = relationStyle(link as ExplainLink);
  const alpha = isPath ? style.alpha : 0.08;
  const lineWidth = isPath ? style.width : 1;

  const sx = source.x as number;
  const sy = source.y as number;
  const tx = target.x as number;
  const ty = target.y as number;
  const dx = sx + (tx - sx) * progress;
  const dy = sy + (ty - sy) * progress;

  ctx.save();
  ctx.strokeStyle = `rgba(103, 232, 249, ${alpha})`;
  ctx.lineWidth = lineWidth;
  ctx.setLineDash(isPath ? style.dash : []);
  ctx.beginPath();
  ctx.moveTo(sx, sy);
  ctx.lineTo(dx, dy);
  ctx.stroke();

  if (isPath && progress > 0.15) {
    ctx.fillStyle = 'rgba(56, 189, 248, 0.88)';
    ctx.beginPath();
    ctx.arc(dx, dy, 2.2, 0, Math.PI * 2);
    ctx.fill();

    const relationText = String(link.relationText ?? link.relationType ?? '').trim();
    if (relationText) {
      const mx = sx + (dx - sx) * 0.5;
      const my = sy + (dy - sy) * 0.5;
      drawRelationLabel(ctx, relationText, mx, my, alpha, globalScale);
    }
  }
  ctx.restore();
}

function drawNode(node: any, ctx: CanvasRenderingContext2D, globalScale: number) {
  const nodeId = normalizeNodeId(node.id);
  if (!nodeId) return;

  const isPath = pathNodeIds.has(nodeId) || Boolean(node.isPath);
  const isSeed = seedNodeIds.has(nodeId) || Boolean(node.isSeed);

  const baseSize = Math.max(4, Math.min(10, 4 + Math.sqrt(Math.max(1, normalizeNumber(node.value, 1)))));
  const radius = baseSize + (isPath ? 2.2 : 0) + (isSeed ? 1.6 : 0);

  const scale = highlightActive ? (nodeScaleMap.get(nodeId) ?? 0.9) : 1;
  const opacity = highlightActive ? (nodeOpacityMap.get(nodeId) ?? (isPath ? 0.1 : 0.05)) : isPath ? 0.95 : 0.15;
  const label = trimLabel(String(node.name ?? node.label ?? node.id ?? ''), 18);

  ctx.save();

  if (isSeed) {
    ctx.beginPath();
    ctx.fillStyle = 'rgba(34, 211, 238, 0.2)';
    ctx.arc(node.x, node.y, (radius * scale) + 7, 0, Math.PI * 2);
    ctx.fill();
  }
  if (isPath) {
    ctx.beginPath();
    ctx.fillStyle = 'rgba(96, 165, 250, 0.16)';
    ctx.arc(node.x, node.y, (radius * scale) + 4, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.beginPath();
  ctx.fillStyle = toRgba(nodeColor(node), opacity);
  ctx.arc(node.x, node.y, radius * scale, 0, Math.PI * 2);
  ctx.fill();

  if (isSeed) {
    ctx.beginPath();
    ctx.strokeStyle = `rgba(34, 211, 238, ${Math.min(0.98, opacity + 0.2)})`;
    ctx.lineWidth = 1.6;
    ctx.arc(node.x, node.y, (radius * scale) + 2.2, 0, Math.PI * 2);
    ctx.stroke();
  }

  if (globalScale >= 0.45) {
    const fontSize = getFontSize(globalScale, 10, 18);
    ctx.font = `600 ${fontSize}px sans-serif`;
    ctx.fillStyle = `rgba(229, 231, 235, ${Math.min(1, opacity + 0.2)})`;
    ctx.textBaseline = 'middle';
    ctx.fillText(label, node.x + (radius * scale) + 4, node.y);
  }

  ctx.restore();
}

function updateSize() {
  if (!graph || !containerRef.value) return;
  const { clientWidth, clientHeight } = containerRef.value;
  if (!clientWidth || !clientHeight) return;
  graph.width(clientWidth);
  graph.height(clientHeight);
  requestZoomToFit('resize', 240);
}

function initGraph() {
  if (!containerRef.value || graph) return;
  const createGraph = ForceGraph as unknown as () => any;

  graph = createGraph()(containerRef.value)
    .backgroundColor('#060d1d')
    .nodeId('id')
    .enableNodeDrag(true)
    .warmupTicks(70)
    .cooldownTicks(220)
    .linkCanvasObjectMode(() => 'replace')
    .linkCanvasObject((link: any, ctx: CanvasRenderingContext2D, globalScale: number) => drawLink(link, ctx, globalScale))
    .nodeCanvasObject((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => drawNode(node, ctx, globalScale))
    .onBackgroundClick(() => clearHighlight())
    .onEngineStop(() => {
      attemptZoomToFit(`engine-stop:${zoomReason || 'unknown'}`);
    })
    .graphData({ nodes: [], links: [] });

  try {
    graph.d3Force('charge')?.strength?.(-140);
    graph.d3Force('link')?.distance?.(90);
    graph.d3VelocityDecay?.(0.35);
  } catch {}

  updateSize();
  resizeObserver = new ResizeObserver(() => updateSize());
  resizeObserver.observe(containerRef.value);

  if (renderedGraph.value.nodes.length > 0 || renderedGraph.value.links.length > 0) {
    graph.graphData({
      nodes: renderedGraph.value.nodes.map((n) => ({ ...n })),
      links: renderedGraph.value.links.map((l) => ({ ...l })),
    });
    graph.d3ReheatSimulation?.();
    refreshGraph();
    requestZoomToFit('init-replay', 260);
  }
}

function applyRenderedGraph(graphData: NormalizedGraph, sourceTag: string, chainNodePaths: string[][] = []) {
  renderedGraph.value = graphData;

  visibleNodeIds.clear();
  pathNodeIds.clear();
  pathLinkIds.clear();
  seedNodeIds.clear();

  graphData.nodes.forEach((node) => {
    visibleNodeIds.add(node.id);
    if (node.isPath) pathNodeIds.add(node.id);
    if (node.isSeed) seedNodeIds.add(node.id);
  });
  graphData.links.forEach((link) => {
    if (link.isPath) pathLinkIds.add(link.id);
  });

  if (!graph) return;

  graph.graphData({
    nodes: graphData.nodes.map((n) => ({ ...n })),
    links: graphData.links.map((l) => ({ ...l })),
  });

  graph.d3ReheatSimulation?.();

  refreshGraph();

  requestZoomToFit(`apply:${sourceTag}`, 260);
  console.info('[Explain2D]', {
    phase: 'render',
    source: sourceTag,
    renderedNodes: graphData.nodes.length,
    renderedLinks: graphData.links.length,
    chainCount: chainNodePaths.length,
  });
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
  const annotated: NormalizedGraph = {
    nodes: normalized.nodes.map((node) => ({ ...node, isPath: false, isSeed: false })),
    links: normalized.links.map((link) => ({ ...link, isPath: false })),
  };
  applyRenderedGraph(annotated, 'setGraphData');
}

function easeOutCubic(value: number): number {
  return 1 - (1 - value) ** 3;
}

function highlightByWaves(payload: HighlightPayload) {
  clearAnimation();

  const sourceGraph = normalizeGraphPayload(payload.graph);

  if (!sourceGraph.nodes.length && !sourceGraph.links.length) {
    clearHighlight();
    return;
  }

  const pathResult = buildPathSubgraph(sourceGraph, payload);
  applyRenderedGraph({ nodes: pathResult.nodes, links: pathResult.links }, `payload.graph -> expand`, pathResult.chainNodePaths);

  if (!pathResult.nodes.length) {
    clearHighlight();
    return;
  }

  highlightActive = true;
  nodeOpacityMap.clear();
  nodeScaleMap.clear();
  linkProgressMap.clear();

  pathResult.nodes.forEach((node) => {
    nodeOpacityMap.set(node.id, 0.05);
    nodeScaleMap.set(node.id, node.isSeed ? 1.1 : 0.86);
  });
  pathResult.links.forEach((link) => linkProgressMap.set(link.id, 0));

  const maxDepth = Number.isFinite(payload.maxDepth) ? Math.max(1, Number(payload.maxDepth)) : 3;
  const seeds = pathResult.nodes.filter((node) => node.isSeed).map((node) => node.id);
  const depthMap = computeDepthMap(pathResult.links, seeds, maxDepth);
  pathResult.nodes.forEach((node) => {
    if (!depthMap.has(node.id)) depthMap.set(node.id, maxDepth);
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
      const eased = easeOutCubic(progress);
      nodeOpacityMap.set(node.id, 0.05 + eased * 0.95);
      nodeScaleMap.set(node.id, (node.isSeed ? 1.1 : 0.86) + eased * 0.24);
    });

    pathResult.links.forEach((link) => {
      const depth = linkDepthMap.get(link.id) ?? 0;
      const elapsed = now - startAt - depth * WAVE_DELAY;
      const progress = Math.min(Math.max(elapsed / LINK_DRAW_DURATION, 0), 1);
      if (progress < 1) isAnimating = true;
      linkProgressMap.set(link.id, easeOutCubic(progress));
    });

    refreshGraph();
    if (isAnimating) {
      rafId = requestAnimationFrame(animate);
      return;
    }
    rafId = null;
    requestZoomToFit('wave-complete', 260);
  };

  rafId = requestAnimationFrame(animate);
}

function computeDepthMap(links: ExplainLink[], seeds: string[], maxDepth: number): Map<string, number> {
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
    if (depthMap.has(seed)) return;
    depthMap.set(seed, 0);
    queue.push({ id: seed, depth: 0 });
  });

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current.depth >= maxDepth) continue;
    const neighbors = adjacency.get(current.id) ?? [];
    neighbors.forEach((neighborId) => {
      if (depthMap.has(neighborId)) return;
      depthMap.set(neighborId, current.depth + 1);
      queue.push({ id: neighborId, depth: current.depth + 1 });
    });
  }

  return depthMap;
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
.kg-graph2d {
  background:
    radial-gradient(circle at 20% 10%, rgba(56, 189, 248, 0.08), transparent 35%),
    radial-gradient(circle at 80% 80%, rgba(14, 116, 144, 0.12), transparent 40%),
    #060d1d;
}
</style>
