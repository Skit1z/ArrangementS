import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Card, Input, Modal, Space, Table, Tag, Upload } from "antd";
import { DownloadOutlined, UploadOutlined } from "@ant-design/icons";
import { useState } from "react";

import { api, errorMessage } from "@/api/client";

interface Person {
  id: string;
  student_no: string;
  class_name: string;
  full_name: string;
  phone: string;
  status: string;
  is_in_scheduling_pool: boolean;
}

export default function PeoplePage() {
  const [keyword, setKeyword] = useState("");
  const { data, isLoading } = useQuery<Person[]>({
    queryKey: ["people", keyword],
    queryFn: async () => (await api.get("/people", { params: { keyword: keyword || undefined } })).data,
  });

  const [importVisible, setImportVisible] = useState(false);

  return (
    <Card title="人员管理">
      <Space style={{ marginBottom: 16, display: "flex", justifyContent: "space-between" }}>
        <Input.Search
          placeholder="按姓名或学号搜索"
          allowClear
          style={{ width: 320 }}
          onSearch={setKeyword}
        />
        <Space>
          <Button
            icon={<DownloadOutlined />}
            onClick={() => {
              window.open(api.defaults.baseURL + "/people/import/template");
            }}
          >
            下载导入模板
          </Button>
          <Button type="primary" icon={<UploadOutlined />} onClick={() => setImportVisible(true)}>
            批量导入人员
          </Button>
        </Space>
      </Space>
      
      <Table<Person>
        rowKey="id"
        loading={isLoading}
        dataSource={data}
        columns={[
          { title: "学号", dataIndex: "student_no" },
          { title: "班级", dataIndex: "class_name" },
          { title: "姓名", dataIndex: "full_name" },
          { title: "手机号", dataIndex: "phone" },
          {
            title: "状态",
            dataIndex: "status",
            render: (v) => <Tag color={v === "active" ? "green" : "default"}>{v}</Tag>,
          },
          {
            title: "自动排班",
            dataIndex: "is_in_scheduling_pool",
            render: (v: boolean) => (v ? <Tag color="blue">参与</Tag> : <Tag>不参与</Tag>),
          },
        ]}
      />

      {importVisible && (
        <ImportModal onClose={() => setImportVisible(false)} />
      )}
    </Card>
  );
}

function ImportModal({ onClose }: { onClose: () => void }) {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [previewData, setPreviewData] = useState<any>(null);

  const previewM = useMutation({
    mutationFn: async (f: File) => {
      const formData = new FormData();
      formData.append("file", f);
      const res = await api.post("/people/import/preview", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return res.data;
    },
    onSuccess: (data) => setPreviewData(data),
    onError: (e) => message.error(errorMessage(e)),
  });

  const confirmM = useMutation({
    mutationFn: async (batchId: string) => {
      const res = await api.post(`/people/import/${batchId}/confirm`);
      return res.data;
    },
    onSuccess: (data) => {
      message.success(`成功导入！新增账号 ${data.created_count} 个`);
      qc.invalidateQueries({ queryKey: ["people"] });
      onClose();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const handleUpload = (f: File) => {
    previewM.mutate(f);
    return false;
  };

  return (
    <Modal
      title="批量导入人员"
      open
      onCancel={onClose}
      width={800}
      footer={
        previewData ? (
          <Space>
            <Button onClick={() => setPreviewData(null)}>重新上传</Button>
            <Button
              type="primary"
              loading={confirmM.isPending}
              disabled={previewData.error_rows > 0}
              onClick={() => confirmM.mutate(previewData.batch_id)}
            >
              确认导入
            </Button>
          </Space>
        ) : null
      }
    >
      {!previewData ? (
        <Upload.Dragger
          accept=".xlsx"
          showUploadList={false}
          beforeUpload={handleUpload}
          disabled={previewM.isPending}
        >
          <p className="ant-upload-drag-icon">
            <UploadOutlined />
          </p>
          <p className="ant-upload-text">点击或将 Excel 文件拖拽到此处进行预览</p>
          <p className="ant-upload-hint">请先下载模板，按格式填写后上传</p>
        </Upload.Dragger>
      ) : (
        <Space direction="vertical" style={{ width: "100%" }}>
          <Space>
            <Tag color="blue">新增：{previewData.new_rows}</Tag>
            <Tag color="orange">更新：{previewData.updated_rows}</Tag>
            <Tag>无变化：{previewData.total_rows - previewData.new_rows - previewData.updated_rows - previewData.error_rows}</Tag>
            <Tag color="red">错误：{previewData.error_rows}</Tag>
          </Space>
          <Table
            size="small"
            dataSource={previewData.rows}
            rowKey="row_no"
            scroll={{ y: 400 }}
            pagination={false}
            columns={[
              { title: "行号", dataIndex: "row_no", width: 60 },
              { title: "学号", dataIndex: "student_no", width: 120 },
              { title: "姓名", dataIndex: "full_name", width: 100 },
              {
                title: "状态",
                dataIndex: "status",
                width: 90,
                render: (v) => {
                  if (v === "new") return <Tag color="blue">新增</Tag>;
                  if (v === "update") return <Tag color="orange">更新</Tag>;
                  if (v === "error") return <Tag color="red">错误</Tag>;
                  return <Tag>无变化</Tag>;
                },
              },
              {
                title: "错误信息",
                dataIndex: "errors",
                render: (errs: string[]) => errs?.length > 0 ? errs.join("；") : "-",
              },
            ]}
          />
        </Space>
      )}
    </Modal>
  );
}
