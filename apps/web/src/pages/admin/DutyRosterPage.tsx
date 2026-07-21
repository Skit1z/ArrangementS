import { useQuery } from "@tanstack/react-query";
import { App, Button, Card, DatePicker, Empty, Space, Spin, Tag } from "antd";
import { DownloadOutlined, CameraOutlined, CalendarOutlined } from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import { useRef, useState } from "react";
import { toPng } from "html-to-image";

import { api } from "@/api/client";
import { adminApi, type Semester } from "@/features/admin/api";
import type { SlotView, WeekView } from "@/features/schedule/types";

function mondayOf(d: Dayjs): string {
  const day = d.day() === 0 ? 7 : d.day();
  return d.subtract(day - 1, "day").format("YYYY-MM-DD");
}

function computeWeekLabel(weekStartStr: string, semesters: Semester[]): string {
  const target = dayjs(weekStartStr);
  if (!semesters || semesters.length === 0)
    return `${target.format("YYYY年")} 第 ${target.isoWeek()} 周`;
  const sorted = [...semesters].sort((a, b) =>
    dayjs(a.first_monday).diff(dayjs(b.first_monday)),
  );
  for (const sem of sorted) {
    const s = dayjs(sem.first_monday);
    const e = s.add(sem.week_count, "week");
    if ((target.isSame(s, "day") || target.isAfter(s)) && target.isBefore(e)) {
      return `${sem.name} · 第 ${Math.floor(target.diff(s, "day") / 7) + 1} 周`;
    }
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

function buildMatrix(
  slots: SlotView[],
  venueNames: Map<string, string>,
  phoneMap: Map<string, string>,
) {
  const days: string[] = [];
  const venueMap = new Map<string, string>();
  const matrix: Record<string, Record<string, { name: string; phone: string }[]>> = {};
  const normalSlots = slots.filter((s) => s.source_type === "fixed_shift");

  for (const slot of normalSlots) {
    const date = dayjs(slot.slot_start_at).format("MM-DD (ddd)");
    if (!days.includes(date)) days.push(date);
    if (!venueMap.has(slot.venue_id))
      venueMap.set(slot.venue_id, venueNames.get(slot.venue_id) ?? slot.venue_id);
  }

  for (const [vid] of venueMap) {
    matrix[vid] = {};
    for (const d of days) matrix[vid][d] = [];
  }

  for (const slot of normalSlots) {
    const date = dayjs(slot.slot_start_at).format("MM-DD (ddd)");
    for (const [vid] of venueMap) {
      if (!matrix[vid][date]) matrix[vid][date] = [];
    }
    const entries = slot.assignments
      .filter((a) => a.person_name)
      .map((a) => ({
        name: a.person_name!,
        phone: phoneMap.get(a.person_id ?? "") ?? "",
      }));
    if (slot.venue_id in matrix && date in matrix[slot.venue_id]) {
      matrix[slot.venue_id][date].push(...entries);
    }
  }

  return { days, venueMap, matrix };
}

export default function DutyRosterPage() {
  const { message } = App.useApp();
  const printRef = useRef<HTMLDivElement>(null);
  const [weekStart, setWeekStart] = useState(() => mondayOf(dayjs()));

  const semestersQ = useQuery({
    queryKey: ["admin", "semesters"],
    queryFn: adminApi.semesters.list,
  });

  const venuesQ = useQuery({
    queryKey: ["admin", "venues"],
    queryFn: adminApi.venues.list,
  });

  const peopleQ = useQuery({
    queryKey: ["admin", "people"],
    queryFn: adminApi.people.list,
  });

  const weekQuery = useQuery<WeekView>({
    queryKey: ["schedule", "weeks", weekStart],
    queryFn: async () => (await api.get<WeekView>(`/schedule/weeks/${weekStart}`)).data,
    enabled: !!weekStart,
  });

  const venueNameMap = new Map((venuesQ.data ?? []).map((v) => [v.id, v.name]));
  const phoneMap = new Map((peopleQ.data ?? []).map((p) => [p.id, p.phone ?? ""]));

  const handleExportExcel = () => {
    if (!weekQuery.data) return;
    try {
      const { days, venueMap, matrix } = buildMatrix(
        weekQuery.data.slots,
        venueNameMap,
        phoneMap,
      );

      // 使用 HTML 表格生成格式化 Excel
      const rows = Array.from(venueMap).map(([vid, name]) => {
        const cells = days.map((d) => {
          const entries = matrix[vid]?.[d] ?? [];
          return entries.map((e) => (e.phone ? `${e.name} ${e.phone}` : e.name)).join("\n");
        });
        return [name, ...cells];
      });

      const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
        table { border-collapse: collapse; font-family: 'Microsoft YaHei', SimHei, sans-serif; }
        th { background: #1F497D; color: #fff; font-weight: 600; padding: 8px 10px; border: 1px solid #1F497D; text-align: center; font-size: 13px; }
        td { padding: 8px 10px; border: 1px solid #b8cce4; text-align: center; font-size: 12px; vertical-align: middle; white-space: pre-line; }
        tr:nth-child(even) td { background: #f5f8fc; }
        tr:nth-child(odd) td { background: #ffffff; }
        td:first-child { font-weight: 700; background: #e9edf4; color: #1F497D; min-width: 80px; }
      </style></head><body><table>
        <thead><tr><th>场地</th>${days.map((d) => `<th>${d}</th>`).join("")}</tr></thead>
        <tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c || "—"}</td>`).join("")}</tr>`).join("")}</tbody>
      </table></body></html>`;

      const blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${weekQuery.data.week_label ?? "值班表"}_${weekStart}.xls`;
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
      const dataUrl = await toPng(printRef.current, {
        backgroundColor: "#ffffff",
        pixelRatio: 2,
      });
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
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            onClick={handleExportExcel}
            disabled={!weekQuery.data}
          >
            导出 Excel
          </Button>
          <Button
            icon={<CameraOutlined />}
            onClick={handleExportImage}
            disabled={!weekQuery.data}
          >
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
        <div ref={printRef}>
          <div style={{ textAlign: "center", marginBottom: 16 }}>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#1F497D" }}>
              值班安排表
            </h2>
            <div style={{ fontSize: 14, color: "#595959", marginTop: 4 }}>
              {wl} · {weekQuery.data.week_start} ~ {weekQuery.data.week_end}
            </div>
            <Tag
              color={weekQuery.data.status === "published" ? "green" : "orange"}
              style={{ marginTop: 4 }}
            >
              {weekQuery.data.status === "published" ? "已发布" : "草稿"}
            </Tag>
          </div>

          {(() => {
            const { days, venueMap, matrix } = buildMatrix(
              weekQuery.data.slots,
              venueNameMap,
              phoneMap,
            );
            if (venueMap.size === 0)
              return <Empty description="本周暂无固定班次数据" />;

            return (
              <div style={{ overflowX: "auto" }}>
                <table
                  style={{
                    borderCollapse: "collapse",
                    width: "100%",
                    minWidth: 800,
                    fontSize: 13,
                  }}
                >
                  <thead>
                    <tr>
                      <th
                        style={{
                          border: "1px solid #d9d9d9",
                          padding: "8px 12px",
                          background: "#1F497D",
                          color: "#fff",
                          fontWeight: 600,
                          minWidth: 90,
                        }}
                      >
                        场地
                      </th>
                      {days.map((d) => (
                        <th
                          key={d}
                          style={{
                            border: "1px solid #d9d9d9",
                            padding: "8px 12px",
                            background: "#1F497D",
                            color: "#fff",
                            fontWeight: 600,
                            minWidth: 100,
                          }}
                        >
                          {d}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Array.from(venueMap).map(([vid, name]) => (
                      <tr key={vid}>
                        <td
                          style={{
                            border: "1px solid #d9d9d9",
                            padding: "8px 12px",
                            fontWeight: 600,
                            background: "#e9edf4",
                            textAlign: "center",
                            color: "#1F497D",
                          }}
                        >
                          {name}
                        </td>
                        {days.map((d) => {
                          const entries = matrix[vid]?.[d] ?? [];
                          return (
                            <td
                              key={d}
                              style={{
                                border: "1px solid #d9d9d9",
                                padding: "6px 8px",
                                textAlign: "center",
                                minWidth: 100,
                              }}
                            >
                              {entries.length > 0 ? (
                                entries.map((e, i) => (
                                  <div
                                    key={i}
                                    style={{
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: 6,
                                      margin: "2px 3px",
                                      padding: "2px 8px",
                                      borderRadius: 4,
                                      background: "#e6f4ff",
                                      border: "1px solid #91caff",
                                      fontSize: 12,
                                      whiteSpace: "nowrap",
                                    }}
                                  >
                                    <span style={{ fontWeight: 600, color: "#1F497D" }}>
                                      {e.name}
                                    </span>
                                    {e.phone && (
                                      <span style={{ color: "#666", fontSize: 11 }}>
                                        {e.phone}
                                      </span>
                                    )}
                                  </div>
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
              </div>
            );
          })()}
        </div>
      )}
    </Card>
  );
}
