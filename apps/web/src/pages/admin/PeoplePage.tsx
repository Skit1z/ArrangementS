import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Card, DatePicker, Form, Input, InputNumber, List, Modal, Popconfirm, Select, Space, Switch, Table, Tag, TimePicker, Upload } from "antd";
import { DownloadOutlined, UploadOutlined, SettingOutlined, DeleteOutlined, UserAddOutlined, EditOutlined } from "@ant-design/icons";
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
  const [editingPerson, setEditingPerson] = useState<any | null>(null);
  const { data, isLoading } = useQuery<Person[]>({
    queryKey: ["people", keyword],
    queryFn: async () => (await api.get("/people", { params: { keyword: keyword || undefined } })).data,
  });

  const [importVisible, setImportVisible] = useState(false);
  const [addPersonVisible, setAddPersonVisible] = useState(false);
  const [createdAccountInfo, setCreatedAccountInfo] = useState<{
    name: string;
    username: string;
    initialPassword: string;
  } | null>(null);

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

  const deletePersonM = useMutation({
    mutationFn: (id: string) => adminApi.people.delete(id),
    onSuccess: () => {
      message.success("人员及关联账号已删除");
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
            type="primary"
            icon={<UserAddOutlined />}
            onClick={() => setAddPersonVisible(true)}
          >
            手动添加人员
          </Button>
          <Button
            icon={<DownloadOutlined />}
            onClick={() => {
              window.open(api.defaults.baseURL + "/people/import/template");
            }}
          >
            下载导入模板
          </Button>
          <Button icon={<UploadOutlined />} onClick={() => setImportVisible(true)}>
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
          { title: "班级", dataIndex: "class_name", render: (v) => v || "—" },
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
            width: 240,
            render: (_, r: Person) => (
              <Space wrap>
                <Button
                  icon={<EditOutlined />}
                  size="small"
                  onClick={() => setEditingPerson(r)}
                >
                  编辑
                </Button>
                <Button
                  icon={<SettingOutlined />}
                  size="small"
                  onClick={() => setRulesPerson(r)}
                >
                  规则
                </Button>
                <Popconfirm
                  title="确定删除该人员及其关联账号？"
                  description="该删除不可撤销，确定操作？"
                  onConfirm={() => deletePersonM.mutate(r.id)}
                >
                  <Button danger icon={<DeleteOutlined />} size="small">
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      {editingPerson && (
        <EditPersonModal
          person={editingPerson}
          onClose={() => setEditingPerson(null)}
          onSuccess={() => qc.invalidateQueries({ queryKey: ["people"] })}
        />
      )}

      {importVisible && (
        <ImportModal onClose={() => setImportVisible(false)} />
      )}

      {addPersonVisible && (
        <AddPersonModal
          open={addPersonVisible}
          onClose={() => setAddPersonVisible(false)}
          onSuccess={(info) => {
            setCreatedAccountInfo(info);
            qc.invalidateQueries({ queryKey: ["people"] });
          }}
        />
      )}

      {createdAccountInfo && (
        <Modal
          open={!!createdAccountInfo}
          title="🎉 人员添加成功"
          onOk={() => setCreatedAccountInfo(null)}
          onCancel={() => setCreatedAccountInfo(null)}
          cancelButtonProps={{ style: { display: "none" } }}
          okText="我知道了"
        >
          <p style={{ fontSize: 14, marginBottom: 12 }}>
            已成功为 <b>{createdAccountInfo.name}</b> 创建人员档案并开通登录账号：
          </p>
          <div
            style={{
              background: "#fafafa",
              padding: 16,
              borderRadius: 8,
              border: "1px solid #f0f0f0",
            }}
          >
            <p style={{ margin: "4px 0" }}>
              <b>登录账号（学号）：</b> {createdAccountInfo.username}
            </p>
            <p style={{ margin: "4px 0" }}>
              <b>初始密码：</b> <Tag color="blue">{createdAccountInfo.initialPassword}</Tag>
            </p>
          </div>
          <p style={{ fontSize: 12, color: "#888", marginTop: 12 }}>
            * 提示：用户登录系统后可随时自行修改初始密码。
          </p>
        </Modal>
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
    queryFn: async () => (await api.get(`/admin/people/${person.id}/constraints`)).data,
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
      } else if (type === "forbid_date") {
        value = { dates: (values.dates ?? []).map((d: any) => d.format("YYYY-MM-DD")) };
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
      } else if (type === "suspend") {
        value = null;
      }

      const effective: { effective_start?: string; effective_end?: string } = {};
      if (values.effective_range) {
        if (values.effective_range[0]) effective.effective_start = values.effective_range[0].format("YYYY-MM-DD");
        if (values.effective_range[1]) effective.effective_end = values.effective_range[1].format("YYYY-MM-DD");
      } else if (type === "suspend" && values.suspend_range) {
        // 暂停排班的起止直接作为约束有效期
        if (values.suspend_range[0]) effective.effective_start = values.suspend_range[0].format("YYYY-MM-DD");
        if (values.suspend_range[1]) effective.effective_end = values.suspend_range[1].format("YYYY-MM-DD");
      }

      await api.post(`/admin/people/${person.id}/constraints`, {
        constraint_type: type,
        constraint_value: value,
        is_hard: true,
        ...effective,
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
      await api.delete(`/admin/people/constraints/${cid}`);
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
    let text: string;
    if (c.constraint_type === "suspend") {
      text = "暂停排班";
    } else if (c.constraint_type === "forbid_venue") {
      const names = (val.venue_ids || [])
        .map((vid: string) => venuesQ.data?.find((v) => v.id === vid)?.name || vid)
        .join("、");
      text = `禁止在场地【${names}】值班`;
    } else if (c.constraint_type === "only_venue") {
      const names = (val.venue_ids || [])
        .map((vid: string) => venuesQ.data?.find((v) => v.id === vid)?.name || vid)
        .join("、");
      text = `只允许在场地【${names}】值班`;
    } else if (c.constraint_type === "forbid_weekday") {
      const wNames = (val.weekdays || []).map((w: number) => weekdaysMap[w] || w).join("、");
      text = `禁止在【${wNames}】值班`;
    } else if (c.constraint_type === "forbid_date") {
      text = `禁止日期【${(val.dates || []).join("、")}】`;
    } else if (c.constraint_type === "forbid_time") {
      const rangesStr = (val.ranges || [])
        .map((r: any) => `${r.start}–${r.end}`)
        .join("、");
      text = `禁止在时段【${rangesStr}】值班`;
    } else if (c.constraint_type === "no_pair_with") {
      const pNames = (val.person_ids || [])
        .map((pid: string) => allPeople.find((p) => p.id === pid)?.full_name || pid)
        .join("、");
      text = `禁止与【${pNames}】同班值班`;
    } else if (c.constraint_type === "weekly_limit") {
      text = `每周最多值班：${val.limit} 次`;
    } else {
      text = JSON.stringify(val);
    }
    // 追加有效期标注
    if (c.effective_start || c.effective_end) {
      const s = c.effective_start || "…";
      const e = c.effective_end || "…";
      text += `（生效：${s} ~ ${e}）`;
    }
    return text;
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
              <Select.Option value="suspend">暂停排班（按日期范围）</Select.Option>
              <Select.Option value="forbid_venue">禁止值班场地</Select.Option>
              <Select.Option value="only_venue">仅限值班场地</Select.Option>
              <Select.Option value="forbid_weekday">禁止值班星期</Select.Option>
              <Select.Option value="forbid_date">禁止具体日期</Select.Option>
              <Select.Option value="forbid_time">禁止值班时段</Select.Option>
              <Select.Option value="no_pair_with">禁止同班人员</Select.Option>
              <Select.Option value="weekly_limit">每周频次上限</Select.Option>
            </Select>
          </Form.Item>

          {type === "suspend" && (
            <Form.Item name="suspend_range" label="暂停起止日期" rules={[{ required: true, message: "请选择暂停起止" }]}>
              <DatePicker.RangePicker format="YYYY-MM-DD" style={{ width: "100%" }} />
            </Form.Item>
          )}

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

          {type === "forbid_date" && (
            <Form.Item name="dates" label="选择具体日期" rules={[{ required: true, message: "请选择日期" }]}>
              <DatePicker multiple format="YYYY-MM-DD" style={{ width: "100%" }} />
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

          {type !== "suspend" && (
            <Form.Item name="effective_range" label="规则有效期（可选，不填=永久）">
              <DatePicker.RangePicker format="YYYY-MM-DD" style={{ width: "100%" }} />
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

function AddPersonModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: (data: { name: string; username: string; initialPassword: string }) => void;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm();

  const createMut = useMutation({
    mutationFn: async (values: any) => {
      return await adminApi.people.create({
        student_no: values.student_no,
        class_name: values.class_name,
        full_name: values.full_name,
        phone: values.phone,
        difficulty_level: values.difficulty_level || null,
        id_card: values.id_card || null,
        bank_card: values.bank_card || null,
        is_in_scheduling_pool: values.is_in_scheduling_pool ?? true,
      });
    },
    onSuccess: (res) => {
      form.resetFields();
      onClose();
      onSuccess({
        name: res.person.full_name,
        username: res.person.student_no,
        initialPassword: res.initial_password,
      });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  return (
    <Modal
      open={open}
      title="手动添加人员"
      footer={null}
      onCancel={onClose}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{ is_in_scheduling_pool: true }}
        onFinish={(vals) => createMut.mutate(vals)}
      >
        <Form.Item
          name="student_no"
          label="学号"
          rules={[{ required: true, message: "请输入学号" }]}
        >
          <Input placeholder="例如：2023000001" />
        </Form.Item>

        <Form.Item
          name="class_name"
          label="班级（可选）"
        >
          <Input placeholder="例如：计科2301（非必填）" />
        </Form.Item>

        <Form.Item
          name="full_name"
          label="姓名"
          rules={[{ required: true, message: "请输入姓名" }]}
        >
          <Input placeholder="例如：张三" />
        </Form.Item>

        <Form.Item
          name="phone"
          label="手机号"
          rules={[
            { required: true, message: "请输入手机号" },
            { pattern: /^1[3-9]\d{9}$/, message: "请输入有效的手机号" },
          ]}
        >
          <Input placeholder="例如：13800138000" />
        </Form.Item>

        <Form.Item name="difficulty_level" label="困难等级（可选）">
          <Select allowClear placeholder="选择困难等级">
            <Select.Option value="A">A 级困难</Select.Option>
            <Select.Option value="B">B 级困难</Select.Option>
            <Select.Option value="C">C 级困难</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item name="id_card" label="身份证号（可选，自动加密）">
          <Input placeholder="例如：110105200001011234" />
        </Form.Item>

        <Form.Item name="bank_card" label="银行卡号（可选，自动加密）">
          <Input placeholder="例如：6222021001112222" />
        </Form.Item>

        <Form.Item
          name="is_in_scheduling_pool"
          label="参与自动排班"
          valuePropName="checked"
        >
          <Switch checkedChildren="参与" unCheckedChildren="不参与" />
        </Form.Item>

        <Form.Item style={{ marginBottom: 0, textAlign: "right" }}>
          <Space>
            <Button onClick={onClose}>取消</Button>
            <Button type="primary" htmlType="submit" loading={createMut.isPending}>
              确认添加
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Modal>
  );
}

function EditPersonModal({
  person,
  onClose,
  onSuccess,
}: {
  person: any;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm();

  const updateMut = useMutation({
    mutationFn: (vals: any) => adminApi.people.update(person.id, vals),
    onSuccess: () => {
      message.success("人员信息已修改");
      onSuccess();
      onClose();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  return (
    <Modal
      title={`编辑人员信息 · ${person.full_name}`}
      open
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={updateMut.isPending}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          student_no: person.student_no,
          class_name: person.class_name,
          full_name: person.full_name,
          phone: person.phone,
          difficulty_level: person.difficulty_level,
          is_in_scheduling_pool: person.is_in_scheduling_pool,
        }}
        onFinish={(vals) => updateMut.mutate(vals)}
      >
        <Form.Item
          name="student_no"
          label="学号"
          rules={[{ required: true, message: "请输入学号" }]}
        >
          <Input />
        </Form.Item>

        <Form.Item
          name="full_name"
          label="姓名"
          rules={[{ required: true, message: "请输入姓名" }]}
        >
          <Input />
        </Form.Item>

        <Form.Item name="class_name" label="班级（可选）">
          <Input placeholder="非必填" />
        </Form.Item>

        <Form.Item
          name="phone"
          label="手机号"
          rules={[
            { required: true, message: "请输入手机号" },
            { pattern: /^1[3-9]\d{9}$/, message: "请输入有效的手机号" },
          ]}
        >
          <Input />
        </Form.Item>

        <Form.Item name="difficulty_level" label="困难等级（可选）">
          <Select allowClear placeholder="选择困难等级">
            <Select.Option value="A">A 级困难</Select.Option>
            <Select.Option value="B">B 级困难</Select.Option>
            <Select.Option value="C">C 级困难</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item name="id_card" label="修改身份证号（不填则保持不变，可选）">
          <Input placeholder="输入新身份证号进行替换" />
        </Form.Item>

        <Form.Item name="bank_card" label="修改银行卡号（不填则保持不变，可选）">
          <Input placeholder="输入新银行卡号进行替换" />
        </Form.Item>

        <Form.Item
          name="is_in_scheduling_pool"
          label="参与自动排班"
          valuePropName="checked"
        >
          <Switch checkedChildren="参与" unCheckedChildren="不参与" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
