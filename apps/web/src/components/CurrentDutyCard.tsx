import { useQuery } from "@tanstack/react-query";
import { Badge, Card, Empty, Skeleton, Space, Tag } from "antd";
import { ClockCircleOutlined, PhoneOutlined, UserOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { adminApi, type CurrentDutyItem } from "@/features/admin/api";

export function LiveClock() {
  const [timeStr, setTimeStr] = useState(() => dayjs().format("YYYY-MM-DD HH:mm:ss ddd"));

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeStr(dayjs().format("YYYY-MM-DD HH:mm:ss ddd"));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <Space size={4} style={{ color: "#1677ff", fontWeight: 600, fontSize: 13 }}>
      <ClockCircleOutlined />
      <span>北京时间：{timeStr}</span>
    </Space>
  );
}

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
          <span style={{ fontWeight: 600, fontSize: 15 }}>当前在岗 / 实时值班人员</span>
        </Space>
      }
      extra={<LiveClock />}
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
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, alignItems: "center" }}>
                  <span style={{ fontWeight: 600, color: "#1F497D", fontSize: 14 }}>
                    📍 {venueName}
                  </span>
                  {timeRange && (
                    <Tag color="blue" style={{ margin: 0 }}>
                      在岗时段：{timeRange}
                    </Tag>
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
                      <span style={{ fontSize: 12, color: "#888" }}>（{item.class_name}）</span>
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
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
