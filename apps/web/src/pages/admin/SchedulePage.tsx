import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Button,
  Card,
  DatePicker,
  Empty,
  Form,
  InputNumber,
  Modal,
  Select,
  Space,
  Spin,
  Tag,
  Tabs,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useState } from "react";

import { api, errorMessage } from "@/api/client";
import DutyRosterPage from "@/pages/admin/DutyRosterPage";
import ScheduleBoard from "@/features/schedule/ScheduleBoard";
import {
  type Board,
  boardFromWeek,
  type Conflict,
  type DraftOperation,
  type WeekPerson,
  type WeekView,
} from "@/features/schedule/types";
import { adminApi, type Semester, type Venue } from "@/features/admin/api";

function mondayOf(d: Dayjs): string {
  const day = d.day() === 0 ? 7 : d.day();
  return d.subtract(day - 1, "day").format("YYYY-MM-DD");
}

function computeWeekLabel(weekStartStr: string, semesters: Semester[]): string {
  const target = dayjs(weekStartStr);
  if (!semesters || semesters.length === 0) {
    return `${target.format("YYYY年")} 第 ${target.isoWeek()} 周`;
  }

  // 排序学期
  const sorted = [...semesters].sort((a, b) =>
    dayjs(a.first_monday).diff(dayjs(b.first_monday))
  );

  // 1. 是否落在某个学期内
  for (const sem of sorted) {
    const start = dayjs(sem.first_monday);
    const end = start.add(sem.week_count, "week");
    if (target.isSame(start, "day") || (target.isAfter(start) && target.isBefore(end))) {
      const weekNum = Math.floor(target.diff(start, "day") / 7) + 1;
      return `${sem.name} 第 ${weekNum} 周`;
    }
  }

  // 2. 是否落在学期后的假期
  const pastSems = sorted.filter((s) => !dayjs(s.first_monday).isAfter(target));
  if (pastSems.length > 0) {
    const latest = pastSems[pastSems.length - 1];
    const semEnd = dayjs(latest.first_monday).add(latest.week_count, "week");
    if (target.isSame(semEnd, "day") || target.isAfter(semEnd)) {
      const vacWeek = Math.floor(target.diff(semEnd, "day") / 7) + 1;
      const isWinter = [1, 2, 3, 11, 12].includes(semEnd.month() + 1);
      const vacName = isWinter ? "寒假" : "暑假";
      return `${latest.name}后 ${vacName}第 ${vacWeek} 周`;
    }
  }

  // 3. 在第一个学期之前
  const first = sorted[0];
  const firstStart = dayjs(first.first_monday);
  if (target.isBefore(firstStart)) {
    const vacWeeks = Math.floor(firstStart.diff(target, "day") / 7);
    const isWinter = [2, 3].includes(firstStart.month() + 1);
    const vacName = isWinter ? "寒假" : "暑假";
    return `${first.name}前 ${vacName}第 ${vacWeeks} 周`;
  }

  return `${target.format("YYYY年")} 第 ${target.isoWeek()} 周`;
}

