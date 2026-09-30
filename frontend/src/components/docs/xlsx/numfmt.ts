// ── Định dạng giá trị ô Excel theo numFmt, kiểu hiển thị Excel tiếng Việt ──
// Dấu phẩy thập phân, dấu chấm nhóm nghìn, ngày dd/mm/yyyy - đúng như người dùng
// thấy khi mở biên bản bằng Excel cài vùng Việt Nam. Chỉ ĐỔI CÁCH VIẾT của giá trị
// đã lưu (làm tròn hiển thị như Excel), không tính toán lại gì.

const DECIMAL = ",";
const GROUP = ".";

/** Excel lưu dựng sẵn mục 14/22 bằng mẫu Mỹ nhưng hiển thị theo vùng: ở VN là dd/mm/yyyy. */
const LOCALE_DATE_FORMATS: Record<string, string> = {
  "mm-dd-yy": "dd/mm/yyyy",
  "m/d/yy": "dd/mm/yyyy",
  "m/d/yy h:mm": "dd/mm/yyyy h:mm",
};

/** Tách các phần `dương;âm;không;chữ`, bỏ qua `;` trong ngoặc kép hoặc sau `\`. */
function splitSections(format: string): string[] {
  const sections: string[] = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < format.length; i++) {
    const ch = format[i];
    if (ch === "\\" && !quoted && i + 1 < format.length) {
      current += ch + format[++i];
      continue;
    }
    if (ch === '"') quoted = !quoted;
    if (ch === ";" && !quoted) {
      sections.push(current);
      current = "";
      continue;
    }
    current += ch;
  }
  sections.push(current);
  return sections;
}

/** Bỏ chỉ thị trong ngoặc vuông: màu `[Red]`, điều kiện `[>=100]`, vùng `[$-42A]`. */
function stripDirectives(section: string): string {
  return section.replace(/\[[^\]]*\]/g, "");
}

interface NumberPattern {
  prefix: string;
  code: string;
  suffix: string;
  /** số dấu `%` KHÔNG nằm trong ngoặc kép - mỗi dấu nhân giá trị với 100 */
  percent: number;
}

