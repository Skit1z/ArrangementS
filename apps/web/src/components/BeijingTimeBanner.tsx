import { ClockCircleOutlined } from "@ant-design/icons";
import { Tag } from "antd";
import dayjs from "dayjs";
import { useEffect, useState } from "react";

export function BeijingTimeBanner() {
  const [timeStr, setTimeStr] = useState(() => dayjs().format("YYYY年MM月DD日 HH:mm:ss ddd"));

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeStr(dayjs().format("YYYY年MM月DD日 HH:mm:ss ddd"));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div
      style={{
        background: "linear-gradient(135deg, #1F497D 0%, #1677ff 100%)",
        color: "#fff",
        borderRadius: 12,
        padding: "16px 22px",
        marginBottom: 20,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        boxShadow: "0 4px 16px rgba(22, 119, 255, 0.18)",
      }}
    >
      <div>
        <div style={{ fontSize: 13, opacity: 0.85, marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
          <ClockCircleOutlined />
          <span>实时北京时间</span>
        </div>
        <div
          style={{
            fontSize: 26,
            fontWeight: 700,
            letterSpacing: 1.2,
            fontFamily: "'SF Mono', Consolas, Monaco, monospace, sans-serif",
          }}
        >
          {timeStr}
        </div>
      </div>
      <Tag
        color="green"
        style={{
          fontSize: 13,
          fontWeight: 600,
          padding: "6px 14px",
          borderRadius: 20,
          border: "none",
          background: "rgba(82, 196, 26, 0.25)",
          color: "#73d13d",
        }}
      >
        ● 实时同步
      </Tag>
    </div>
  );
}
