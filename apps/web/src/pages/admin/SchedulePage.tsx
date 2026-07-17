import { useQuery } from "@tanstack/react-query";
import { Alert, Card, DatePicker, Empty, Space, Spin, Table, Tag } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useState } from "react";

import { api } from "@/api/client";

interface AssignmentView {
  id: string;
  person_name: string | null;
  plan_status: string;
}
interface SlotView {
  id: string;
  slot_start_at: string;
  slot_end_at: string;
  required_people: number;
  status: string;
  assignments: AssignmentView[];
}
interface WeekView {
  plan_id: string;
  week_start: string;
  status: string;
  revision: number;
  slots: SlotView[];
}

function mondayOf(d: Dayjs): string {
  const day = d.day() === 0 ? 7 : d.day();
  return d.subtract(day - 1, "day").format("YYYY-MM-DD");
}

export default function SchedulePage() {
  const [week, setWeek] = useState<string>(mondayOf(dayjs()));

  const { data, isLoading, error } = useQuery<WeekView>({
    queryKey: ["week", week],
    queryFn: async () => (await api.get(`/schedule/weeks/${week}`)).data,
    retry: false,
  });

  return (
    <Card
      title="周排班"
      extra={
        <Space>
          <DatePicker
            picker="week"
            onChange={(d) => d && setWeek(mondayOf(d))}
            value={dayjs(week)}
          />
          {data && <Tag color={data.status === "published" ? "green" : "orange"}>{data.status}</Tag>}
          {data && <span>修订号 {data.revision}</span>}
        </Space>
      }
    >
      {isLoading && <Spin />}
      {error && <Alert type="info" message="该周尚无排班计划，可在后端生成后查看" showIcon />}
      {data && data.slots.length === 0 && <Empty description="本周暂无岗位" />}
      {data && data.slots.length > 0 && (
        <Table<SlotView>
          rowKey="id"
          dataSource={data.slots}
          pagination={false}
          columns={[
            {
              title: "时间",
              render: (_, s) =>
                `${dayjs(s.slot_start_at).format("MM-DD HH:mm")} - ${dayjs(s.slot_end_at).format("HH:mm")}`,
            },
            { title: "需求人数", dataIndex: "required_people" },
            {
              title: "已排人员",
              render: (_, s) =>
                s.assignments
                  .filter((a) => a.person_name)
                  .map((a) => a.person_name)
                  .join("、") || <Tag color="red">空缺</Tag>,
            },
            { title: "状态", dataIndex: "status" },
          ]}
        />
      )}
      <div style={{ marginTop: 12, color: "#999" }}>
        提示：拖拽排班界面为后续增量，当前为只读周视图。
      </div>
    </Card>
  );
}
