import { afterEach, describe, expect, it, vi } from "vitest";
import {
  exportFilename,
  fetchProvenance,
  fetchRecords,
  provenanceParams,
} from "./dataApi";

// Xác nhận client dựng đúng URL cho bề mặt tra cứu dữ liệu và ánh xạ tham chiếu
// xuất xứ sang tham số truy vấn đúng loại (P1).

afterEach(() => {
  vi.unstubAllGlobals();
});

function mockJson(payload: unknown) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      calls.push(String(input));
      return { ok: true, status: 200, json: async () => payload } as unknown as Response;
    }),
  );
  return calls;
}

describe("dataApi", () => {
  it("provenanceParams ánh xạ đúng từng loại tham chiếu", () => {
    expect(provenanceParams({ field: "error", kind: "measurement", id: 7 })).toEqual({
      measurement_id: 7,
      field: "error",
    });
    expect(provenanceParams({ field: "range_min", kind: "fact", id: 12 })).toEqual({ fact_id: 12 });
    expect(provenanceParams({ field: "calibrated_at", kind: "record", id: 3 })).toEqual({ record_id: 3 });
    expect(provenanceParams({ field: "quote", kind: "extraction", id: 5 })).toEqual({ extraction_id: 5 });
  });

  it("fetchRecords gửi bộ lọc + phân trang trong query string", async () => {
    const calls = mockJson({ items: [], total: 0 });
    await fetchRecords({ verdict: "dat", limit: 25, offset: 50, sort: "calibrated_at", order: "desc" });
    expect(calls[0]).toContain("/api/data/records?");
    expect(calls[0]).toContain("verdict=dat");
    expect(calls[0]).toContain("limit=25");
    expect(calls[0]).toContain("offset=50");
    expect(calls[0]).toContain("sort=calibrated_at");
  });

  it("fetchProvenance gửi đúng measurement_id và field", async () => {
    const calls = mockJson({ kind: "measurement" });
    await fetchProvenance({ field: "error", kind: "measurement", id: 9 });
    expect(calls[0]).toContain("/api/data/provenance?");
    expect(calls[0]).toContain("measurement_id=9");
    expect(calls[0]).toContain("field=error");
  });

  it("exportFilename có tiền tố và đuôi .xlsx", () => {
    const name = exportFilename();
    expect(name.startsWith("du-lieu-kiem-dinh-")).toBe(true);
    expect(name.endsWith(".xlsx")).toBe(true);
  });
});
