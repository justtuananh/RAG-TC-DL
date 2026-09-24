import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  AuthError,
  ROLE_LABEL,
  TOKEN_KEY,
  authFetch,
  canWrite,
  clearToken,
  decodeToken,
  expiresWithin,
  fetchMe,
  getToken,
  isTokenExpired,
  login,
  logout,
  refreshToken,
  setToken,
  subscribeUnauthorized,
  userFromToken,
  type TokenPayload,
} from "./auth";

// ── helpers tạo JWT giả (chỉ cần 3 phần base64url; chữ ký không được xác thực ở client) ──
function b64url(obj: unknown): string {
  return btoa(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function makeToken(overrides: Partial<TokenPayload> = {}, expOffsetSec = 3600): string {
  const now = Math.floor(Date.now() / 1000);
  const payload: TokenPayload = {
    user_id: 7,
    username: "tech",
    role: "technician",
    exp: now + expOffsetSec,
    ...overrides,
  };
  return `${b64url({ alg: "HS256", typ: "JWT" })}.${b64url(payload)}.signature`;
}
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** fetch giả có tham số tường minh để đọc được `mock.calls[i][1]`. */
function mockFetch(impl: () => Promise<Response>) {
  return vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => impl());
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("lưu token ở localStorage", () => {
  it("get/set/clear round-trip", () => {
    expect(getToken()).toBeNull();
    setToken("abc.def.ghi");
    expect(getToken()).toBe("abc.def.ghi");
    expect(localStorage.getItem(TOKEN_KEY)).toBe("abc.def.ghi");
    clearToken();
    expect(getToken()).toBeNull();
  });
});

describe("decodeToken", () => {
  it("đọc đúng payload user_id/username/role/exp", () => {
    const token = makeToken({ user_id: 42, username: "kythuat", role: "technician" });
    const p = decodeToken(token);
    expect(p).toMatchObject({ user_id: 42, username: "kythuat", role: "technician" });
    expect(typeof p?.exp).toBe("number");
  });

  it("trả null cho token rỗng/sai định dạng", () => {
    expect(decodeToken(null)).toBeNull();
    expect(decodeToken("")).toBeNull();
    expect(decodeToken("not-a-jwt")).toBeNull();
    expect(decodeToken("a.b")).toBeNull();
  });

  it("trả null khi payload thiếu trường bắt buộc", () => {
    const bad = `${b64url({ alg: "HS256" })}.${b64url({ user_id: 1, username: "x" })}.sig`;
    expect(decodeToken(bad)).toBeNull();
  });

  it("trả null khi phần payload không phải JSON", () => {
    const raw = btoa("not json at all").replace(/=+$/, "");
    const bad = `${b64url({ alg: "HS256" })}.${raw}.sig`;
    expect(decodeToken(bad)).toBeNull();
  });
});

describe("isTokenExpired", () => {
  it("false khi exp ở tương lai", () => {
    expect(isTokenExpired(makeToken({}, 3600))).toBe(false);
  });

  it("true khi exp đã qua", () => {
    expect(isTokenExpired(makeToken({}, -10))).toBe(true);
  });

  it("true cho token thiếu/hỏng", () => {
    expect(isTokenExpired(null)).toBe(true);
    expect(isTokenExpired("garbage")).toBe(true);
  });

  it("so sánh theo mốc thời gian truyền vào", () => {
    const expSec = 1_000_000;
    const token = makeToken({ exp: expSec });
    expect(isTokenExpired(token, expSec * 1000 - 1)).toBe(false);
    expect(isTokenExpired(token, expSec * 1000)).toBe(true);
  });
});

describe("expiresWithin (gia hạn trượt sớm)", () => {
  it("true khi còn ít hơn ngưỡng", () => {
    expect(expiresWithin(makeToken({}, 1800), 3600 * 1000)).toBe(true);
  });

  it("false khi còn nhiều hơn ngưỡng", () => {
    expect(expiresWithin(makeToken({}, 7200), 3600 * 1000)).toBe(false);
  });

  it("false khi đã hết hạn hoặc thiếu token", () => {
    expect(expiresWithin(makeToken({}, -10), 3600 * 1000)).toBe(false);
    expect(expiresWithin(null, 3600 * 1000)).toBe(false);
  });
});

describe("vai trò & người dùng", () => {
  it("userFromToken dựng AuthUser từ payload", () => {
    const user = userFromToken(makeToken({ user_id: 5, username: "admin", role: "admin" }));
    expect(user).toEqual({ id: 5, username: "admin", full_name: null, role: "admin" });
  });

  it("canWrite đúng ma trận quyền", () => {
    expect(canWrite("technician")).toBe(true);
    expect(canWrite("admin")).toBe(true);
    expect(canWrite("viewer")).toBe(false);
    expect(canWrite("approver")).toBe(false);
    expect(canWrite(null)).toBe(false);
    expect(canWrite(undefined)).toBe(false);
  });

  it("ROLE_LABEL phủ đủ 4 vai trò", () => {
    expect(Object.keys(ROLE_LABEL).sort()).toEqual(["admin", "approver", "technician", "viewer"]);
  });
});

describe("authFetch", () => {
  it("gắn Authorization: Bearer khi có token", async () => {
    const token = makeToken();
    setToken(token);
    const spy = mockFetch(async () => jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", spy);

    await authFetch("/api/documents/x", { method: "DELETE" });

    const init = spy.mock.calls[0][1] as RequestInit;
    expect((init.headers as Headers).get("Authorization")).toBe(`Bearer ${token}`);
  });

  it("không gắn Authorization khi chưa đăng nhập", async () => {
    const spy = mockFetch(async () => jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", spy);

    await authFetch("/api/documents/x", { method: "DELETE" });

    const init = spy.mock.calls[0][1] as RequestInit;
    expect((init.headers as Headers).get("Authorization")).toBeNull();
  });

  it("gặp 401 thì xoá token và phát tín hiệu mở đăng nhập", async () => {
    setToken(makeToken());
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Invalid or expired token" }, 401)),
    );
    const handler = vi.fn();
    const unsubscribe = subscribeUnauthorized(handler);

    const res = await authFetch("/api/documents/x", { method: "DELETE" });

    expect(res.status).toBe(401);
    expect(getToken()).toBeNull();
    expect(handler).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it("không phát tín hiệu khi notifyOn401 = false (dùng lúc khôi phục phiên)", async () => {
    setToken(makeToken());
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "nope" }, 401)),
    );
    const handler = vi.fn();
    const unsubscribe = subscribeUnauthorized(handler);

    await authFetch("/api/auth/me", {}, { notifyOn401: false });

    expect(getToken()).toBeNull();
    expect(handler).not.toHaveBeenCalled();
    unsubscribe();
  });
});

describe("login / fetchMe / refresh / logout", () => {
  it("login thành công lưu token và trả người dùng", async () => {
    const token = makeToken({ user_id: 9, username: "kythuat", role: "technician" });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ access_token: token, token_type: "bearer" })),
    );

    const user = await login("kythuat", "mật-khẩu");

    expect(getToken()).toBe(token);
    expect(user).toMatchObject({ id: 9, username: "kythuat", role: "technician" });
  });

  it("login sai mật khẩu ném AuthError và KHÔNG lưu token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Sai tên đăng nhập hoặc mật khẩu." }, 401)),
    );

    await expect(login("kythuat", "sai")).rejects.toBeInstanceOf(AuthError);
    expect(getToken()).toBeNull();
  });

  it("fetchMe gửi bearer và trả hồ sơ đầy đủ", async () => {
    const token = makeToken();
    setToken(token);
    const spy = mockFetch(async () => jsonResponse({ id: 7, username: "tech", full_name: "Kỹ thuật", role: "technician" }));
    vi.stubGlobal("fetch", spy);

    const user = await fetchMe();

    expect(user.full_name).toBe("Kỹ thuật");
    expect(((spy.mock.calls[0][1] as RequestInit).headers as Headers).get("Authorization")).toBe(`Bearer ${token}`);
  });

  it("refreshToken lưu token mới", async () => {
    setToken(makeToken());
    const fresh = makeToken({ exp: 7200 });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ access_token: fresh, token_type: "bearer" })),
    );

    const returned = await refreshToken();

    expect(returned).toBe(fresh);
    expect(getToken()).toBe(fresh);
  });

  it("logout xoá token kể cả khi gọi server lỗi", async () => {
    setToken(makeToken());
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("mất mạng");
      }),
    );

    await logout();

    expect(getToken()).toBeNull();
  });
});
