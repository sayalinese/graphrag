<template>
  <div class="kg-graph2d relative h-full w-full overflow-hidden rounded-2xl" @mouseenter="resumeGraph" @mouseleave="pauseGraphDeferred">
    <div ref="containerRef" class="absolute inset-0 z-0"></div>
    <div
      v-if="!hasGraphData"
      class="pointer-events-none absolute inset-0 z-10 flex items-center justify-center px-6 text-center text-sm text-gray-400"
    >
      请在左侧对话中输入一个问题，图谱将在此展示
    </div>
  </div>
</template>

<script lang="ts" setup>
import ForceGraph from 'force-graph';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps<{
  graphData?: any;
}>();

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
const NODE_CLICK_PADDING = 10;
const NODE_CLICK_MIN_RADIUS = 16;
const NODE_DRAG_SUPPRESS_MS = 180;
const ZOOM_FIT_PADDING_MIN = 8;
const ZOOM_FIT_PADDING_MAX = 18;
const ZOOM_FIT_PADDING_RATIO = 0.04;
const PATH_LABEL_MIN_SCALE = 1.0;
const GLOBAL_LABEL_MIN_SCALE = 1.85;

const containerRef = ref<HTMLDivElement | null>(null);
const renderedGraph = ref<NormalizedGraph>({ nodes: [], links: [] });
const hasGraphData = computed(() => renderedGraph.value.nodes.length > 0);

const visibleNodeIds = new Set<string>();
const pathNodeIds = new Set<string>();
const pathLinkIds = new Set<string>();
const seedNodeIds = new Set<string>();
const highDegreeNeighborIds = new Set<string>(); // 种子节点直连且度数>4
const hoveredNodeIds = new Set<string>();
const hoveredLinkIds = new Set<string>();

// 三档节点半径
const NODE_R_SEED = 10;    // 档位1：起始实体
const NODE_R_HIGH  = 8;    // 档位2：直连高度节点
const NODE_R_BASE  = 5;    // 档位3：其他节点

const nodeOpacityMap = new Map<string, number>();
const nodeScaleMap = new Map<string, number>();
const linkProgressMap = new Map<string, number>();

let graph: any = null;
let resizeObserver: ResizeObserver | null = null;
let themeObserver: MutationObserver | null = null;
let animationToken = 0;
let rafId: number | null = null;
let highlightActive = false;
let hoveredCenterNodeId = '';
let suppressNodeClickUntil = 0;
let nodeDragged = false;

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

  const graphData = graph.graphData?.() ?? { nodes: [], links: [] };
  const graphNodes = Array.isArray(graphData.nodes) ? graphData.nodes : [];
  const graphLinks = Array.isArray(graphData.links) ? graphData.links : [];
  const idSet = new Set(graphNodes.map((n: any) => normalizeNodeId(n?.id)).filter(Boolean));
  const matched = Array.from(visibleNodeIds).filter((id) => idSet.has(id));

  zoomAppliedId = requestId;
  if (!matched.length) return;

  // 计算有连接的节点集合，孤立节点不参与 zoomToFit 的 bounding box 计算
  const connectedIds = new Set<string>();
  graphLinks.forEach((link: any) => {
    const src = normalizeNodeId(typeof link.source === 'object' ? link.source?.id : link.source);
    const tgt = normalizeNodeId(typeof link.target === 'object' ? link.target?.id : link.target);
    if (src) connectedIds.add(src);
    if (tgt) connectedIds.add(tgt);
  });
  // 若没有任何边（纯节点图），退回全部可见节点
  const fitIds = connectedIds.size > 0
    ? new Set(matched.filter((id) => connectedIds.has(id)))
    : new Set(matched);
  if (!fitIds.size) return;

  const containerSize = Math.min(
    containerRef.value?.clientWidth || Number.POSITIVE_INFINITY,
    containerRef.value?.clientHeight || Number.POSITIVE_INFINITY,
  );
  const fitPadding = Number.isFinite(containerSize)
    ? Math.max(ZOOM_FIT_PADDING_MIN, Math.min(ZOOM_FIT_PADDING_MAX, Math.round(containerSize * ZOOM_FIT_PADDING_RATIO)))
    : ZOOM_FIT_PADDING_MAX;

  graph.zoomToFit(650, fitPadding, (node: any) => fitIds.has(normalizeNodeId(node?.id)));
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
  if (node.isSeed) return '#4ade80';           // 档位1：亮绿
  const nodeId = normalizeNodeId(node.id);
  if (highDegreeNeighborIds.has(nodeId)) return '#f59e0b'; // 档位2：琥珀橙
  if (node.isPath) return '#60a5fa';           // 档位3（连通）：蓝色
  return '#64748b';                            // 孤立节点：灰色
}

