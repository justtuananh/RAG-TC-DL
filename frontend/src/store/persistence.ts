import type { Conversation, ConvGroup, Message } from "../types";

// Lưu/đọc lịch sử hội thoại ở localStorage (offline, 1 máy).
const KEY = "qtkd.conversations.v1";
// Không để effect tự lưu ghi đè dữ liệu chưa đọc được bằng danh sách rỗng.
let unreadableRaw: string | null = null;

/**
 * Tin nhắn lưu trước khi gỡ nhánh số liệu còn trường `branch`/`data`;
 * bỏ chúng khi nạp, giữ nguyên mọi trường khác.
 */
function dropDataBranch(conv: Conversation): Conversation {
  if (!Array.isArray(conv.messages)) return conv;
  const messages = conv.messages.map((m) => {
    const { branch: _branch, data: _data, ...rest } = m as Message & { branch?: unknown; data?: unknown };
    return rest;
  });
  return { ...conv, messages };
}

export function loadConversations(): Conversation[] {
  let raw: string | null = null;
  unreadableRaw = null;
  try {
    raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) {
      unreadableRaw = raw;
      return [];
    }
    return (arr as Conversation[]).flatMap((conv) => {
      try {
        return [dropDataBranch(conv)];
      } catch {
        // Một mục hỏng không được che mất các hội thoại còn đọc được.
        unreadableRaw = raw;
        return [];
      }
    });
  } catch {
    unreadableRaw = raw;
    return [];
  }
}

export function saveConversations(list: Conversation[]): void {
  try {
    if (unreadableRaw !== null && localStorage.getItem(KEY) === unreadableRaw) {
      if (list.length === 0) return;
      // Chỉ thay dữ liệu gốc sau khi lưu bản sao nguyên vẹn thành công.
      localStorage.setItem(`${KEY}.recovery.${crypto.randomUUID()}`, unreadableRaw);
      unreadableRaw = null;
    }
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
