import { useQuery } from "@tanstack/react-query";
import { Card, Input, Table, Tag } from "antd";
import { useState } from "react";

import { api } from "@/api/client";

interface Person {
  id: string;
  student_no: string;
  class_name: string;
  full_name: string;
  phone: string;
  status: string;
  is_in_scheduling_pool: boolean;
}

export default function PeoplePage() {
  const [keyword, setKeyword] = useState("");
  const { data, isLoading } = useQuery<Person[]>({
    queryKey: ["people", keyword],
    queryFn: async () => (await api.get("/people", { params: { keyword: keyword || undefined } })).data,
  });

  return (
    <Card title="人员管理">
      <Input.Search
        placeholder="按姓名或学号搜索"
        allowClear
        style={{ maxWidth: 320, marginBottom: 16 }}
        onSearch={setKeyword}
      />
      <Table<Person>
        rowKey="id"
        loading={isLoading}
        dataSource={data}
        columns={[
          { title: "学号", dataIndex: "student_no" },
          { title: "班级", dataIndex: "class_name" },
          { title: "姓名", dataIndex: "full_name" },
          { title: "手机号", dataIndex: "phone" },
          {
            title: "状态",
            dataIndex: "status",
            render: (v) => <Tag color={v === "active" ? "green" : "default"}>{v}</Tag>,
          },
          {
            title: "自动排班",
            dataIndex: "is_in_scheduling_pool",
            render: (v: boolean) => (v ? <Tag color="blue">参与</Tag> : <Tag>不参与</Tag>),
          },
        ]}
      />
    </Card>
  );
}
