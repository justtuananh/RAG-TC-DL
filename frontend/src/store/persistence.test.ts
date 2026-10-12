import { describe, it, expect, beforeEach } from "vitest";
import type { Conversation } from "../types";
import { groupOf, loadConversations, saveConversations } from "./persistence";

function conv(updatedAt: string): Conversation {
  return { id: "x", title: "Câu hỏi", snippet: "tóm tắt", pinned: false, createdAt: updatedAt, updatedAt, messages: [], liveSources: [], activeCite: "1" };
}
const isoDaysAgo = (n: number) => {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString();
};

describe("persistence", () => {
  beforeEach(() => localStorage.clear());

  it("load rỗng khi chưa có dữ liệu", () => {
    expect(loadConversations()).toEqual([]);
  });

  it("save rồi load = round-trip", () => {
    const list = [conv(isoDaysAgo(0))];
    saveConversations(list);
    expect(loadConversations()).toEqual(list);
  });

  it("load an toàn khi JSON hỏng", () => {
    localStorage.setItem("qtkd.conversations.v1", "{bad json");
    expect(loadConversations()).toEqual([]);
  });

  it("groupOf phân nhóm theo updatedAt", () => {
    expect(groupOf(isoDaysAgo(0))).toBe("today");
    expect(groupOf(isoDaysAgo(3))).toBe("week");
    expect(groupOf(isoDaysAgo(30))).toBe("older");
  });
});

describe("persistence - tin nhắn cũ của nhánh số liệu", () => {
  it("nạp được, bỏ branch/data, giữ phần văn bản", () => {
    localStorage.setItem(
      "qtkd.conversations.v1",
      JSON.stringify([
        {
          id: "c1",
          title: "Lần kiểm định gần nhất",
          snippet: "…",
          pinned: false,
          createdAt: isoDaysAgo(1),
          updatedAt: isoDaysAgo(1),
          liveSources: [],
          activeCite: "1",
          messages: [
            { role: "user", text: "Lần kiểm định gần nhất của SN-1?" },
            {
              role: "bot",
              markdown: "Kết quả tra cứu: …",
              branch: "data",
              data: { intent: "latest_record", branch: "data", tables: [], citations: [] },
              streaming: false,
            },
          ],
        },
      ]),
    );

    const [conv] = loadConversations();
    expect(conv.messages).toHaveLength(2);
    expect(conv.messages[1].markdown).toBe("Kết quả tra cứu: …");
    expect(conv.messages[1]).not.toHaveProperty("branch");
    expect(conv.messages[1]).not.toHaveProperty("data");
  });
});
