import { useCallback, useEffect, useState } from "react";
import { calculateFormula, decideFormulaDraft, generateFormulaDrafts, listFormulaDrafts, saveFormulaDraft } from "../../services/formulaApi";
import type { FormulaCase, FormulaDraft, FormulaInput, FormulaProposal } from "../../services/formulaApi";
import Markdown from "../common/Markdown";
import { COLOR, RADIUS, SHADOW } from "../../theme";

const field =
  "block min-w-0 w-full mt-1 border border-line rounded-lg px-3 py-2 text-[13px] font-sans font-normal text-on-surface bg-surface outline-none transition-colors placeholder:text-icon-muted focus:border-brand focus:ring-2 focus:ring-primary-container disabled:bg-surface-container-low disabled:text-icon-muted";
const buttonBase =
  "items-center justify-center gap-2 min-h-9 border rounded-lg px-3 py-2 font-sans text-[12.5px] font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-40 disabled:cursor-not-allowed";
const button = `${buttonBase} inline-flex border-line text-secondary bg-surface hover:border-brand hover:text-brand hover:bg-primary-container`;
const primaryButton = `${buttonBase} inline-flex border-brand bg-brand text-on-primary hover:bg-brand-dark hover:border-brand-dark`;
const card = "min-w-0 border border-line bg-surface rounded-[14px] p-4 sm:p-5";
const notice = "border rounded-[10px] px-3 py-2.5 text-[12.5px] leading-relaxed";
const statusColors = {
  pending_review: { color: COLOR.warning, background: COLOR.warningBg, borderColor: COLOR.warningBorder },
  approved: { color: COLOR.success, background: COLOR.successBg, borderColor: COLOR.successBorder },
  rejected: { color: COLOR.danger, background: COLOR.dangerBg, borderColor: COLOR.dangerBorder },
  stale: { color: COLOR.neutral, background: COLOR.neutralBg, borderColor: COLOR.neutralBorder },
};
const labels = { pending_review: "Chờ phê duyệt", approved: "Đã phê duyệt", rejected: "Đã từ chối", stale: "Nguồn hết hiệu lực" };
function StatusBadge({ status }: { status: FormulaDraft["status"] }) {
  return (
    <span
      className="inline-flex items-center border px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap"
      style={{ ...statusColors[status], borderRadius: RADIUS.pill }}
    >
      {labels[status]}
    </span>
  );
}
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

