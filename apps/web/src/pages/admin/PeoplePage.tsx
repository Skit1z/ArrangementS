import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Card, Form, Input, InputNumber, List, Modal, Popconfirm, Select, Space, Switch, Table, Tag, TimePicker, Upload } from "antd";
import { DownloadOutlined, UploadOutlined, SettingOutlined, DeleteOutlined } from "@ant-design/icons";
import { useState } from "react";

import { adminApi } from "@/features/admin/api";
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
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [rulesPerson, setRulesPerson] = useState<Person | null>(null);
  const { data, isLoading } = useQuery<Person[]>({
    queryKey: ["people", keyword],
    queryFn: async () => (await api.get("/people", { params: { keyword: keyword || undefined } })).data,
  });

  const [importVisible, setImportVisible] = useState(false);

  const toggleSchedulingPool = useMutation({
    mutationFn: async ({ personIds, enabled }: { personIds: string[]; enabled: boolean }) => {
      await api.put("/people/scheduling-pool", { person_ids: personIds, enabled });
    },
    onSuccess: () => {
      message.success("自动排班状态已更新");
      qc.invalidateQueries({ queryKey: ["people"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

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
            render: (v: boolean, r: Person) => (
              <Switch
                checked={v}
                onChange={(checked) => toggleSchedulingPool.mutate({ personIds: [r.id], enabled: checked })}
                loading={toggleSchedulingPool.isPending}
              />
            ),
          },
          {
            title: "操作",
            key: "action",
            render: (_, r: Person) => (
              <Button
                icon={<SettingOutlined />}
                size="small"
                onClick={() => setRulesPerson(r)}
              >
                规则管理
              </Button>
            ),
          },
        ]}
      />

      {importVisible && (
        <ImportModal onClose={() => setImportVisible(false)} />
      )}

      {rulesPerson && (
        <RulesModal
          person={rulesPerson}
          onClose={() => setRulesPerson(null)}
          allPeople={data ?? []}
        />
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


function RulesModal({
  person,
  onClose,
  allPeople,
}: {
  person: Person;
  onClose: () => void;
  allPeople: Person[];
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [type, setType] = useState<string>("forbid_venue");

  const venuesQ = useQuery<any[]>({
    queryKey: ["admin", "venues"],
    queryFn: adminApi.venues.list,
  });

  const constraintsQ = useQuery({
    queryKey: ["people", person.id, "constraints"],
    queryFn: async () => (await api.get(`/people/${person.id}/constraints`)).data,
  });

  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["people", person.id, "constraints"] });

  const addM = useMutation({
    mutationFn: async (values: any) => {
      let value: any = {};
      if (type === "forbid_venue" || type === "only_venue") {
        value = { venue_ids: values.venue_ids };
      } else if (type === "forbid_weekday") {
        value = { weekdays: values.weekdays };
      } else if (type === "forbid_time") {
        value = {
          ranges: [
            {
              start: values.time_range[0].format("HH:mm"),
              end: values.time_range[1].format("HH:mm"),
            },
          ],
        };
      } else if (type === "no_pair_with") {
        value = { person_ids: values.person_ids };
      } else if (type === "weekly_limit") {
        value = { limit: values.limit };
      }

      await api.post(`/people/${person.id}/constraints`, {
        constraint_type: type,
        constraint_value: value,
        is_hard: true,
      });
    },
    onSuccess: () => {
      message.success("规则添加成功");
      form.resetFields();
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const deleteM = useMutation({
    mutationFn: async (cid: string) => {
      await api.delete(`/people/${person.id}/constraints/${cid}`);
    },
    onSuccess: () => {
      message.success("规则已删除");
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const weekdaysMap: Record<number, string> = {
    1: "周一",
    2: "周二",
    3: "周三",
    4: "周四",
    5: "周五",
    6: "周六",
    7: "周日",
  };

  const renderConstraintValue = (c: any) => {
    const val = c.constraint_value || {};
    if (c.constraint_type === "forbid_venue") {
      const names = (val.venue_ids || [])
        .map((vid: string) => venuesQ.data?.find((v) => v.id === vid)?.name || vid)
        .join("、");
      return `禁止在场地【${names}】值班`;
    }
    if (c.constraint_type === "only_venue") {
      const names = (val.venue_ids || [])
        .map((vid: string) => venuesQ.data?.find((v) => v.id === vid)?.name || vid)
        .join("、");
      return `只允许在场地【${names}】值班`;
    }
    if (c.constraint_type === "forbid_weekday") {
      const wNames = (val.weekdays || []).map((w: number) => weekdaysMap[w] || w).join("、");
      return `禁止在【${wNames}】值班`;
    }
    if (c.constraint_type === "forbid_time") {
      const rangesStr = (val.ranges || [])
        .map((r: any) => `${r.start}–${r.end}`)
        .join("、");
      return `禁止在时段【${rangesStr}】值班`;
    }
    if (c.constraint_type === "no_pair_with") {
      const pNames = (val.person_ids || [])
        .map((pid: string) => allPeople.find((p) => p.id === pid)?.full_name || pid)
        .join("、");
      return `禁止与【${pNames}】同班值班`;
    }
    if (c.constraint_type === "weekly_limit") {
      return `每周最多值班：${val.limit} 次`;
    }
    return JSON.stringify(val);
  };

  const otherPeople = allPeople.filter((p) => p.id !== person.id);

  return (
    <Modal
      title={`排班规则管理 - ${person.full_name}`}
      open
      onCancel={onClose}
      footer={null}
      width={700}
    >
      <div style={{ marginBottom: 20 }}>
        <h4 style={{ margin: "0 0 10px 0" }}>已配置规则</h4>
        <List
          loading={constraintsQ.isLoading || venuesQ.isLoading}
          dataSource={constraintsQ.data ?? []}
          renderItem={(c: any) => (
            <List.Item
              actions={[
                <Popconfirm title="确定删除此规则？" onConfirm={() => deleteM.mutate(c.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />}>
                    删除
                  </Button>
                </Popconfirm>,
              ]}
            >
              <span>{renderConstraintValue(c)}</span>
            </List.Item>
          )}
          locale={{ emptyText: "暂无自定义规则" }}
        />
      </div>

      <div style={{ borderTop: "1px solid #f0f0f0", paddingTop: 20 }}>
        <h4 style={{ margin: "0 0 16px 0" }}>新增排班规则</h4>
        <Form form={form} layout="vertical" onFinish={(v) => addM.mutate(v)}>
          <Form.Item label="规则类型">
            <Select value={type} onChange={(val) => { setType(val); form.resetFields(); }}>
              <Select.Option value="forbid_venue">禁止值班场地</Select.Option>
              <Select.Option value="only_venue">仅限值班场地</Select.Option>
              <Select.Option value="forbid_weekday">禁止值班星期</Select.Option>
              <Select.Option value="forbid_time">禁止值班时段</Select.Option>
              <Select.Option value="no_pair_with">禁止同班人员</Select.Option>
              <Select.Option value="weekly_limit">每周频次上限</Select.Option>
            </Select>
          </Form.Item>

          {(type === "forbid_venue" || type === "only_venue") && (
            <Form.Item name="venue_ids" label="选择场地" rules={[{ required: true, message: "请选择场地" }]}>
              <Select mode="multiple" placeholder="选择场地">
                {(venuesQ.data ?? []).map((v) => (
                  <Select.Option key={v.id} value={v.id}>
                    {v.name}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          )}

          {type === "forbid_weekday" && (
            <Form.Item name="weekdays" label="选择星期" rules={[{ required: true, message: "请选择星期" }]}>
              <Select mode="multiple" placeholder="选择星期">
                {[1, 2, 3, 4, 5, 6, 7].map((w) => (
                  <Select.Option key={w} value={w}>
                    {weekdaysMap[w]}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          )}

          {type === "forbid_time" && (
            <Form.Item name="time_range" label="选择时段" rules={[{ required: true, message: "请选择时间段" }]}>
              <TimePicker.RangePicker format="HH:mm" minuteStep={15} style={{ width: "100%" }} />
            </Form.Item>
          )}

          {type === "no_pair_with" && (
            <Form.Item name="person_ids" label="选择人员" rules={[{ required: true, message: "请选择人员" }]}>
              <Select mode="multiple" placeholder="选择人员" showSearch optionFilterProp="label">
                {otherPeople.map((p) => (
                  <Select.Option key={p.id} value={p.id} label={`${p.full_name} (${p.class_name})`}>
                    {p.full_name} ({p.class_name})
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          )}

          {type === "weekly_limit" && (
            <Form.Item name="limit" label="次数上限" rules={[{ required: true, message: "请输入次数" }]}>
              <InputNumber min={1} max={10} style={{ width: "100%" }} />
            </Form.Item>
          )}

          <Button type="primary" htmlType="submit" loading={addM.isPending} block>
            添加规则
          </Button>
        </Form>
      </div>
    </Modal>
  );
}
