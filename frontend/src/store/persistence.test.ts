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