function getFontSize(globalScale: number, min = 10, max = 18) {
  const safeScale = Math.max(0.25, Math.min(3, globalScale || 1));
  const size = 11 / safeScale;
  return Math.max(min, Math.min(max, size));
}

function getNodeBaseRadius(node: any): number {
  const nodeId = normalizeNodeId(node?.id);
  const isSeed = seedNodeIds.has(nodeId) || Boolean(node?.isSeed);
  if (isSeed) return NODE_R_SEED;
  if (highDegreeNeighborIds.has(nodeId)) return NODE_R_HIGH;
  return NODE_R_BASE;
}

function getNodeRenderScale(node: any): number {
  const nodeId = normalizeNodeId(node?.id);
  const hoverActive = hoveredNodeIds.size > 0;
  const isHoveredNode = hoveredNodeIds.has(nodeId);
  const isHoverCenter = hoveredCenterNodeId === nodeId;
  const baseScale = highlightActive ? (nodeScaleMap.get(nodeId) ?? 0.9) : 1;

  if (!hoverActive) return baseScale;
  if (isHoverCenter) return Math.max(baseScale, 1.22);
  if (isHoveredNode) return Math.max(baseScale, 1.08);
  return Math.min(baseScale, 0.82);
}

function paintNodePointerArea(node: any, color: string, ctx: CanvasRenderingContext2D, globalScale: number) {
  if (!Number.isFinite(node?.x) || !Number.isFinite(node?.y)) return;

  const scale = getNodeRenderScale(node);
  const radius = Math.max(NODE_CLICK_MIN_RADIUS, getNodeBaseRadius(node) * scale + NODE_CLICK_PADDING);

  ctx.save();
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
  ctx.fill();

  if (globalScale >= 0.35) {
    const label = trimLabel(String(node?.name ?? node?.label ?? node?.id ?? ''), 18);
    if (label) {
      const fontSize = getFontSize(globalScale, 10, 18);
      ctx.font = `600 ${fontSize}px sans-serif`;
      const textWidth = ctx.measureText(label).width;
      const rectX = node.x + radius;
      const rectY = node.y - fontSize / 2 - 4;
      ctx.fillRect(rectX, rectY, textWidth + 10, fontSize + 8);
    }
  }

  ctx.restore();
}

function isDarkMode(): boolean {
  return document.documentElement.classList.contains('dark');
}

