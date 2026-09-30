import { useEffect, useState } from "react";
import { loadWorkbookModel } from "./loadWorkbook";
import type { WorkbookModel } from "./sheetModel";

export type WorkbookState = { status: "loading" } | { status: "ready"; model: WorkbookModel } | { status: "error"; message: string };

/** Mô hình workbook của `url` (dùng chung cache); bỏ qua kết quả khi component đã gỡ. */
export function useWorkbook(url: string): WorkbookState {
  const [state, setState] = useState<WorkbookState>({ status: "loading" });
  useEffect(() => {
    let active = true;
    setState({ status: "loading" });
    loadWorkbookModel(url)
      .then((model) => active && setState({ status: "ready", model }))
      .catch((e: unknown) => active && setState({ status: "error", message: e instanceof Error ? e.message : "Không đọc được tệp Excel." }));
    return () => {
      active = false;
    };
  }, [url]);
  return state;
}
