import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Actions } from "../../store/useAppStore";
import type { AppState, AuthState } from "../../types";
import DataTab from "./DataTab";

// Thanh chọn loại dữ liệu dạng tab (role=tablist) thay cho <select> cũ.

const AUTH: AuthState = {
  user: { id: 1, username: "kythuat", full_name: null, role: "viewer" },
  enabled: true,
  loginOpen: false,
  loginBusy: false,
  loginError: null,
  loginNotice: null,
  restoreDone: true,
};

function render() {
  const state = { auth: AUTH, pendingDeviceId: null } as unknown as AppState;
  return renderToStaticMarkup(<DataTab state={state} actions={{} as unknown as Actions} />);
}

describe("DataTab — thanh tab loại dữ liệu", () => {
  it("có role=tablist và đủ các loại dữ liệu", () => {
    const html = render();
    expect(html).toContain('role="tablist"');
    expect(html).toContain('role="tab"');
    expect(html).toContain("Hồ sơ kiểm định");
    expect(html).toContain("Chuẩn mẫu");
    expect(html).toContain("Kiểm định viên");
    expect(html).toContain("Danh mục tiêu chuẩn, quy trình");
    expect(html).toContain("Lĩnh vực công nhận");
  });

  it("tab Hồ sơ kiểm định được chọn mặc định", () => {
    const html = render();
    expect(html).toContain('aria-selected="true"');
    expect(html).toMatch(/aria-selected="true"[^>]*>Hồ sơ kiểm định/);
  });
});