function drawRelationLabel(ctx: CanvasRenderingContext2D, label: string, x: number, y: number, alpha: number, globalScale: number) {
  if (!label) return;
  if (globalScale < 1.0) return;

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
  const dark = isDarkMode();
  if (dark) {
    ctx.fillStyle = 'rgba(10, 25, 47, 0.84)';
    ctx.fillRect(rectX, rectY, rectW, rectH);
    ctx.strokeStyle = 'rgba(34, 211, 238, 0.45)';
    ctx.lineWidth = 0.8;
    ctx.strokeRect(rectX, rectY, rectW, rectH);
  }
  ctx.fillStyle = dark ? 'rgba(229, 231, 235, 0.95)' : 'rgba(15, 23, 42, 0.88)';
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
  const hoverActive = hoveredNodeIds.size > 0;
  const isHoveredLink = hoveredLinkIds.has(linkId);
  const progress = highlightActive ? (linkProgressMap.get(linkId) ?? 0) : 1;
  const style = relationStyle(link as ExplainLink);
  const defaultAlpha = isPath ? style.alpha : 0.08;
    const alpha = hoverActive
      ? isHoveredLink
        ? defaultAlpha
        : isPath
          ? 0.16
          : 0
      : defaultAlpha;
    if (alpha <= 0) return;
    const lineWidth = hoverActive
    ? isHoveredLink
      ? style.width + 1.2
      : isPath
        ? Math.max(1.1, style.width * 0.72)
        : 0.8
    : isPath
      ? style.width
      : 1;

  const sx = source.x as number;
  const sy = source.y as number;
  const tx = target.x as number;
  const ty = target.y as number;
  const dx = sx + (tx - sx) * progress;
  const dy = sy + (ty - sy) * progress;

  ctx.save();
  ctx.strokeStyle = hoverActive && isHoveredLink
    ? 'rgba(34, 211, 238, 0.98)'
    : `rgba(103, 232, 249, ${alpha})`;
  ctx.lineWidth = lineWidth;
  ctx.setLineDash(isPath ? style.dash : []);
  ctx.beginPath();
  ctx.moveTo(sx, sy);
  ctx.lineTo(dx, dy);
  ctx.stroke();

  if ((isPath || isHoveredLink) && progress > 0.15) {
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
  const hoverActive = hoveredNodeIds.size > 0;
  const isHoveredNode = hoveredNodeIds.has(nodeId);
  const isHoverCenter = hoveredCenterNodeId === nodeId;

  const radius = getNodeBaseRadius(node);

  const baseScale = highlightActive ? (nodeScaleMap.get(nodeId) ?? 0.9) : 1;
  const baseOpacity = highlightActive ? (nodeOpacityMap.get(nodeId) ?? (isPath ? 0.1 : 0.05)) : isPath ? 0.95 : 0.15;
  const scale = hoverActive
    ? isHoverCenter
      ? Math.max(baseScale, 1.22)
      : isHoveredNode
        ? Math.max(baseScale, 1.08)
        : Math.min(baseScale, 0.82)
    : baseScale;
  const opacity = hoverActive
      ? isHoveredNode
        ? baseOpacity
        : isPath
          ? Math.max(baseOpacity, 0.14)
          : 0
      : baseOpacity;
    const label = trimLabel(String(node.name ?? node.label ?? node.id ?? ''), 18);

    if (opacity <= 0) return;

    ctx.save();

  if (isSeed) {
    ctx.beginPath();
    ctx.fillStyle = 'rgba(34, 211, 238, 0.2)';
    ctx.arc(node.x, node.y, (radius * scale) + 7, 0, Math.PI * 2);
    ctx.fill();
  }
  if (isHoverCenter) {
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(34, 211, 238, 0.96)';
    ctx.lineWidth = 2.2;
    ctx.arc(node.x, node.y, (radius * scale) + 5, 0, Math.PI * 2);
    ctx.stroke();
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

  // LOD 标签：种子/档位2/悬停节点始终显示；普通连接节点放大后才显示
  const isHighDegree = highDegreeNeighborIds.has(nodeId);
  const showLabel =
    isSeed ||
    isHighDegree ||
    isHoveredNode ||
    (isPath && globalScale >= PATH_LABEL_MIN_SCALE) ||
    globalScale >= GLOBAL_LABEL_MIN_SCALE;
  if (showLabel && label) {
    const prominent = isSeed || isHoveredNode;
    const mid = isHighDegree && !prominent;
    const trimmedLabel = trimLabel(label, prominent ? 20 : mid ? 16 : 12);
    const fontSize = getFontSize(globalScale, prominent ? 11 : mid ? 10 : 9, prominent ? 15 : mid ? 13 : 13);
    ctx.font = `${prominent ? '700' : mid ? '600' : '500'} ${fontSize}px sans-serif`;
    const textX = node.x + (radius * scale) + 5;
    const textY = node.y;
    const dark = isDarkMode();
    const labelAlpha = prominent ? Math.min(1, opacity + 0.3) : Math.min(0.85, opacity + 0.1);
    ctx.fillStyle = dark
      ? prominent
        ? `rgba(226, 232, 240, ${labelAlpha})`
        : `rgba(186, 200, 218, ${labelAlpha})`
      : prominent
        ? `rgba(15, 23, 42, ${labelAlpha})`
        : `rgba(51, 65, 85, ${labelAlpha})`;
    ctx.textBaseline = 'middle';
    ctx.fillText(trimmedLabel, textX, textY);
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
    .backgroundColor('rgba(0,0,0,0)')
    .nodeId('id')
    .enableNodeDrag(true)
    .warmupTicks(70)
    .cooldownTicks(220)
    .linkCanvasObjectMode(() => 'replace')
    .linkCanvasObject((link: any, ctx: CanvasRenderingContext2D, globalScale: number) => drawLink(link, ctx, globalScale))
    .nodeCanvasObject((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => drawNode(node, ctx, globalScale))
    .nodePointerAreaPaint((node: any, color: string, ctx: CanvasRenderingContext2D, globalScale: number) =>
      paintNodePointerArea(node, color, ctx, globalScale),
    )
    .onNodeDrag((_node: any, translate: { x?: number; y?: number }) => {
      if (Math.hypot(translate?.x ?? 0, translate?.y ?? 0) > 0.5) {
        nodeDragged = true;
      }
    })
    .onNodeDragEnd(() => {
      if (!nodeDragged) return;
      suppressNodeClickUntil = performance.now() + NODE_DRAG_SUPPRESS_MS;
      nodeDragged = false;
    })
    .onNodeClick((node: any) => handleNodeActivate(node))
    .onBackgroundClick(() => {
      clearHoverHighlight();
      clearHighlight();
    })
    .onEngineStop(() => {
      attemptZoomToFit(`engine-stop:${zoomReason || 'unknown'}`);
    })
    .graphData({ nodes: [], links: [] });



    // 这里调整大小
  try {
    graph.d3Force('charge')?.strength?.(-120);
    graph.d3Force('link')?.distance?.(72);
    graph.d3VelocityDecay?.(0.28);
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
  highDegreeNeighborIds.clear();

  graphData.nodes.forEach((node) => {
    visibleNodeIds.add(node.id);
    if (node.isPath) pathNodeIds.add(node.id);
    if (node.isSeed) seedNodeIds.add(node.id);
  });
  graphData.links.forEach((link) => {
    if (link.isPath) pathLinkIds.add(link.id);
  });

  // 计算每个节点在当前视图内的度数，找出种子节点的直连且度数 > 4 的邻居（档位2）
  // Tier 2：整张图中度数 > 4 的非 seed 节点（枢纽节点，不限是否为直接邻居）
  // 兜底：若无节点满足阈值（小图场景），则取所有非 seed 节点中度数最高的前3个
  const degreeMap = new Map<string, number>();
  graphData.links.forEach((link) => {
    degreeMap.set(link.sourceId, (degreeMap.get(link.sourceId) ?? 0) + 1);
    degreeMap.set(link.targetId, (degreeMap.get(link.targetId) ?? 0) + 1);
  });
  graphData.nodes.forEach((node) => {
    if (!seedNodeIds.has(node.id) && (degreeMap.get(node.id) ?? 0) > 4) {
      highDegreeNeighborIds.add(node.id);
    }
  });
  // 兜底：小图中无节点满足 > 4，则从非 seed 节点里按度数取前3
  if (highDegreeNeighborIds.size === 0 && graphData.nodes.length > 1) {
    graphData.nodes
      .filter((n) => !seedNodeIds.has(n.id))
      .sort((a, b) => (degreeMap.get(b.id) ?? 0) - (degreeMap.get(a.id) ?? 0))
      .slice(0, 3)
      .forEach((n) => highDegreeNeighborIds.add(n.id));
  }

  if (!graph) return;

  graph.graphData({
    nodes: graphData.nodes.map((n) => ({ ...n })),
    links: graphData.links.map((l) => ({ ...l })),
  });

  graph.d3ReheatSimulation?.();

  refreshGraph();

  requestZoomToFit(`apply:${sourceTag}`, 260);
  resumeGraph();
  pauseGraphDeferred();
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

function clearHoverHighlight() {
  hoveredCenterNodeId = '';
  hoveredNodeIds.clear();
  hoveredLinkIds.clear();
}

function handleNodeActivate(node: any) {
  if (performance.now() < suppressNodeClickUntil) return;

  const hoveredId = normalizeNodeId(node?.id);
  if (!hoveredId) {
    if (hoveredNodeIds.size === 0) return;
    clearHoverHighlight();
    refreshGraph();
    return;
  }

  if (hoveredCenterNodeId === hoveredId) {
    clearHoverHighlight();
    refreshGraph();
    return;
  }

  clearHoverHighlight();
  hoveredCenterNodeId = hoveredId;
  hoveredNodeIds.add(hoveredId);

  renderedGraph.value.links.forEach((link) => {
    if (link.sourceId !== hoveredId && link.targetId !== hoveredId) return;
    hoveredNodeIds.add(link.sourceId);
    hoveredNodeIds.add(link.targetId);
    hoveredLinkIds.add(link.id);
  });

  refreshGraph();
}

function setGraphData(payload: GraphPayload) {
  clearHoverHighlight();
  clearHighlight();
  const normalized = normalizeGraphPayload(payload);
  const seedId = normalized.nodes[0]?.id;
  const annotated: NormalizedGraph = {
    nodes: normalized.nodes.map((node) => ({
      ...node,
      isPath: true,
      isSeed: node.id === seedId,
    })),
    links: normalized.links.map((link) => ({ ...link, isPath: true })),
  };
  applyRenderedGraph(annotated, 'setGraphData');
}

function easeOutCubic(value: number): number {
  return 1 - (1 - value) ** 3;
}

function highlightByWaves(payload: HighlightPayload) {
  clearHoverHighlight();
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

  // 监听主题切换，触发重绘（标签颜色在每帧内实时读取 isDarkMode，这里强制重绘一帧）
  themeObserver = new MutationObserver(() => {
    if (graph) graph.refresh();
  });
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
});

watch(() => props.graphData, (newVal) => {
  if (newVal) {
    const nodes = newVal.entities || newVal.nodes || [];
    const links = newVal.relations || newVal.edges || newVal.links || [];
    if (nodes.length > 0 || links.length > 0) {
      setGraphData({ nodes, links });
    }
  }
}, { deep: true, immediate: true });

let animationPauseTimer: number | null = null;

function resumeGraph() {
  if (animationPauseTimer !== null) {
    window.clearTimeout(animationPauseTimer);
    animationPauseTimer = null;
  }
  if (graph) {
    graph.resumeAnimation();
  }
}

function pauseGraphDeferred() {
  if (animationPauseTimer !== null) {
    window.clearTimeout(animationPauseTimer);
  }
  animationPauseTimer = window.setTimeout(() => {
    if (graph) {
      graph.pauseAnimation();
    }
  }, 5000);
}

onBeforeUnmount(() => {
  clearAnimation();
  if (themeObserver) {
    themeObserver.disconnect();
    themeObserver = null;
  }
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
  background: transparent;
}
</style>
