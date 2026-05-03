<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';

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

const canvasRef = ref<HTMLCanvasElement | null>(null);
let animFrame: number | null = null;

// 节点颜色配置
const NODE_STYLE = {
  root:      { fill: '#2C7A7B', text: '#FFFFFF', stroke: '#285E5F', r: 28 },
  feature:   { fill: '#F0FDFA', text: '#2C7A7B', stroke: '#2C7A7B', r: 22 },
  disease:   { fill: '#1C1917', text: '#FFFFFF', stroke: '#1C1917', r: 24 },
  knowledge: { fill: '#F5F5F4', text: '#78716C', stroke: '#E7E5E4', r: 18 },
};

// 力导向布局（简化版 Verlet 积分）
interface NodeState {
  id: string;
  label: string;
  type: SkinGraphNode['type'];
  x: number;
  y: number;
  vx: number;
  vy: number;
  fx?: number;  // 固定 x（根节点）
  fy?: number;  // 固定 y（根节点）
}

let nodes: NodeState[] = [];
let isDragging = false;
let dragNode: NodeState | null = null;

function initLayout(w: number, h: number) {
  nodes = props.nodes.map((n, i) => {
    const angle = (i / props.nodes.length) * Math.PI * 2;
    const r = n.type === 'root' ? 0 : 
              n.type === 'feature' ? h * 0.25 :
              n.type === 'disease' ? h * 0.38 : h * 0.44;
    return {
      ...n,
      x: w / 2 + (n.type === 'root' ? 0 : Math.cos(angle) * r * 1.1),
      y: h / 2 + (n.type === 'root' ? 0 : Math.sin(angle) * r * 0.7),
      vx: 0,
      vy: 0,
      fx: n.type === 'root' ? w / 2 : undefined,
      fy: n.type === 'root' ? h * 0.22 : undefined,
    };
  });
}

function tick(w: number, h: number) {
  const alpha = 0.3;
  const repulsion = 1800;
  const springLen = 80;
  const springK = 0.08;
  const damping = 0.88;

  // 斥力
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i]!;
      const b = nodes[j]!;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = repulsion / (dist * dist);
      const fx = (dx / dist) * force * alpha;
      const fy = (dy / dist) * force * alpha;
      if (!a.fx) a.vx -= fx;
      if (!a.fy) a.vy -= fy;
      if (!b.fx) b.vx += fx;
      if (!b.fy) b.vy += fy;
    }
  }

  // 弹簧力（按边）
  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  for (const link of props.links) {
    const a = nodeMap.get(link.source);
    const b = nodeMap.get(link.target);
    if (!a || !b) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const force = (dist - springLen) * springK;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;
    if (!a.fx) a.vx += fx;
    if (!a.fy) a.vy += fy;
    if (!b.fx) b.vx -= fx;
    if (!b.fy) b.vy -= fy;
  }

  // 中心引力（防止节点飞出）
  for (const n of nodes) {
    if (!n.fx) n.vx += (w / 2 - n.x) * 0.01;
    if (!n.fy) n.vy += (h / 2 - n.y) * 0.01;
  }

  // 更新位置
  const padding = 36;
  for (const n of nodes) {
    if (n.fx !== undefined) n.x = n.fx;
    else {
      n.vx *= damping;
      n.x = Math.max(padding, Math.min(w - padding, n.x + n.vx));
    }
    if (n.fy !== undefined) n.y = n.fy;
    else {
      n.vy *= damping;
      n.y = Math.max(padding, Math.min(h - padding, n.y + n.vy));
    }
  }
}

function draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.clearRect(0, 0, w, h);
  const nodeMap = new Map(nodes.map(n => [n.id, n]));

  // 连线
  for (const link of props.links) {
    const a = nodeMap.get(link.source);
    const b = nodeMap.get(link.target);
    if (!a || !b) continue;
    const isKnowledge = b.type === 'knowledge';
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = '#E7E5E4';
    ctx.lineWidth = 1.5;
    if (isKnowledge) {
      ctx.setLineDash([4, 3]);
    } else {
      ctx.setLineDash([]);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // 箭头
    const angle = Math.atan2(b.y - a.y, b.x - a.x);
    const style = NODE_STYLE[b.type];
    const endX = b.x - Math.cos(angle) * (style.r + 3);
    const endY = b.y - Math.sin(angle) * (style.r + 3);
    ctx.beginPath();
    ctx.moveTo(endX, endY);
    ctx.lineTo(
      endX - 8 * Math.cos(angle - 0.4),
      endY - 8 * Math.sin(angle - 0.4),
    );
    ctx.lineTo(
      endX - 8 * Math.cos(angle + 0.4),
      endY - 8 * Math.sin(angle + 0.4),
    );
    ctx.closePath();
    ctx.fillStyle = '#D6D3D1';
    ctx.fill();
  }

  // 节点
  for (const n of nodes) {
    const style = NODE_STYLE[n.type];
    ctx.beginPath();
    ctx.arc(n.x, n.y, style.r, 0, Math.PI * 2);
    ctx.fillStyle = style.fill;
    ctx.fill();
    ctx.strokeStyle = style.stroke;
    ctx.lineWidth = n.type === 'root' ? 0 : 1.5;
    ctx.stroke();

    // 标签（多行）
    ctx.fillStyle = style.text;
    const fontSize = n.type === 'root' ? 10 : 9;
    ctx.font = `600 ${fontSize}px -apple-system,"PingFang SC","Microsoft YaHei",sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    const maxW = style.r * 1.7;
    const words = n.label.split('');
    const lines: string[] = [];
    let cur = '';
    for (const ch of words) {
      if (ctx.measureText(cur + ch).width > maxW && cur) {
        lines.push(cur);
        cur = ch;
      } else {
        cur += ch;
      }
    }
    if (cur) lines.push(cur);

    const lineH = fontSize + 2;
    const startY = n.y - ((lines.length - 1) / 2) * lineH;
    for (let i = 0; i < lines.length; i++) {
      ctx.fillText(lines[i]!, n.x, startY + i * lineH);
    }
  }
}

let frameCount = 0;
function loop(ctx: CanvasRenderingContext2D, w: number, h: number) {
  if (frameCount < 180) {
    tick(w, h);
    frameCount++;
  }
  draw(ctx, w, h);
  animFrame = requestAnimationFrame(() => loop(ctx, w, h));
}

// 拖拽
function getCanvasXY(e: MouseEvent | TouchEvent, rect: DOMRect) {
  if ('touches' in e) {
    const t = e.touches[0]!;
    return { x: t.clientX - rect.left, y: t.clientY - rect.top };
  }
  return { x: (e as MouseEvent).clientX - rect.left, y: (e as MouseEvent).clientY - rect.top };
}

function findNode(x: number, y: number) {
  for (const n of nodes) {
    const r = NODE_STYLE[n.type].r + 4;
    if ((x - n.x) ** 2 + (y - n.y) ** 2 <= r * r) return n;
  }
  return null;
}

function onPointerDown(e: MouseEvent | TouchEvent) {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const { x, y } = getCanvasXY(e, rect);
  const node = findNode(x * scaleX, y * scaleY);
  if (node) {
    isDragging = true;
    dragNode = node;
    frameCount = 0;
  }
}

function onPointerMove(e: MouseEvent | TouchEvent) {
  if (!isDragging || !dragNode) return;
  e.preventDefault();
  const canvas = canvasRef.value;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const { x, y } = getCanvasXY(e, rect);
  dragNode.x = x * scaleX;
  dragNode.y = y * scaleY;
  dragNode.vx = 0;
  dragNode.vy = 0;
  frameCount = 0;
}

function onPointerUp() {
  isDragging = false;
  dragNode = null;
}

onMounted(() => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const W = 320;
  const H = 280;
  canvas.width = W;
  canvas.height = H;

  initLayout(W, H);
  frameCount = 0;
  loop(ctx, W, H);

  canvas.addEventListener('mousedown', onPointerDown);
  canvas.addEventListener('mousemove', onPointerMove);
  canvas.addEventListener('mouseup', onPointerUp);
  canvas.addEventListener('touchstart', onPointerDown, { passive: false });
  canvas.addEventListener('touchmove', onPointerMove, { passive: false });
  canvas.addEventListener('touchend', onPointerUp);
});

onBeforeUnmount(() => {
  if (animFrame) cancelAnimationFrame(animFrame);
  const canvas = canvasRef.value;
  if (!canvas) return;
  canvas.removeEventListener('mousedown', onPointerDown);
  canvas.removeEventListener('mousemove', onPointerMove);
  canvas.removeEventListener('mouseup', onPointerUp);
  canvas.removeEventListener('touchstart', onPointerDown);
  canvas.removeEventListener('touchmove', onPointerMove);
  canvas.removeEventListener('touchend', onPointerUp);
});

watch(() => [props.nodes, props.links], () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  initLayout(canvas.width, canvas.height);
  frameCount = 0;
}, { deep: true });
</script>

<template>
  <div class="kg-wrap">
    <canvas
      ref="canvasRef"
      class="kg-canvas"
      title="可拖拽节点查看关联关系"
    />
  </div>
</template>

<style scoped>
.kg-wrap {
  width: 100%;
  border-radius: var(--skin-radius-md);
  overflow: hidden;
  background: var(--skin-bg);
  border: 1px solid var(--skin-border-soft);
  cursor: grab;
}

.kg-wrap:active {
  cursor: grabbing;
}

.kg-canvas {
  width: 100%;
  height: auto;
  display: block;
  touch-action: none;
}
</style>
