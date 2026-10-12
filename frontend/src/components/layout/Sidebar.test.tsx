import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Sidebar from "./Sidebar";
import type { AppState } from "../../types";
import type { Actions } from "../../store/useAppStore";

let root: Root;
let host: HTMLDivElement;
let narrow: boolean;
let notifyResize: (() => void) | undefined;
const actions = { go: vi.fn(), newChat: vi.fn() } as unknown as Actions;
const state = { tab: "docs", histSearch: "", conversations: [] } as unknown as AppState;
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  narrow = true;
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.stubGlobal("matchMedia", () => ({
    get matches() {
      return narrow;
    },
    addEventListener: (_event: string, callback: () => void) => {
      notifyResize = callback;
    },
    removeEventListener: () => {
      notifyResize = undefined;
    },
  }));
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});
afterEach(async () => {
  await act(async () => {
    root.unmount();
  });
  host.remove();
  vi.unstubAllGlobals();
});
const expandButton = () => host.querySelector('[aria-label="Mở rộng menu"]') as HTMLButtonElement | null;
async function mount() {
  await act(async () => {
    root.render(<Sidebar state={state} actions={actions} />);
  });
}
async function click(element: HTMLElement) {
  await act(async () => {
    element.click();
  });
}

describe("responsive navigation", () => {
  it("starts compact on mobile, permits expansion, and collapses after navigation", async () => {
    localStorage.setItem("nav_collapsed", "0");
    await mount();
    expect(expandButton()).not.toBeNull();
    expect(host.querySelector("aside")?.style.width).toBe("68px");
    await click(expandButton()!);
    expect(host.querySelector("aside")?.style.width).toBe("272px");
    await click(host.querySelector('[aria-label="Tài liệu"]') as HTMLElement);
    expect(actions.go).toHaveBeenCalledWith("docs");
    expect(expandButton()).not.toBeNull();
    expect(localStorage.getItem("nav_collapsed")).toBe("0");
  });
  it("adapts to viewport changes without overwriting the desktop preference", async () => {
    narrow = false;
    localStorage.setItem("nav_collapsed", "0");
    await mount();
    expect(expandButton()).toBeNull();
    await act(async () => {
      narrow = true;
      notifyResize?.();
    });
    expect(expandButton()).not.toBeNull();
    await act(async () => {
      narrow = false;
      notifyResize?.();
    });
    expect(expandButton()).toBeNull();
    expect(localStorage.getItem("nav_collapsed")).toBe("0");
  });
});
