import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DownloadOutlined, UploadOutlined } from "@ant-design/icons";
import { App, Button, Card, Modal, Select, Space, Spin, Tag } from "antd";
import { useState } from "react";
import { errorMessage } from "@/api/client";
import { PdfFilePicker } from "@/components/PdfFilePicker";
import { TimetableEntryEditor } from "@/components/TimetableEntryEditor";
import { adminApi, type ActiveTimetableOut, type CourseRuleOut } from "@/features/admin/api";
import type { ParsedEntry } from "@/features/me/api";

const PERIOD_BLOCKS = [
  { label: "1-2 节", start: 1, end: 2 },
  { label: "3-4 节", start: 3, end: 4 },
  { label: "5-6 节", start: 5, end: 6 },
  { label: "7-8 节", start: 7, end: 8 },
  { label: "9-10 节", start: 9, end: 10 },
];
const WEEKDAYS = [
  { label: "周一", value: 1 },
  { label: "周二", value: 2 },
  { label: "周三", value: 3 },
  { label: "周四", value: 4 },
  { label: "周五", value: 5 },
  { label: "周六", value: 6 },
  { label: "周日", value: 7 },
];

function isRuleActiveOnWeek(rule: CourseRuleOut, targetWeek: number): boolean {
  if (rule.week_start !== null && rule.week_start !== undefined && targetWeek < rule.week_start) {
    return false;
  }
  if (rule.week_end !== null && rule.week_end !== undefined && targetWeek > rule.week_end) {
    return false;
  }
  if (rule.week_parity === "odd" && targetWeek % 2 !== 1) {
    return false;
  }
  if (rule.week_parity === "even" && targetWeek % 2 !== 0) {
    return false;
  }
  if (rule.explicit_weeks && rule.explicit_weeks.length > 0) {
    return rule.explicit_weeks.includes(targetWeek);
  }
  return true;
}

