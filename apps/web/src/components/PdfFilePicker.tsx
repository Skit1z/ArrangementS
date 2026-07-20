import { UploadOutlined } from "@ant-design/icons";
import { App, Button, Spin } from "antd";
import { useRef, useState } from "react";

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
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleClick = () => {
    if (disabled) {
      if (disabledReason) message.error(disabledReason);
      return;
    }
    inputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onSelectFile(file);
    }
    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled) {
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
      onClick={handleClick}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      style={{
        border: `2px dashed ${isDragOver ? "#1677ff" : disabled ? "#d9d9d9" : "#91caff"}`,
        borderRadius: 8,
        background: isDragOver ? "#e6f4ff" : disabled ? "#fafafa" : "#f0f7ff",
        padding: "24px 16px",
        textAlign: "center",
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "all 0.2s",
        marginTop: 12,
        userSelect: "none",
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        style={{ display: "none" }}
        onChange={handleFileChange}
      />
      {isPending ? (
        <Spin tip="正在智能解析 PDF 课表，请稍候..." />
      ) : (
        <>
          <p style={{ fontSize: 38, color: disabled ? "#ccc" : "#1677ff", margin: "4px 0" }}>📄</p>
          <p style={{ color: disabled ? "#999" : "#1677ff", margin: "4px 0", fontWeight: 600, fontSize: 15 }}>
            {disabled ? disabledReason || "当前不可上传" : "点击选择 或 拖拽 PDF 课表文件至此"}
          </p>
          <p style={{ color: "#888", fontSize: 12, margin: "4px 0 12px" }}>
            仅支持学校教务系统导出的 PDF 课表 (10MB 以内)
          </p>
          {!disabled && (
            <Button
              type="primary"
              icon={<UploadOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                handleClick();
              }}
            >
              选择 PDF 文件
            </Button>
          )}
        </>
      )}
    </div>
  );
}
