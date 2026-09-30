import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import ExcelJS from "exceljs";
import { describe, expect, it } from "vitest";
import { DEFAULT_THEME } from "./colors";
import { buildSheetModel, buildWorkbookModel, columnWidthPx, GRIDLINE, sliceRows, type MeasureText, type SheetModel } from "./sheetModel";

// Đo chữ tất định: 7 px mỗi ký tự (không có canvas trong happy-dom).
const measure: MeasureText = (text) => text.length * 7;

function sheet(build: (ws: ExcelJS.Worksheet) => void): SheetModel {
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet("KQ KĐ");
  build(ws);
  return buildSheetModel(ws, DEFAULT_THEME, { measure });
}

const cellAt = (model: SheetModel, row: number, col: number) => model.rows.find((r) => r.index === row)?.cells.find((c) => c.col === col);

describe("columnWidthPx", () => {
  it("độ rộng mặc định 8,43 ký tự = 64 px như Excel", () => {
    expect(columnWidthPx(9.140625)).toBe(64);
  });
});

describe("buildSheetModel - lưới ô", () => {
  it("ô gộp thành colSpan/rowSpan và bỏ các ô bị che", () => {
    const model = sheet((ws) => {
      ws.getCell("A1").value = "TRUNG TÂM ĐO LƯỜNG";
      ws.mergeCells("A1:C2");
      ws.getCell("D3").value = 1;
    });
    const master = cellAt(model, 0, 0);
    expect(master?.colSpan).toBe(3);
    expect(master?.rowSpan).toBe(2);
    expect(cellAt(model, 0, 1)).toBeUndefined();
    expect(cellAt(model, 1, 0)).toBeUndefined();
    expect(cellAt(model, 0, 3)).toBeDefined();
  });

  it("bỏ cột ẩn khỏi lưới", () => {
    const model = sheet((ws) => {
      ws.getCell("A1").value = "a";
      ws.getCell("B1").value = "b";
      ws.getCell("C1").value = "c";
      ws.getColumn(2).hidden = true;
    });
    expect(model.cols.map((c) => c.index)).toEqual([0, 2]);
    expect(model.rows[0].cells.map((c) => c.col)).toEqual([0, 2]);
  });

  it("số theo numFmt, căn phải; công thức dùng kết quả đã lưu", () => {
    const model = sheet((ws) => {
      ws.getCell("A1").value = 67.5707;
      ws.getCell("A1").numFmt = "0.00000";
      ws.getCell("B1").value = { formula: "A1*2", result: 135.1414 };
      ws.getColumn(1).width = 20;
      ws.getColumn(2).width = 20;
    });
    expect(cellAt(model, 0, 0)?.display.text).toBe("67,57070");
    expect(cellAt(model, 0, 0)?.style.textAlign).toBe("right");
    expect(cellAt(model, 0, 1)?.display.text).toBe("135,1414");
  });

  it("số General quá rộng được làm tròn bớt như Excel, số cố định thì ###, giá trị đầy đủ ở tooltip", () => {
    const model = sheet((ws) => {
      ws.getCell("A1").value = 67.5680034394153;
      ws.getCell("B1").value = 16893.58119;
      ws.getCell("B1").numFmt = "#,##0.00000";
      ws.getColumn(1).width = 7;
      ws.getColumn(2).width = 7;
    });
    const general = cellAt(model, 0, 0);
    expect(general?.display.text).toMatch(/^67,5\d*$/);
    expect(general?.title).toBe("67,56800344");
    const fixed = cellAt(model, 0, 1);
    expect(fixed?.display.text).toMatch(/^#+$/);
    expect(fixed?.title).toBe("16.893,58119");
  });

  it("chữ dài tràn sang ô trống bên phải, không tràn qua ô có dữ liệu", () => {
    const model = sheet((ws) => {
      ws.getCell("A1").value = "Phương pháp kiểm định:";
      ws.getCell("A2").value = "Nhiệt độ môi trường:";
      ws.getCell("B2").value = "(21 ± 2) ºC";
    });
    const spilled = cellAt(model, 0, 0);
    expect(spilled?.contentStyle.position).toBe("relative");
    expect(Number(spilled?.contentStyle.width)).toBeGreaterThan(64);
    expect(spilled?.style.borderRight).toBe("none");
    const blocked = cellAt(model, 1, 0);
    expect(blocked?.contentStyle.width).toBeUndefined();
    expect(blocked?.style.borderRight).toBe(GRIDLINE);
  });

  it("shrinkToFit thu cỡ chữ cho vừa ô, không tràn sang ô bên cạnh", () => {
    const model = sheet((ws) => {
      ws.getCell("A1").value = "PHÒNG ĐL NHIỆT-ÁP SUẤT";
      ws.getCell("A1").font = { size: 14 };
      ws.getCell("A1").alignment = { shrinkToFit: true };
    });
    const cell = cellAt(model, 0, 0);
    expect(cell?.contentStyle.width).toBeUndefined();
    expect(parseFloat(String(cell?.contentStyle.fontSize))).toBeLessThan(14);
  });

  it("ô gộp lệch metric chút ít: thu vừa khít thay vì cắt chữ; lệch nhiều thì giữ cỡ chữ", () => {
    const model = sheet((ws) => {
      ws.getCell("A1").value = "x".repeat(19); // 133 px chữ trong 122 px (2 cột 64 px trừ lề): 11pt × 122/133
      ws.mergeCells("A1:B1");
      ws.getCell("A2").value = "x".repeat(40);
      ws.mergeCells("A2:B2");
    });
    const slight = cellAt(model, 0, 0);
    expect(slight?.contentStyle.fontSize).toBe("10.09pt");
    expect(slight?.contentStyle.width).toBeUndefined();
    expect(cellAt(model, 1, 0)?.contentStyle.fontSize).toBeUndefined();
  });

  it("viền trái của ô bên cạnh được vẽ thành cạnh phải của ô này", () => {
    const model = sheet((ws) => {
      ws.getCell("A1").value = "x";
      ws.getCell("B1").value = "y";
      ws.getCell("B1").border = { left: { style: "medium", color: { argb: "FFFF0000" } } };
    });
    expect(cellAt(model, 0, 0)?.style.borderRight).toBe("2px solid #FF0000");
  });

  it("ô tô nền che đường lưới; tắt lưới thì không kẻ", () => {
    const filled = sheet((ws) => {
      ws.getCell("A1").value = "x";
      ws.getCell("A1").fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FFFFFF00" } };
    });
    expect(cellAt(filled, 0, 0)?.style.background).toBe("#FFFF00");
    expect(cellAt(filled, 0, 0)?.style.borderBottom).toBe("none");

    const noGrid = sheet((ws) => {
      ws.views = [{ showGridLines: false }];
      ws.getCell("A1").value = "x";
    });
    expect(noGrid.showGridLines).toBe(false);
    expect(cellAt(noGrid, 0, 0)?.style.borderBottom).toBe("none");
  });

  it("ký tự Wingdings của ô đánh dấu hiện thành ô vuông Unicode", () => {
    const model = sheet((ws) => {
      ws.getCell("A1").value = " Đạt";
      ws.getCell("A2").value = " Không đạt";
    });
    expect(cellAt(model, 0, 0)?.display.text).toBe("☑ Đạt");
    expect(cellAt(model, 1, 0)?.display.text).toBe("☐ Không đạt");
  });
});

describe("sliceRows - trích đoạn quanh một dòng", () => {
  it("dời ô gộp bắt đầu phía trên xuống dòng đầu cửa sổ", () => {
    const model = sheet((ws) => {
      ws.getCell("A1").value = "Bảng 2";
      ws.mergeCells("A1:A4");
      ws.getCell("B5").value = "cuối";
    });
    const window = sliceRows(model, 2, 3);
    expect(window.rows.map((r) => r.index)).toEqual([2, 3]);
    const carried = window.rows[0].cells.find((c) => c.col === 0);
    expect(carried?.display.text).toBe("Bảng 2");
    expect(carried?.rowSpan).toBe(2);
  });
});

describe("buildWorkbookModel - biên bản thật", () => {
  it("đọc đủ sheet và giữ nguyên văn ô đầu mục", async () => {
    const file = resolve(__dirname, "../../../../../TC_DL/Biên_bản_kiểm_định_áp_kế_pittông_SN_1045_2023-06-20.xlsx");
    const wb = new ExcelJS.Workbook();
    const bytes = readFileSync(file);
    await wb.xlsx.load(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
    const model = buildWorkbookModel(wb, { measure });
    expect(model.sheets.map((s) => s.name)).toEqual(["Chọn quả", "KQ KĐ", "KQ KĐ (2)", "Tính toán"]);
    const texts = model.sheets[1].rows.flatMap((r) => r.cells.map((c) => c.display.text));
    expect(texts).toContain("МП-60");
    expect(texts.some((t) => t.startsWith("Phạm vi đo"))).toBe(true);
  });
});
