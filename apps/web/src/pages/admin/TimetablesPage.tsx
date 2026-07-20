import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UploadOutlined } from "@ant-design/icons";
import { App, Button, Card, Modal, Select, Space, Spin, Tag } from "antd";
import { useState } from "react";
import { errorMessage } from "@/api/client";
import { PdfFilePicker } from "@/components/PdfFilePicker";
import { TimetableEntryEditor } from "@/components/TimetableEntryEditor";
import { adminApi, type ActiveTimetableOut } from "@/features/admin/api";
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
      if (!proxyParsed?.length || proxyParsed.some((entry) =>
        entry.period_start > entry.period_end || !entry.week_expr.trim()
      )) {
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
            style={{ width: 110 }}
          />
          <span style={{ marginLeft: 16 }}>人员筛选：</span>
          <Select
            allowClear
            showSearch
            placeholder="查看所有人"
            style={{ width: 200 }}
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
                  width: 60,
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
                  }}
                >
                  {block.label}
                </td>
                {WEEKDAYS.map((wd) => {
                  const busyPeopleInBlock: { personName: string; courseName: string }[] = [];
                  for (const person of peopleToDisplay) {
                    const overlappingRule = person.rules.find(
                      (rule) =>
                        rule.weekday === wd.value &&
                        !(rule.period_end < block.start || rule.period_start > block.end)
                    );
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
