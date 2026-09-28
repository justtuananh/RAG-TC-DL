import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import FormulaReviewPanel from "./FormulaReviewPanel";
import * as api from "../../services/formulaApi";
import type { FormulaDraft } from "../../services/formulaApi";

vi.mock("../../services/formulaApi");
const sample = (id = "first", status: FormulaDraft["status"] = "pending_review"): FormulaDraft => ({
  id,
  revision: 1,
  status,
  proposal: {
    title: `Formula ${id}`,
    expression: "x*2",
    unit: "m",
    variables: [{ key: "x", label: "Chiều dài", unit: "m" }],
    conditions: [{ key: "valid", label: "Số liệu phù hợp" }],
    test_cases: [{ inputs: { x: { value: "2", unit: "m" } }, expected: "4", unit: "m" }],
  },
  source: { document_id: "test.docx", file: "test.docx", sha256: "hash", fid: id, kind: "equation", section: "1", latex: "y=2x", context: "Example" },
  warnings: [],
  validation_errors: [],
  review: null,
  history: [],
});
let host: HTMLDivElement;
let root: Root;
function button(text: string) {
  const match = [...host.querySelectorAll("button")].find((b) => b.textContent?.includes(text));
  if (!match) throw new Error(`Missing button: ${text}`);
  return match;
}
async function click(element: HTMLElement) {
  await act(async () => {
    element.click();
  });
}
async function input(label: string, value: string) {
  const element = host.querySelector(`[aria-label="${label}"]`) as HTMLInputElement;
  await act(async () => {
    const proto = element.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
async function mount(drafts: FormulaDraft[] = [sample()]) {
  vi.mocked(api.listFormulaDrafts).mockResolvedValue({ drafts, units: ["m", "cm"] });
  await act(async () => {
    root.render(<FormulaReviewPanel documentId="test.docx" isDocx />);
  });
}
beforeEach(() => {
  vi.resetAllMocks();
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});
afterEach(async () => {
  await act(async () => {
    root.unmount();
  });
  host.remove();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Formula review workflow", () => {
  it("requires reviewer, rationale and explicit confirmation before registering", async () => {
    const draft = sample();
    vi.mocked(api.decideFormulaDraft).mockResolvedValue({ ...draft, revision: 2, status: "approved" });
    await mount([draft]);
    expect(button("Phê duyệt và đăng ký").disabled).toBe(true);
    expect(host.textContent).not.toContain("Sử dụng bộ tính đã duyệt");
    await input("Người phê duyệt", "Người thử nghiệm");
    await input("Nhận xét và căn cứ", "Đối chiếu nguồn và đáp án độc lập");
    expect(button("Phê duyệt và đăng ký").disabled).toBe(true);
    const confirm = [...host.querySelectorAll('input[type="checkbox"]')].find((e) => e.parentElement?.textContent?.includes("Tôi đã đối chiếu"))!;
    await click(confirm as HTMLElement);
    expect(button("Phê duyệt và đăng ký").disabled).toBe(false);
    await click(button("Phê duyệt và đăng ký"));
    expect(api.decideFormulaDraft).toHaveBeenCalledWith(draft, "approve", "Người thử nghiệm", "Đối chiếu nguồn và đáp án độc lập", true);
    expect(host.textContent).toContain("Sử dụng bộ tính đã duyệt");
  });

  it("rejects with reviewer and rationale, without enabling calculation", async () => {
    const draft = sample();
    vi.mocked(api.decideFormulaDraft).mockResolvedValue({ ...draft, revision: 2, status: "rejected" });
    await mount([draft]);
    expect(button("Từ chối").disabled).toBe(true);
    await input("Người phê duyệt", "Người thử nghiệm");
    await input("Nhận xét và căn cứ", "Thiếu điều kiện nguồn");
    await click(button("Từ chối"));
    expect(api.decideFormulaDraft).toHaveBeenCalledWith(draft, "reject", "Người thử nghiệm", "Thiếu điều kiện nguồn", false);
    expect(host.textContent).toContain("Đã từ chối");
    expect(host.textContent).not.toContain("Sử dụng bộ tính đã duyệt");
  });

  it("saving changes to an approved definition returns to review", async () => {
    const draft = sample("first", "approved");
    await mount([draft]);
    vi.mocked(api.saveFormulaDraft).mockImplementation(async (_, proposal) => ({ ...draft, proposal, revision: 2, status: "pending_review" }));
    await input("Tên công thức", "Cần duyệt lại");
    expect(host.textContent).not.toContain("Sử dụng bộ tính đã duyệt");
    await click(button("Lưu bản nháp"));
    expect(host.textContent).toContain("Phiên bản 2");
    expect(button("Phê duyệt và đăng ký").disabled).toBe(true);
    expect(host.textContent).not.toContain("Sử dụng bộ tính đã duyệt");
  });

  it("keeps unsaved edits if switching or refresh is cancelled", async () => {
    await mount([sample(), sample("second")]);
    const confirm = vi.fn().mockReturnValue(false);
    vi.stubGlobal("confirm", confirm);
    await input("Tên công thức", "Chỉnh sửa chưa lưu");
    await click(button("second"));
    expect((host.querySelector('[aria-label="Tên công thức"]') as HTMLInputElement).value).toBe("Chỉnh sửa chưa lưu");
    await click(button("Tải lại danh sách"));
    expect(api.listFormulaDrafts).toHaveBeenCalledTimes(1);
    expect(confirm).toHaveBeenCalledTimes(2);
    confirm.mockReturnValue(true);
    await click(button("Tải lại danh sách"));
    expect((host.querySelector('[aria-label="Tên công thức"]') as HTMLInputElement).value).toBe("Formula first");
  });

  it("retains edits and shows version conflicts without approving", async () => {
    await mount();
    vi.mocked(api.saveFormulaDraft).mockRejectedValue(new Error("Phiên bản đã thay đổi"));
    await input("Tên công thức", "Bản của tôi");
    await click(button("Lưu bản nháp"));
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("Phiên bản đã thay đổi");
    expect((host.querySelector('[aria-label="Tên công thức"]') as HTMLInputElement).value).toBe("Bản của tôi");
    expect(api.decideFormulaDraft).not.toHaveBeenCalled();
  });

  it("calculates an approved version with inputs, units and conditions; clears obsolete results", async () => {
    const draft = sample("first", "approved");
    await mount([draft]);
    vi.mocked(api.calculateFormula).mockResolvedValue({ value: "6", unit: "m", source: "test.docx", source_hash: "hash", approved_by: "Reviewer" });
    expect(button("Tính kết quả").disabled).toBe(true);
    await input("Tính x", "3");
    expect(button("Tính kết quả").disabled).toBe(true);
    const condition = [...host.querySelectorAll('input[type="checkbox"]')].find((e) => e.parentElement?.textContent === "Số liệu phù hợp")!;
    await click(condition as HTMLElement);
    await click(button("Tính kết quả"));
    expect(api.calculateFormula).toHaveBeenCalledWith(draft, { x: { value: "3", unit: "m" } }, { valid: true });
    expect(host.textContent).toContain("6 m — test.docx — người duyệt: Reviewer");
    await input("Tính x", "4");
    expect(host.textContent).not.toContain("6 m — test.docx");
    await input("Biểu thức tính", "x*3");
    expect(host.textContent).not.toContain("Sử dụng bộ tính đã duyệt");
  });

  it("renames a variable in test case inputs so saved cases remain editable", async () => {
    await mount();
    vi.mocked(api.saveFormulaDraft).mockResolvedValue({ ...sample(), revision: 2 });
    await input("Tên biến 1", "length");
    await click(button("Lưu bản nháp"));
    const proposal = vi.mocked(api.saveFormulaDraft).mock.calls[0][1];
    expect(proposal.test_cases[0].inputs).toEqual({ length: { value: "2", unit: "m" } });
  });

  it("disables stale definitions and reports loading failures", async () => {
    await mount([sample("old", "stale")]);
    expect((host.querySelector('[aria-label="Tên công thức"]') as HTMLInputElement).closest("fieldset")?.disabled).toBe(true);
    expect(host.textContent).not.toContain("Sử dụng bộ tính đã duyệt");
    vi.mocked(api.listFormulaDrafts).mockRejectedValue(new Error("Mất kết nối máy chủ"));
    await click(button("Tải lại danh sách"));
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("Mất kết nối máy chủ");
  });
});

it("handles constructor variables and conditions without inherited values", async () => {
  const draft = sample("prototype", "approved");
  draft.proposal.variables.push({ key: "constructor", label: "Second", unit: "m" });
  draft.proposal.conditions.push({ key: "constructor", label: "Explicit second condition" });
  await mount([draft]);
  const checks = [...host.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')].filter((c) =>
    ["Số liệu phù hợp", "Explicit second condition"].includes(c.parentElement?.textContent ?? ""),
  );
  expect(checks).toHaveLength(2);
  expect(checks.every((c) => !c.checked)).toBe(true);
  await input("Tính x", "3");
  for (const c of checks) await click(c);
  expect(button("Tính kết quả").disabled).toBe(true);
  await input("Tính constructor", "4");
  expect(button("Tính kết quả").disabled).toBe(false);
  vi.mocked(api.calculateFormula).mockResolvedValue({ value: "7", unit: "m", source: "test.docx", source_hash: "hash", approved_by: "Reviewer" });
  await click(button("Tính kết quả"));
  expect(api.calculateFormula).toHaveBeenCalledWith(
    draft,
    { x: { value: "3", unit: "m" }, constructor: { value: "4", unit: "m" } },
    { valid: true, constructor: true },
  );
});
