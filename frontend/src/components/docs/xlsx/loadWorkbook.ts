import { buildWorkbookModel, type WorkbookModel } from "./sheetModel";

// Tải + dựng mô hình workbook cho trình xem tài liệu và ngăn xuất xứ. ExcelJS (~1 MB)
// chỉ được tải khi thật sự mở tệp Excel (dynamic import).
//
// Mỗi lần mở đều hỏi lại máy chủ (`cache: "no-cache"`), vì tệp cùng tên có thể đã được
// tải lên lại với số liệu đã sửa: chỉ dùng lại mô hình đã dựng khi ETag không đổi, để
// không bao giờ hiện số liệu cũ. Các lần gọi đồng thời cho cùng URL dùng chung một lần tải.

interface CachedModel {
  version: string;
  model: WorkbookModel;
}

const MAX_CACHED = 8;
const models = new Map<string, CachedModel>();
const inflight = new Map<string, Promise<WorkbookModel>>();

function remember(url: string, entry: CachedModel): void {
  models.delete(url);
  models.set(url, entry);
  while (models.size > MAX_CACHED) models.delete(models.keys().next().value as string);
}

async function fetchAndBuild(url: string): Promise<WorkbookModel> {
  const [{ default: ExcelJS }, response] = await Promise.all([import("exceljs"), fetch(url, { cache: "no-cache" })]);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error((body as { detail?: string } | null)?.detail || `HTTP ${response.status}`);
  }
  const version = response.headers.get("etag") ?? response.headers.get("last-modified");
  const cached = models.get(url);
  if (version && cached?.version === version) return cached.model;

  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(await response.arrayBuffer());
  const model = buildWorkbookModel(workbook);
  if (version) remember(url, { version, model });
  else models.delete(url);
  return model;
}

export function loadWorkbookModel(url: string): Promise<WorkbookModel> {
  const pending = inflight.get(url);
  if (pending) return pending;
  const job = fetchAndBuild(url);
  inflight.set(url, job);
  const clear = () => inflight.delete(url);
  job.then(clear, clear);
  return job;
}
