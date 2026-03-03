
export function estimateTokens(text: string): number {
  if (!text) return 0;
  // 将代码块内内容整体也纳入统计，不做特殊处理
  // 粗略拆分：中文每字 1 token；英文/数字/符号按空白与标点分段。
  let count = 0;
  for (const ch of text) {
    // 中文 unicode 范围 (含 CJK Unified Ideographs)
    if (/[\u4e00-\u9fa5]/.test(ch)) {
      count += 1;
    }
  }
  // 去掉中文后剩余部分按正则分词
  const nonChinese = text.replace(/[\u4e00-\u9fa5]/g, ' ');
  const parts = nonChinese
    .split(/\s+/)
    .map((p) => p.trim())
    .filter(Boolean);
  count += parts.reduce((sum, p) => sum + Math.ceil(p.length / 4), 0); // 近似每 4 字符 ~ 1 token
  return count;
}

export function formatTokenInfo(text: string, maxTokens?: number) {
  const used = estimateTokens(text);
  const left = maxTokens ? Math.max(0, maxTokens - used) : undefined;
  return { used, left };
}
