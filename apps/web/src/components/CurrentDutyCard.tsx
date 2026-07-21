import { useQuery } from "@tanstack/react-query";
import { Badge, Card, Empty, Skeleton, Space } from "antd";
import { ClockCircleOutlined, PhoneOutlined, UserOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { adminApi, type CurrentDutyItem, type ShiftInfo } from "@/features/admin/api";

function ShiftPeople({ people }: { people: { full_name: string; class_name: string | null; phone: string | null }[] }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {people.map((p, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 8px",
            borderRadius: 4,
            background: "#fff",
            border: "1px solid #e8e8e8",
            fontSize: 12,
          }}
        >
          <UserOutlined style={{ color: "#1677ff", fontSize: 12 }} />
          <span style={{ fontWeight: 600 }}>{p.full_name}</span>
          {p.class_name ? <span style={{ color: "#888" }}>({p.class_name})</span> : null}
          {p.phone ? (
            <a href={`tel:${p.phone}`} style={{ fontSize: 11, color: "#1677ff", marginLeft: 2 }}>
              <PhoneOutlined /> {p.phone}
            </a>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function ShiftCard({
  shift,
  label,
  isCurrent,
}: {
  shift: ShiftInfo;
  label: string;
  isCurrent?: boolean;
}) {
  const start = dayjs(shift.start_at);
  const end = dayjs(shift.end_at);
  const timeStr = `${start.format("HH:mm")} - ${end.format("HH:mm")}`;

  return (
    <div
      style={{
        flex: isCurrent ? "1.4" : "1",
        minWidth: isCurrent ? 200 : 140,
        background: isCurrent
          ? "linear-gradient(180deg, #e6f4ff 0%, #bae0ff 100%)"
          : "#f5f5f5",
        borderRadius: 10,
        padding: isCurrent ? "12px 14px" : "8px 10px",
        border: isCurrent ? "2px solid #1677ff" : "1px solid #e0e0e0",
        boxShadow: isCurrent ? "0 4px 16px rgba(22,119,255,0.18)" : "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      {/* Label */}
      <div
        style={{
          fontSize: isCurrent ? 13 : 11,
          fontWeight: 600,
          color: isCurrent ? "#1677ff" : "#8c8c8c",
          marginBottom: 6,
          textAlign: "center",
        }}
      >
        {isCurrent && <Badge status="processing" color="green" style={{ marginRight: 4 }} />}
        {label}
      </div>

      {/* Time */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          gap: 6,
          marginBottom: 8,
        }}
      >
        <ClockCircleOutlined style={{ fontSize: isCurrent ? 14 : 12, color: isCurrent ? "#1677ff" : "#999" }} />
        <span
          style={{
            fontWeight: 700,
            fontSize: isCurrent ? 15 : 12,
            color: isCurrent ? "#1F497D" : "#595959",
          }}
        >
          {timeStr}
        </span>
      </div>

      {/* People */}
      {shift.people.length > 0 ? (
        <ShiftPeople people={shift.people} />
      ) : (
        <div style={{ fontSize: 11, color: "#ccc", textAlign: "center" }}>暂无安排</div>
      )}
    </div>
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
          <span style={{ fontWeight: 600, fontSize: 15 }}>当前值班人员</span>
        </Space>
      }
      style={{ marginBottom: 16, borderRadius: 10, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
    >
      {isLoading ? (
        <Skeleton active paragraph={{ rows: 2 }} />
      ) : !data || data.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前时刻暂无在岗值班人员" />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {Array.from(new Set(data.map((d) => d.venue_id))).map((venueId) => {
            const items = data.filter((d) => d.venue_id === venueId);
            const venueName = items[0]?.venue_name ?? "值班岗位";
            const first = items[0];
            const prevShift = first?.previous_shift;
            const nextShift = first?.next_shift;

            // 构建当前班次 people
            const currentPeople = items.map((item) => ({
              full_name: item.full_name,
              class_name: item.class_name,
              phone: item.phone,
            }));

            const currentStart = items[0]?.slot_start_at ?? "";
            const currentEnd = items[0]?.slot_end_at ?? "";

            return (
              <div key={venueId}>
                {/* 场地标题 */}
                <div style={{ fontWeight: 600, color: "#1F497D", fontSize: 14, marginBottom: 8 }}>
                  📍 {venueName}
                </div>

                {/* 三栏布局 */}
                <div style={{ display: "flex", gap: 10, alignItems: "stretch", flexWrap: "wrap" }}>
                  {/* 上一班 */}
                  {prevShift ? (
                    <ShiftCard shift={prevShift} label="上一班" />
                  ) : (
                    <div style={{ flex: 1, minWidth: 140 }} />
                  )}

                  {/* 当前班（居中突出） */}
                  <ShiftCard
                    shift={{
                      start_at: currentStart,
                      end_at: currentEnd,
                      people: currentPeople,
                    }}
                    label="当前在岗"
                    isCurrent
                  />

                  {/* 下一班 */}
                  {nextShift ? (
                    <ShiftCard shift={nextShift} label="下一班" />
                  ) : (
                    <div style={{ flex: 1, minWidth: 140 }} />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
