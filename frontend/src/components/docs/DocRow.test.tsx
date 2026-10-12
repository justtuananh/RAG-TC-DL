import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Actions } from "../../store/useAppStore";
import type { DocItem } from "../../types";
import DocRow from "./DocRow";
import DocTableRow from "./DocTableRow";

// Tài liệu superseded hiển thị câu giải thích (trong `error`) làm chú thích nhãn
// trạng thái ở cả dạng thẻ (DocRow) và dạng bảng (DocTableRow), không tô màu lỗi.

const NOTE = "Đã có phiên bản mới hơn: QTKĐ 1.061 2026.docx";

const SUPERSEDED: DocItem = {
  id: "s1",
  name: "QTKĐ 1.061 bản cũ.pdf",
  ext: "PDF",
  size: "2 MB",
  pages: 12,
  date: "01/01/2026",
  status: "superseded",
  error: NOTE,
};

const READY: DocItem = {
  id: "r1",
  name: "QTKĐ 1.061 2026.docx",
  ext: "DOCX",
  size: "2 MB",
  pages: 12,
  date: "02/01/2026",
  status: "ready",
};

describe("tài liệu superseded - chú thích trạng thái", () => {
  it("dạng thẻ: dùng error làm chú thích, màu trung tính", () => {
    const html = renderToStaticMarkup(<DocRow doc={SUPERSEDED} renaming={false} actions={{} as Actions} />);
    expect(html).toContain("Đã thay thế");
    expect(html).toContain(NOTE);
    expect(html).toContain("#64706A"); // màu neutral
    expect(html).not.toContain("#C8102E"); // màu danger
  });

  it("dạng bảng: dùng error làm chú thích, màu trung tính", () => {
    const html = renderToStaticMarkup(<DocTableRow doc={SUPERSEDED} renaming={false} actions={{} as Actions} />);
    expect(html).toContain("Đã thay thế");
    expect(html).toContain(NOTE);
    expect(html).toContain("#64706A");
    expect(html).not.toContain("#C8102E");
  });
});

// Lý do "Đã thay thế" (trong `doc.error`) hiện thành dòng phụ ngay dưới tên tệp,
// không chỉ nằm trong `title` của nhãn trạng thái (phải rê chuột mới thấy).
describe("tài liệu superseded - dòng lý do dưới tên tệp", () => {
  it("dạng thẻ: hiện câu error thành dòng phụ dưới tên", () => {
    const html = renderToStaticMarkup(<DocRow doc={SUPERSEDED} renaming={false} actions={{} as Actions} />);
    expect(html).toContain(`title="${NOTE}"`); // title đầy đủ
    expect(html).toContain(`>${NOTE}</div>`); // và nội dung hiển thị thật
    expect(html).toContain("text-overflow:ellipsis");
  });

  it("dạng bảng: hiện câu error thành dòng phụ dưới tên", () => {
    const html = renderToStaticMarkup(<DocTableRow doc={SUPERSEDED} renaming={false} actions={{} as Actions} />);
    expect(html).toContain(`title="${NOTE}"`);
    expect(html).toContain(`>${NOTE}</div>`);
    expect(html).toContain("text-overflow:ellipsis");
  });

  it("hàng ready không có dòng phụ", () => {
    expect(renderToStaticMarkup(<DocRow doc={READY} renaming={false} actions={{} as Actions} />)).not.toContain(NOTE);
    expect(renderToStaticMarkup(<DocTableRow doc={READY} renaming={false} actions={{} as Actions} />)).not.toContain(NOTE);
  });
});
