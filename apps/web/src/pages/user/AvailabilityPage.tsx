import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Card, Checkbox, DatePicker, Empty, Form, Input, List, Tag, Typography } from "antd";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";

import { errorMessage } from "@/api/client";
import { meApi, STATUS_COLOR, STATUS_LABEL } from "@/features/me/api";
import { colors } from "@/theme";

interface FormValues {
  range: [Dayjs, Dayjs];
  reason: string;
  weekly?: boolean;
  recurrenceUntil?: Dayjs;
}

export default function AvailabilityPage({ hideTitle }: { hideTitle?: boolean }) {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [form] = Form.useForm<FormValues>();

  const list = useQuery({ queryKey: ["me", "availability"], queryFn: meApi.availabilityRequests });

  const create = useMutation({
    mutationFn: (v: FormValues) =>
      meApi.createAvailabilityRequest(
        v.range[0].toISOString(),
        v.range[1].toISOString(),
        v.reason.trim(),
        v.weekly && v.recurrenceUntil
          ? `FREQ=WEEKLY;UNTIL=${v.recurrenceUntil.endOf("day").toISOString()}`
          : null,
      ),
    onSuccess: () => {
      message.success("已提交，等待管理员审核");
      form.resetFields();
      qc.invalidateQueries({ queryKey: ["me", "availability"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const withdraw = useMutation({
    mutationFn: meApi.withdrawAvailabilityRequest,
    onSuccess: () => {
      message.success("已撤回");
      qc.invalidateQueries({ queryKey: ["me", "availability"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  return (
    <div>
      {!hideTitle && (
        <Typography.Title level={4} style={{ marginTop: 0 }}>
          不可值班申请
        </Typography.Title>
      )}

      <Card size="small" title="新建申请" style={{ marginBottom: 12 }}>
        <Form form={form} layout="vertical" onFinish={(v) => create.mutate(v)}>
          <Form.Item name="range" label="不可值班时间段" rules={[{ required: true, message: "请选择时间段" }]}>
            <DatePicker.RangePicker showTime format="YYYY-MM-DD HH:mm" style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="reason" label="原因" rules={[{ required: true, message: "原因必填" }]}>
            <Input.TextArea rows={2} placeholder="请说明原因" />
          </Form.Item>
          <Form.Item name="weekly" valuePropName="checked">
            <Checkbox>每周重复</Checkbox>
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, next) => prev.weekly !== next.weekly}>
            {({ getFieldValue }) =>
              getFieldValue("weekly") ? (
                <Form.Item
                  name="recurrenceUntil"
                  label="重复截止日期"
                  rules={[{ required: true, message: "请选择重复截止日期" }]}
                >
                  <DatePicker
                    format="YYYY-MM-DD"
                    disabledDate={(d) => d.isBefore(dayjs().startOf("day"))}
                    style={{ width: "100%" }}
                  />
                </Form.Item>
              ) : null
            }
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={create.isPending}>
            提交申请
          </Button>
        </Form>
      </Card>

      <Card size="small" title="我的申请" loading={list.isLoading}>
        {!list.data?.length ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无申请" />
        ) : (
          <List
            dataSource={list.data}
            renderItem={(r) => (
              <List.Item
                actions={
                  r.status === "pending"
                    ? [
                        <Button key="w" size="small" onClick={() => withdraw.mutate(r.id)}>
                          撤回
                        </Button>,
                      ]
                    : []
                }
              >
                <div>
                  <div>
                    {dayjs(r.start_at).format("MM-DD HH:mm")} – {dayjs(r.end_at).format("MM-DD HH:mm")}
                    <Tag color={STATUS_COLOR[r.status]} style={{ marginLeft: 8 }}>
                      {STATUS_LABEL[r.status] ?? r.status}
                    </Tag>
                  </div>
                  <div style={{ fontSize: 12, color: "#888" }}>{r.reason}</div>
                  {r.recurrence_rule && <div style={{ fontSize: 12, color: colors.primary }}>每周重复</div>}
                </div>
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
}