export default function SchedulePage() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [week, setWeek] = useState<string>(mondayOf(dayjs()));
  const [board, setBoard] = useState<Board>({});
  const [baseline, setBaseline] = useState<Board>({});
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [creatingManual, setCreatingManual] = useState(false);
  const [activeVenueId, setActiveVenueId] = useState<string | null>(null);

  const semestersQuery = useQuery<Semester[]>({
    queryKey: ["admin", "semesters"],
    queryFn: adminApi.semesters.list,
  });

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

  useEffect(() => {
    if (venuesQuery.data && venuesQuery.data.length > 0 && !activeVenueId) {
      setActiveVenueId(venuesQuery.data[0].id);
    }
  }, [venuesQuery.data, activeVenueId]);

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
    mutationFn: async (params?: { seed?: number; clear_locks?: boolean } | void) =>
      (
        await api.post(`/schedule/weeks/${week}/generate`, {
          seed: params?.seed ?? 42,
          clear_locks: params?.clear_locks ?? false,
        })
      ).data,
    onSuccess: (d) => {
      message.success(`已生成：${d.status}，空缺 ${d.vacancies}，耗时 ${d.solve_time_seconds.toFixed(2)}s`);
      qc.invalidateQueries({ queryKey: ["week", week] });
      qc.invalidateQueries({ queryKey: ["week-people", week] });
    },
    onError: (e) => {
      const msg = errorMessage(e);
      const alreadyCleared = generate.variables?.clear_locks === true;
      if (!alreadyCleared && (msg.includes("锁定") || msg.includes("冲突"))) {
        Modal.confirm({
          title: "锁定岗位冲突提示",
          content: msg,
          okText: "解锁所有岗位并重新生成",
          okType: "danger",
          cancelText: "稍后处理",
          onOk: () => {
            generate.mutate({ clear_locks: true });
          },
        });
      } else {
        message.error(msg);
      }
    },
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

  const unpublish = useMutation({
    mutationFn: async () => (await api.post(`/schedule/weeks/${week}/unpublish`)).data,
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
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const data = weekQuery.data;

  return (
    <Tabs
      defaultActiveKey="board"
      items={[
        {
          key: "board",
          label: "排班微调与生成",
          children: (
            <Card
              title="周排班"
              extra={
                <Space wrap>
                  <DatePicker
                    picker="week"
                    value={dayjs(week)}
                    onChange={(d) => d && setWeek(mondayOf(d))}
                    format={() =>
                      data?.week_label || computeWeekLabel(week, semestersQuery.data ?? [])
                    }
                    style={{ width: 280 }}
                  />
                  <Button onClick={() => setWeek(mondayOf(dayjs()))}>本周</Button>
                  <Button onClick={() => setCreatingManual(true)} disabled={!data}>
                    新增临时班次
                  </Button>
                  <Button onClick={() => generate.mutate()} loading={generate.isPending}>
                    自动生成
                  </Button>
                  {data?.status === "published" ? (
                    <Button danger onClick={() => unpublish.mutate()} loading={unpublish.isPending}>
                      撤销发布
                    </Button>
                  ) : (
                    <Button type="primary" onClick={() => publish.mutate()} loading={publish.isPending} disabled={!data}>
                      发布
                    </Button>
                  )}
                  {data && <Tag color={data.status === "published" ? "green" : "orange"}>{data.status}</Tag>}
                  {data && <span style={{ fontSize: 12 }}>修订号 {data.revision}</span>}
                </Space>
              }
            >
              {weekQuery.isLoading && <Spin style={{ display: "block", margin: "40px auto" }} />}
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
                  checkingConflicts={checkConflicts.isPending}
                  activeVenueId={activeVenueId}
                  setActiveVenueId={setActiveVenueId}
                />
              )}

              {creatingManual && (
                <ManualSlotModal
                  weekStart={week}
                  venues={venuesQuery.data ?? []}
                  defaultVenueId={activeVenueId}
                  onClose={() => setCreatingManual(false)}
                  onSuccess={() => {
                    setCreatingManual(false);
                    weekQuery.refetch();
                  }}
                />
              )}
            </Card>
          ),
        },
        {
          key: "roster",
          label: "值班表导出与预览",
          children: <DutyRosterPage />,
        },
      ]}
    />
  );
}

function ManualSlotModal({
  weekStart,
  venues,
  defaultVenueId,
  onClose,
  onSuccess,
}: {
  weekStart: string;
  venues: Venue[];
  defaultVenueId: string | null;
  onClose: () => void;
  onSuccess: () => void;
}) {
  // weekStart 用作开始/结束时间选择器的默认值（当周周一 08:00）
  const defaultStart = dayjs(weekStart).hour(8).minute(0).second(0);
  const { message } = App.useApp();
  const [form] = Form.useForm();
  
  const createM = useMutation({
    mutationFn: async (values: any) => {
      return (await api.post("/admin/duty-slots/manual", {
        venue_id: values.venue_id,
        start_at: values.start_at.toISOString(),
        end_at: values.end_at.toISOString(),
        required_people: values.required_people,
      })).data;
    },
    onSuccess: () => {
      message.success("临时班次已创建");
      onSuccess();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  return (
    <Modal
      title="新增临时班次"
      open
      onOk={form.submit}
      onCancel={onClose}
      confirmLoading={createM.isPending}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={(values) => createM.mutate(values)}
        initialValues={{
          required_people: 1,
          venue_id: defaultVenueId || undefined,
          start_at: defaultStart,
          end_at: defaultStart.add(2, "hour"),
        }}
      >
        <Form.Item name="venue_id" label="场地" rules={[{ required: true }]}>
          <Select
            options={venues.map((v) => ({ label: v.name, value: v.id }))}
          />
        </Form.Item>
        <Form.Item name="start_at" label="开始时间 (半小时为单位)" rules={[{ required: true }]}>
          <DatePicker
            showTime={{ format: "HH:mm", minuteStep: 30 }}
            format="YYYY-MM-DD HH:mm"
            style={{ width: "100%" }}
            placeholder="选择开始时间"
          />
        </Form.Item>
        <Form.Item name="end_at" label="结束时间 (半小时为单位)" rules={[{ required: true }]}>
          <DatePicker
            showTime={{ format: "HH:mm", minuteStep: 30 }}
            format="YYYY-MM-DD HH:mm"
            style={{ width: "100%" }}
            placeholder="选择结束时间"
          />
        </Form.Item>
        <Form.Item name="required_people" label="所需人数" rules={[{ required: true }]}>
          <InputNumber min={1} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
