import { useQuery } from "@tanstack/react-query";
import { Badge, Card, Empty, Skeleton, Space } from "antd";
import { ClockCircleOutlined, PhoneOutlined, UserOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { adminApi, type CurrentDutyItem } from "@/features/admin/api";

export function CurrentDutyCard() {
  const { data, isLoading } = useQuery<CurrentDutyItem[]>({
    queryKey: ["schedule", "current-duty"],
    queryFn: adminApi.schedule.currentDuty,
    refetchInterval: 15000,
    staleTime: 60000,
    gcTime: 300000,
    placeholderData: (previousData) => previousData,
  });

  return (
    <Card
      size="small"
      title={
        <Space>
          <Badge status="processing" color="green" />
          <span style={{ fontWeight: 600, fontSize: 15 }}>当前值班人员</span>
        </Space>
      }
      style={{ marginBottom: 16, borderRadius: 10, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
    >
      {isLoading ? (
        <Skeleton active paragraph={{ rows: 2 }} />
      ) : !data || data.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="当前时刻暂无在岗值班人员"
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {Array.from(new Set(data.map((d) => d.venue_id))).map((venueId) => {
            const venueItems = data.filter((d) => d.venue_id === venueId);
            const venueName = venueItems[0]?.venue_name ?? "值班岗位";
            const slotStart = venueItems[0]?.slot_start_at;
            const slotEnd = venueItems[0]?.slot_end_at;
            const timeRange =
              slotStart && slotEnd
                ? `${dayjs(slotStart).format("HH:mm")} - ${dayjs(slotEnd).format("HH:mm")}`
                : "";
            const slotDate = slotStart ? dayjs(slotStart).format("MM-DD") : "";

            // 取同一场地的第一项的 previous/next shift（这些字段后端已下发到每条记录）
            const previousShift = venueItems[0]?.previous_shift ?? [];
            const nextShift = venueItems[0]?.next_shift ?? [];

            return (
              <div
                key={venueId}
                style={{
                  background: "#fafafa",
                  padding: "10px 14px",
                  borderRadius: 8,
                  border: "1px solid #f0f0f0",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 10,
                    flexWrap: "wrap",
                    gap: 6,
                  }}
                >
                  <span style={{ fontWeight: 600, color: "#1F497D", fontSize: 14 }}>
                    📍 {venueName}
                  </span>
                  {timeRange && (
                    <div
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        background: "linear-gradient(135deg, #1677ff 0%, #4096ff 100%)",
                        color: "#fff",
                        fontWeight: 600,
                        fontSize: 13,
                        padding: "4px 12px",
                        borderRadius: 14,
                        boxShadow: "0 2px 6px rgba(22, 119, 255, 0.25)",
                      }}
                    >
                      <ClockCircleOutlined />
                      <span>{slotDate && `${slotDate} `}{timeRange}</span>
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
                  {venueItems.map((item) => (
                    <div
                      key={item.assignment_id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        background: "#fff",
                        padding: "8px 12px",
                        borderRadius: 6,
                        border: "1px solid #e8e8e8",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
                      }}
                    >
                      <UserOutlined style={{ color: "#52c41a", fontSize: 16 }} />
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{item.full_name}</span>
                      {item.class_name ? (
                        <span style={{ fontSize: 12, color: "#888" }}>（{item.class_name}）</span>
                      ) : null}
                      {item.phone ? (
                        <a
                          href={`tel:${item.phone}`}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            color: "#1677ff",
                            fontSize: 13,
                            fontWeight: 500,
                            marginLeft: 4,
                            textDecoration: "none",
                          }}
                        >
                          <PhoneOutlined /> {item.phone}
                        </a>
                      ) : (
                        <span style={{ fontSize: 12, color: "#ccc" }}>暂无电话</span>
                      )}
                    </div>
                  ))}
                </div>

                {/* 前/后一班提示 */}
                {(previousShift.length > 0 || nextShift.length > 0) && (
                  <div
                    style={{
                      marginTop: 10,
                      paddingTop: 10,
                      borderTop: "1px dashed #e0e0e0",
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 16,
                      fontSize: 12,
                      color: "#666",
                    }}
                  >
                    {previousShift.length > 0 && (
                      <div>
                        <span style={{ color: "#8c8c8c" }}>上一班：</span>
                        <span style={{ color: "#262626", fontWeight: 500 }}>
                          {previousShift
                            .map((p) => `${p.full_name}${p.phone ? `(${p.phone})` : ""}`)
                            .join("、")}
                        </span>
                      </div>
                    )}
                    {nextShift.length > 0 && (
                      <div>
                        <span style={{ color: "#8c8c8c" }}>下一班：</span>
                        <span style={{ color: "#262626", fontWeight: 500 }}>
                          {nextShift
                            .map((p) => `${p.full_name}${p.phone ? `(${p.phone})` : ""}`)
                            .join("、")}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
