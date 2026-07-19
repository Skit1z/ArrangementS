import { useQuery } from "@tanstack/react-query";
import { Card, DatePicker, Descriptions, Empty, Statistic, Typography, Button } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { hoursOf, meApi } from "@/features/me/api";

export default function HoursPage() {
  const navigate = useNavigate();
  const [month, setMonth] = useState(dayjs().format("YYYY-MM"));
  const hours = useQuery({ queryKey: ["me", "hours", month], queryFn: () => meApi.hours(month) });
  const d = hours.data;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate(-1)}
          style={{ fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center" }}
        />
        <Typography.Title level={4} style={{ margin: 0 }}>
          我的工时
        </Typography.Title>
      </div>
      <DatePicker
        picker="month"
        value={dayjs(month)}
        onChange={(v) => v && setMonth(v.format("YYYY-MM"))}
        style={{ marginBottom: 12 }}
        allowClear={false}
      />

      <Card size="small" loading={hours.isLoading} style={{ marginBottom: 12 }}>
        {d && !d.calculated ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="本月尚未统计（管理员重算后可见）" />
        ) : (
          <div style={{ display: "flex", gap: 32 }}>
            <Statistic title="实际完成工时" value={hoursOf(d?.completed_minutes ?? 0)} suffix="h" />
            <Statistic title="倍率增加" value={hoursOf(d?.multiplier_extra_minutes ?? 0)} suffix="h" />
          </div>
        )}
      </Card>

      {d?.calculated && (
        <>
          <Card size="small" title="次数统计" style={{ marginBottom: 12 }}>
            <Descriptions column={3} size="small">
              <Descriptions.Item label="请假">{d.leave_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="换班转出">{d.swap_out_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="未到岗">{d.absence_count ?? 0}</Descriptions.Item>
            </Descriptions>
          </Card>

          <Card size="small" title="各场地工时">
            {d.venues.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无场地工时" />
            ) : (
              <Descriptions column={2} size="small">
                {d.venues.map((v) => (
                  <Descriptions.Item key={v.venue_id} label={`场地 ${v.venue_id.slice(0, 6)}`}>
                    {hoursOf(v.completed_minutes)}h
                  </Descriptions.Item>
                ))}
              </Descriptions>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
