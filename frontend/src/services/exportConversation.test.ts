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
    // công thức thành công thức Word thật (phân số), cả inline lẫn khối
    expect(xml).toContain("<m:f>");
    expect(xml).toContain("<m:oMathPara>");
    expect(xml.match(/<m:oMath[ >]/g)).toHaveLength(2);
    expect(xml).not.toContain("⟦OMML");
    expect(xml).toContain("<w:tbl>");
    expect(xml).toContain("QTKĐ 1.159");
    expect(xml).not.toContain("đang gõ");
  });

  it("keeps verbatim LaTeX when a formula cannot be converted", async () => {
    const bad: Message[] = [{ role: "bot", markdown: "Công thức $\\badmacro{x}$ ở đây" }];
    const blob = await buildExportBlob("docx", "T", bad, NOW);
    const xml = strFromU8(unzipSync(new Uint8Array(await blob.arrayBuffer()))["word/document.xml"]);
    expect(xml).toContain("$\\badmacro{x}$");
    expect(xml).not.toContain("<m:oMath");
  });

  it("puts the term after a sum into the sum body, leaving no empty placeholder", async () => {
    const sum: Message[] = [{ role: "bot", markdown: "$$\\sum_{i=1}^{n} x_i$$" }];
    const blob = await buildExportBlob("docx", "T", sum, NOW);
    const xml = strFromU8(unzipSync(new Uint8Array(await blob.arrayBuffer()))["word/document.xml"]);
    expect(xml).toMatch(/<m:nary>.*<m:e><m:sSub>.*<\/m:sSub><\/m:e><\/m:nary>/s);
    expect(xml).not.toContain("<m:e/>");
  });

  it("wraps text the converter leaves bare, so every character sits in an m:t", async () => {
    const md: Message[] = [{ role: "bot", markdown: "$$\\int_0^1 f(x)\\,dx$$" }];
    const blob = await buildExportBlob("docx", "T", md, NOW);
    const xml = strFromU8(unzipSync(new Uint8Array(await blob.arrayBuffer()))["word/document.xml"]);
    const math = xml.slice(xml.indexOf("<m:oMathPara>"), xml.indexOf("</m:oMathPara>"));
    expect(math).toContain("(x)");
    expect(math).not.toMatch(/<\/(m:r|m:sub|m:sup)>[^<\s]/);
    expect(math.replace(/<m:t[^>]*>[^<]*<\/m:t>/g, "")).not.toMatch(/>[^<\s]+</);
  });
});
