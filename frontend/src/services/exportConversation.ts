import {
  AlignmentType,
  BorderStyle,
  Document,
  HeadingLevel,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
  type ParagraphChild,
} from "docx";
import { strFromU8, strToU8, unzipSync, zipSync } from "fflate";
import katex from "katex";
import { mml2omml } from "mathml2omml";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import type { BackendSource, Message } from "../types";

export type ExportFormat = "json" | "docx";

const ACCENT = "2D6A43";
const ACCENT_SOFT = "E6F0EA";
const BORDER = "C9D3CC";
const TEXT_MUTED = "5F6B64";
const FONT = "Calibri";
const FONT_MONO = "Consolas";
const BODY_SIZE = 22; // half-points = 11pt
const INDENT_STEP = 360; // twips

/** Chỉ xuất các lượt đã hoàn chỉnh: bỏ tin đang stream, tin lỗi và tin rỗng. */
export function exportableMessages(messages: Message[]): Message[] {
  return messages.filter((m) => !m.streaming && !m.error && (m.role === "user" ? !!m.text : !!m.markdown));
}

export function exportFileName(title: string, format: ExportFormat, now: Date): string {
  const slug = title
    .replace(/[\\/:*?"<>|\n\r\t]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 50)
    .trim();
  const date = now.toISOString().slice(0, 10);
  return `${slug || "hoi-thoai"} - ${date}.${format}`;
}

export function buildExportJson(title: string, messages: Message[], now: Date): string {
  const items = exportableMessages(messages).map((m) =>
    m.role === "user" ? { role: "user", text: m.text } : { role: "assistant", markdown: m.markdown, sources: m.sources ?? [] },
  );
  return JSON.stringify({ title, exportedAt: now.toISOString(), messages: items }, null, 2);
}

// ───────────────────────── Markdown → DOCX ─────────────────────────

interface MdNode {
  type: string;
  value?: string;
  children?: MdNode[];
  depth?: number;
  ordered?: boolean;
  start?: number;
}

interface RunStyle {
  bold?: boolean;
  italics?: boolean;
}

type Block = Paragraph | Table;

const parser = unified().use(remarkParse).use(remarkGfm).use(remarkMath);

function parseMarkdown(markdown: string): MdNode[] {
  return (parser.parse(markdown) as MdNode).children ?? [];
}

function plainText(n: MdNode): string {
  return n.value ?? (n.children ?? []).map(plainText).join("");
}

const EMPTY_NARY_BODY = "<m:e/></m:nary>";
const XML_TAG = /<(\/?)([\w:]+)[^>]*?(\/?)>/g;

/** Vị trí ngay sau phần tử bắt đầu tại `start`, hoặc -1 nếu ở đó không phải thẻ mở. */
function elementEnd(xml: string, start: number): number {
  XML_TAG.lastIndex = start;
  let depth = 0;
  for (let m = XML_TAG.exec(xml); m; m = XML_TAG.exec(xml)) {
    if (m.index !== start && depth === 0) return -1;
    if (m[1]) depth -= 1;
    else if (!m[3]) depth += 1;
    if (depth <= 0) return depth < 0 ? -1 : XML_TAG.lastIndex;
  }
  return -1;
}

/**
 * KaTeX đặt thân của Σ, ∏, ∫ làm phần tử đứng sau; bộ chuyển để thân trống nên Word hiện ô vuông.
 * Đưa phần tử đứng ngay sau vào thân (toán tử lớn áp dụng cho số hạng kế tiếp).
 */
function fillEmptyNary(omml: string): string {
  let out = omml;
  for (let at = out.indexOf(EMPTY_NARY_BODY); at >= 0; at = out.indexOf(EMPTY_NARY_BODY, at + 1)) {
    const next = at + EMPTY_NARY_BODY.length;
    const end = elementEnd(out, next);
    if (end < 0) continue;
    out = `${out.slice(0, at)}<m:e>${out.slice(next, end)}</m:e></m:nary>${out.slice(end)}`;
  }
  return out;
}

const OMML_TEXT_NODE = /(<m:t\b[^>]*>[^<]*<\/m:t>)|>([^<]+)</g;

/** Bộ chuyển đôi khi để chữ trần (vd. "(x)") ngoài <m:r><m:t>: sai lược đồ, Word có thể báo hỏng hoặc bỏ chữ. */
function wrapBareText(omml: string): string {
  return omml.replace(OMML_TEXT_NODE, (all, textRun: string | undefined, bare: string | undefined) =>
    textRun || !bare?.trim() ? all : `><m:r><m:t xml:space="preserve">${bare}</m:t></m:r><`,
  );
}

/** Công thức Word (OMML) dựng từ LaTeX nguyên văn; null nếu KaTeX hoặc bộ chuyển không đọc được. */
export function latexToOmml(latex: string): string | null {
  try {
    const html = katex.renderToString(latex, { output: "mathml", throwOnError: true });
    const mathml = (html.match(/<math[\s\S]*<\/math>/)?.[0] ?? "").replace(/<annotation[\s\S]*?<\/annotation>/g, "");
    const omml = wrapBareText(fillEmptyNary(mml2omml(mathml)));
    return omml.includes("<m:oMath") ? omml : null;
  } catch {
    return null;
  }
}

// Công thức đi qua docx dưới dạng chạy chữ giữ chỗ, rồi được thay bằng OMML sau khi đóng gói
// (thư viện docx không nhận XML công thức thô). Giữ chỗ mang sẵn OMML nên không cần trạng thái chung.
const MATH_OPEN = "⟦OMML:";
const MATH_CLOSE = "⟧";
const MATH_RUN = new RegExp(`<w:r>(?:<w:rPr>.*?</w:rPr>)?<w:t[^>]*>${MATH_OPEN}([DI])([^${MATH_CLOSE}]*)${MATH_CLOSE}</w:t></w:r>`, "g");

function mathRun(latex: string, display: boolean): TextRun {
  const omml = latexToOmml(latex);
  if (!omml) {
    // Không chuyển được: giữ LaTeX nguyên văn thay vì mất công thức.
    const d = display ? "$$" : "$";
    return new TextRun({ text: `${d}${latex}${d}`, font: FONT_MONO, size: 20, color: ACCENT });
  }
  return new TextRun({ text: `${MATH_OPEN}${display ? "D" : "I"}${encodeURIComponent(omml)}${MATH_CLOSE}` });
}

async function injectMath(docx: Blob): Promise<Blob> {
  const files = unzipSync(new Uint8Array(await docx.arrayBuffer()));
  const xml = strFromU8(files["word/document.xml"]);
  if (!xml.includes(MATH_OPEN)) return docx;
  files["word/document.xml"] = strToU8(
    xml.replace(MATH_RUN, (_, kind: string, enc: string) => {
      const omml = decodeURIComponent(enc);
      return kind === "D" ? `<m:oMathPara>${omml}</m:oMathPara>` : omml;
    }),
  );
  return new Blob([zipSync(files)], { type: docx.type });
}

function inlineRuns(nodes: MdNode[] | undefined, style: RunStyle = {}): ParagraphChild[] {
  return (nodes ?? []).flatMap((n): ParagraphChild[] => {
    switch (n.type) {
      case "text":
        return [new TextRun({ text: n.value ?? "", ...style })];
      case "strong":
        return inlineRuns(n.children, { ...style, bold: true });
      case "emphasis":
        return inlineRuns(n.children, { ...style, italics: true });
      case "inlineCode":
        return [new TextRun({ text: n.value ?? "", font: FONT_MONO, size: 20, ...style })];
      case "inlineMath":
        // Công thức giữ nguyên nội dung LaTeX gốc, chỉ đổi cách hiển thị.
        return [mathRun(n.value ?? "", false)];
      case "break":
        return [new TextRun({ text: "", break: 1 })];
      default:
        return n.children ? inlineRuns(n.children, style) : n.value ? [new TextRun({ text: n.value, ...style })] : [];
    }
  });
}

function blocks(nodes: MdNode[], depth = 0): Block[] {
  return nodes.flatMap((n): Block[] => {
    switch (n.type) {
      case "heading":
        return [
          new Paragraph({
            heading: n.depth && n.depth <= 2 ? HeadingLevel.HEADING_3 : HeadingLevel.HEADING_4,
            spacing: { before: 200, after: 80 },
            keepNext: true,
            children: inlineRuns(n.children),
          }),
        ];
      case "paragraph": {
        // remark-math coi `$$…$$` một dòng là inlineMath: đoạn chỉ có công thức thì dựng thành khối.
        const only = n.children?.length === 1 && n.children[0].type === "inlineMath" ? n.children[0] : null;
        if (only) return blocks([{ type: "math", value: only.value }], depth);
        return [
          new Paragraph({
            spacing: { after: 100, line: 300 },
            indent: depth ? { left: depth * INDENT_STEP } : undefined,
            children: inlineRuns(n.children),
          }),
        ];
      }
      case "math":
        return [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { before: 80, after: 140 },
            children: [mathRun(n.value ?? "", true)],
          }),
        ];
      case "code":
        return (n.value ?? "").split("\n").map(
          (line) =>
            new Paragraph({
              shading: { type: ShadingType.CLEAR, fill: "F3F4F2" },
              indent: { left: depth * INDENT_STEP },
              children: [new TextRun({ text: line, font: FONT_MONO, size: 20 })],
            }),
        );
      case "list":
        return listBlocks(n, depth);
      case "blockquote":
        return [
          new Paragraph({
            spacing: { after: 100, line: 300 },
            indent: { left: (depth + 1) * INDENT_STEP },
            border: { left: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 8 } },
            children: [new TextRun({ text: plainText(n), italics: true, color: TEXT_MUTED })],
          }),
        ];
      case "table":
        return [tableBlock(n), new Paragraph({ spacing: { after: 80 }, children: [] })];
      case "thematicBreak":
        return [new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BORDER } } })];
      default:
        return n.children ? blocks(n.children, depth) : [];
    }
  });
}

