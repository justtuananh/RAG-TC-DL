import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ChatDataPayload } from "../../types";
import DataResultTable from "./DataResultTable";

// Bảng kết quả số liệu trong chat (Sprint 9): mỗi ô số là <button> xuất xứ (P1),
// số hiệu thiết bị mở trang thiết bị, và KHÔNG nhét số vào văn xuôi.

const PAYLOAD: ChatDataPayload = {
  intent: "device_history",
  branch: "data",
  title: "Lịch sử kiểm định — Thiết bị SN-1",
  note: "Đọc từ sổ cái hồ sơ đã duyệt.",
  empty: false,
  tables: [
    {
      title: "Dòng thời gian kiểm định",
      note: null,
      total: 2,
      columns: [
        { key: "calibrated_at", label: "Ngày kiểm định" },
        { key: "serial_no", label: "Số hiệu" },
        { key: "measurement_count", label: "Số điểm đo" },
      ],
      rows: [
        {
          calibrated_at: { text: "15/01/2025", numeric: false, provenance: { field: "calibrated_at", kind: "record", id: 2 }, device_id: 3, record_id: 2 },
          serial_no: { text: "SN-1", numeric: false, provenance: null, device_id: 3, record_id: 2 },
          measurement_count: { text: "1", numeric: true, provenance: { field: "measurement_count", kind: "record", id: 2 }, device_id: 3, record_id: 2 },
        },
      ],
    },
  ],
  citations: [
    {
      kind: "record",
      file_stem: "BB_2024_001",
      document_id: "BB_2024_001",
      display_name: "BB_2024_001.docx",
      section_path: "Phụ lục A",
      chunk_id: "chunk-1",
      quote: "Số hiệu: SN-1",
      value_text: "SN-1",
    },
  ],
};

function render(payload: ChatDataPayload = PAYLOAD) {
  return renderToStaticMarkup(
    <DataResultTable payload={payload} onOpenProvenance={() => {}} onOpenDevice={() => {}} />,
  );
}

describe("DataResultTable — bảng số liệu chat", () => {
  it("dựng bảng có caption và nhãn sổ cái", () => {
    const html = render();
    expect(html).toContain('role="table"');
    expect(html).toContain("<caption");
    expect(html).toContain("Sổ cái đã duyệt");
  });

  it("ô số có tham chiếu xuất xứ là nút bàn phím (P1)", () => {
    const html = render();
    expect(html).toContain('class="prov-cell"');
    expect(html).toContain('data-prov-kind="record"');
    expect(html).toContain('aria-label="Xem nguồn: 1"');
    expect(html).toContain('type="button"');
  });

  it("số hiệu thiết bị mở trang thiết bị", () => {
    const html = render();
    expect(html).toContain("Xem lịch sử thiết bị SN-1");
    expect(html).toContain('data-prov-id="3"');
  });

  it("trích dẫn sổ cái hiển thị tách biệt", () => {
    const html = render();
    expect(html).toContain("Trích dẫn sổ cái");
    expect(html).toContain("BB_2024_001.docx");
  });

  it("trạng thái rỗng có thông báo", () => {
    const html = render({ ...PAYLOAD, empty: true, tables: [], citations: [] });
    expect(html).toContain("Không có dữ liệu đã duyệt phù hợp.");
  });
});