export default function FormulaReviewPanel({
  documentId,
  isDocx,
  onDirtyChange,
}: {
  documentId: string;
  isDocx: boolean;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const [drafts, setDrafts] = useState<FormulaDraft[]>([]);
  const [units, setUnits] = useState<string[]>([]);
  const [activeId, setActiveId] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [dirty, setDirty] = useState(false);
  const [editorBusy, setEditorBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [editorVersion, setEditorVersion] = useState(0);
  const reportDirty = useCallback(
    (value: boolean) => {
      setDirty(value);
      onDirtyChange?.(value);
    },
    [onDirtyChange],
  );
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  function mayDiscard() {
    return !dirty || window.confirm("Có chỉnh sửa chưa lưu. Bỏ các chỉnh sửa này để tiếp tục?");
  }

  useEffect(() => {
    let live = true;
    listFormulaDrafts(documentId)
      .then((data) => {
        if (!live) return;
        setDrafts(data.drafts);
        setUnits(data.units);
        setActiveId(data.drafts[0]?.id ?? "");
      })
      .catch((e) => {
        if (live) setError(e instanceof Error ? e.message : "Không tải được bản nháp.");
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [documentId]);

  async function reload(generate: boolean) {
    if (editorBusy || !mayDiscard()) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (generate) {
        const result = await generateFormulaDrafts(documentId);
        setMessage(`Đã tạo ${result.created} bản nháp mới từ ${result.candidates} công thức. Bản nháp và quyết định đã có được giữ nguyên.`);
      }
      const data = await listFormulaDrafts(documentId);
      setDrafts(data.drafts);
      setUnits(data.units);
      reportDirty(false);
      setEditorVersion((v) => v + 1);
      setActiveId((id) => (data.drafts.some((d) => d.id === id) ? id : (data.drafts[0]?.id ?? "")));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được bản nháp.");
    } finally {
      setBusy(false);
    }
  }

  function updated(value: FormulaDraft) {
    setDrafts((list) => list.map((d) => (d.id === value.id ? value : d)));
  }
  const active = drafts.find((d) => d.id === activeId);
  const visible = drafts.filter((d) => filter === "all" || d.status === filter);
  return (
    <section
      aria-label="Phê duyệt công thức"
      className="p-4 sm:p-5 font-sans text-[13px] leading-relaxed text-on-surface bg-background [overflow-wrap:anywhere]"
    >
      <div className={`${card} flex flex-wrap items-end gap-3 mb-4`} style={{ boxShadow: SHADOW.sm }}>
        <h2 className="basis-full text-[15px] font-bold">Công thức và bộ tính</h2>
        <button className={primaryButton} disabled={busy || editorBusy || loading || !isDocx} onClick={() => reload(true)}>
          {busy ? "Đang xử lý…" : "Tạo bản nháp từ DOCX"}
        </button>
        <button className={button} disabled={busy || editorBusy || loading} onClick={() => reload(false)}>
          Tải lại danh sách
        </button>
        <label>
          Trạng thái{" "}
          <select aria-label="Lọc trạng thái công thức" className={field} value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">Tất cả ({drafts.length})</option>
            {Object.entries(labels).map(([key, label]) => (
              <option key={key} value={key}>
                {label} ({drafts.filter((d) => d.status === key).length})
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="text-sm text-secondary mb-3">Công thức trích xuất cần được đối chiếu với tài liệu gốc. Chỉ bộ tính đã phê duyệt mới được sử dụng.</p>
      {!isDocx && <p>Hiện hỗ trợ tạo bản nháp từ DOCX. PDF chưa có luồng định vị công thức để phê duyệt.</p>}
      {error && (
        <p
          role="alert"
          className={`${notice} whitespace-pre-wrap`}
          style={{ color: COLOR.danger, background: COLOR.dangerBg, borderColor: COLOR.dangerBorder }}
        >
          {error}
        </p>
      )}
      {message && (
        <p role="status" className={`${notice} mb-3`} style={{ color: COLOR.success, background: COLOR.successBg, borderColor: COLOR.successBorder }}>
          {message}
        </p>
      )}
      {loading && <p role="status">Đang tải bản nháp…</p>}
      {!loading && !drafts.length && !error && (
        <p className="py-6 text-secondary">
          Chưa có bản nháp. Tài liệu DOCX mới sẽ được tạo bản nháp khi xử lý; với tài liệu đã có, dùng nút tạo bản nháp phía trên.
        </p>
      )}
      <div className="grid items-start gap-4 xl:grid-cols-[250px_minmax(0,1fr)]">
        <nav aria-label="Danh sách công thức" className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1 max-h-[45vh] xl:max-h-[75vh] overflow-auto rounded-[10px]">
          {visible.map((d) => (
            <button
              key={d.id}
              className={`${buttonBase} block w-full text-left border-line hover:border-brand hover:bg-primary-container`}
              style={{
                background: activeId === d.id ? COLOR.accentSoft : COLOR.surface,
                borderColor: activeId === d.id ? COLOR.accent : COLOR.border,
                boxShadow: SHADOW.sm,
              }}
              aria-current={activeId === d.id ? "true" : undefined}
              disabled={busy || editorBusy}
              onClick={() => {
                if (d.id !== activeId && mayDiscard()) {
                  reportDirty(false);
                  setActiveId(d.id);
                }
              }}
            >
              <span className="flex flex-wrap items-center justify-between gap-2">
                <strong className="text-brand">{d.source.fid}</strong>
                <StatusBadge status={d.status} />
              </span>
              <span className="block text-xs mt-2 font-normal text-secondary">{d.proposal.title}</span>
            </button>
          ))}
        </nav>
        {active && (
          <DraftEditor
            key={`${active.id}:${active.revision}:${editorVersion}`}
            draft={active}
            locked={busy}
            units={units}
            onUpdated={updated}
            onDirtyChange={reportDirty}
            onBusyChange={setEditorBusy}
          />
        )}
      </div>
    </section>
  );
}

function DraftEditor({
  draft,
  units,
  onUpdated,
  onDirtyChange,
  onBusyChange,
  locked,
}: {
  draft: FormulaDraft;
  locked: boolean;
  units: string[];
  onUpdated: (draft: FormulaDraft) => void;
  onDirtyChange: (dirty: boolean) => void;
  onBusyChange: (busy: boolean) => void;
}) {
  const [proposal, setProposal] = useState<FormulaProposal>(() => clone(draft.proposal));
  const [reviewer, setReviewer] = useState("");
  const [note, setNote] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [inputs, setInputs] = useState<Record<string, FormulaInput>>(() => Object.create(null));
  const [checks, setChecks] = useState<Record<string, boolean>>(() => Object.create(null));
  const [result, setResult] = useState("");
  const dirty = JSON.stringify(proposal) !== JSON.stringify(draft.proposal);
  const stale = draft.status === "stale";
  useEffect(() => {
    onDirtyChange(dirty);
  }, [dirty, onDirtyChange]);
  useEffect(() => {
    onBusyChange(busy);
    return () => onBusyChange(false);
  }, [busy, onBusyChange]);
  function change<K extends keyof FormulaProposal>(key: K, value: FormulaProposal[K]) {
    setProposal((old) => ({ ...old, [key]: value }));
    setConfirmed(false);
    setResult("");
  }
  function editVariable(index: number, changes: Partial<FormulaProposal["variables"][number]>) {
    const previous = proposal.variables[index];
    const next = { ...previous, ...changes };
    const cases = proposal.test_cases.map((c) => {
      const inputs = { ...c.inputs };
      const input = inputs[previous.key];
      delete inputs[previous.key];
      if (input) {
        const value =
          next.kind === "series"
            ? Array.isArray(input.value)
              ? input.value
              : [input.value]
            : Array.isArray(input.value)
              ? (input.value[0] ?? "")
              : input.value;
        inputs[next.key] = { ...input, value };
      }
      return { ...c, inputs };
    });
    setProposal((old) => ({ ...old, variables: old.variables.map((v, i) => (i === index ? next : v)), test_cases: cases }));
    setConfirmed(false);
    setResult("");
  }
  async function act(operation: () => Promise<FormulaDraft>) {
    setBusy(true);
    setError("");
    try {
      onUpdated(await operation());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Thao tác thất bại.");
    } finally {
      setBusy(false);
    }
  }
  const unitSelect = (value: string, onChange: (unit: string) => void, name: string) => (
    <select aria-label={name} className={field} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Chọn đơn vị</option>
      {units.map((u) => (
        <option key={u}>{u}</option>
      ))}
    </select>
  );
  function addCase() {
    const inputs = Object.fromEntries(proposal.variables.map((v) => [v.key, { value: v.kind === "series" ? [""] : "", unit: v.unit }]));
    change("test_cases", [...proposal.test_cases, { inputs, expected: "", unit: proposal.unit }]);
  }
  function editCase(index: number, value: FormulaCase) {
    change(
      "test_cases",
      proposal.test_cases.map((c, i) => (i === index ? value : c)),
    );
  }

  return (
    <article className="min-w-0 space-y-4 [&_label]:text-[12.5px] [&_label]:text-secondary [&_h4]:text-on-surface [&_input[type=checkbox]]:accent-brand [&_input[type=checkbox]]:shrink-0">
      <div className={`${card} space-y-3`} style={{ boxShadow: SHADOW.sm }}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h3 className="flex flex-wrap items-center gap-2 font-semibold">
            <span className="text-brand">{draft.source.fid}</span>
            <StatusBadge status={draft.status} />
            <span className="text-xs font-normal text-icon-muted">Phiên bản {draft.revision}</span>
          </h3>
          <a className="text-brand underline" href={`/api/documents/${encodeURIComponent(draft.source.document_id)}/file`} target="_blank" rel="noreferrer">
            Mở nguồn gốc
          </a>
        </div>
        <p className="text-sm">
          {draft.source.file} — {draft.source.section}
        </p>
        {draft.source.latex ? (
          <Markdown className="overflow-x-auto rounded-lg bg-surface-container-low px-3 py-2">{`$$\n${draft.source.latex}\n$$`}</Markdown>
        ) : (
          <p className={notice} style={{ color: COLOR.warning, background: COLOR.warningBg, borderColor: COLOR.warningBorder }}>
            Chưa đọc được biểu thức. Cần kiểm tra tài liệu gốc.
          </p>
        )}
        <details>
          <summary className="cursor-pointer">Ngữ cảnh và phiên bản nguồn</summary>
          <pre className="whitespace-pre-wrap text-xs mt-2">{draft.source.context || "Không có trích đoạn định vị."}</pre>
          <p className="break-all text-xs mt-2">SHA-256: {draft.source.sha256}</p>
        </details>
      </div>
      <ul className="text-xs list-disc pl-5 space-y-1" style={{ color: COLOR.warning }}>
        {draft.warnings.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
      {draft.validation_errors.length > 0 && (
        <div className={notice} style={{ color: COLOR.warning, background: COLOR.warningBg, borderColor: COLOR.warningBorder }} role="status">
          <strong>Cần bổ sung trước khi duyệt</strong>
          <ul className="list-disc pl-5 text-sm">
            {draft.validation_errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}
      {error && (
        <p
          role="alert"
          className={`${notice} whitespace-pre-wrap`}
          style={{ color: COLOR.danger, background: COLOR.dangerBg, borderColor: COLOR.dangerBorder }}
        >
          {error}
        </p>
      )}
      <fieldset disabled={stale || busy || locked} className={`${card} space-y-4`}>
        <label className="block">
          Tên công thức
          <input aria-label="Tên công thức" className={field} value={proposal.title} onChange={(e) => change("title", e.target.value)} />
        </label>
        <label className="block">
          Biểu thức tính
          <input
            aria-label="Biểu thức tính"
            className={field}
            value={proposal.expression}
            onChange={(e) => change("expression", e.target.value)}
            placeholder="Ví dụ: rho*g*h hoặc abs(p-pc)"
          />
        </label>
        <p className="text-xs text-secondary">
          Tên biến dùng chữ thường không dấu, chữ số và dấu gạch dưới, bắt đầu bằng chữ cái. Phép tính: +, -, *, /, **; hàm: sqrt, abs, mean, rss, slope, max.
          Số thập phân dùng dấu chấm.
        </p>
        <label className="block">Đơn vị kết quả{unitSelect(proposal.unit, (u) => change("unit", u), "Đơn vị kết quả")}</label>
        <h4 className="font-semibold">Biến đầu vào</h4>
        {proposal.variables.map((v, index) => {
          const edit = (changes: Partial<typeof v>) => editVariable(index, changes);
          return (
            <div key={index} className="min-w-0 border border-line rounded-[10px] bg-surface-container-low p-3 space-y-3">
              <div className="grid sm:grid-cols-3 gap-3 [&>label]:min-w-0">
                <label>
                  Tên biến
                  <input aria-label={`Tên biến ${index + 1}`} className={field} value={v.key} onChange={(e) => edit({ key: e.target.value })} />
                </label>
                <label>
                  Ý nghĩa
                  <input aria-label={`Ý nghĩa biến ${index + 1}`} className={field} value={v.label} onChange={(e) => edit({ label: e.target.value })} />
                </label>
                <label>Đơn vị{unitSelect(v.unit, (u) => edit({ unit: u }), `Đơn vị biến ${index + 1}`)}</label>
              </div>
              <div className="grid sm:grid-cols-2 2xl:grid-cols-3 gap-3 items-end [&>label]:min-w-0">
                <label>
                  Kiểu{" "}
                  <select
                    className={field}
                    value={v.kind ?? "scalar"}
                    onChange={(e) => edit({ kind: e.target.value as "scalar" | "series", min_items: 1, max_items: 100 })}
                  >
                    <option value="scalar">Một số</option>
                    <option value="series">Danh sách số</option>
                  </select>
                </label>
                <label>
                  Tối thiểu
                  <input className={field} value={v.min ?? ""} onChange={(e) => edit({ min: e.target.value || null })} />
                </label>
                <label>
                  <input type="checkbox" checked={v.exclusive_min ?? false} onChange={(e) => edit({ exclusive_min: e.target.checked })} /> Lớn hơn tối thiểu
                </label>
                <label>
                  Tối đa
                  <input className={field} value={v.max ?? ""} onChange={(e) => edit({ max: e.target.value || null })} />
                </label>
                <label>
                  <input type="checkbox" checked={v.exclusive_max ?? false} onChange={(e) => edit({ exclusive_max: e.target.checked })} /> Nhỏ hơn tối đa
                </label>
                {v.kind === "series" && (
                  <>
                    <label>
                      Ít nhất bao nhiêu số
                      <input type="number" className={field} value={v.min_items ?? 1} onChange={(e) => edit({ min_items: Number(e.target.value) })} />
                    </label>
                    <label>
                      Nhiều nhất bao nhiêu số
                      <input type="number" className={field} value={v.max_items ?? 100} onChange={(e) => edit({ max_items: Number(e.target.value) })} />
                    </label>
                  </>
                )}
                <button
                  className={button}
                  onClick={() => {
                    setProposal((old) => ({
                      ...old,
                      variables: old.variables.filter((_, i) => i !== index),
                      test_cases: old.test_cases.map((c) => ({ ...c, inputs: Object.fromEntries(Object.entries(c.inputs).filter(([key]) => key !== v.key)) })),
                    }));
                    setConfirmed(false);
                    setResult("");
                  }}
                >
                  Xóa biến
                </button>
              </div>
            </div>
          );
        })}
        <button
          className={button}
          disabled={proposal.variables.length >= 12}
          onClick={() => change("variables", [...proposal.variables, { key: "", label: "", unit: "" }])}
        >
          Thêm biến
        </button>
        <h4 className="font-semibold">Điều kiện áp dụng</h4>
        {proposal.conditions.map((c, index) => (
          <div key={index} className="flex gap-2">
            <input
              aria-label={`Điều kiện ${index + 1}`}
              className={field}
              value={c.label}
              onChange={(e) =>
                change(
                  "conditions",
                  proposal.conditions.map((item, i) => (i === index ? { ...item, label: e.target.value } : item)),
                )
              }
            />
            <button
              className={button}
              onClick={() =>
                change(
                  "conditions",
                  proposal.conditions.filter((_, i) => i !== index),
                )
              }
            >
              Xóa
            </button>
          </div>
        ))}
        <button
          className={button}
          disabled={proposal.conditions.length >= 20}
          onClick={() => change("conditions", [...proposal.conditions, { key: `condition_${Date.now()}`, label: "" }])}
        >
          Thêm điều kiện
        </button>
        <h4 className="font-semibold">Ca tính đối chứng</h4>
        <p className="text-sm text-secondary">Nhập số liệu và đáp án đã tính độc lập. Không lấy kết quả của bộ tính làm đáp án đối chứng.</p>
        {proposal.test_cases.map((c, index) => (
          <div key={index} className="min-w-0 border border-line rounded-[10px] bg-surface-container-low p-3 space-y-3">
            <strong>Ca {index + 1}</strong>
            {proposal.variables.map((v) => (
              <div key={v.key} className="grid sm:grid-cols-2 gap-3 [&>label]:min-w-0">
                <label>
                  {v.label || v.key}
                  <input
                    aria-label={`Ca ${index + 1} ${v.key}`}
                    className={field}
                    placeholder={v.kind === "series" ? "Mỗi số ngăn bằng dấu ;" : "Dấu chấm thập phân"}
                    value={Array.isArray(c.inputs[v.key]?.value) ? (c.inputs[v.key].value as string[]).join(";") : (c.inputs[v.key]?.value ?? "")}
                    onChange={(e) =>
                      editCase(index, {
                        ...c,
                        inputs: {
                          ...c.inputs,
                          [v.key]: {
                            value: v.kind === "series" ? e.target.value.split(";").map((x) => x.trim()) : e.target.value,
                            unit: c.inputs[v.key]?.unit || v.unit,
                          },
                        },
                      })
                    }
                  />
                </label>
                <label>
                  Đơn vị
                  {unitSelect(
                    c.inputs[v.key]?.unit || v.unit,
                    (u) => editCase(index, { ...c, inputs: { ...c.inputs, [v.key]: { value: c.inputs[v.key]?.value ?? "", unit: u } } }),
                    `Đơn vị ca ${index + 1} ${v.key}`,
                  )}
                </label>
              </div>
            ))}
            <label>
              Đáp án độc lập
              <input
                aria-label={`Đáp án ca ${index + 1}`}
                className={field}
                value={c.expected}
                onChange={(e) => editCase(index, { ...c, expected: e.target.value })}
              />
            </label>
            {unitSelect(c.unit, (u) => editCase(index, { ...c, unit: u }), `Đơn vị đáp án ${index + 1}`)}
            <button
              className={button}
              onClick={() =>
                change(
                  "test_cases",
                  proposal.test_cases.filter((_, i) => i !== index),
                )
              }
            >
              Xóa ca
            </button>
          </div>
        ))}
        <button className={button} disabled={proposal.test_cases.length >= 10} onClick={addCase}>
          Thêm ca đối chứng
        </button>
        <div className="border-t border-line pt-4 flex flex-wrap items-center gap-3">
          <button className={primaryButton} disabled={!dirty} onClick={() => act(() => saveFormulaDraft(draft, proposal))}>
            Lưu bản nháp
          </button>
          <span className="text-xs text-secondary">{dirty ? "Chưa lưu. Lưu xong mới có thể phê duyệt." : "Đang xem phiên bản đã lưu."}</span>
        </div>
        {draft.status === "approved" && (
          <p className={notice} style={{ color: COLOR.warning, background: COLOR.warningBg, borderColor: COLOR.warningBorder }}>
            Lưu thay đổi sẽ thu hồi hiệu lực bộ tính và yêu cầu phê duyệt lại.
          </p>
        )}
      </fieldset>
      {draft.status === "pending_review" && (
        <fieldset disabled={busy || stale || locked} className={`${card} space-y-3`}>
          <legend className="font-semibold px-2 text-[13px] text-on-surface">Quyết định của người rà soát</legend>
          <p className="text-xs text-secondary">Tên người rà soát do bạn khai báo và được lưu trong lịch sử.</p>
          <label className="block">
            Người phê duyệt
            <input aria-label="Người phê duyệt" className={field} value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
          </label>
          <label className="block">
            Nhận xét và căn cứ
            <textarea aria-label="Nhận xét và căn cứ" className={field} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <label className="flex gap-2">
            <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> Tôi đã đối chiếu biểu thức, biến, đơn vị, điều kiện
            và đáp án với tài liệu gốc.
          </label>
          <div className="flex flex-wrap gap-3">
            <button
              className={primaryButton}
              disabled={dirty || !confirmed || !reviewer.trim() || !note.trim() || draft.validation_errors.length > 0}
              onClick={() => act(() => decideFormulaDraft(draft, "approve", reviewer, note, confirmed))}
            >
              Phê duyệt và đăng ký
            </button>
            <button
              className={button}
              disabled={dirty || !reviewer.trim() || !note.trim()}
              onClick={() => act(() => decideFormulaDraft(draft, "reject", reviewer, note, false))}
            >
              Từ chối
            </button>
          </div>
        </fieldset>
      )}
      {draft.review && (
        <p className="text-sm">
          {draft.review.decision === "approve" ? "Đã duyệt" : "Đã từ chối"} bởi {draft.review.reviewer} · {new Date(draft.review.at).toLocaleString("vi-VN")} —{" "}
          {draft.review.note}
        </p>
      )}
      {draft.status === "approved" && !dirty && (
        <fieldset disabled={busy || locked} className={`${card} space-y-3`} style={{ borderColor: COLOR.accentSoftBorder }}>
          <legend className="font-semibold px-2 text-[13px] text-on-surface">Sử dụng bộ tính đã duyệt</legend>
          {draft.proposal.variables.map((v) => (
            <div className="grid sm:grid-cols-2 gap-3 [&>label]:min-w-0" key={v.key}>
              <label>
                {v.label}
                <input
                  aria-label={`Tính ${v.key}`}
                  className={field}
                  value={Array.isArray(inputs[v.key]?.value) ? (inputs[v.key].value as string[]).join(";") : (inputs[v.key]?.value ?? "")}
                  placeholder={v.kind === "series" ? "Mỗi số ngăn bằng dấu ;" : "Giá trị"}
                  onChange={(e) => {
                    setInputs((old) =>
                      Object.assign(Object.create(null), old, {
                        [v.key]: {
                          value: v.kind === "series" ? e.target.value.split(";").map((x) => x.trim()) : e.target.value,
                          unit: old[v.key]?.unit || v.unit,
                        },
                      }),
                    );
                    setResult("");
                  }}
                />
              </label>
              <label>
                Đơn vị
                {unitSelect(
                  inputs[v.key]?.unit || v.unit,
                  (u) => {
                    setInputs((old) => Object.assign(Object.create(null), old, { [v.key]: { value: old[v.key]?.value ?? "", unit: u } }));
                    setResult("");
                  },
                  `Đơn vị tính ${v.key}`,
                )}
              </label>
            </div>
          ))}
          {draft.proposal.conditions.map((c) => (
            <label key={c.key} className="flex gap-2">
              <input
                type="checkbox"
                checked={checks[c.key] ?? false}
                onChange={(e) => {
                  setChecks((old) => Object.assign(Object.create(null), old, { [c.key]: e.target.checked }));
                  setResult("");
                }}
              />
              {c.label}
            </label>
          ))}
          <button
            className={primaryButton}
            disabled={
              draft.proposal.conditions.some((c) => !checks[c.key]) ||
              draft.proposal.variables.some(
                (v) =>
                  !inputs[v.key] ||
                  (Array.isArray(inputs[v.key].value) ? (inputs[v.key].value as string[]).some((x) => !x.trim()) : !(inputs[v.key].value as string).trim()),
              )
            }
            onClick={async () => {
              setBusy(true);
              setError("");
              setResult("");
              try {
                const r = await calculateFormula(draft, inputs, checks);
                setResult(`${r.value} ${r.unit} — ${r.source} — người duyệt: ${r.approved_by}`);
              } catch (e) {
                setError(e instanceof Error ? e.message : "Không tính được.");
              } finally {
                setBusy(false);
              }
            }}
          >
            Tính kết quả
          </button>
          {result && (
            <p
              role="status"
              className={`${notice} font-semibold`}
              style={{ color: COLOR.success, background: COLOR.successBg, borderColor: COLOR.successBorder }}
            >
              {result}
            </p>
          )}
        </fieldset>
      )}
      <details className={`${card} text-secondary`}>
        <summary className="cursor-pointer">Lịch sử bản nháp và quyết định</summary>
        <ul className="text-xs space-y-1 mt-2">
          {draft.history.map((event, index) => (
            <li key={index}>
              Phiên bản {event.revision} · {event.action} · {new Date(event.at).toLocaleString("vi-VN")} {event.reviewer && `· ${event.reviewer}`}{" "}
              {event.note && `— ${event.note}`}
            </li>
          ))}
        </ul>
      </details>
    </article>
  );
}
