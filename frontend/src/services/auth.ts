import type { AuthUser, UserRole } from "../types";

// ── Phiên đăng nhập phía client (Sprint 1) ──
// Token JWT lưu ở localStorage. Các route ĐỌC/CHAT vẫn công khai (không cần token);
// chỉ route GHI (upload / process / delete / rename) mới gắn `Authorization: Bearer`.
// Backend là nơi xác thực chữ ký — ở đây chỉ giải mã payload để biết vai trò/hạn.

export const TOKEN_KEY = "qtkd.auth.token";

/** Vai trò được phép thao tác ghi — khớp ma trận quyền ở backend (§5.6). */
export const WRITE_ROLES: readonly UserRole[] = ["technician", "admin"];

export const ROLE_LABEL: Record<UserRole, string> = {
  viewer: "Người xem",
  technician: "Kỹ thuật viên",
  approver: "Người duyệt",
  admin: "Quản trị viên",
};

export interface TokenPayload {
  user_id: number;
  username: string;
  role: UserRole;
  exp: number; // epoch giây
}

/** Lỗi xác thực kèm mã HTTP để nơi gọi phân biệt 401 (hết phiên) với lỗi khác. */
export class AuthError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "AuthError";
    this.status = status;
  }
}

// ── localStorage (bọc try/catch cho chế độ riêng tư / hết quota) ──
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* noop */
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* noop */
  }
}

// ── Giải mã JWT (base64url) — KHÔNG xác thực chữ ký ──
function base64UrlDecode(input: string): string {
  const b64 = input.replace(/-/g, "+").replace(/_/g, "/");
  const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

export function decodeToken(token: string | null | undefined): TokenPayload | null {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const raw = JSON.parse(base64UrlDecode(parts[1]));
    if (typeof raw?.user_id !== "number" || typeof raw?.username !== "string" || typeof raw?.role !== "string" || typeof raw?.exp !== "number") {
      return null;
    }
    return { user_id: raw.user_id, username: raw.username, role: raw.role as UserRole, exp: raw.exp };
  } catch {
    return null;
  }
}

/** Token thiếu/hỏng/đã quá hạn đều coi là hết hiệu lực. */
export function isTokenExpired(token: string | null | undefined, nowMs: number = Date.now()): boolean {
  const payload = decodeToken(token);
  if (!payload) return true;
  return payload.exp * 1000 <= nowMs;
}

export function userFromToken(token: string | null | undefined): AuthUser | null {
  const p = decodeToken(token);
  if (!p) return null;
  return { id: p.user_id, username: p.username, full_name: null, role: p.role };
}

/** Token sẽ hết hạn trong vòng `withinMs` (để gia hạn trượt sớm). Token đã hết hạn → false. */
export function expiresWithin(token: string | null | undefined, withinMs: number, nowMs: number = Date.now()): boolean {
  const payload = decodeToken(token);
  if (!payload) return false;
  const remaining = payload.exp * 1000 - nowMs;
  return remaining > 0 && remaining <= withinMs;
}

export function canWrite(role: UserRole | null | undefined): boolean {
  return !!role && WRITE_ROLES.includes(role);
}

// ── Tín hiệu 401 toàn cục → mở màn hình đăng nhập ──
type UnauthorizedHandler = () => void;
const unauthorizedHandlers = new Set<UnauthorizedHandler>();

/** Đăng ký nhận tín hiệu khi một request gặp 401 (token hết hạn/bị từ chối). */
export function subscribeUnauthorized(handler: UnauthorizedHandler): () => void {
  unauthorizedHandlers.add(handler);
  return () => {
    unauthorizedHandlers.delete(handler);
  };
}

export function notifyUnauthorized(): void {
  for (const handler of unauthorizedHandlers) handler();
}

export interface AuthFetchOptions {
  /** true (mặc định): phát tín hiệu mở màn hình đăng nhập khi gặp 401. */
  notifyOn401?: boolean;
}

/**
 * fetch có kèm bearer token (dùng cho route ghi + /me + /refresh).
 * Gặp 401 thì xoá token hỏng và (mặc định) phát tín hiệu để UI mở đăng nhập.
 */
export async function authFetch(input: RequestInfo | URL, init: RequestInit = {}, options: AuthFetchOptions = {}): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(input, { ...init, headers });
  if (res.status === 401) {
    clearToken();
    if (options.notifyOn401 !== false) notifyUnauthorized();
  }
  return res;
}

// ── API xác thực (backend api_server.py /api/auth/*) ──
async function _errorMessage(res: Response, fallback: string): Promise<string> {
  const body = await res.json().catch(() => null);
  return body?.detail || fallback;
}

/** POST /api/auth/login → lưu token, trả về người dùng suy từ token. */
export async function login(username: string, password: string): Promise<AuthUser> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    throw new AuthError(await _errorMessage(res, "Đăng nhập thất bại."), res.status);
  }
  const data = (await res.json()) as { access_token?: string };
  if (!data?.access_token) throw new AuthError("Máy chủ không trả về token.", 500);
  setToken(data.access_token);
  // Token hợp lệ nhưng payload lạ → vẫn vào được với quyền thấp nhất.
  return userFromToken(data.access_token) ?? { id: 0, username, full_name: null, role: "viewer" };
}

/** GET /api/auth/me — dùng khi khôi phục phiên từ localStorage để lấy họ tên/vai trò. */
export async function fetchMe(): Promise<AuthUser> {
  const res = await authFetch("/api/auth/me", {}, { notifyOn401: false });
  if (!res.ok) throw new AuthError(await _errorMessage(res, "Không đọc được thông tin người dùng."), res.status);
  return (await res.json()) as AuthUser;
}

/** POST /api/auth/refresh — gia hạn trượt, trả token mới và lưu lại. */
export async function refreshToken(): Promise<string> {
  const res = await authFetch("/api/auth/refresh", { method: "POST" }, { notifyOn401: false });
  if (!res.ok) throw new AuthError(await _errorMessage(res, "Không làm mới được phiên đăng nhập."), res.status);
  const data = (await res.json()) as { access_token?: string };
  if (!data?.access_token) throw new AuthError("Máy chủ không trả về token.", 500);
  setToken(data.access_token);
  return data.access_token;
}

/** POST /api/auth/logout (best-effort) rồi luôn xoá token phía client. */
export async function logout(): Promise<void> {
  try {
    await authFetch("/api/auth/logout", { method: "POST" }, { notifyOn401: false });
  } catch {
    /* mất mạng cũng không sao — token client vẫn bị xoá ở finally */
  } finally {
    clearToken();
  }
}
