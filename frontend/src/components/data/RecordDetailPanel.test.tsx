import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { DataMeasurement, DataRecordRow } from "../../types";
import RecordDetailPanel from "./RecordDetailPanel";

// Panel "Chi tiết hồ sơ" > "Điểm đo": M1 đơn vị sai số riêng, M2 giá trị trống
// không kèm đơn vị, M3 cột Mốc có cả mục đo lẫn nhãn.

function makePoint(overrides: Partial<DataMeasurement> = {}): DataMeasurement {
  return {
    id: 1,
    record_id: 1,
    ord: 1,
    step_code: "A.4",
    label: "5",
    nominal_value: 5,
    measured_value: 5,
    error_value: 0.017,
    unit_id: 10,
    unit_code: "g",
    unit_name: "gam",
    error_unit_id: 20,
    error_unit_code: "%",
    limit_value: 0.05,
    within_limit: true,
    note: null,
    quote: "A.4 | 5 | 5 | 0,017 | 0,05",
    nominal_text: "5",
    measured_text: "5",
    error_text: "0,017",
    limit_text: "0,05",
    provenance: [
      { field: "nominal", kind: "measurement", id: 1 },
      { field: "measured", kind: "measurement", id: 1 },
      { field: "error", kind: "measurement", id: 1 },
      { field: "limit", kind: "measurement", id: 1 },
    ],
    ...overrides,
  };
}

function makeRecord(measurements: DataMeasurement[]): DataRecordRow {
  return {
    id: 1,
    serial_no: "SN-1",
    device_id: 3,
    device_type_id: 1,
    device_type_name: "Áp kế píttông tiêu chuẩn",
    quantity_id: 1,
    quantity_name: "Áp suất",
    model_code: null,
    manufacturer: null,
    owner_org: null,
    procedure_id: 1,
    procedure_number: "1.159",
    procedure_title: null,
    mode: "dinh_ky",
    mode_label: "Định kỳ",
    calibrated_at: "2024-01-15T00:00:00",
    expires_at: null,
    expires_from_fact_id: null,
    verdict: "dat",
    verdict_label: "Đạt",
    cert_no: null,
    lab_name: null,
    env_temp_c: null,
    env_humidity_pct: null,
    range_min: null,
    range_max: null,
    range_min_display: null,
    range_max_display: null,
    range_unit_code: null,
    range_fact_id: null,
    accuracy_text: null,
    accuracy_fact_id: null,
    measurement_count: measurements.length,
    document_id: "BB_1",
    file_stem: "BB_1",
    extraction_id: 5,
    extraction_section_path: "Phụ lục A",
    extraction_chunk_id: "chunk-1",
    extraction_quote: null,
    provenance: [],
    measurements,
  };
}

function render(measurements: DataMeasurement[]): string {
  return renderToStaticMarkup(
    <RecordDetailPanel
      record={makeRecord(measurements)}
      loading={false}
      onClose={() => {}}
      onOpenProvenance={() => {}}
      onOpenDevice={() => {}}
    />,
  );
}

describe("RecordDetailPanel — điểm đo", () => {
  it("M1: sai số và giới hạn dùng đơn vị riêng error_unit_code", () => {
    const html = render([makePoint()]);
    expect(html).toContain("0.017 %");
    expect(html).toContain("0.05 %");
    // Không dùng nhầm đơn vị giá trị đo (g).
    expect(html).not.toContain("0.017 g");
  });

  it("M2: giá trị trống hiện — không kèm đơn vị", () => {
    const html = render([
      makePoint({
        error_value: null,
        error_text: null,
        error_unit_id: null,
        error_unit_code: null,
        unit_code: "kgf/cm2",
        limit_value: null,
        limit_text: null,
      }),
    ]);
    expect(html).toContain("—");
    expect(html).not.toContain("— kgf/cm2");
  });

  it("M3: cột Mốc hiện cả mục đo lẫn nhãn", () => {
    const html = render([makePoint({ step_code: "A.4", label: "5" })]);
    expect(html).toContain("A.4 · 5");
  });

  it("M4: giá trị và đơn vị nằm trên một dòng (không xuống dòng)", () => {
    const html = render([makePoint()]);
    expect(html).toMatch(/white-space:\s*nowrap/);
  });

  it("M4: bảng điểm đo cuộn ngang trong panel thay vì bị xén cột", () => {
    const html = render([makePoint()]);
    expect(html).toMatch(/overflow-x:\s*auto/);
  });

  it("M3: thiếu mục đo hoặc nhãn vẫn có nhãn mốc", () => {
    expect(render([makePoint({ step_code: "A.4", label: null })])).toContain("A.4");
    expect(render([makePoint({ step_code: null, label: "5" })])).toContain("5");
  });
});
