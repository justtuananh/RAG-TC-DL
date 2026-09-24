import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { DataRecordRow, FilterOptions } from "../../types";
import RecordsTable from "./RecordsTable";

// Kiểm accessibility của bảng dữ liệu: vai trò, aria, và các nút xuất xứ phải là
// <button> (điều hướng được bằng bàn phím) chứ không phải <span> bấm chuột.

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

function makeRow(overrides: Partial<DataRecordRow> = {}): DataRecordRow {
  return {
    id: 1,
    serial_no: "SN-1",
    device_id: 3,
    device_type_id: 1,
    device_type_name: "Van an toàn",
    quantity_id: 1,
    quantity_name: "Áp suất",
    model_code: "VA-1",
    manufacturer: "Acme",
    owner_org: "Nhà máy X",
    procedure_id: 1,
    procedure_number: "1.061",
    procedure_title: "Van an toàn",
    mode: "dinh_ky",
    mode_label: "Định kỳ",
    calibrated_at: "2024-01-15T00:00:00",
    expires_at: "2025-01-15T00:00:00",
    expires_from_fact_id: 9,
    verdict: "dat",
    verdict_label: "Đạt",
    cert_no: "C-1",
    lab_name: "Phòng đo",
    env_temp_c: 20,
    env_humidity_pct: 55,
    range_min: 0,
    range_max: 160000000,
    range_unit_code: "Pa",
    range_fact_id: 12,
    accuracy_text: "± 0,5 %",
    accuracy_fact_id: 13,
    measurement_count: 3,
    document_id: "BB_1",
    file_stem: "BB_1",
    extraction_id: 5,
    extraction_section_path: "Phụ lục A",
    extraction_chunk_id: "chunk-1",
    extraction_quote: "Số hiệu: SN-1",
    provenance: [
      { field: "calibrated_at", kind: "record", id: 1 },
      { field: "expires_at", kind: "record", id: 1 },
      { field: "env_temp_c", kind: "record", id: 1 },
      { field: "env_humidity_pct", kind: "record", id: 1 },
      { field: "range_min", kind: "fact", id: 12 },
      { field: "range_max", kind: "fact", id: 12 },
      { field: "accuracy_text", kind: "fact", id: 13 },
      { field: "measurement_count", kind: "record", id: 1 },
    ],
    ...overrides,
  };
}

function render(rows: DataRecordRow[] = [makeRow()], extra: Partial<Parameters<typeof RecordsTable>[0]> = {}) {
  return renderToStaticMarkup(
    <RecordsTable
      rows={rows}
      options={OPTIONS}
      filters={{ sort: "calibrated_at", order: "desc" }}
      sort="calibrated_at"
      order="desc"
      loading={false}
      error={null}
      selectedId={null}
      onFilterChange={() => {}}
      onSort={() => {}}
      onOpenRecord={() => {}}
      onOpenDevice={() => {}}
      onOpenProvenance={() => {}}
      {...extra}
    />,
  );
}

describe("RecordsTable — accessibility", () => {
  it("bảng có caption mô tả và role table", () => {
    const html = render();
    expect(html).toContain('role="table"');
    expect(html).toContain("<caption");
    expect(html).toContain("mỗi ô số bấm để mở đoạn nguyên văn nguồn");
  });

  it("cột sắp xếp dùng aria-sort và nút sắp xếp có nhãn", () => {
    const html = render();
    expect(html).toContain('aria-sort="descending"');
    expect(html).toContain("Sắp xếp theo Ngày kiểm định");
  });

  it("mọi ô lọc ở đầu cột đều có aria-label", () => {
    const html = render();
    for (const label of [
      "Lọc theo số hiệu, model, QTKĐ",
      "Lọc theo loại thiết bị",
      "Lọc theo đại lượng",
      "Lọc theo QTKĐ",
      "Lọc từ ngày kiểm định",
      "Lọc đến ngày kiểm định",
      "Phạm vi đo nhỏ nhất",
      "Phạm vi đo lớn nhất",
      "Đơn vị phạm vi đo",
      "Lọc theo cấp chính xác",
      "Lọc theo kết luận",
    ]) {
      expect(html).toContain(`aria-label="${label}"`);
    }
  });

  it("mỗi ô số là một <button> xuất xứ điều hướng được bằng bàn phím", () => {
    const html = render();
    expect(html).toContain('class="prov-cell"');
    expect(html).toContain('data-prov-kind="fact"');
    expect(html).toContain('data-prov-id="12"');
    expect(html).toContain('aria-label="Xem nguồn:');
    // Nút, không phải span: có type="button".
    expect(html).toContain('type="button"');
  });

  it("số hiệu thiết bị mở trang thiết bị bằng nút có nhãn", () => {
    const html = render();
    expect(html).toContain("Xem lịch sử thiết bị SN-1");
  });

  it("mở chi tiết hồ sơ bằng nút bàn phím, không chỉ click hàng", () => {
    const html = render();
    expect(html).toContain('aria-label="Xem chi tiết hồ sơ SN-1"');
  });

  it("trạng thái rỗng có thông báo thay vì bảng trống", () => {
    const html = render([]);
    expect(html).toContain("Không có hồ sơ đã duyệt khớp bộ lọc.");
  });

  it("lỗi hiển thị trong role=alert", () => {
    const html = render([makeRow()], { error: "Lỗi thử" });
    expect(html).toContain('role="alert"');
    expect(html).toContain("Lỗi thử");
  });
});
