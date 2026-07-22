import { useQuery } from "@tanstack/react-query";
import { App, Button, Card, DatePicker, Empty, Radio, Space, Spin, Tag } from "antd";
import { DownloadOutlined, CameraOutlined, CalendarOutlined } from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import { useRef, useState } from "react";
import { toPng } from "html-to-image";

import { api } from "@/api/client";
import { adminApi, type Semester } from "@/features/admin/api";
import type { SlotView, WeekView } from "@/features/schedule/types";

/** 值班表列标题（6 个时段） */
const TIME_SLOTS = [
  { key: "A", label: "一二节", range: "08:00-09:30" },
  { key: "B", label: "三四节", range: "09:30-11:00" },
  { key: "C", label: "中午", range: "11:00-14:00" },
  { key: "D", label: "五六节", range: "14:00-16:00" },
  { key: "E", label: "16:00-17:30", range: "16:00-17:30" },
  { key: "F", label: "17:30-19:00", range: "17:30-19:00" },
] as const;

/** 解析 ISO 时间为 Date 对象 */
function toBeijingDate(iso: string): Date {
  return new Date(iso);
}

/** 根据时间起点将槽位映射到 6 个时段 */
function classifyTimeSlot(slot: SlotView): string {
  const bj = toBeijingDate(slot.slot_start_at);
  const h = bj.getHours();
  const m = bj.getMinutes();
  // 早晚离散时段精确匹配
  if (h === 8) return "A";           // 一二节   08:00-09:30
  if (h === 9 && m >= 30) return "B"; // 三四节   09:30-11:00
  if (h === 10) return "B";          // 三四节   10:00-10:...
  if (h >= 11 && h < 14) return "C"; // 中午     11:00-14:00
  if (h >= 14 && h < 16) return "D"; // 五六节   14:00-16:00
  if (h === 16) return "E";          // 16:00-17:30
  if (h >= 17 || h < 8) return "F";  // 17:30-19:00 + 夜间/凌晨班
  return "F";
}

function mondayOf(d: Dayjs): string {
  const day = d.day() === 0 ? 7 : d.day();
  return d.subtract(day - 1, "day").format("YYYY-MM-DD");
}

function computeWeekLabel(weekStartStr: string, semesters: Semester[]): string {
  const target = dayjs(weekStartStr);
  if (!semesters || semesters.length === 0)
    return `${target.format("YYYY年")} 第 ${target.isoWeek()} 周`;
  const sorted = [...semesters].sort((a, b) => dayjs(a.first_monday).diff(dayjs(b.first_monday)));
  for (const sem of sorted) {
    const s = dayjs(sem.first_monday);
    const e = s.add(sem.week_count, "week");
    if ((target.isSame(s, "day") || target.isAfter(s)) && target.isBefore(e))
      return `${sem.name} · 第 ${Math.floor(target.diff(s, "day") / 7) + 1} 周`;
  }
  for (const sem of sorted.reverse()) {
    const e = dayjs(sem.first_monday).add(sem.week_count, "week");
    if (target.isSame(e, "day") || target.isAfter(e)) {
      const wk = Math.floor(target.diff(e, "day") / 7) + 1;
      const w = [1, 2, 3, 11, 12].includes(e.month() + 1) ? "寒假" : "暑假";
      return `${sem.name}后 · ${w}第 ${wk} 周`;
    }
  }
  return `${target.format("YYYY年")} 第 ${target.isoWeek()} 周`;
}

const WEEKDAY = ["一", "二", "三", "四", "五", "六", "日"];

type PersonEntry = { name: string; phone: string };

/** 按 场地 → 星期 → 时段 组织数据 */
function buildRoster(slots: SlotView[], venueId: string, phoneMap: Map<string, string>) {
  const matrix: Record<string, Record<string, PersonEntry[]>> = {};
  for (let w = 0; w < 7; w++) matrix[WEEKDAY[w]] = {};
  for (const s of TIME_SLOTS) {
    for (let w = 0; w < 7; w++) matrix[WEEKDAY[w]][s.key] = [];
  }

  for (const slot of slots) {
    if (slot.source_type !== "fixed_shift" || slot.venue_id !== venueId) continue;
    const bj = toBeijingDate(slot.slot_start_at);
    const weekday = bj.getDay(); // 0=周日
    const label = WEEKDAY[weekday === 0 ? 6 : weekday - 1];
    const tKey = classifyTimeSlot(slot);
    const entries: PersonEntry[] = slot.assignments
      .filter((a) => a.person_name)
      .map((a) => ({ name: a.person_name!, phone: phoneMap.get(a.person_id ?? "") ?? "" }));
    if (matrix[label]?.[tKey]) {
      matrix[label][tKey].push(...entries);
    }
  }
  return matrix;
}

