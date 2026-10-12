import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Actions } from "../../store/useAppStore";
import type { AppState, DocItem } from "../../types";
import DocsTab from "./DocsTab";

// Tab Tài liệu: upload chỉ nhận Word/PDF; tab "Đã thay thế" lọc tài liệu
// superseded (QTKĐ cũ đã có phiên bản mới hơn).

function doc(partial: Partial<DocItem> & Pick<DocItem, "id" | "name" | "status">): DocItem {
  return { ext: "PDF", size: "1 MB", pages: "—", date: "01/01/2026", ...partial };
}

function render(documents: DocItem[], filter: AppState["docStatusFilter"] = "all"): string {
  const state = {
    documents,
    docStatusFilter: filter,
    docSearch: "",
    docPageSize: 20,
    docPage: 1,
    renamingDoc: null,
    viewingDoc: null,
  } as unknown as AppState;
  return renderToStaticMarkup(<DocsTab state={state} actions={{} as Actions} />);
}

const SUPERSEDED_NOTE = "Đã có phiên bản mới hơn: QTKĐ 1.061 2026.docx";

const DOCS: DocItem[] = [
  doc({ id: "s1", name: "QTKĐ 1.061 bản cũ.pdf", status: "superseded", error: SUPERSEDED_NOTE }),
  doc({ id: "s2", name: "QTKĐ 2.014 bản cũ.pdf", status: "superseded", error: "Đã có phiên bản mới hơn: QTKĐ 2.014 2026.pdf" }),
  doc({ id: "r1", name: "Biên bản kiểm định mới.docx", status: "ready" }),
];

describe("DocsTab - ô tải lên chỉ nhận Word/PDF", () => {
  it("input file có accept .docx,.doc,.pdf, không nhận Excel", () => {
    const html = render([DOCS[2]]);
    expect(html).toContain('accept=".docx,.doc,.pdf"');
    expect(html).not.toContain(".xlsx");
    expect(html).not.toContain(".xls");
  });
});

describe("DocsTab - tab Đã thay thế", () => {
  it("lọc đúng tài liệu superseded và đếm đúng số", () => {
    const html = render(DOCS, "superseded");
    // Tab mang nhãn "Đã thay thế" kèm số đếm 2.
    expect(html).toMatch(/Đã thay thế<span[^>]*>2<\/span>/);
    expect(html).toContain("2 tệp");
    expect(html).toContain("QTKĐ 1.061 bản cũ.pdf");
    expect(html).toContain("QTKĐ 2.014 bản cũ.pdf");
    expect(html).not.toContain("Biên bản kiểm định mới.docx");
  });

  it("hiện câu trong error làm chú thích, không tô màu lỗi", () => {
    const html = render([DOCS[0]], "superseded");
    expect(html).toContain(SUPERSEDED_NOTE);
    expect(html).not.toContain("#C8102E"); // màu danger của trạng thái error
  });
});
