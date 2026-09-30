import ExcelJS from "exceljs";
import { afterEach, describe, expect, it, vi } from "vitest";
import { loadWorkbookModel } from "./loadWorkbook";

// Regression (review): cache mô hình workbook theo URL không bao giờ hết hạn, nên tải
// lên lại biên bản cùng tên với số liệu đã sửa vẫn hiện số cũ. Nay cache theo ETag.

async function xlsxBytes(value: string): Promise<ArrayBuffer> {
  const wb = new ExcelJS.Workbook();
  wb.addWorksheet("KQ KĐ").getCell("A1").value = value;
  return (await wb.xlsx.writeBuffer()) as ArrayBuffer;
}

function serve(files: Record<string, { etag: string; bytes: ArrayBuffer }>, key: () => string) {
  const fetchMock = vi.fn(async () => {
    const file = files[key()];
    return new Response(file.bytes, { status: 200, headers: { etag: file.etag } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const firstCell = (model: Awaited<ReturnType<typeof loadWorkbookModel>>) => model.sheets[0].rows[0].cells[0].display.text;

afterEach(() => vi.unstubAllGlobals());

describe("loadWorkbookModel", () => {
  it("ETag không đổi: dùng lại mô hình đã dựng", async () => {
    const fetchMock = serve({ v1: { etag: '"v1"', bytes: await xlsxBytes("0,34") } }, () => "v1");
    const a = await loadWorkbookModel("/api/documents/a/preview");
    const b = await loadWorkbookModel("/api/documents/a/preview");
    expect(b).toBe(a);
    expect(fetchMock).toHaveBeenCalledTimes(2); // luôn hỏi lại máy chủ
  });

  it("tệp được tải lên lại (ETag đổi): dựng lại, không hiện số liệu cũ", async () => {
    let version = "v1";
    serve(
      {
        v1: { etag: '"v1"', bytes: await xlsxBytes("0,34") },
        v2: { etag: '"v2"', bytes: await xlsxBytes("0,36") },
      },
      () => version,
    );
    expect(firstCell(await loadWorkbookModel("/api/documents/b/preview"))).toBe("0,34");
    version = "v2";
    expect(firstCell(await loadWorkbookModel("/api/documents/b/preview"))).toBe("0,36");
  });

  it("các lần gọi đồng thời dùng chung một lần tải", async () => {
    const fetchMock = serve({ v1: { etag: '"v1"', bytes: await xlsxBytes("x") } }, () => "v1");
    const [a, b] = await Promise.all([loadWorkbookModel("/api/documents/c/preview"), loadWorkbookModel("/api/documents/c/preview")]);
    expect(a).toBe(b);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
