import { describe, it, expect, beforeEach, vi } from "vitest";
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

describe("persistence - bảo toàn dữ liệu chưa đọc được", () => {
  beforeEach(() => localStorage.clear());

  it.each(["{bad json", '{"conversations":[]}', '[null]'])("không ghi đè dữ liệu gốc sau khi nạp lỗi: %s", (raw) => {
    localStorage.setItem("qtkd.conversations.v1", raw);
    const loaded = loadConversations();
    saveConversations(loaded);
    expect(localStorage.getItem("qtkd.conversations.v1")).toBe(raw);
  });

  it("lưu trở lại sau khi dữ liệu gốc đã được khôi phục", () => {
    localStorage.setItem("qtkd.conversations.v1", "{bad json");
    loadConversations();
    const restored = [conv(isoDaysAgo(1))];
    localStorage.setItem("qtkd.conversations.v1", JSON.stringify(restored));
    expect(loadConversations()).toEqual(restored);
    saveConversations([]);
    expect(localStorage.getItem("qtkd.conversations.v1")).toBe("[]");
  });
});

describe("persistence - tiếp tục lưu sau khi sao lưu dữ liệu lỗi", () => {
  beforeEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

  it("giữ bản gốc trước khi lưu hội thoại mới", () => {
    const raw = "{bad json";
    localStorage.setItem("qtkd.conversations.v1", raw);
    loadConversations();
    const fresh = [conv(isoDaysAgo(0))];
    saveConversations(fresh);
    expect(loadConversations()).toEqual(fresh);
    const backupKeys = Object.keys(localStorage).filter((key) => key.startsWith("qtkd.conversations.v1.recovery."));
    expect(backupKeys).toHaveLength(1);
    expect(localStorage.getItem(backupKeys[0])).toBe(raw);
  });

  it("không ghi đè bản gốc khi sao lưu thất bại", () => {
    const raw = "{bad json";
    localStorage.setItem("qtkd.conversations.v1", raw);
    loadConversations();
    const storage = localStorage;
    vi.stubGlobal("localStorage", {
      getItem: storage.getItem.bind(storage),
      setItem: (key: string, value: string) => {
        if (key.includes(".recovery.")) throw new Error("quota");
        storage.setItem(key, value);
      },
    });
    try {
      saveConversations([conv(isoDaysAgo(0))]);
      expect(storage.getItem("qtkd.conversations.v1")).toBe(raw);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("nạp các hội thoại tốt khi xen một mục lỗi, sao lưu trước khi lưu lại", () => {
    const good = conv(isoDaysAgo(1));
    const raw = JSON.stringify([null, good]);
    localStorage.setItem("qtkd.conversations.v1", raw);
    const loaded = loadConversations();
    expect(loaded).toEqual([good]);
    expect(localStorage.getItem("qtkd.conversations.v1")).toBe(raw);
    saveConversations(loaded);
    expect(loadConversations()).toEqual([good]);
    const backupKeys = Object.keys(localStorage).filter((key) => key.startsWith("qtkd.conversations.v1.recovery."));
    expect(backupKeys).toHaveLength(1);
    expect(localStorage.getItem(backupKeys[0])).toBe(raw);
  });
});
