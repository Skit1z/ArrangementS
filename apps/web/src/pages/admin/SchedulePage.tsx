import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Alert, Button, Card, DatePicker, Empty, Space, Spin, Tag } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useState } from "react";

import { api, errorMessage } from "@/api/client";
import ScheduleBoard from "@/features/schedule/ScheduleBoard";
import {
  type Board,
  boardFromWeek,
  type Conflict,
  type DraftOperation,
  type WeekView,
} from "@/features/schedule/types";
import { adminApi, type Venue } from "@/features/admin/api";

function mondayOf(d: Dayjs): string {
  const day = d.day() === 0 ? 7 : d.day();
  return d.subtract(day - 1, "day").format("YYYY-MM-DD");
}

export default function SchedulePage() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [week, setWeek] = useState<string>(mondayOf(dayjs()));
  const [board, setBoard] = useState<Board>({});
  const [baseline, setBaseline] = useState<Board>({});
  const [conflicts, setConflicts] = useState<Conflict[]>([]);

  const weekQuery = useQuery<WeekView>({
    queryKey: ["week", week],
    queryFn: async () => (await api.get(`/schedule/weeks/${week}`)).data,
    retry: false,
  });

  const peopleQuery = useQuery<WeekPerson[]>({
    queryKey: ["week-people", week],
    queryFn: async () => (await api.get(`/schedule/weeks/${week}/people`)).data,
    retry: false,
    enabled: !!weekQuery.data,
  });

  const venuesQuery = useQuery<Venue[]>({
    queryKey: ["admin", "venues"],
    queryFn: adminApi.venues.list,
  });

  // 服务端数据变化时重置棋盘与基线
  useEffect(() => {
    if (weekQuery.data) {
      const b = boardFromWeek(weekQuery.data);
      setBoard(b);
      setBaseline(b);
      setConflicts([]);
      if (weekQuery.data.slots.length > 0) {
        checkConflicts.mutate();
      }
    }
  }, [weekQuery.data]);

  const generate = useMutation({
    mutationFn: async () => (await api.post(`/schedule/weeks/${week}/generate`, { seed: 42 })).data,
    onSuccess: (d) => {
      message.success(`已生成：${d.status}，空缺 ${d.vacancies}，耗时 ${d.solve_time_seconds.toFixed(2)}s`);
      qc.invalidateQueries({ queryKey: ["week", week] });
      qc.invalidateQueries({ queryKey: ["week-people", week] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const save = useMutation({
    mutationFn: async (ops: DraftOperation[]) =>
      (await api.patch(`/schedule/weeks/${week}/draft`, {
        version: weekQuery.data!.version,
        operations: ops,
      })).data as WeekView,
    onSuccess: () => {
      message.success("草稿已保存");
      qc.invalidateQueries({ queryKey: ["week", week] });
      qc.invalidateQueries({ queryKey: ["week-people", week] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const publish = useMutation({
    mutationFn: async () => (await api.post(`/schedule/weeks/${week}/publish`)).data,
    onSuccess: (d) => {
      message.success(d.message);
      qc.invalidateQueries({ queryKey: ["week", week] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const checkConflicts = useMutation({
    mutationFn: async () => (await api.post(`/schedule/weeks/${week}/validate`)).data as Conflict[],
    onSuccess: (d) => {
      setConflicts(d);
      if (d.length) {
        message.warning(`发现 ${d.length} 处冲突`);
      }
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const data = weekQuery.data;

  return (
    <Card
      title="周排班"
      extra={
        <Space wrap>
          <DatePicker picker="week" value={dayjs(week)} onChange={(d) => d && setWeek(mondayOf(d))} />
          <Button onClick={() => setWeek(mondayOf(dayjs()))}>本周</Button>
          <Button onClick={() => generate.mutate()} loading={generate.isPending}>
            自动生成
          </Button>
          <Button type="primary" onClick={() => publish.mutate()} loading={publish.isPending} disabled={!data}>
            发布
          </Button>
          {data && <Tag color={data.status === "published" ? "green" : "orange"}>{data.status}</Tag>}
          {data && <span style={{ fontSize: 12 }}>修订号 {data.revision}</span>}
        </Space>
      }
    >
      {weekQuery.isLoading && <Spin />}
      {weekQuery.error && (
        <Alert type="info" showIcon message="该周尚无排班计划，点击「自动生成」创建草稿" />
      )}
      {data && data.slots.length === 0 && <Empty description="本周暂无岗位" />}
      {data && data.slots.length > 0 && (
        <ScheduleBoard
          week={data}
          people={peopleQuery.data ?? []}
          venues={venuesQuery.data ?? []}
          baseline={baseline}
          board={board}
          setBoard={setBoard}
          conflicts={conflicts}
          onSave={(ops) => save.mutate(ops)}
          saving={save.isPending}
        />
      )}
    </Card>
  );
}
