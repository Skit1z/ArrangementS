import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Card, Typography } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { PdfFilePicker } from "@/components/PdfFilePicker";
import { TimetableEntryEditor } from "@/components/TimetableEntryEditor";
import { meApi, type ParsedEntry } from "@/features/me/api";

export default function UploadTimetablePage() {
  const { message, modal } = App.useApp();
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [parsed, setParsed] = useState<ParsedEntry[] | null>(null);
  const [fileName, setFileName] = useState<string>("");

  // 查询本人当前学期是否已有生效课表（用于覆盖确认弹窗）
  const activeQuery = useQuery({
    queryKey: ["me", "timetable", "active"],
    queryFn: meApi.timetable.myActive,
  });

  const parseMut = useMutation({
    mutationFn: (file: File) => meApi.timetable.parsePdf(file),
    onSuccess: (data) => {
      if (data.entries.length === 0) {
        message.error("未在 PDF 中识别到课程");
        return;
      }
      setParsed(data.entries);
      message.success(`已解析出 ${data.entries.length} 条课程时段`);
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const confirmMut = useMutation({
    mutationFn: async () => {
      // 1. 创建 upload（semester_id / person_id 不传，后端用当前学期 + 当前用户）
      const up = await meApi.timetable.upload(fileName, parsed!);
      // 2. 直接 approve 生效（上传即生效）
      await meApi.timetable.approve(up.id);
    },
    onSuccess: () => {
      message.success("课表已生效");
      qc.invalidateQueries({ queryKey: ["me"] });
      navigate("/app/home");
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const handleConfirm = () => {
    if (!parsed?.length || parsed.some((entry) =>
      entry.period_start > entry.period_end || !entry.week_expr.trim()
    )) {
      message.error("请检查节次范围和周次，至少保留一条有效课程时段");
      return;
    }
    if (activeQuery.data) {
      modal.confirm({
        title: "确认覆盖现有课表",
        content: `你已于 ${dayjs(activeQuery.data.uploaded_at).format("YYYY-MM-DD")} 上传过课表（${activeQuery.data.entries.length} 条）。新上传将覆盖旧课表。是否继续？`,
        okText: "覆盖并生效",
        cancelText: "取消",
        okButtonProps: { danger: true },
        onOk: () => confirmMut.mutate(),
      });
    } else {
      confirmMut.mutate();
    }
  };

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
          上传我的课表
        </Typography.Title>
      </div>

      {activeQuery.data && (
        <Card size="small" style={{ marginBottom: 12, background: "#fffbe6", border: "1px solid #ffe58f" }}>
          <div style={{ fontSize: 13 }}>
            ⚠️ 你已于 {dayjs(activeQuery.data.uploaded_at).format("YYYY-MM-DD")} 上传过课表
            （{activeQuery.data.entries.length} 条）。再次上传将覆盖。
          </div>
        </Card>
      )}

      <Card size="small" style={{ marginBottom: 12 }}>
        <PdfFilePicker
          isPending={parseMut.isPending}
          onSelectFile={(file) => {
            setFileName(file.name);
            parseMut.mutate(file);
          }}
        />
      </Card>

      {parsed && (
        <Card
          size="small"
          title={`解析结果（${parsed.length} 条）`}
          extra={
            <Button type="primary" loading={confirmMut.isPending} onClick={handleConfirm}>
              确认生效
            </Button>
          }
        >
          <TimetableEntryEditor value={parsed} onChange={setParsed} />
          <div style={{ marginTop: 8, color: "#888", fontSize: 12 }}>
            * 仅记录时段占用用于排班，不存储课程名等业务信息。
          </div>
        </Card>
      )}
    </div>
  );
}
