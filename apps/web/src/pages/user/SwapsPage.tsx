import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Card, Empty, List, Space, Tabs, Tag, Typography } from "antd";
import dayjs from "dayjs";

import { errorMessage } from "@/api/client";
import { meApi, STATUS_COLOR, STATUS_LABEL, type SwapRequest } from "@/features/me/api";

export default function SwapsPage() {
  const { message } = App.useApp();
  const qc = useQueryClient();

  const invitations = useQuery({ queryKey: ["me", "invitations"], queryFn: meApi.invitations });
  const mine = useQuery({ queryKey: ["me", "swaps"], queryFn: meApi.swaps });
  const open = useQuery({ queryKey: ["me", "open-swaps"], queryFn: meApi.openSwaps });

  const onDone = (okMsg: string) => ({
    onSuccess: () => {
      message.success(okMsg);
      qc.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (e: unknown) => message.error(errorMessage(e)),
  });

  const accept = useMutation({ mutationFn: meApi.acceptSwap, ...onDone("已同意，等待管理员审核") });
  const reject = useMutation({ mutationFn: meApi.rejectSwap, ...onDone("已拒绝") });
  const apply = useMutation({ mutationFn: meApi.applySwap, ...onDone("报名成功，等待管理员选择") });
  const withdraw = useMutation({ mutationFn: meApi.withdrawSwap, ...onDone("已撤回") });

  const statusTag = (s: SwapRequest) => (
    <Tag color={STATUS_COLOR[s.status] ?? "default"}>{STATUS_LABEL[s.status] ?? s.status}</Tag>
  );

  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        换班
      </Typography.Title>
      <Tabs
        items={[
          {
            key: "inv",
            label: `收到的邀请${invitations.data?.length ? ` (${invitations.data.length})` : ""}`,
            children: (
              <Card size="small" loading={invitations.isLoading}>
                {!invitations.data?.length ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无邀请" />
                ) : (
                  <List
                    dataSource={invitations.data}
                    renderItem={(s) => (
                      <List.Item>
                        <div style={{ width: "100%" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                            <span style={{ fontWeight: 600 }}>{s.requester_name} 邀请你接替其班次</span>
                            {statusTag(s)}
                          </div>
                          {s.slot_start_at && (
                            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
                              班次：{dayjs(s.slot_start_at).format("MM-DD ddd HH:mm")}–{dayjs(s.slot_end_at).format("HH:mm")} ({s.venue_name})
                              <br />
                              联系电话：{s.requester_phone || "无"}
                            </div>
                          )}
                          <Space style={{ marginTop: 8 }}>
                            <Button size="small" type="primary" onClick={() => accept.mutate(s.id)}>
                              同意
                            </Button>
                            <Button size="small" onClick={() => reject.mutate(s.id)}>
                              拒绝
                            </Button>
                          </Space>
                        </div>
                      </List.Item>
                    )}
                  />
                )}
              </Card>
            ),
          },
          {
            key: "mine",
            label: "我发起的",
            children: (
              <Card size="small" loading={mine.isLoading}>
                {!mine.data?.length ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无发起的换班" />
                ) : (
                  <List
                    dataSource={mine.data}
                    renderItem={(s) => (
                      <List.Item>
                        <div style={{ width: "100%" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                            <span style={{ fontWeight: 600 }}>{s.mode === "open" ? "公开替班" : "指定换班"}</span>
                            {statusTag(s)}
                          </div>
                          {s.slot_start_at && (
                            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
                              班次：{dayjs(s.slot_start_at).format("MM-DD ddd HH:mm")}–{dayjs(s.slot_end_at).format("HH:mm")} ({s.venue_name})
                            </div>
                          )}
                          {!["approved", "rejected", "withdrawn"].includes(s.status) && (
                            <Button size="small" style={{ marginTop: 8 }} onClick={() => withdraw.mutate(s.id)}>
                              撤回
                            </Button>
                          )}
                        </div>
                      </List.Item>
                    )}
                  />
                )}
              </Card>
            ),
          },
          {
            key: "open",
            label: "公开替班",
            children: (
              <Card size="small" loading={open.isLoading}>
                {!open.data?.length ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无公开征集" />
                ) : (
                  <List
                    dataSource={open.data}
                    renderItem={(s) => (
                      <List.Item>
                        <div style={{ width: "100%" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                            <span style={{ fontWeight: 600 }}>{s.requester_name} 征集替班人员</span>
                            {statusTag(s)}
                          </div>
                          {s.slot_start_at && (
                            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
                              班次：{dayjs(s.slot_start_at).format("MM-DD ddd HH:mm")}–{dayjs(s.slot_end_at).format("HH:mm")} ({s.venue_name})
                              <br />
                              联系电话：{s.requester_phone || "无"}
                            </div>
                          )}
                          <Button
                            size="small"
                            type="primary"
                            style={{ marginTop: 8 }}
                            onClick={() => apply.mutate(s.id)}
                          >
                            我要报名
                          </Button>
                        </div>
                      </List.Item>
                    )}
                  />
                )}
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}
