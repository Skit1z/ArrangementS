import { useQuery } from "@tanstack/react-query";
import { Card, Select, Spin, Tag, Space } from "antd";
import { useState } from "react";
import { adminApi, type ActiveTimetableOut } from "@/features/admin/api";

const PERIODS = Array.from({ length: 14 }, (_, i) => i + 1);
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

  if (isLoading) {
    return <Spin style={{ display: "block", margin: "100px auto" }} />;
  }

  const allPeople = data ?? [];

  // Build grid data
  // grid[weekday][period] = list of { person_name, course_name }
  const grid: Record<number, Record<number, { personName: string; courseName: string }[]>> = {};
  for (const wd of WEEKDAYS) {
    grid[wd.value] = {};
    for (const p of PERIODS) {
      grid[wd.value][p] = [];
    }
  }

  const peopleToDisplay = selectedPerson
    ? allPeople.filter((p) => p.person_id === selectedPerson)
    : allPeople;

  for (const person of peopleToDisplay) {
    for (const rule of person.rules) {
      for (let p = rule.period_start; p <= rule.period_end; p++) {
        if (grid[rule.weekday] && grid[rule.weekday][p]) {
          grid[rule.weekday][p].push({
            personName: person.person_name,
            courseName: rule.course_name ?? "未知课程",
          });
        }
      }
    }
  }

  return (
    <Card 
      title={<span style={{ fontSize: '20px', fontWeight: 600 }}>全员课表 (忙碌时间)</span>}
      bordered={false}
      style={{ boxShadow: '0 4px 12px rgba(0,0,0,0.05)', borderRadius: 12 }}
    >
      <div style={{ marginBottom: 16 }}>
        <Space>
          <span>人员筛选：</span>
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
            * 显示由于上课而不可排班的人员。未在表格中出现的人员即为该时段“空闲”。
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
            {PERIODS.map((period) => (
              <tr key={period}>
                <td style={{ border: "1px solid #f0f0f0", padding: 8, textAlign: "center", background: "#fafafa" }}>
                  第 {period} 节
                </td>
                {WEEKDAYS.map((wd) => {
                  const busyPeople = grid[wd.value][period];
                  return (
                    <td key={wd.value} style={{ border: "1px solid #f0f0f0", padding: 8, verticalAlign: "top" }}>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {busyPeople.map((b, idx) => (
                          <Tag key={idx} color={selectedPerson ? "blue" : "default"}>
                            {b.personName}
                            {selectedPerson && ` (${b.courseName})`}
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
