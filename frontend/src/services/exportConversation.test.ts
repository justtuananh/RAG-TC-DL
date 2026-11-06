import { describe, expect, it } from "vitest";
import { unzipSync, strFromU8 } from "fflate";
import type { Message } from "../types";
import { buildExportBlob, buildExportJson, exportFileName, exportableMessages } from "./exportConversation";

const NOW = new Date("2026-11-06T10:00:00Z");

const messages: Message[] = [
  { role: "user", text: "Áp suất tính thế nào?" },
  {
    role: "bot",
    markdown:
      "## Công thức\n\nÁp suất $p=\\frac{F}{S}$:\n\n$$p=\\frac{F}{S}$$\n\n- **Bước 1**: đo F\n- Bước 2\n\n| Đại lượng | Đơn vị |\n|---|---|\n| p | MPa |",
    sources: [{ index: 1, file_stem: "QTKĐ 1.159", section_path: "6.3.2", kind: "para", snippet: "", rerank_score: 1, parent_text: "", child_text: "" }],
  },
  { role: "user", text: "Câu đang chờ" },
  { role: "bot", markdown: "đang gõ", streaming: true },
  { role: "bot", markdown: "lỗi", error: true },
];

describe("exportableMessages", () => {
  it("drops streaming, errored and empty messages", () => {
    expect(exportableMessages(messages).map((m) => m.role)).toEqual(["user", "bot", "user"]);
  });
});

describe("exportFileName", () => {
  it("strips path-unsafe characters and appends date and extension", () => {
    expect(exportFileName('A/B: "C"?', "docx", NOW)).toBe("A B C - 2026-11-06.docx");
  });
  it("falls back when the title is empty", () => {
    expect(exportFileName("///", "json", NOW)).toBe("hoi-thoai - 2026-11-06.json");
  });
});

describe("buildExportJson", () => {
  it("keeps verbatim LaTeX and sources, without transient messages", () => {
    const data = JSON.parse(buildExportJson("T", messages, NOW));
    expect(data.exportedAt).toBe(NOW.toISOString());
    expect(data.messages).toHaveLength(3);
    expect(data.messages[1].markdown).toContain("$p=\\frac{F}{S}$");
    expect(data.messages[1].sources[0].file_stem).toBe("QTKĐ 1.159");
  });
});

describe("buildExportBlob docx", () => {
  it("produces a docx whose body has the question, formula, table and source", async () => {
    const blob = await buildExportBlob("docx", "Áp suất", messages, NOW);
    const files = unzipSync(new Uint8Array(await blob.arrayBuffer()));
    const xml = strFromU8(files["word/document.xml"]);
    expect(xml).toContain("Câu hỏi 1");
    expect(xml).toContain("Áp suất tính thế nào?");
    expect(xml).toContain("$p=\\frac{F}{S}$");
    expect(xml).toContain("$$p=\\frac{F}{S}$$");
    expect(xml).toContain("<w:tbl>");
    expect(xml).toContain("QTKĐ 1.159");
    expect(xml).not.toContain("đang gõ");
  });
});
