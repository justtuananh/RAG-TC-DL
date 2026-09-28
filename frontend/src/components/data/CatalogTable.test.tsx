import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { CatalogRow } from "../../types";
import CatalogTable from "./CatalogTable";

// Bảng danh mục NAS: cột theo loại, ô tìm kiếm, lọc nhóm, nút nguồn, nhãn "Quá
// hạn" và dấu kế thừa "như trên". Kiểm bằng renderToStaticMarkup.

function makeRow(overrides: Partial<CatalogRow> = {}): CatalogRow {
  return {
    id: 1,
    ord: 1,
    document_id: "bieu3",
    extraction_id: 5,
    quote: "1 | Áp kế pittông | nt",
    display_name: "bieu3.xlsx",
    file_stem: "bieu3",
    provenance: {
      document_id: "bieu3",
      display_name: "bieu3.xlsx",
      file_stem: "bieu3",
      extraction_id: 5,
      quote: "1 | Áp kế pittông | nt",
    },
    ...overrides,
  };
}

const NOOP = () => undefined;

function render(rows: CatalogRow[], extra: Partial<Parameters<typeof CatalogTable>[0]> = {}) {
  return renderToStaticMarkup(
    <CatalogTable
      kind="lab_standard"
      rows={rows}
      groups={[]}
      q=""
      group=""
      loading={false}
      error={null}
      onSearch={NOOP}
      onGroup={NOOP}
      onOpenSource={NOOP}
      {...extra}
    />,
  );
}

describe("CatalogTable — chuẩn mẫu", () => {
  it("hiện cột hạn kế tiếp ước tính, quá hạn và dấu kế thừa", () => {
    const html = render([
      makeRow({
        name: "Áp kế píttông",
        model: "MΠ-6",
        serial: "5393",
        interval_text: "nt",
        last_cal_text: "6/2021 TTĐL",
        next_due_year: 2020,
        next_due_month: 1,
        next_due_derived: 1,
        inherited: ["interval", "last_calibration"],
      }),
    ]);
    expect(html).toContain("Hạn KĐ/HC kế tiếp (ước tính)");
    expect(html).toContain("01/2020");
    expect(html).toContain("Quá hạn");
    // Dấu kế thừa nhỏ kèm tooltip "như trên".
    expect(html).toContain('title="như trên"');
    expect(html).toContain('aria-label="như trên"');
    expect(html).toContain("Xem nguồn");
  });

  it("có ô tìm kiếm nhưng không có lọc nhóm cho chuẩn mẫu", () => {
    const html = render([]);
    expect(html).toContain('type="search"');
    expect(html).not.toContain("Lọc theo nhóm lĩnh vực");
    expect(html).toContain("Không có dòng đã duyệt khớp bộ lọc");
  });
});

describe("CatalogTable — danh mục quy trình", () => {
  it("hiện lọc nhóm, liên kết QTKĐ và dấu kế thừa issuer", () => {
    const html = renderToStaticMarkup(
      <CatalogTable
        kind="procedure_catalog"
        rows={[
          makeRow({
            ord: 2,
            group_code: "I",
            code_text: "QTKĐ 1.159:2021",
            title: "Qps kế Pít tông",
            issuer: "Cục TC - ĐL - CL",
            year_issued: 2022,
            inherited: ["issuer"],
            procedure_link: {
              procedure_id: 7,
              number: "1.159",
              title: "Áp kế pít tông",
              year: 2021,
              document_id: "QTKD_1.159",
            },
          }),
        ]}
        groups={[{ code: "I", title: "Lĩnh vực áp suất" }]}
        q=""
        group=""
        loading={false}
        onSearch={NOOP}
        onGroup={NOOP}
        onOpenSource={NOOP}
      />,
    );
    expect(html).toContain("Lọc theo nhóm lĩnh vực");
    expect(html).toContain("I - Lĩnh vực áp suất");
    expect(html).toContain("Đã có QTKĐ 1.159 trong kho");
    expect(html).toContain('title="như trên"');
  });
});
