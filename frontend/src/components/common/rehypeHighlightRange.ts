import type { Element, ElementContent, Root, RootContent, Text } from "hast";

// Plugin rehype tô sáng một khoảng ký tự [start, end) của CHUỖI MARKDOWN NGUỒN.
// remark giữ `position.offset` trên từng nút hast, nên đoạn trích được tô đúng chỗ
// kể cả khi nằm trong ô bảng hay giữa công thức - thay vì chèn thẻ vào chuỗi
// markdown (làm vỡ cú pháp bảng `| … |`). Không dùng HTML thô: an toàn với nguồn.

export interface HighlightRange {
  start: number;
  end: number;
}

export interface HighlightOptions {
  source: string;
  range: HighlightRange | null;
}

export const HIGHLIGHT_CLASS = "src-hl";

const mark = (children: ElementContent[]): Element => ({
  type: "element",
  tagName: "mark",
  properties: { className: [HIGHLIGHT_CLASS] },
  children,
});

const isMath = (node: Element) => {
  const className = node.properties?.className;
  const classes = Array.isArray(className) ? className.map(String) : [];
  return classes.includes("language-math") || classes.includes("math-inline") || classes.includes("math-display");
};

function offsets(node: RootContent | ElementContent): [number, number] | null {
  const start = node.position?.start.offset;
  const end = node.position?.end.offset;
  return start == null || end == null ? null : [start, end];
}

/** Tách nút chữ thành trước / tô sáng / sau khi giá trị trùng đúng chuỗi nguồn; nếu không, tô cả nút. */
function splitText(node: Text, from: number, source: string, range: HighlightRange): ElementContent[] {
  const value = node.value;
  if (source.slice(from, from + value.length) !== value) return [mark([node])];
  const a = Math.max(0, range.start - from);
  const b = Math.min(value.length, range.end - from);
  const parts: ElementContent[] = [];
  if (a > 0) parts.push({ type: "text", value: value.slice(0, a) });
  parts.push(mark([{ type: "text", value: value.slice(a, b) }]));
  if (b < value.length) parts.push({ type: "text", value: value.slice(b) });
  return parts;
}

function highlightChildren(parent: Root | Element, source: string, range: HighlightRange): void {
  const next: ElementContent[] = [];
  for (const child of parent.children as ElementContent[]) {
    const span = offsets(child);
    const overlaps = span !== null && span[0] < range.end && span[1] > range.start;
    if (child.type === "text") {
      next.push(...(overlaps && span ? splitText(child, span[0], source, range) : [child]));
    } else if (child.type === "element") {
      if (overlaps && isMath(child)) {
        next.push(mark([child])); // rehype-katex vẫn tìm thấy nút công thức bên trong <mark>
      } else {
        if (overlaps || span === null) highlightChildren(child, source, range);
        next.push(child);
      }
    } else {
      next.push(child);
    }
  }
  // Plugin unified biến đổi cây tại chỗ theo quy ước của hệ sinh thái rehype.
  (parent as Element).children = next;
}

export default function rehypeHighlightRange(options: HighlightOptions) {
  return (tree: Root) => {
    const { range, source } = options;
    if (!range || range.end <= range.start) return;
    highlightChildren(tree, source, range);
  };
}
