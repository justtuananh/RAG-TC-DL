import { Storage } from "happy-dom";

// Node 22+ (máy này là Node 26) tự định nghĩa `localStorage`/`sessionStorage`
// trên globalThis. Khi không truyền `--localstorage-file`, getter `localStorage`
// của Node trả về `undefined`, còn Vitest khi "populate" global cho môi trường
// happy-dom lại BỎ QUA những key đã tồn tại trên global của Node — nên
// `localStorage` thật của happy-dom không bao giờ tới được test, khiến
// `persistence.test.ts` chết với "localStorage is undefined".
//
// Cài Storage thật của happy-dom cho môi trường test để test chạy đúng ngữ nghĩa
// Web Storage (get/set/remove/clear/length/key), KHÔNG nới lỏng assertion nào.
for (const key of ["localStorage", "sessionStorage"] as const) {
  Object.defineProperty(globalThis, key, {
    value: new Storage(),
    configurable: true,
    writable: true,
  });
}

// happy-dom dựng document không có doctype nên `document.compatMode` là
// `undefined` (không phải "CSS1Compat"). KaTeX kiểm tra `"CSS1Compat" !==
// document.compatMode` lúc nạp module → coi là quirks mode, in cảnh báo và VÔ
// HIỆU HOÁ `katex.render`. Ép chế độ standards cho môi trường test để test công
// thức chạy đúng như trên trình duyệt thật.
if (document.compatMode !== "CSS1Compat") {
  Object.defineProperty(document, "compatMode", {
    value: "CSS1Compat",
    configurable: true,
  });
}