export default function DutyRosterPage() {
  const { message } = App.useApp();
  const printRef = useRef<HTMLDivElement>(null);
  const [weekStart, setWeekStart] = useState(() => mondayOf(dayjs()));
  const [selectedVenue, setSelectedVenue] = useState<string | null>(null);

  const semestersQ = useQuery({ queryKey: ["admin", "semesters"], queryFn: adminApi.semesters.list });
  const venuesQ = useQuery({ queryKey: ["admin", "venues"], queryFn: adminApi.venues.list });
  const peopleQ = useQuery({ queryKey: ["admin", "people"], queryFn: adminApi.people.list });
  const weekQuery = useQuery<WeekView>({
    queryKey: ["schedule", "weeks", weekStart],
    queryFn: async () => (await api.get<WeekView>(`/schedule/weeks/${weekStart}`)).data,
    enabled: !!weekStart,
  });

  const fixedVenues = (venuesQ.data ?? []).filter((v) => v.venue_type === "fixed_shift");
  const phoneMap = new Map((peopleQ.data ?? []).map((p) => [p.id, p.phone ?? ""]));

  // 默认选中第一个固定班次场地
  const activeVenue = selectedVenue ?? fixedVenues[0]?.id ?? null;

  const roster = weekQuery.data
    ? buildRoster(weekQuery.data.slots, activeVenue ?? "", phoneMap)
    : null;

  const currentVenueName = fixedVenues.find((v) => v.id === activeVenue)?.name ?? "";

  const handleExportExcel = () => {
    if (!roster || !activeVenue) return;
    try {
      const rows = TIME_SLOTS.map((s) => {
        const cells = WEEKDAY.map((w) =>
          (roster[w]?.[s.key] ?? []).map((e) => (e.phone ? `${e.name} (${e.phone})` : e.name)).join("\n"),
        );
        return [s.label, ...cells];
      });

      const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
        table { border-collapse: collapse; font-family: 'Microsoft YaHei', sans-serif; table-layout: fixed; width: 100%; }
        th { background-color: #1F497D; color: #ffffff; font-weight: bold; padding: 12px 8px; border: 1px solid #1F497D; text-align: center; font-size: 13px; height: 36px; }
        th.weekend { background-color: #fa8c16; border-color: #fa8c16; }
        td { padding: 10px 8px; border: 1px solid #d9d9d9; text-align: center; font-size: 12px; vertical-align: top; white-space: pre-line; word-wrap: break-word; line-height: 1.6; mso-number-format:'\\@'; }
        tr:nth-child(even) td { background-color: #fcfcfc; }
        tr:nth-child(odd) td { background-color: #ffffff; }
        td.row-header { font-weight: bold; background-color: #e9edf4; color: #1F497D; width: 110px; vertical-align: middle; }
      </style></head><body>
        <h2 style="text-align:center;color:#1F497D;font-size:18px;margin:12px 0 6px;">${currentVenueName} · ${wl}</h2>
        <div style="text-align:center;color:#666666;font-size:12px;margin-bottom:16px;">${weekQuery.data?.week_start ?? ""} ~ ${weekQuery.data?.week_end ?? ""}</div>
        <table border="1">
          <colgroup>
            <col style="width: 110px;" />
            ${WEEKDAY.map(() => '<col style="width: 140px;" />').join("")}
          </colgroup>
          <thead>
            <tr>
              <th>时段</th>
              ${WEEKDAY.map((w, idx) => `<th class="${idx >= 5 ? "weekend" : ""}">周${w}</th>`).join("")}
            </tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (r) =>
                  `<tr>${r
                    .map((c, i) =>
                      i === 0 ? `<td class="row-header">${c}</td>` : `<td>${c || "—"}</td>`,
                    )
                    .join("")}</tr>`,
              )
              .join("")}
          </tbody>
        </table>
      </body></html>`;

      const blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${currentVenueName}_值班表_${weekStart}.xls`;
      a.click();
      URL.revokeObjectURL(url);
      message.success("值班表已导出（Excel 格式）");
    } catch {
      message.error("导出失败");
    }
  };

  const handleExportImage = async () => {
    if (!printRef.current) return;
    try {
      const dataUrl = await toPng(printRef.current, { backgroundColor: "#ffffff", pixelRatio: 2 });
      const link = document.createElement("a");
      link.download = `值班表_${weekStart}.png`;
      link.href = dataUrl;
      link.click();
      message.success("值班表图片已导出");
    } catch {
      message.error("导出图片失败");
    }
  };

  const wl = computeWeekLabel(weekStart, semestersQ.data ?? []);

  return (
    <Card
      title={
        <Space>
          <CalendarOutlined />
          <span style={{ fontSize: 16, fontWeight: 600 }}>值班表</span>
        </Space>
      }
      extra={
        <Space>
          <DatePicker
            picker="week"
            value={dayjs(weekStart)}
            onChange={(v) => v && setWeekStart(mondayOf(v))}
            allowClear={false}
            format="YYYY-MM-DD"
          />
          <Button type="primary" icon={<DownloadOutlined />} onClick={handleExportExcel} disabled={!roster}>
            导出 Excel
          </Button>
          <Button icon={<CameraOutlined />} onClick={handleExportImage} disabled={!roster}>
            导出图片
          </Button>
        </Space>
      }
      bordered={false}
      style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.05)", borderRadius: 12 }}
    >
      {weekQuery.isLoading ? (
        <Spin style={{ display: "block", margin: "80px auto" }} />
      ) : !weekQuery.data || weekQuery.data.slots.length === 0 ? (
        <Empty description={`${wl} — 暂无排班数据`} style={{ margin: "40px 0" }} />
      ) : (
        <>
          {/* 场地切换按钮 */}
          <div style={{ marginBottom: 16, textAlign: "center" }}>
            <Radio.Group
              value={activeVenue}
              onChange={(e) => setSelectedVenue(e.target.value)}
              optionType="button"
              buttonStyle="solid"
              size="middle"
            >
              {fixedVenues.map((v) => (
                <Radio.Button key={v.id} value={v.id}>
                  {v.name}
                </Radio.Button>
              ))}
            </Radio.Group>
          </div>

          {/* 外层限制溢出横向滚动，内层 printRef 展开全宽不含滚动条 */}
          <div style={{ overflowX: "auto" }}>
            <div ref={printRef} style={{ background: "#ffffff", padding: "16px 20px", minWidth: 950, boxSizing: "border-box" }}>
              <div style={{ textAlign: "center", marginBottom: 16 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "#1F497D" }}>
                  {currentVenueName} · 值班安排表
                </h2>
                <div style={{ fontSize: 13, color: "#595959", marginTop: 4 }}>
                  {wl} · {weekQuery.data.week_start} ~ {weekQuery.data.week_end}
                </div>
                <Tag color={weekQuery.data.status === "published" ? "green" : "orange"} style={{ marginTop: 4 }}>
                  {weekQuery.data.status === "published" ? "已发布" : "草稿"}
                </Tag>
              </div>

              {roster ? (
                <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 900, fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={thStyle}>时段</th>
                      {WEEKDAY.map((w, wi) => (
                        <th key={w} style={{ ...thStyle, background: wi >= 5 ? "#fa8c16" : "#1F497D" }}>
                          {w}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {TIME_SLOTS.map((s) => (
                      <tr key={s.key}>
                        <td style={{ ...rowHeaderStyle(0), fontSize: 13 }}>
                          <div style={{ fontWeight: 600 }}>{s.label}</div>
                        </td>
                        {WEEKDAY.map((w) => {
                          const entries = roster[w]?.[s.key] ?? [];
                          return (
                            <td key={w} style={cellStyle}>
                              {entries.length > 0 ? (
                                entries.map((e, i) => (
                                  <span key={i} style={tagStyle}>
                                    <strong style={{ color: "#1F497D" }}>{e.name}</strong>
                                    {e.phone && <span style={{ color: "#666", marginLeft: 4 }}>{e.phone}</span>}
                                  </span>
                                ))
                              ) : (
                                <span style={{ color: "#d9d9d9" }}>—</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <Empty description="请选择值班场地" />
              )}
            </div>
          </div>
        </>
      )}
    </Card>
  );
}

const thStyle: React.CSSProperties = {
  border: "1px solid #d9d9d9",
  padding: "7px 8px",
  background: "#1F497D",
  color: "#fff",
  textAlign: "center",
  fontWeight: 600,
  minWidth: 90,
};

const rowHeaderStyle = (wi: number): React.CSSProperties => ({
  border: "1px solid #d9d9d9",
  padding: "8px 10px",
  fontWeight: 700,
  background: wi >= 5 ? "#fff7e6" : "#e9edf4",
  textAlign: "center",
  color: "#1F497D",
  fontSize: 14,
});

const cellStyle: React.CSSProperties = {
  border: "1px solid #d9d9d9",
  padding: "6px 6px",
  textAlign: "center",
  minWidth: 90,
  verticalAlign: "top",
};

const tagStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  margin: "2px 2px",
  padding: "2px 6px",
  borderRadius: 3,
  background: "#e6f4ff",
  border: "1px solid #91caff",
  fontSize: 12,
  whiteSpace: "nowrap",
};