export default function TimetablesPage() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<ActiveTimetableOut[]>({
    queryKey: ["admin", "timetables", "active"],
    queryFn: adminApi.timetables.active,
  });
  const peopleQuery = useQuery({
    queryKey: ["admin", "people", "timetable-picker"],
    queryFn: adminApi.people.list,
  });

  const [selectedPerson, setSelectedPerson] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"busy" | "free">("busy");
  const [selectedWeek, setSelectedWeek] = useState<number | "all">("all");

  // admin 代传 state
  const [proxyOpen, setProxyOpen] = useState(false);
  const [proxyPersonId, setProxyPersonId] = useState<string | null>(null);
  const [proxyParsed, setProxyParsed] = useState<ParsedEntry[] | null>(null);
  const [proxyFileName, setProxyFileName] = useState("");

  const parseMut = useMutation({
    mutationFn: (file: File) => adminApi.timetables.parsePdf(file),
    onSuccess: (d) => {
      if (!d.entries.length) {
        message.error("未识别到课程");
        return;
      }
      setProxyParsed(d.entries);
      message.success(`解析出 ${d.entries.length} 条`);
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const confirmMut = useMutation({
    mutationFn: async () => {
      if (
        !proxyParsed?.length ||
        proxyParsed.some(
          (entry) =>
            entry.period_start > entry.period_end || !entry.week_expr.trim()
        )
      ) {
        throw new Error("请检查节次范围和周次，至少保留一条有效课程时段");
      }
      const up = await adminApi.timetables.uploadFor(
        proxyPersonId!,
        proxyFileName,
        proxyParsed!
      );
      await adminApi.timetables.approve(up.id);
    },
    onSuccess: () => {
      message.success("代传课表已生效");
      setProxyOpen(false);
      setProxyParsed(null);
      setProxyPersonId(null);
      setProxyFileName("");
      qc.invalidateQueries({ queryKey: ["admin", "timetables"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  if (isLoading) {
    return <Spin style={{ display: "block", margin: "100px auto" }} />;
  }

  const allPeople = data ?? [];
  const selectablePeople = (peopleQuery.data ?? []).filter((person) => person.status === "active");
  const peopleToDisplay = selectedPerson
    ? allPeople.filter((p) => p.person_id === selectedPerson)
    : allPeople;

  return (
    <Card
      title={<span style={{ fontSize: "20px", fontWeight: 600 }}>全员课表</span>}
      bordered={false}
      style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.05)", borderRadius: 12 }}
    >
      <div style={{ marginBottom: 16 }}>
        <Space wrap>
          <span>视图：</span>
          <Select
            value={viewMode}
            onChange={(v) => setViewMode(v as "busy" | "free")}
            options={[
              { label: "有课表", value: "busy" },
              { label: "无课表", value: "free" },
            ]}
            style={{ width: 100 }}
          />
          <span style={{ marginLeft: 8 }}>周次：</span>
          <Select
            value={selectedWeek}
            onChange={(v) => setSelectedWeek(v as number | "all")}
            style={{ width: 140 }}
            options={[
              { label: "全学期 (所有周)", value: "all" },
              ...Array.from({ length: 20 }, (_, i) => ({
                label: `第 ${i + 1} 周`,
                value: i + 1,
              })),
            ]}
          />
          <span style={{ marginLeft: 8 }}>人员筛选：</span>
          <Select
            allowClear
            showSearch
            placeholder="查看所有人"
            style={{ width: 180 }}
            value={selectedPerson}
            onChange={setSelectedPerson}
            options={selectablePeople.map((p) => ({ label: p.full_name, value: p.id }))}
            filterOption={(input, option) =>
              (option?.label ?? "").toLowerCase().includes(input.toLowerCase())
            }
          />
          <Button icon={<UploadOutlined />} onClick={() => setProxyOpen(true)}>
            为某人代传课表
          </Button>
          <Button
            type="primary"
            ghost
            icon={<DownloadOutlined />}
            onClick={async () => {
              const weekParam = selectedWeek === "all" ? undefined : selectedWeek;
              try {
                await adminApi.timetables.exportFree(weekParam);
                message.success("全员无课表 Excel 已生成并开始下载");
              } catch (_e) {
                exportFreeClientFallback(allPeople, selectablePeople, WEEKDAYS, PERIOD_BLOCKS, weekParam);
                message.success("全员无课表 Excel 已生成并开始下载");
              }
            }}
          >
            导出无课表 Excel
          </Button>
          <span style={{ color: "#888", fontSize: 13, marginLeft: 8 }}>
            {viewMode === "busy"
              ? "* 显示由于上课而不可排班的人员。"
              : "* 显示当前时段无课可排班的人员。"}
          </span>
        </Space>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 1000 }}>
          <thead>
            <tr>
              <th
                style={{
                  border: "1px solid #f0f0f0",
                  padding: "12px 8px",
                  background: "#fafafa",
                  width: 90,
                  whiteSpace: "nowrap",
                }}
              >
                节次
              </th>
              {WEEKDAYS.map((wd) => (
                <th
                  key={wd.value}
                  style={{
                    border: "1px solid #f0f0f0",
                    padding: "12px 8px",
                    background: "#fafafa",
                    width: "14%",
                  }}
                >
                  {wd.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PERIOD_BLOCKS.map((block) => (
              <tr key={block.label}>
                <td
                  style={{
                    border: "1px solid #f0f0f0",
                    padding: 8,
                    textAlign: "center",
                    background: "#fafafa",
                    whiteSpace: "nowrap",
                    width: 90,
                  }}
                >
                  {block.label}
                </td>
                {WEEKDAYS.map((wd) => {
                  const busyPeopleInBlock: { personName: string; courseName: string }[] = [];
                  for (const person of peopleToDisplay) {
                    const overlappingRule = person.rules.find((rule) => {
                      if (rule.weekday !== wd.value) return false;
                      if (rule.period_end < block.start || rule.period_start > block.end) return false;
                      if (selectedWeek !== "all") {
                        if (!isRuleActiveOnWeek(rule, selectedWeek)) return false;
                      }
                      return true;
                    });
                    if (overlappingRule) {
                      busyPeopleInBlock.push({
                        personName: person.person_name,
                        courseName: overlappingRule.course_name ?? "未知课程",
                      });
                    }
                  }

                  const busyNames = new Set(busyPeopleInBlock.map((b) => b.personName));
                  const freePeople = peopleToDisplay.filter(
                    (p) => !busyNames.has(p.person_name)
                  );

                  const displayPeople =
                    viewMode === "busy"
                      ? busyPeopleInBlock
                      : freePeople.map((p) => ({ personName: p.person_name, courseName: "" }));
                  return (
                    <td
                      key={wd.value}
                      style={{
                        border: "1px solid #f0f0f0",
                        padding: 8,
                        verticalAlign: "top",
                        background: "#fff",
                      }}
                    >
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {displayPeople.map((b, idx) => (
                          <Tag key={idx} color={viewMode === "busy" ? "red" : "green"}>
                            {b.personName}
                          </Tag>
                        ))}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal
        open={proxyOpen}
        title="为某人代传课表"
        width={780}
        onCancel={() => {
          setProxyOpen(false);
          setProxyParsed(null);
          setProxyPersonId(null);
          setProxyFileName("");
        }}
        onOk={proxyParsed ? () => confirmMut.mutate() : undefined}
        okText={proxyParsed ? "确认生效" : undefined}
        confirmLoading={confirmMut.isPending}
        okButtonProps={proxyParsed ? {} : { disabled: true }}
        footer={proxyParsed ? undefined : null}
      >
        {!proxyParsed ? (
          <>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: "block", marginBottom: 6, fontWeight: 600 }}>选择人员：</label>
              <Select
                showSearch
                placeholder="输入姓名或选择人员"
                optionFilterProp="label"
                style={{ width: "100%" }}
                value={proxyPersonId}
                onChange={setProxyPersonId}
                options={selectablePeople.map((p) => ({ label: p.full_name, value: p.id }))}
              />
            </div>
            <PdfFilePicker
              disabled={!proxyPersonId}
              disabledReason="请先在上方选择人员"
              isPending={parseMut.isPending}
              onSelectFile={(file) => {
                setProxyFileName(file.name);
                parseMut.mutate(file);
              }}
            />
          </>
        ) : (
          <TimetableEntryEditor value={proxyParsed} onChange={setProxyParsed} maxHeight={340} />
        )}
      </Modal>
    </Card>
  );
}

function exportFreeClientFallback(
  allPeople: ActiveTimetableOut[],
  selectablePeople: { id: string; full_name: string }[],
  weekdays: { label: string; value: number }[],
  periodBlocks: { label: string; start: number; end: number }[],
  week?: number
) {
  const today = new Date().toISOString().slice(0, 10);
  const weekSubtitle = week ? `第 ${week} 周` : "全学期";
  let html = `
    <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
    <head>
      <meta charset="utf-8" />
      <style>
        table { border-collapse: collapse; font-family: "微软雅黑", sans-serif; table-layout: fixed; width: 100%; }
        th, td { border: 1px solid #D9D9D9; padding: 8px 12px; text-align: left; vertical-align: top; word-break: break-all; }
        .title { background-color: #D9E1F2; font-size: 16px; font-weight: bold; color: #1F497D; text-align: center; height: 40px; vertical-align: middle; }
        .sub { background-color: #F9FBFD; font-size: 10px; color: #595959; text-align: center; height: 24px; font-style: italic; vertical-align: middle; }
        .header-cell { background-color: #1F497D; color: #FFFFFF; font-weight: bold; text-align: center; vertical-align: middle; height: 32px; font-size: 12px; }
        .period-cell { background-color: #F2F2F2; font-weight: bold; text-align: center; vertical-align: middle; width: 140px; font-size: 11px; }
        .data-cell { font-size: 11px; color: #262626; vertical-align: top; }
        .spacer { height: 12px; border: none !important; background-color: transparent !important; }
      </style>
    </head>
    <body>
      <table border="1">
        <colgroup>
          <col width="140" />
          <col width="180" />
          <col width="180" />
          <col width="180" />
          <col width="180" />
          <col width="180" />
          <col width="180" />
          <col width="180" />
        </colgroup>
        <tr><td colspan="8" class="title">全员无课表（可排班人员汇总表） - ${weekSubtitle}</td></tr>
        <tr><td colspan="8" class="sub">导出日期：${today}  |  人员总数：${selectablePeople.length}人  |  范围：${weekSubtitle}  |  说明：列表中为对应时间段无课、可参与班次排班的人员名单</td></tr>
        <tr><td colspan="8" class="spacer"></td></tr>
        <tr>
          <th class="header-cell" style="width: 140px;">节次 / 时间</th>
          ${weekdays.map((w) => `<th class="header-cell" style="width: 180px;">${w.label}</th>`).join("")}
        </tr>
  `;

  for (const block of periodBlocks) {
    html += `<tr><td class="period-cell">${block.label}</td>`;
    for (const wd of weekdays) {
      const freePeople = selectablePeople.filter((person) => {
        const rules = allPeople.find((p) => p.person_id === person.id)?.rules ?? [];
        const hasCourse = rules.some((r) => {
          if (r.weekday !== wd.value) return false;
          if (r.period_end < block.start || r.period_start > block.end) return false;
          if (week !== undefined) {
            if (!isRuleActiveOnWeek(r, week)) return false;
          }
          return true;
        });
        return !hasCourse;
      });

      const names = freePeople.map((p) => p.full_name).join("、");
      html += `<td class="data-cell">${names || "（无）"}</td>`;
    }
    html += `</tr>`;
  }

  html += `</table></body></html>`;

  const blob = new Blob(["\uFEFF" + html], { type: "application/vnd.ms-excel;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `全员无课表_${week ? `第${week}周_` : ""}${today}.xls`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
