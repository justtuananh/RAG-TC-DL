import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { FilterOptions } from "../../types";
import type { RecordFilters } from "../../services/dataApi";
import RecordFilterBar from "./RecordFilterBar";

// Thanh lọc: ô tìm kiếm, chip kết luận, khoảng ngày, hàng 2 tự mở khi có bộ lọc đang bật,
// dải chip gỡ lọc và tổng số hồ sơ đã duyệt.

const OPTIONS: FilterOptions = {
  device_types: [{ value: 1, label: "Van an toàn" }],
  quantities: [{ value: 1, label: "Áp suất" }],
  procedures: [{ value: 1, label: "1.061" }],
  verdicts: [
    { value: "dat", label: "Đạt" },
    { value: "khong_dat", label: "Không đạt" },
  ],
  sorts: ["calibrated_at"],
};

function render(filters: RecordFilters = {}, total = 20) {
  return renderToStaticMarkup(<RecordFilterBar filters={filters} options={OPTIONS} total={total} onChange={() => {}} />);
}

let root: Root | null = null;
let container: HTMLDivElement | null = null;

function mount(filters: RecordFilters, onChange: (patch: Partial<RecordFilters>) => void) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => {
    root?.render(<RecordFilterBar filters={filters} options={OPTIONS} total={20} onChange={onChange} />);
  });
  return container;
}

afterEach(() => {
  if (root) act(() => root?.unmount());
  root = null;
  container?.remove();
  container = null;
});

function clickByText(el: HTMLElement, text: string) {
  const button = Array.from(el.querySelectorAll("button")).find((item) => item.textContent?.trim() === text);
  if (!button) throw new Error(`Không tìm thấy nút ${text}`);
  act(() => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

describe("RecordFilterBar", () => {
  it("hàng 1 có ô tìm kiếm rộng, chip kết luận và khoảng ngày", () => {
    const html = render();
    expect(html).toContain('aria-label="Lọc theo số hiệu, model, QTKĐ"');
    expect(html).toContain("Tìm số hiệu, model, QTKĐ…");
    expect(html).toContain("Tất cả");
    expect(html).toContain("Đạt");
    expect(html).toContain("Không đạt");
    expect(html).toContain('aria-label="Lọc từ ngày kiểm định"');
    expect(html).toContain('aria-label="Lọc đến ngày kiểm định"');
    expect(html).toContain("Bộ lọc khác");
    expect(html).toContain("20 hồ sơ đã duyệt");
  });

  it("hàng 2 thu gọn mặc định", () => {
    const html = render();
    expect(html).not.toContain("Lọc theo cấp chính xác");
    expect(html).not.toContain("Mọi đại lượng");
  });

  it("hàng 2 tự mở khi có bộ lọc của hàng 2 đang bật", () => {
    const html = render({ accuracy: "± 0,5 %" });
    expect(html).toContain("Lọc theo cấp chính xác");
    expect(html).toContain("Mọi đại lượng");
    expect(html).toContain("Mọi QTKĐ");
  });

  it("giữ nguyên aria-label của mọi ô lọc", () => {
    const html = render({ device_type_id: 1 });
    for (const label of ["Lọc theo loại thiết bị", "Lọc theo đại lượng", "Lọc theo QTKĐ", "Phạm vi đo nhỏ nhất", "Phạm vi đo lớn nhất", "Đơn vị phạm vi đo", "Lọc theo cấp chính xác"]) {
      expect(html).toContain(`aria-label="${label}"`);
    }
  });

  it("chip bộ lọc đang bật có nút gỡ riêng", () => {
    const html = render({ search: "SN-1", verdict: "khong_dat" });
    expect(html).toContain('aria-label="Bỏ lọc Tìm: SN-1"');
    expect(html).toContain('aria-label="Bỏ lọc Kết luận: Không đạt"');
  });

  it("chip kết luận gọi onChange({ verdict })", () => {
    const onChange = vi.fn();
    const el = mount({}, onChange);
    clickByText(el, "Không đạt");
    expect(onChange).toHaveBeenCalledWith({ verdict: "khong_dat" });
  });

  it("nút gỡ chip gọi onChange xoá đúng bộ lọc", () => {
    const onChange = vi.fn();
    const el = mount({ search: "SN-1" }, onChange);
    const remove = el.querySelector<HTMLButtonElement>('button[aria-label="Bỏ lọc Tìm: SN-1"]');
    if (!remove) throw new Error("Không tìm thấy nút gỡ chip");
    act(() => {
      remove.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(onChange).toHaveBeenCalledWith({ search: undefined });
  });
});
