import { useQuery } from "@tanstack/react-query";
import { Card, Empty, Skeleton, Tag } from "antd";
import { ClockCircleOutlined, EnvironmentOutlined, PhoneOutlined, UserOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { adminApi, type CurrentDutyItem, type ShiftInfo } from "@/features/admin/api";
import { cardShadow, colors, fontSize, radius } from "@/theme";

interface PersonInfo {
  full_name: string;
  class_name: string | null;
  phone: string | null;
}

/**
 * 值班人员条目：姓名为主信息，电话为可点击的辅助操作。
 * 当前班与非当前班使用同一信息结构，仅通过颜色层级区分。
 */
function PersonRow({ person, emphasize }: { person: PersonInfo; emphasize?: boolean }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 8,
        padding: "5px 0",
        lineHeight: 1.6,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
        <UserOutlined
          style={{ fontSize: 12, color: emphasize ? colors.primary : colors.textTertiary, flexShrink: 0 }}
        />
        <span
          style={{
            fontSize: emphasize ? fontSize.bodyStrong : fontSize.body,
            fontWeight: emphasize ? 600 : 500,
            color: emphasize ? colors.textPrimary : colors.textSecondary,
            whiteSpace: "nowrap",
          }}
        >
          {person.full_name}
        </span>
        {person.class_name ? (
          <span
            style={{
              fontSize: fontSize.caption,
              color: colors.textTertiary,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {person.class_name}
          </span>
        ) : null}
      </div>
      {person.phone ? (
        <a
          href={`tel:${person.phone}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: fontSize.caption,
            color: colors.primary,
            flexShrink: 0,
            textDecoration: "none",
          }}
        >
          <PhoneOutlined style={{ fontSize: 11 }} />
          {person.phone}
        </a>
      ) : null}
    </div>
  );
}

function ShiftPanel({
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
        flex: isCurrent ? "1.3" : "1",
        minWidth: isCurrent ? 220 : 160,
        background: isCurrent ? colors.primaryBg : colors.bgFill,
        border: `1px solid ${isCurrent ? colors.primaryBorder : colors.borderLight}`,
        // 当前班用左侧强调条替代粗边框与渐变，简洁且层级明确
        borderLeft: isCurrent ? `3px solid ${colors.primary}` : `1px solid ${colors.borderLight}`,
        borderRadius: radius.inner,
        padding: isCurrent ? "12px 16px" : "10px 14px",
      }}
    >
      {/* 班次标签 + 状态 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 4,
        }}
      >
        <span
          style={{
            fontSize: fontSize.caption,
            color: isCurrent ? colors.primary : colors.textTertiary,
            fontWeight: isCurrent ? 600 : 400,
            letterSpacing: 0.5,
          }}
        >
          {label}
        </span>
        {isCurrent ? (
          <Tag
            color={colors.primary}
            style={{
              marginInlineEnd: 0,
              fontSize: 11,
              lineHeight: "18px",
              borderRadius: 3,
              border: "none",
            }}
          >
            在岗
          </Tag>
        ) : null}
      </div>

      {/* 时间段：该面板内最重要的信息 */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: shift.people.length > 0 ? 6 : 0 }}>
        <ClockCircleOutlined
          style={{ fontSize: 13, color: isCurrent ? colors.primary : colors.textTertiary }}
        />
        <span
          style={{
            fontSize: isCurrent ? fontSize.title : fontSize.body,
            fontWeight: 600,
            color: isCurrent ? colors.textPrimary : colors.textSecondary,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {timeStr}
        </span>
      </div>

      {/* 人员列表 */}
      {shift.people.length > 0 ? (
        <div
          style={{
            borderTop: `1px solid ${isCurrent ? colors.primaryBorder : colors.borderLight}`,
            paddingTop: 4,
          }}
        >
          {shift.people.map((p, i) => (
            <PersonRow key={i} person={p} emphasize={isCurrent} />
          ))}
        </div>
      ) : (
        <div style={{ fontSize: fontSize.caption, color: colors.textQuaternary }}>暂无安排</div>
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
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          {/* 小面积状态点：唯一保留的"鲜活"元素 */}
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: colors.success,
              display: "inline-block",
            }}
          />
          <span style={{ fontWeight: 600, fontSize: fontSize.title, color: colors.textPrimary }}>
            当前值班人员
          </span>
        </span>
      }
      style={{ marginBottom: 16, borderRadius: radius.card, boxShadow: cardShadow }}
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

            const currentPeople = items.map((item) => ({
              full_name: item.full_name,
              class_name: item.class_name,
              phone: item.phone,
            }));

            const currentStart = items[0]?.slot_start_at ?? "";
            const currentEnd = items[0]?.slot_end_at ?? "";

            return (
              <div key={venueId}>
                {/* 场地标题：图标 + 文字，层级低于卡片标题 */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: fontSize.body,
                    fontWeight: 600,
                    color: colors.textSecondary,
                    marginBottom: 8,
                  }}
                >
                  <EnvironmentOutlined style={{ fontSize: 12, color: colors.textTertiary }} />
                  {venueName}
                </div>

                {/* 三栏布局：窄屏自动换行堆叠 */}
                <div style={{ display: "flex", gap: 12, alignItems: "stretch", flexWrap: "wrap" }}>
                  {prevShift ? (
                    <ShiftPanel shift={prevShift} label="上一班" />
                  ) : (
                    <div style={{ flex: 1, minWidth: 160 }} />
                  )}

                  <ShiftPanel
                    shift={{
                      start_at: currentStart,
                      end_at: currentEnd,
                      people: currentPeople,
                    }}
                    label="当前班次"
                    isCurrent
                  />

                  {nextShift ? (
                    <ShiftPanel shift={nextShift} label="下一班" />
                  ) : (
                    <div style={{ flex: 1, minWidth: 160 }} />
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
