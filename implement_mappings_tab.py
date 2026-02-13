#!/usr/bin/env python3
"""
实现映射管理Tab的内容
"""
import os

def implement_mappings_tab():
    """实现映射管理Tab的内容"""
    file_path = r"D:\code\BugSeek\frontend\src\pages\FieldMappingSuggestions.tsx"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"开始修改文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 找到映射管理Tab的位置并替换其内容
        old_mappings_tab = """{
            key: 'mappings',
            label: '映射管理',
            children: (
              <div>
                {/* 映射管理Tab的内容 - 待实现 */}
                <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>
                  <Empty description="映射管理功能开发中..." />
                </div>
              </div>
            )
          }"""
        
        new_mappings_tab = """{
            key: 'mappings',
            label: '映射管理',
            children: (
              <div>
                {/* 工具栏 */}
                <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Space>
                    <Select
                      value={mappingFilter}
                      onChange={(value: any) => setMappingFilter(value)}
                      style={{ width: 120 }}
                      size="small"
                    >
                      <Select.Option value="all">全部状态</Select.Option>
                      <Select.Option value="confirmed">已确认</Select.Option>
                      <Select.Option value="rejected">已拒绝</Select.Option>
                      <Select.Option value="proposed">待审核</Select.Option>
                    </Select>
                    <Button 
                      icon={<SyncOutlined />} 
                      onClick={fetchMappings}
                      size="small"
                    >
                      刷新
                    </Button>
                  </Space>
                  <Space>
                    <Tag color="blue">{mappings.length} 条映射</Tag>
                  </Space>
                </div>

                {/* 映射列表表格 */}
                <Table
                  dataSource={mappings}
                  rowKey="id"
                  loading={mappingsLoading}
                  pagination={{
                    current: mappingsPagination.current,
                    pageSize: mappingsPagination.pageSize,
                    total: mappingsPagination.total,
                    showSizeChanger: true,
                    showQuickJumper: true,
                    showTotal: (total) => `共 ${total} 条`,
                    onChange: (page, pageSize) => {
                      setMappingsPagination({
                        ...mappingsPagination,
                        current: page,
                        pageSize: pageSize || 20
                      });
                    },
                    onShowSizeChange: (current, size) => {
                      setMappingsPagination({
                        current: 1,
                        pageSize: size,
                        total: mappingsPagination.total
                      });
                    }
                  }}
                  columns={[
                    {
                      title: 'API',
                      key: 'api',
                      render: (_: any, record: fieldMappingService.FieldMappingWithDetails) => (
                        <div>
                          <Tag color={getMethodColor(record.definition_method)}>
                            {record.definition_method}
                          </Tag>
                          <span>{record.definition_path}</span>
                        </div>
                      )
                    },
                    {
                      title: 'API 字段',
                      dataIndex: 'api_field_path',
                      key: 'api_field_path'
                    },
                    {
                      title: '映射表/字段',
                      key: 'mapping',
                      render: (_: any, record: fieldMappingService.FieldMappingWithDetails) => (
                        <div>
                          <strong>{record.db_table}</strong>.{record.db_column}
                        </div>
                      )
                    },
                    {
                      title: '置信度',
                      dataIndex: 'confidence',
                      key: 'confidence',
                      width: 100,
                      render: (score: number) => {
                        if (!score) return <span>-</span>;
                        const percentage = (score * 100).toFixed(1);
                        let color = 'default';
                        if (score >= 0.85) color = 'success';
                        else if (score >= 0.7) color = 'processing';
                        else if (score >= 0.5) color = 'warning';
                        else color = 'error';
                        return (
                          <Progress 
                            percent={parseFloat(percentage)} 
                            size="small" 
                            strokeColor={color}
                            format={() => `${percentage}%`}
                          />
                        );
                      }
                    },
                    {
                      title: '来源',
                      dataIndex: 'source',
                      key: 'source',
                      width: 100,
                      render: (source: string) => {
                        if (source === 'ai') {
                          return <Tag color="green">自动 AI</Tag>;
                        }
                        return <Tag color="blue">手动</Tag>;
                      }
                    },
                    {
                      title: '操作',
                      key: 'action',
                      width: 120,
                      render: (_: any, record: fieldMappingService.FieldMappingWithDetails) => (
                        <Space size="small">
                          <Popconfirm
                            title="确认删除？"
                            onConfirm={() => handleDeleteMapping(record.id)}
                            okText="确定"
                            cancelText="取消"
                          >
                            <Button 
                              type="link" 
                              size="small" 
                              danger
                            >
                              删除
                            </Button>
                          </Popconfirm>
                        </Space>
                      )
                    }
                  ]}
                />
              </div>
            )
          }"""
        
        if old_mappings_tab in content:
            content = content.replace(old_mappings_tab, new_mappings_tab)
            print("✅ 映射管理Tab内容已实现")
        else:
            print("⚠️  未找到映射管理Tab的占位符")
        
        # 备份原文件
        backup_path = file_path + ".backup7"
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        print(f"✅ 已备份原文件到: {backup_path}")
        
        # 写入修改后的内容
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 已应用修改到: {file_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ 修改失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("实现映射管理Tab的内容")
    print("=" * 60)
    print()
    
    result = implement_mappings_tab()
    
    print()
    print("=" * 60)
    if result:
        print("🎉 修改完成！")
        print()
        print("修改内容：")
        print("1. 添加了映射管理Tab的工具栏")
        print("2. 添加了映射列表表格")
        print("3. 添加了操作按钮（删除）")
        print("4. 添加了分页功能")
        print()
        print("下一步：验证功能是否正常工作")
    else:
        print("⚠️  修改失败")
    print("=" * 60)