function listBlocks(list: MdNode, depth: number): Block[] {
  const left = (depth + 1) * INDENT_STEP;
  return (list.children ?? []).flatMap((item, i) => {
    const marker = list.ordered ? `${(list.start ?? 1) + i}.` : "•";
    const [first, ...rest] = item.children ?? [];
    const head: Block[] =
      first?.type === "paragraph"
        ? [
            new Paragraph({
              spacing: { after: 60, line: 300 },
              indent: { left, hanging: 280 },
              tabStops: [{ type: "left", position: left }],
              children: [new TextRun({ text: `${marker}\t` }), ...inlineRuns(first.children)],
            }),
          ]
        : first
          ? blocks([first], depth + 1)
          : [];
    return [...head, ...blocks(rest, depth + 1)];
  });
}

function tableBlock(table: MdNode): Table {
  const rows = (table.children ?? []).map(
    (row, r) =>
      new TableRow({
        tableHeader: r === 0,
        cantSplit: true,
        children: (row.children ?? []).map(
          (cell) =>
            new TableCell({
              shading: r === 0 ? { type: ShadingType.CLEAR, fill: ACCENT_SOFT } : undefined,
              margins: { top: 60, bottom: 60, left: 100, right: 100 },
              children: [new Paragraph({ children: inlineRuns(cell.children, r === 0 ? { bold: true } : {}) })],
            }),
        ),
      }),
  );
  const line = { style: BorderStyle.SINGLE, size: 4, color: BORDER };
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: { top: line, bottom: line, left: line, right: line, insideHorizontal: line, insideVertical: line },
    rows,
  });
}

