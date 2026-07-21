import { ClockCircleOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { cardShadow, colors, fontSize, radius } from "@/theme";

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
        background: colors.bgContainer,
        border: `1px solid ${colors.borderLight}`,
        borderRadius: radius.card,
        padding: "14px 20px",
        marginBottom: 16,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        boxShadow: cardShadow,
      }}
    >
      <div>
        <div
          style={{
            fontSize: fontSize.caption,
            color: colors.textTertiary,
            marginBottom: 2,
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <ClockCircleOutlined style={{ fontSize: 12 }} />
          <span>实时北京时间</span>
        </div>
        <div
          style={{
            fontSize: fontSize.display,
            fontWeight: 600,
            letterSpacing: 0.5,
            color: colors.textPrimary,
            fontFamily: "'SF Mono', Consolas, Monaco, monospace, sans-serif",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {timeStr}
        </div>
      </div>
    </div>
  );
}
