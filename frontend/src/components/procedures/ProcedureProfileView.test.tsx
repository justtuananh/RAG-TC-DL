import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ProcedureFact, ProcedureProfile } from "../../types";
import ProcedureProfileView, { type ReviewInfo } from "./ProcedureProfileView";

// Trang Hồ sơ QTKĐ: đủ khối khi có tri thức, thông báo rõ khi chưa duyệt gì, và mọi giá
// trị nguyên văn đều là nút mở nguồn.

function fact(overrides: Partial<ProcedureFact>): ProcedureFact {
  return {
    id: 1,
    extraction_id: 10,
    fact_kind: "working_range",
    label: "Phạm vi đo",
    rel_op: "range",
    value_min: null,
    value_max: 140000000,
    value_text: "đến 1 400 bar",
    condition_text: null,
    unit_code: "Pa",
    section_path: "1 Phạm vi áp dụng",
    ...overrides,
  };
}

const ALL = { ban_dau: true, dinh_ky: true, sau_sua_chua: true };

function makeProfile(overrides: Partial<ProcedureProfile> = {}): ProcedureProfile {
  return {
    procedure: {
      id: 2,
      number: "1.061",
      year: 2021,
      title: "VAN AN TOÀN CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar",
      edition: "ND_V2",
      device_type_id: 1,
      device_type_name: "Van an toàn",
      quantity_name: "Áp suất",
    },
    document: { id: "QTKD_1.061_2021_ND_V2", file_stem: "QTKD_1.061_2021_ND_V2", display_name: "QTKD_1.061_2021_ND_V2.docx" },
    parameters: [
      { kind: "working_range", label: "Phạm vi đo", items: [fact({})] },
      { kind: "accuracy_class", label: "Cấp chính xác", items: [] },
      { kind: "max_permissible_error", label: "Sai số cho phép lớn nhất", items: [] },
      {
        kind: "calibration_interval",
        label: "Chu kỳ kiểm định",
        items: [fact({ id: 3, fact_kind: "calibration_interval", label: "Chu kỳ kiểm định", value_text: "12 tháng" })],
      },
    ],
    conditions: [fact({ id: 4, fact_kind: "env_condition", label: "Nhiệt độ môi trường", value_text: "(20 ± 5) oC" })],
    modes: [
      { key: "ban_dau", label: "Ban đầu" },
      { key: "dinh_ky", label: "Định kỳ" },
      { key: "sau_sua_chua", label: "Sau sửa chữa" },
    ],
    steps: [
      { fact_id: 7, label: "Kiểm tra đo lường", section_ref: "6.3", depth: 0, modes: ALL },
      { fact_id: 7, label: "Xác định độ chênh áp", section_ref: "6.3.2", depth: 1, modes: ALL },
    ],
    formulas: [],
    standards: [{ id: 5, extraction_id: 50, ord: 1, name_vi: "Áp kế chuẩn", range_text: "(0 ÷ 1600) bar", accuracy_text: "0,05 %", note: null }],
    terms: [{ id: 6, extraction_id: 60, term_vi: "Độ chênh áp", term_en: "blowdown", definition: "là độ chênh lệch giữa áp suất chỉnh đặt và áp suất đóng" }],
    records: { total: 0, devices: 0, latest_at: null, verdicts: { dat: 0, khong_dat: 0 }, recent: [] },
    ...overrides,
  };
}

const noop = () => {};
const handlers = { onOpenProvenance: noop, onOpenDocument: noop, onAsk: noop, onOpenDevice: noop, onOpenRecords: noop, onOpenReview: noop };

const VIEWER: ReviewInfo = { canReview: false, pending: null, loading: false };

function render(profile: ProcedureProfile, review: ReviewInfo = VIEWER): string {
  return renderToStaticMarkup(<ProcedureProfileView profile={profile} review={review} {...handlers} />);
}