const NUMBER_CODE = /[0#?.,]/;

/** Tách mẫu số thành chữ đứng trước / mã số / chữ đứng sau (bỏ ngoặc kép, `\x`, `_x`, `*x`). */
function tokenizeNumber(section: string): NumberPattern {
  let prefix = "";
  let code = "";
  let suffix = "";
  let percent = 0;
  const push = (text: string, isCode: boolean) => {
    if (isCode) code += text;
    else if (code) suffix += text;
    else prefix += text;
  };
  for (let i = 0; i < section.length; i++) {
    const ch = section[i];
    if (ch === '"') {
      const end = section.indexOf('"', i + 1);
      push(section.slice(i + 1, end < 0 ? undefined : end), false);
      i = end < 0 ? section.length : end;
    } else if (ch === "\\") {
      push(section[++i] ?? "", false);
    } else if (ch === "_") {
      push(" ", false);
      i++;
    } else if (ch === "*") {
      i++;
    } else if ((ch === "E" || ch === "e") && /[+-]/.test(section[i + 1] ?? "")) {
      push(ch + section[++i], true);
    } else if (ch === "%") {
      percent++;
      push(ch, false);
    } else if (NUMBER_CODE.test(ch) && !(ch === "," && !code)) {
      push(ch, true);
    } else {
      push(ch, false);
    }
  }
  return { prefix, code, suffix, percent };
}

function isDateSection(section: string): boolean {
  const codes = section
    .replace(/"[^"]*"/g, "")
    .replace(/\\./g, "")
    .replace(/[_*]./g, "");
  return /[dmyhs]/i.test(codes.replace(/General/gi, "")) && !/[0#?]/.test(codes);
}

function groupThousands(integer: string): string {
  return integer.replace(/\B(?=(\d{3})+(?!\d))/g, GROUP);
}

/** Làm tròn thập phân như Excel (1.005 → "1.01", không lỗi nhị phân của toFixed). */
function toFixedDecimal(value: number, digits: number): string {
  const rounded = Number(`${Math.round(Number(`${value}e${digits}`))}e-${digits}`);
  return (Number.isFinite(rounded) ? rounded : value).toFixed(digits);
}

function exponential(value: number, decimals: number, expDigits: number): string {
  const [mantissa, exponent] = value.toExponential(decimals).split("e");
  const exp = Number(exponent);
  return `${mantissa.replace(".", DECIMAL)}E${exp < 0 ? "-" : "+"}${String(Math.abs(exp)).padStart(expDigits, "0")}`;
}

/** Kiểu "General" của Excel: tối đa 10 chữ số có nghĩa, số rất lớn/rất nhỏ chuyển dạng mũ. */
export function formatGeneral(value: number): string {
  if (!Number.isFinite(value)) return String(value);
  if (value === 0) return "0";
  const abs = Math.abs(value);
  if (abs >= 1e11 || abs < 1e-4) {
    return exponential(value, 5, 2).replace(/,?0+E/, "E");
  }
  const integerDigits = Math.floor(Math.log10(abs)) + 1;
  const decimals = Math.max(0, 10 - Math.max(1, integerDigits));
  const text = toFixedDecimal(value, decimals)
    .replace(/(\.\d*?)0+$/, "$1")
    .replace(/\.$/, "");
  return text.replace(".", DECIMAL);
}

function formatNumberSection(value: number, section: string, withSign: boolean): string {
  const { prefix, code: numeric, suffix, percent } = tokenizeNumber(section);
  if (!numeric.replace(/,/g, "")) return prefix + suffix;
  const scaled = value * Math.pow(100, percent);
  const sign = withSign && scaled < 0 ? "-" : "";

  const sci = /E[+-]/i.exec(numeric);
  const mantissaCode = sci ? numeric.slice(0, sci.index) : numeric;
  const [intCode, fracCode = ""] = mantissaCode.split(".");
  const decimals = (fracCode.match(/[0#?]/g) || []).length;
  const minDecimals = (fracCode.match(/0/g) || []).length;
  const minInteger = (intCode.match(/0/g) || []).length;
  const grouped = /[0#?],[0#?]/.test(intCode);

  if (sci) {
    const expDigits = (numeric.slice(sci.index + 2).match(/0/g) || []).length || 2;
    return `${sign}${prefix}${exponential(Math.abs(scaled), decimals, expDigits)}${suffix}`;
  }

  let [integer, fraction = ""] = toFixedDecimal(Math.abs(scaled), decimals).split(".");
  fraction = fraction.replace(/0+$/, "").padEnd(minDecimals, "0");
  if (integer === "0" && minInteger === 0) integer = "";
  integer = integer.padStart(minInteger, "0");
  if (grouped) integer = groupThousands(integer);
  const isZero = !/[1-9]/.test(integer + fraction);
  const body = fraction ? `${integer}${DECIMAL}${fraction}` : integer || (minInteger ? "0" : "");
  return `${isZero ? "" : sign}${prefix}${body}${suffix}`;
}

const pad2 = (n: number) => String(n).padStart(2, "0");

const DATE_TOKEN = /"[^"]*"|\\.|yyyy|yy|mmmmm|mmmm|mmm|mm|m|dddd|ddd|dd|d|hh|h|ss|s|AM\/PM|A\/P|./gi;
const WEEKDAYS = ["Chủ nhật", "Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy"];

/** `m`/`mm` là PHÚT nếu đứng ngay sau giờ hoặc ngay trước giây (quy tắc của Excel). */
function isMinuteToken(tokens: string[], index: number): boolean {
  const isTime = (t: string | undefined) => !!t && /^[hmsd]/i.test(t) && !t.startsWith('"');
  const before = tokens.slice(0, index).reverse().find(isTime);
  const after = tokens.slice(index + 1).find(isTime);
  return /^h/i.test(before ?? "") || /^s/i.test(after ?? "");
}

/** Ngày giờ theo mẫu Excel; ExcelJS trả Date theo UTC nên đọc bằng getter UTC. */
export function formatDate(date: Date, format: string): string {
  const section = stripDirectives(LOCALE_DATE_FORMATS[format.trim().toLowerCase()] ?? format);
  const twelveHour = /AM\/PM|A\/P/i.test(section);
  const tokens = section.match(DATE_TOKEN) || [];
  const hours = date.getUTCHours();
  return tokens
    .map((token, index) => {
      const lower = token.toLowerCase();
      if (token.startsWith('"')) return token.slice(1, -1);
      if (token.startsWith("\\")) return token.slice(1);
      if ((lower === "m" || lower === "mm") && isMinuteToken(tokens, index)) {
        return lower === "mm" ? pad2(date.getUTCMinutes()) : String(date.getUTCMinutes());
      }
      const h12 = hours % 12 || 12;
      const parts: Record<string, string> = {
        yyyy: String(date.getUTCFullYear()),
        yy: pad2(date.getUTCFullYear() % 100),
        mmmmm: `Tháng ${date.getUTCMonth() + 1}`,
        mmmm: `Tháng ${date.getUTCMonth() + 1}`,
        mmm: `Thg ${date.getUTCMonth() + 1}`,
        mm: pad2(date.getUTCMonth() + 1),
        m: String(date.getUTCMonth() + 1),
        dddd: WEEKDAYS[date.getUTCDay()],
        ddd: WEEKDAYS[date.getUTCDay()],
        dd: pad2(date.getUTCDate()),
        d: String(date.getUTCDate()),
        hh: pad2(twelveHour ? h12 : hours),
        h: String(twelveHour ? h12 : hours),
        ss: pad2(date.getUTCSeconds()),
        s: String(date.getUTCSeconds()),
        "am/pm": hours < 12 ? "SA" : "CH",
        "a/p": hours < 12 ? "S" : "C",
      };
      return parts[lower] ?? token;
    })
    .join("");
}

/** Số serial Excel (gốc 1899-12-30) → Date UTC. */
export function serialToDate(serial: number): Date {
  return new Date(Date.UTC(1899, 11, 30) + Math.round(serial * 86400000));
}

/** Chuỗi hiển thị của một số theo numFmt (trống = General). */
export function formatNumber(value: number, numFmt?: string | null): string {
  const format = (numFmt ?? "").trim();
  if (!format || /^general$/i.test(format)) return formatGeneral(value);
  const sections = splitSections(format);
  let section = sections[0];
  let withSign = true;
  if (value < 0 && sections.length > 1 && sections[1] !== "") {
    section = sections[1];
    withSign = false; // phần âm tự mang dấu/ngoặc của nó
  } else if (value === 0 && sections.length > 2 && sections[2] !== "") {
    section = sections[2];
  }
  const cleaned = stripDirectives(section);
  if (/^\s*(general|@)?\s*$/i.test(cleaned)) return formatGeneral(withSign ? value : Math.abs(value));
  if (isDateSection(cleaned)) return formatDate(serialToDate(value), LOCALE_DATE_FORMATS[format.toLowerCase()] ?? cleaned);
  return formatNumberSection(withSign ? value : Math.abs(value), cleaned, withSign);
}

/** Chữ theo phần `@` của numFmt (ví dụ `"SN: "@`); không có phần chữ thì giữ nguyên. */
export function formatText(text: string, numFmt?: string | null): string {
  const sections = splitSections(numFmt ?? "");
  const section = sections.length > 3 ? sections[3] : sections.find((s) => s.includes("@"));
  if (!section) return text;
  const [before, after = ""] = stripDirectives(section).split("@");
  const unquote = (s: string) => s.replace(/"([^"]*)"/g, "$1").replace(/\\(.)/g, "$1");
  return `${unquote(before)}${text}${unquote(after)}`;
}
