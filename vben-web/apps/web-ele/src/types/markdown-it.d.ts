declare module 'markdown-it' {
  import type { Options } from 'markdown-it';
  class MarkdownIt {
    constructor(options?: Options);
    render(src: string): string;
    utils: { escapeHtml(str: string): string };
  }
  export default MarkdownIt;
}
