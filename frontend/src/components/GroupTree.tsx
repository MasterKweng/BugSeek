import React, { useState, useCallback, useEffect } from 'react';
import { Input, Space, Button, Dropdown, Modal, Form, message, Popconfirm, List, Empty, Checkbox, Tag } from 'antd';
const { TextArea } = Input;
import {
  FolderOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SearchOutlined,
  MoreOutlined
} from '@ant-design/icons';

interface GroupNode {
  key: string;
  title: string;
  group_id?: number;
  description?: string;
  endpoint_count?: number;
  sort_order?: number;
  selected_count?: number;
}

interface GroupTreeProps {
  groups: any[];
  selectedGroupId: number | null;
  onGroupSelect: (groupId: number | null) => void;
  onGroupCreate?: (values: any) => void;
  onGroupUpdate?: (groupId: number, values: any) => void;
  onGroupDelete?: (groupId: number) => void;
  selectedEndpointIds?: number[];
  onToggleGroup?: (groupId: number, select: boolean) => void;
}

const GroupTree: React.FC<GroupTreeProps> = ({
  groups,
  selectedGroupId,
  onGroupSelect,
  onGroupCreate,
  onGroupUpdate,
  onGroupDelete,
  selectedEndpointIds = [],
  onToggleGroup
}) => {
  const [searchValue, setSearchValue] = useState('');
  const [filteredGroups, setFilteredGroups] = useState<any[]>([]);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [currentGroup, setCurrentGroup] = useState<any>(null);
  const [editForm] = Form.useForm();
  const [createForm] = Form.useForm();

  // 过滤分组
  useEffect(() => {
    if (!searchValue) {
      setFilteredGroups(groups);
      return;
    }

    const filtered = groups.filter(group => 
      group.name.toLowerCase().includes(searchValue.toLowerCase())
    );
    setFilteredGroups(filtered);
  }, [groups, searchValue]);

  // 搜索过滤
  const handleSearch = (value: string) => {
    setSearchValue(value);
  };

  // 编辑分组
  const handleEditGroup = (group: any) => {
    setCurrentGroup(group);
    editForm.setFieldsValue({
      name: group.name,
      description: group.description || ''
    });
    setEditModalVisible(true);
  };

  // 提交编辑
  const handleEditSubmit = async () => {
    try {
      const values = await editForm.validateFields();
      onGroupUpdate?.(currentGroup.id, values);
      setEditModalVisible(false);
      setCurrentGroup(null);
      editForm.resetFields();
    } catch (error) {
      console.error('编辑分组失败:', error);
    }
  };

  // 创建分组
  const handleCreateGroup = async () => {
    try {
      const values = await createForm.validateFields();
      onGroupCreate?.(values);
      setCreateModalVisible(false);
      createForm.resetFields();
    } catch (error) {
      console.error('创建分组失败:', error);
    }
  };

  // 删除分组
  const handleDeleteGroup = (groupId: number) => {
    onGroupDelete?.(groupId);
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 搜索框和添加按钮 */}
      <div style={{ marginBottom: 12, flexShrink: 0 }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            placeholder="搜索分组..."
            prefix={<SearchOutlined />}
            value={searchValue}
            onChange={(e) => handleSearch(e.target.value)}
            allowClear
            style={{ flex: 1 }}
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalVisible(true)}
          >
            添加分类
          </Button>
        </Space.Compact>
      </div>

      {/* 分组列表 */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {filteredGroups.length === 0 ? (
          <Empty
            description={searchValue ? '未找到匹配的分组' : '暂无分组'}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            style={{ marginTop: 40 }}
          />
        ) : (
          <List
            dataSource={filteredGroups}
            renderItem={(group) => (
              <List.Item
                style={{
                  padding: '10px 12px',
                  cursor: 'pointer',
                  backgroundColor: selectedGroupId === group.id ? '#e6f7ff' : 'transparent',
                  borderLeft: selectedGroupId === group.id ? '3px solid #1890ff' : '3px solid transparent',
                  transition: 'all 0.3s ease',
                }}
                onClick={() => onGroupSelect(group.id)}
                actions={[
                  <Dropdown
                    key="actions"
                    menu={{
                      items: [
                        {
                          key: 'edit',
                          label: '编辑',
                          icon: <EditOutlined />,
                          onClick: (e) => {
                            e.domEvent.stopPropagation();
                            handleEditGroup(group);
                          }
                        },
                        {
                          key: 'delete',
                          label: '删除',
                          icon: <DeleteOutlined />,
                          danger: true,
                          onClick: (e) => {
                            e.domEvent.stopPropagation();
                            Modal.confirm({
                              title: '确认删除',
                              content: `确定要删除分组 "${group.name}" 吗？`,
                              okText: '确定',
                              cancelText: '取消',
                              onOk: () => handleDeleteGroup(group.id)
                            });
                          }
                        }
                      ]
                    }}
                    trigger={['click']}
                  >
                    <MoreOutlined 
                      style={{ color: '#999', padding: '4px' }}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Dropdown>
                ]}
              >
                <List.Item.Meta
                  avatar={
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {onToggleGroup && (
                        <Checkbox
                          checked={group.endpoint_count > 0 && group.selected_count === group.endpoint_count}
                          indeterminate={group.selected_count > 0 && group.selected_count < group.endpoint_count}
                          onClick={(e) => {
                            e.stopPropagation();
                            onToggleGroup(group.id, group.selected_count === 0 || group.selected_count < group.endpoint_count);
                          }}
                        />
                      )}
                      <FolderOutlined style={{ color: '#1890ff', fontSize: 16 }} />
                    </div>
                  }
                  title={
                    <Space>
                      <span style={{ fontSize: 14 }}>{group.name}</span>
                      <Tag color="blue">{group.endpoint_count || 0}</Tag>
                    </Space>
                  }
                  description={
                    onToggleGroup && group.endpoint_count > 0 && (
                      <span style={{ color: '#999', fontSize: 12 }}>
                        已选 {group.selected_count || 0} / {group.endpoint_count}
                      </span>
                    )
                  }
                />
              </List.Item>
            )}
          />
        )}
      </div>

      {/* 创建分组弹窗 */}
      <Modal
        title="添加分类"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false);
          createForm.resetFields();
        }}
        onOk={handleCreateGroup}
        width={500}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            label="分类名称"
            name="name"
            rules={[{ required: true, message: '请输入分类名称' }]}
          >
            <Input placeholder="分类名称" />
          </Form.Item>
          <Form.Item label="分类描述" name="description">
            <TextArea rows={3} placeholder="分类描述" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑分组弹窗 */}
      <Modal
        title="编辑分组"
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false);
          setCurrentGroup(null);
          editForm.resetFields();
        }}
        onOk={handleEditSubmit}
        width={500}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item
            label="分组名称"
            name="name"
            rules={[{ required: true, message: '请输入分组名称' }]}
          >
            <Input placeholder="分组名称" />
          </Form.Item>
          <Form.Item label="分组描述" name="description">
            <TextArea rows={3} placeholder="分组描述" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default GroupTree;