import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Actions } from "../../store/useAppStore";
import type { AppState, BackendSource } from "../../types";
import SourcePanel from "./SourcePanel";

// Ô "Đoạn trả lời" hiện `quote` (đoạn con + công thức nó nói tới), không chỉ dòng
// "trong đó: … là …" của đoạn con (QTKĐ 1.159 mục 6.3.2).

const DEFINITION = "$A_{0s}$ là diện tích hiệu dụng của píttông chuẩn, m2;";

const SOURCE: BackendSource = {
  index: 1,
  file_stem: "QTKD_1.159_2021_ND_FINAL",
  section_path: "6.3.2 Xác định diện tích hiệu dụng",
  kind: "paragraph",
  snippet: DEFINITION,
  rerank_score: 0.99,
  parent_text: "Phần đầu mục.",
  child_text: DEFINITION,
  quote: `| $P_{s,i} = \\frac{F}{A_{0s}}$ |  |\n| --- | --- |\n\ntrong đó:\n\n${DEFINITION}`,
};

function highlighted(source: BackendSource): string {
  const state = { liveSources: [source], activeCite: "1", pulse: 0, sourceW: 430 } as unknown as AppState;
  const html = renderToStaticMarkup(<SourcePanel state={state} actions={{} as Actions} />);
  return html.slice(html.indexOf("Đoạn trả lời"), html.indexOf("Ngữ cảnh đầy đủ"));
}

describe("SourcePanel", () => {
  it("tô sáng đoạn trích có công thức", () => {
    const box = highlighted(SOURCE);
    expect(box).toContain("katex");
    expect(box).toContain("trong đó:");
  });

  it("hội thoại cũ không có quote thì tô sáng đoạn con", () => {
    const box = highlighted({ ...SOURCE, quote: undefined });
    expect(box).toContain("diện tích hiệu dụng");
    expect(box).not.toContain("trong đó:");
  });
});
