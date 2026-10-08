import type { ProcedureProfile } from "../../types";
import { COLOR } from "../../theme";
import { IcArrowRight } from "../common/icons";
import { formatDate, verdictTone } from "../data/format";
import { EmptyLine, SectionCard } from "./ProfileSections";

// Biên bản kiểm định trong sổ cái đã thực hiện theo QTKĐ này: số liệu tóm tắt, vài biên
// bản mới nhất (mở trang thiết bị) và lối sang bảng hồ sơ đã lọc theo QTKĐ.

interface Props {
  profile: ProcedureProfile;
  onOpenDevice: (deviceId: number) => void;
  onOpenAll: () => void;
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 92 }}>
      <span className="tabular-nums" style={{ fontSize: "20px", fontWeight: 700, color: tone ?? COLOR.textPrimary, lineHeight: 1.2 }}>
        {value}
      </span>
      <span style={{ fontSize: "12px", color: COLOR.textMuted }}>{label}</span>
    </div>
  );
}

export default function RecordsSummary({ profile, onOpenDevice, onOpenAll }: Props) {
  const { records } = profile;
  const modeLabel = new Map<string, string>(profile.modes.map((mode) => [mode.key, mode.label]));
  const openAll =
    records.total > 0 ? (
      <button
        type="button"
        className="profile-chip"
        onClick={onOpenAll}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          height: 30,
          padding: "0 12px",
          border: `1px solid ${COLOR.border}`,
          borderRadius: 9999,
          background: COLOR.surface,
          color: COLOR.textSecondary,
          fontSize: "12.5px",
          fontWeight: 600,
          fontFamily: "inherit",
          cursor: "pointer",
        }}
      >
        Xem tất cả trong tab Dữ liệu <IcArrowRight size={13} />
      </button>
    ) : undefined;

  return (
    <SectionCard id="bien-ban" title="Biên bản kiểm định theo quy trình này" count={records.total} aside={openAll}>
      {records.total === 0 ? (
        <EmptyLine>Sổ cái chưa có biên bản đã duyệt nào thực hiện theo QTKĐ này.</EmptyLine>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
            <Stat label="Biên bản" value={String(records.total)} />
            <Stat label="Đạt" value={String(records.verdicts.dat)} tone={COLOR.success} />
            <Stat label="Không đạt" value={String(records.verdicts.khong_dat)} tone={records.verdicts.khong_dat > 0 ? COLOR.danger : undefined} />
            <Stat label="Thiết bị" value={String(records.devices)} />
            <Stat label="Lần kiểm định gần nhất" value={formatDate(records.latest_at)} />
          </div>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, borderTop: `1px solid ${COLOR.border}` }}>
            {records.recent.map((record) => {
              const tone = verdictTone(record.verdict);
              const deviceId = record.device_id;
              const serial = record.serial_no ?? "Thiết bị chưa định danh";
              const meta = [record.mode ? (modeLabel.get(record.mode) ?? record.mode) : null, record.cert_no ? `Biên bản ${record.cert_no}` : null]
                .filter(Boolean)
                .join(" · ");
              return (
                <li
                  key={record.id}
                  style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: `1px solid ${COLOR.border}`, fontSize: "13px" }}
                >
                  <span className="tabular-nums" style={{ width: 92, flexShrink: 0, color: COLOR.textSecondary }}>
                    {formatDate(record.calibrated_at)}
                  </span>
                  {deviceId != null ? (
                    <button type="button" className="serial-link" onClick={() => onOpenDevice(deviceId)} aria-label={`Mở lịch sử thiết bị ${serial}`}>
                      {serial}
                    </button>
                  ) : (
                    <span style={{ fontWeight: 600 }}>{serial}</span>
                  )}
                  <span style={{ flex: 1, minWidth: 0, color: COLOR.textMuted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {meta}
                  </span>
                  <span
                    style={{ flexShrink: 0, fontSize: "11px", fontWeight: 700, color: tone.fg, background: tone.bg, padding: "2px 9px", borderRadius: 9999 }}
                  >
                    {tone.label}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </SectionCard>
  );
}