// ───────────────────────── Bố cục tài liệu ─────────────────────────

function label(text: string, extra: { before?: number; borderTop?: boolean } = {}): Paragraph {
  return new Paragraph({
    spacing: { before: extra.before ?? 0, after: 80 },
    keepNext: true,
    border: extra.borderTop ? { top: { style: BorderStyle.SINGLE, size: 4, color: BORDER, space: 6 } } : undefined,
    children: [new TextRun({ text, bold: true, size: 18, color: TEXT_MUTED, characterSpacing: 40 })],
  });
}

function sourceLine(s: BackendSource): Paragraph {
  return new Paragraph({
    spacing: { after: 40 },
    indent: { left: 280, hanging: 280 },
    children: [
      new TextRun({ text: `[${s.index}] `, bold: true, color: ACCENT, size: 20 }),
      new TextRun({ text: s.file_stem, bold: true, size: 20 }),
      new TextRun({ text: s.section_path ? ` - ${s.section_path}` : "", color: TEXT_MUTED, size: 20 }),
    ],
  });
}

function questionBlock(text: string, n: number): Paragraph[] {
  return [
    new Paragraph({
      heading: HeadingLevel.HEADING_2,
      spacing: { before: 360, after: 100 },
      keepNext: true,
      children: [new TextRun(`Câu hỏi ${n}`)],
    }),
    new Paragraph({
      spacing: { after: 160, line: 300 },
      shading: { type: ShadingType.CLEAR, fill: ACCENT_SOFT },
      border: { left: { style: BorderStyle.SINGLE, size: 24, color: ACCENT, space: 8 } },
      indent: { left: 140 },
      children: [new TextRun({ text, bold: true })],
    }),
  ];
}

function answerBlock(m: Message): Block[] {
  const sources = m.sources ?? [];
  return [
    label("TRẢ LỜI"),
    ...blocks(parseMarkdown(m.markdown ?? "")),
    ...(sources.length > 0 ? [label("NGUỒN", { before: 160, borderTop: true }), ...sources.map(sourceLine)] : []),
  ];
}

export function buildDocx(title: string, messages: Message[], now: Date): Document {
  let n = 0;
  const body = exportableMessages(messages).flatMap((m): Block[] => (m.role === "user" ? questionBlock(m.text ?? "", ++n) : answerBlock(m)));
  return new Document({
    creator: "Trợ lý kiểm định",
    title,
    styles: {
      default: { document: { run: { font: FONT, size: BODY_SIZE } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 40, bold: true, color: ACCENT } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 26, bold: true, color: ACCENT } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 24, bold: true } },
        { id: "Heading4", name: "Heading 4", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 22, bold: true } },
      ],
    },
    sections: [
      {
        properties: { page: { margin: { top: 1134, bottom: 1134, left: 1247, right: 1247 } } },
        children: [
          new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { after: 60 }, children: [new TextRun(title)] }),
          new Paragraph({
            spacing: { after: 120 },
            border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 6 } },
            children: [
              new TextRun({
                text: `Hội thoại tra cứu quy trình kiểm định - xuất lúc ${now.toLocaleString("vi-VN")}`,
                color: TEXT_MUTED,
                size: 20,
              }),
            ],
          }),
          ...body,
        ],
      },
    ],
  });
}

export async function buildExportBlob(format: ExportFormat, title: string, messages: Message[], now: Date): Promise<Blob> {
  if (format === "json") {
    return new Blob([buildExportJson(title, messages, now)], { type: "application/json;charset=utf-8" });
  }
  return injectMath(await Packer.toBlob(buildDocx(title, messages, now)));
}

export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
