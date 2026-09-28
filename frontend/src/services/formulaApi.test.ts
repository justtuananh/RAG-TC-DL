import { afterEach, describe, expect, it, vi } from "vitest";
import { listFormulaDrafts } from "./formulaApi";

afterEach(() => {
  vi.unstubAllGlobals();
});
describe("formula API failures", () => {
  it("reports revision conflicts with a recovery instruction", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Phiên bản đã thay đổi" }), { status: 409 })));
    await expect(listFormulaDrafts("test")).rejects.toThrow("sao chép phần chỉnh sửa cần giữ");
  });
  it("reports an upstream HTML error instead of a JSON parsing exception", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>Unavailable</html>", { status: 503 })));
    await expect(listFormulaDrafts("test")).rejects.toThrow("HTTP 503");
  });
});

const validDraft = () => ({
  id: "draft",
  revision: 1,
  status: "pending_review",
  proposal: { title: "", expression: "", unit: "", variables: [], conditions: [], test_cases: [] },
  source: { document_id: "example", file: "example.docx", sha256: "hash", fid: "F001", kind: "omml", section: "", latex: "", context: "" },
  warnings: [],
  validation_errors: ["Cần bổ sung"],
  review: null,
  history: [],
});
function respond(body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async () => new Response(JSON.stringify(body))),
  );
}
describe("formula response contract", () => {
  it("preserves incomplete drafts without adding approval or changing their fields", async () => {
    const data = { drafts: [validDraft()], units: ["Pa"] };
    respond(data);
    expect(await listFormulaDrafts("example")).toEqual(data);
  });
  it.each([
    ["variables", null],
    ["conditions", null],
    ["test_cases", null],
    ["title", { text: "unsafe shape" }],
    ["variables", [null]],
    ["variables", [{ key: "a", label: {}, unit: "Pa" }]],
    ["conditions", [{ key: "valid", label: [] }]],
    ["test_cases", [{ expected: "2", unit: "Pa", inputs: null }]],
    ["test_cases", [{ expected: "2", unit: "Pa", inputs: { a: { unit: "Pa", value: {} } } }]],
    ["test_cases", [{ expected: "2", unit: "Pa", inputs: { a: { unit: "Pa", value: [null] } } }]],
  ])("rejects malformed proposal.%s before it can reach the editor", async (key, value) => {
    const draft = validDraft();
    Object.assign(draft.proposal, { [key as string]: value });
    respond({ drafts: [draft], units: ["Pa"] });
    await expect(listFormulaDrafts("example")).rejects.toThrow("không đúng cấu trúc");
  });
});
