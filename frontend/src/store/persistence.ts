import type { Conversation, ConvGroup } from "../types";

// Lưu/đọc lịch sử hội thoại ở localStorage (offline, 1 máy).
const KEY = "qtkd.conversations.v1";

export function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? (arr as Conversation[]) : [];
  } catch {
    return [];
  }
}

export function saveConversations(list: Conversation[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    /* hết quota / chế độ riêng tư — bỏ qua */
  }
}

/** Nhóm hội thoại theo updatedAt so với hôm nay. */
export function groupOf(updatedAt: string): ConvGroup {
  const t = new Date(updatedAt).getTime();
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (t >= startToday) return "today";
  if (t >= startToday - 86400000) return "yesterday";
  if (t >= startToday - 7 * 86400000) return "week";
  return "older";
}
