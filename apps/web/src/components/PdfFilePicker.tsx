import { App, Spin } from "antd";
import { useState } from "react";

interface Props {
  disabled?: boolean;
  disabledReason?: string;
  isPending?: boolean;
  onSelectFile: (file: File) => void;
}

export function PdfFilePicker({
  disabled = false,
  disabledReason,
  isPending = false,
  onSelectFile,
}: Props) {
  const { message } = App.useApp();
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onSelectFile(file);
    }
    e.target.value = "";
  };

  const handleDisabledClick = () => {
    if (disabled && disabledReason) {
      message.error(disabledReason);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled || isPending) {
      if (disabledReason) message.error(disabledReason);
      return;
    }
    const file = e.dataTransfer.files?.[0];
    if (file) {
      onSelectFile(file);
    }
  };

  return (
    <div
      onClick={disabled ? handleDisabledClick : undefined}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled && !isPending) setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      style={{
        position: "relative",
        border: `2px dashed ${isDragOver ? "#1677ff" : disabled ? "#d9d9d9" : "#91caff"}`,
        borderRadius: 8,
        background: isDragOver ? "#e6f4ff" : disabled ? "#fafafa" : "#f0f7ff",
        padding: "28px 16px",
        textAlign: "center",
        cursor: disabled || isPending ? "not-allowed" : "pointer",
        transition: "all 0.2s",
        marginTop: 12,
        userSelect: "none",
        overflow: "hidden",
      }}
    >
      {!disabled && !isPending && (
        <input
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleFileChange}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            opacity: 0,
            cursor: "pointer",
            zIndex: 10,
          }}
        />
      )}
      {isPending ? (
        <Spin tip="正在智能解析 PDF 课表，请稍候..." />
      ) : (
        <>
          <p style={{ fontSize: 42, color: disabled ? "#ccc" : "#1677ff", margin: "4px 0" }}>📄</p>
          <p style={{ color: disabled ? "#999" : "#1677ff", margin: "6px 0", fontWeight: 600, fontSize: 16 }}>
            {disabled ? disabledReason || "当前不可上传" : "点击此区域选择 或 拖拽 PDF 课表文件至此"}
          </p>
          <p style={{ color: "#888", fontSize: 13, margin: "4px 0 0" }}>
            仅支持学校教务系统导出的 PDF 格式课表 (10MB 以内)
          </p>
        </>
      )}
    </div>
  );
}
