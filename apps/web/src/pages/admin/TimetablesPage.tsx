import { useQuery } from "@tanstack/react-query";
import { Card, Select, Spin, Tag, Space } from "antd";
import { useState } from "react";
import { adminApi, type ActiveTimetableOut } from "@/features/admin/api";

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
  const { data, isLoading } = useQuery<ActiveTimetableOut[]>({
    queryKey: ["admin", "timetables", "active"],
    queryFn: adminApi.timetables.active,
  });

  const [selectedPerson, setSelectedPerson] = useState<string | null>(null);

  const [viewMode, setViewMode] = useState<"busy" | "free">("busy");

  if (isLoading) {
    return <Spin style={{ display: "block", margin: "100px auto" }} />;
  }

  const allPeople = data ?? [];

  const peopleToDisplay = selectedPerson
    ? allPeople.filter((p) => p.person_id === selectedPerson)
    : allPeople;

  return (
    <Card 
      title={<span style={{ fontSize: '20px', fontWeight: 600 }}>全员课表</span>}
      bordered={false}
      style={{ boxShadow: '0 4px 12px rgba(0,0,0,0.05)', borderRadius: 12 }}
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
            options={allPeople.map((p) => ({
              label: p.person_name,
              value: p.person_id,
            }))}
            filterOption={(input, option) =>
              (option?.label ?? "").toLowerCase().includes(input.toLowerCase())
            }
          />
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
              <th style={{ border: "1px solid #f0f0f0", padding: "12px 8px", background: "#fafafa", width: 60 }}>
                节次
              </th>
              {WEEKDAYS.map((wd) => (
                <th key={wd.value} style={{ border: "1px solid #f0f0f0", padding: "12px 8px", background: "#fafafa", width: "14%" }}>
                  {wd.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PERIOD_BLOCKS.map((block) => (
              <tr key={block.label}>
                <td style={{ border: "1px solid #f0f0f0", padding: 8, textAlign: "center", background: "#fafafa" }}>
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
                  const freePeople = peopleToDisplay.filter((p) => !busyNames.has(p.person_name));
                  
                  const displayPeople = viewMode === "busy" ? busyPeopleInBlock : freePeople.map(p => ({ personName: p.person_name, courseName: "" }));
                  const cellBg = viewMode === "busy" 
                    ? (displayPeople.length > 0 ? "#fff2f0" : "#fff")
                    : (displayPeople.length > 0 ? "#f6ffed" : "#fff");

                  return (
                    <td key={wd.value} style={{ border: "1px solid #f0f0f0", padding: 8, verticalAlign: "top", background: cellBg }}>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {displayPeople.map((b, idx) => (
                          <Tag key={idx} color={viewMode === "busy" ? "red" : "green"}>
                            {b.personName}
                            {viewMode === "busy" && selectedPerson && ` (${b.courseName})`}
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
    </Card>
  );
}
