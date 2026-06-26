import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import Markdown from "./Markdown";

// Regression cho lỗi render bảng + công thức (báo cáo người dùng):
// nguồn QTKĐ dùng bảng pipe `| … |` và công thức `$…$` ngay trong ô.
// Thiếu remark-gfm → bảng render thành text thô; sau khi thêm phải ra <table>.
function html(md: string): string {
  return renderToStaticMarkup(<Markdown>{md}</Markdown>);
}

describe("Markdown — bảng (remark-gfm)", () => {
  const TABLE = ["| TT | Tên | Phạm vi |", "| --- | --- | --- |", "| 1 | Áp kế | 0–60 MPa |"].join("\n");

  it("render bảng pipe thành <table> chứ không phải text thô", () => {
    const out = html(TABLE);
    expect(out).toContain("<table");
    expect(out).toContain("<th");
    expect(out).toContain("<td");
    expect(out).toContain("Phạm vi");
    expect(out).not.toContain("| TT |"); // không còn pipe thô
  });
});

describe("Markdown — công thức (KaTeX)", () => {
  it("render $…$ inline thành KaTeX", () => {
    const out = html("Khối lượng $M = P \\times A_0$ theo công thức.");
    expect(out).toContain("katex");
  });

  it("render công thức NẰM TRONG ô bảng", () => {
    const md = ["| Đại lượng | Công thức |", "| --- | --- |", "| Khối lượng | $M = P \\times A_0$ |"].join("\n");
    const out = html(md);
    expect(out).toContain("<table");
    expect(out).toContain("katex");
  });
});

describe("Markdown — chip trích dẫn [n] (rehype-raw)", () => {
  it("giữ nút .cite-chip do withCiteButtons chèn vào", () => {
    const out = html('Xem chi tiết <button class="cite-chip" data-cite="1">[1]</button>.');
    expect(out).toContain("cite-chip");
    expect(out).toContain('data-cite="1"');
  });
});
