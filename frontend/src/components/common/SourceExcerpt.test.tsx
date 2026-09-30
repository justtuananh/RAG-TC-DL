import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import HighlightedMarkdown from "./HighlightedMarkdown";
import QuoteTable from "./QuoteTable";
import { parseQuoteRows, quotePreview } from "./quoteRows";
import SourceExcerpt from "./SourceExcerpt";

// Regression cho báo cáo người dùng: "Đoạn nguyên văn" in chuỗi thô
// "Ký hiệu: | МП-60 | Số hiệu: | 1045 | …" và Markdown thô (| --- |). Nguyên văn phải
// hiện đúng định dạng: bảng thật, công thức KaTeX, trích dẫn tô sáng.

const SECTION = [
  "Bảng A.1 - Xác định độ tụt áp",
  "",
  "| Lần đo | Áp suất kiểm tra, bar | Giá trị cho phép, bar |",
  "| --- | --- | --- |",
  "| 1 | 250 | 0,5 |",
  "",
  "Công thức $\\Delta p = p_1 - p_2$ tính độ tụt áp.",
].join("\n");

describe("HighlightedMarkdown", () => {
  it("render bảng pipe thành <table> và tô đúng ô chứa trích dẫn", () => {
    const start = SECTION.indexOf("250");
    const html = renderToStaticMarkup(<HighlightedMarkdown text={SECTION} start={start} end={start + 3} />);
    expect(html).toContain("<table");
    expect(html).not.toContain("| --- |");
    expect(html).toMatch(/<td>\s*<mark class="src-hl">250<\/mark>\s*<\/td>/);
  });

  it("tìm trích dẫn trong mục khi thiếu vị trí ký tự", () => {
    const html = renderToStaticMarkup(<HighlightedMarkdown text={SECTION} quote="Xác định độ tụt áp" />);
    expect(html).toContain('<mark class="src-hl">Xác định độ tụt áp</mark>');
  });

  it("công thức trong đoạn tô sáng vẫn render bằng KaTeX", () => {
    const start = SECTION.indexOf("Công thức");
    const html = renderToStaticMarkup(<HighlightedMarkdown text={SECTION} start={start} end={SECTION.length} />);
    expect(html).toContain("katex");
    expect(html).toMatch(/<mark class="src-hl">(?:(?!<\/mark>).)*katex/s);
  });

  it("không nhúng HTML thô của nguồn", () => {
    const html = renderToStaticMarkup(<HighlightedMarkdown text={'Đoạn <img src=x onerror="alert(1)"> nguồn'} />);
    expect(html).not.toContain("<img");
  });
});

describe("parseQuoteRows / QuoteTable", () => {
  it("tách dòng thành ô và nhóm theo sheet", () => {
    const groups = parseQuoteRows("[Sheet: Chọn quả]\nQuả số | Khối lượng\nGốc | 67,5707\n[Sheet: KQ KĐ]\nKý hiệu: | МП-60");
    expect(groups).toEqual([
      {
        sheet: "Chọn quả",
        rows: [
          ["Quả số", "Khối lượng"],
          ["Gốc", "67,5707"],
        ],
      },
      { sheet: "KQ KĐ", rows: [["Ký hiệu:", "МП-60"]] },
    ]);
  });

  it("một dòng trích dẫn thành một hàng bảng, ô giá trị được tô", () => {
    const html = renderToStaticMarkup(<QuoteTable quote="Ký hiệu: | МП-60 | Số hiệu: | 1045" value="1045" />);
    expect(html).not.toContain(" | ");
    expect((html.match(/<td/g) || []).length).toBe(4);
    expect(html).toMatch(/<td[^>]*font-weight:700[^>]*>1045<\/td>/);
  });
});

describe("quotePreview", () => {
  it("dòng bảng Markdown và trích dẫn hồ sơ hiện thành các ô nối bằng ·", () => {
    expect(quotePreview("| | - Kiểm tra tốc độ hạ của píttông | 5.2.4 | + | + | + |")).toBe("- Kiểm tra tốc độ hạ của píttông · 5.2.4 · + · + · +");
    expect(quotePreview("[Sheet: KQ KĐ]\nKý hiệu: | МП-60")).toBe("Ký hiệu: · МП-60");
    expect(quotePreview("Chu kỳ kiểm định là 12 tháng;")).toBe("Chu kỳ kiểm định là 12 tháng;");
  });
});

describe("SourceExcerpt", () => {
  it("không có mục văn bản và không định vị được: dựng trích dẫn thành bảng", () => {
    const html = renderToStaticMarkup(<SourceExcerpt quote="Ký hiệu: | МП-60" value="МП-60" />);
    expect(html).toContain("<table");
    expect(html).toContain("МП-60");
  });

  it("có mục văn bản: render Markdown của mục", () => {
    const html = renderToStaticMarkup(<SourceExcerpt sectionText={SECTION} quote="250" />);
    expect(html).toContain('class="md-doc md-source"');
    expect(html).toContain('<mark class="src-hl">250</mark>');
  });
});