describe("ProcedureProfileView", () => {
  it("hiện số hiệu kèm năm, tên và loại thiết bị", () => {
    const html = render(makeProfile());
    expect(html).toContain("QTKĐ 1.061:2021");
    expect(html).toContain("VAN AN TOÀN CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar");
    expect(html).toContain("Van an toàn");
  });

  it("giá trị nguyên văn là nút mở nguồn của đúng dữ kiện", () => {
    const html = render(makeProfile());
    expect(html).toMatch(/data-prov-kind="fact" data-prov-id="1"[^>]*>đến 1 400 bar/);
    expect(html).toContain("12 tháng");
  });

  it("nói rõ nhóm thông số chưa có dữ kiện thay vì bỏ trống", () => {
    expect(render(makeProfile())).toContain("Chưa có dữ kiện đã duyệt");
  });

  it("ma trận phép kiểm định lùi dòng con và chỉ hiện một nút nguồn cho ô gộp", () => {
    const html = render(makeProfile());
    expect(html).toContain("Xác định độ chênh áp");
    expect(html).toContain("padding-left:32px");
    // Mọi dòng mở được nguồn, kể cả dòng con bóc từ ô gộp (cùng dữ kiện gốc).
    expect(html).toContain("Xem nguyên văn: Xác định độ chênh áp");
    expect(html.match(/data-prov-id/g)?.length ?? 0).toBeGreaterThan(0);
    // Ô có dấu tích có chữ cho trình đọc màn hình; icon chỉ trang trí.
    expect(html).toContain("Áp dụng khi kiểm định định kỳ");
    expect(html).toMatch(/<svg[^>]*aria-hidden="true"/);
  });

  it("thuật ngữ hiện cả tên tiếng Anh và định nghĩa", () => {
    const html = render(makeProfile());
    expect(html).toContain("blowdown");
    expect(html).toContain("là độ chênh lệch giữa áp suất chỉnh đặt và áp suất đóng");
  });

  it("chưa có tri thức đã duyệt: thông báo và lối sang hàng đợi cho người duyệt", () => {
    const empty = makeProfile({
      parameters: makeProfile().parameters.map((group) => ({ ...group, items: [] })),
      conditions: [],
      steps: [],
      standards: [],
      terms: [],
    });
    const html = render(empty, { canReview: true, pending: 38, loading: false });
    expect(html).toContain("Chưa có tri thức nào của QTKĐ này được duyệt");
    expect(html).toContain("đang có 38 dòng chờ duyệt");
    expect(html).toContain("Mở hàng đợi duyệt");
    expect(html).not.toContain("Thông số kỹ thuật");
    // Người xem thường: không có nút duyệt, được hướng dẫn liên hệ người duyệt.
    const viewer = render(empty, VIEWER);
    expect(viewer).not.toContain("Mở hàng đợi duyệt");
    expect(viewer).toContain("liên hệ người duyệt");
    // Người duyệt trong lúc đang đếm: không bảo "liên hệ người duyệt", chưa hiện nút.
    const counting = render(empty, { canReview: true, pending: null, loading: true });
    expect(counting).not.toContain("liên hệ người duyệt");
    expect(counting).not.toContain("Mở hàng đợi duyệt");
    expect(render(empty, { canReview: true, pending: 0, loading: false })).toContain("không còn dòng nào chờ duyệt");
  });

  it("tóm tắt biên bản theo quy trình", () => {
    const html = render(
      makeProfile({
        records: {
          total: 2,
          devices: 1,
          latest_at: "2025-01-15T00:00:00",
          verdicts: { dat: 1, khong_dat: 1 },
          recent: [
            {
              id: 9,
              device_id: 3,
              serial_no: "SN-1",
              device_type_name: "Van an toàn",
              calibrated_at: "2025-01-15T00:00:00",
              verdict: "khong_dat",
              mode: "dinh_ky",
              cert_no: "C-2",
            },
          ],
        },
      }),
    );
    expect(html).toContain("15/01/2025");
    expect(html).toContain("SN-1");
    expect(html).toContain("Định kỳ · Biên bản C-2");
    expect(html).toContain("Xem tất cả trong tab Dữ liệu");
  });
});
