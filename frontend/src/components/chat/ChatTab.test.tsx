import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Actions } from "../../store/useAppStore";
import type { AppState, BackendSource } from "../../types";
import ChatTab from "./ChatTab";

// Thanh nguồn bên phải ẩn mặc định, chỉ hiện khi người dùng bấm [n]/chip nguồn (sourceOpen).

const SOURCE: BackendSource = {
  index: 1,
  file_stem: "QTKD_1.061_2021_ND_V2",
  section_path: "7 Xử lý chung",
  kind: "paragraph",
  snippet: "Chu kỳ kiểm định của van an toàn là 12 tháng.",
  rerank_score: 0.9,
  parent_text: "Chu kỳ kiểm định của van an toàn là 12 tháng.",
  child_text: "Chu kỳ kiểm định của van an toàn là 12 tháng.",
};

function render(sourceOpen: boolean): string {
  const state = {
    tab: "chat",
    input: "",
    proc: null,
    activeCite: "1",
    pulse: 0,
    pinIndex: -1,
    sourceW: 430,
    sourceOpen,
    messages: [],
    liveSources: [SOURCE],
    examples: [],
    streaming: false,
  } as unknown as AppState;
  const actions = new Proxy({}, { get: () => () => undefined }) as unknown as Actions;
  return renderToStaticMarkup(<ChatTab state={state} actions={actions} />);
}

describe("ChatTab", () => {
  it("ẩn thanh nguồn khi chưa bấm vào nguồn", () => {
    expect(render(false)).not.toContain("Nguồn của câu trả lời");
  });

  it("hiện thanh nguồn sau khi bấm vào nguồn", () => {
    expect(render(true)).toContain("Nguồn của câu trả lời");
  });
});
