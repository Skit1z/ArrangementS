import { Tabs } from "antd";
import { useSearchParams } from "react-router-dom";
import SwapsPage from "./SwapsPage";
import AvailabilityPage from "./AvailabilityPage";
import OvertimePage from "./OvertimePage";

export default function RequestsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") || "swaps";

  return (
    <div style={{ paddingBottom: 16 }}>
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setSearchParams({ tab: key })}
        items={[
          {
            key: "swaps",
            label: "换班替班",
            children: <SwapsPage hideTitle />,
          },
          {
            key: "availability",
            label: "不可值班",
            children: <AvailabilityPage hideTitle />,
          },
          {
            key: "overtime",
            label: "加班申请",
            children: <OvertimePage hideTitle />,
          },
        ]}
      />
    </div>
  );
}
