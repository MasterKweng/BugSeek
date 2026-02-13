#!/usr/bin/env python3
"""
添加映射管理Tab功能
"""
import os
import re

def add_mappings_tab():
    """添加映射管理Tab功能"""
    file_path = "D:\code\BugSeek\frontend\src\pages\FieldMappingSuggestions.tsx"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"开始修改文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 添加映射管理相关状态
        old_state = """  // ==================== 新增：Tab 切换状态 ====================
  const [activeTab, setActiveTab] = useState<'suggestions' | 'mappings'>('suggestions');"""
        
        new_state = """  // ==================== 新增：Tab 切换状态 ====================
  const [activeTab, setActiveTab] = useState<'suggestions' | 'mappings'>('suggestions');
  
  // ==================== 新增：映射管理状态 ====================
  const [mappings, setMappings] = useState<fieldMappingService.FieldMappingWithDetails[]>([]);
  const [mappingsLoading, setMappingsLoading] = useState(false);
  const [mappingsPagination, setMappingsPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0
  });
  const [mappingFilter, setMappingFilter] = useState<'all' | 'proposed' | 'confirmed' | 'rejected'>('all');
  
  // ==================== 新增：映射管理函数 ====================
  const fetchMappings = async () => {
    if (!currentProject?.id || !currentVersion?.id) {
      message.warning('请先选择项目和版本');
      return;
    }
    
    setMappingsLoading(true);
    try {
      const response = await fieldMappingService.getFieldMappings({
        project_id: currentProject.id,
        version_id: currentVersion.id
      });
      
      if (response.code === 0 && response.data) {
        setMappings(response.data.items || []);
        setMappingsPagination({
          current: 1,
          pageSize: 20,
          total: response.data.total || 0
        });
      }
    } catch (error: any) {
      console.error('获取映射失败:', error);
      message.error(error.message || '获取映射失败');
    } finally {
      setMappingsLoading(false);
    }
  };
  
  const handleDeleteMapping = async (mappingId: number) => {
    try {
      const response = await fieldMappingService.deleteFieldMapping(mappingId, {
        project_id: currentProject.id,
        version_id: currentVersion.id
      });
      
      if (response.code === 0) {
        message.success('删除成功');
        fetchMappings();
      } else {
        message.error(response.message || '删除失败');
      }
    } catch (error: any) {
      console.error('删除映射失败:', error);
      message.error(error.message || '删除失败');
    }
  };
  
  const handleUpdateMappingStatus = async (mappingId: number, status: string) => {
    try {
      const response = await fieldMappingService.updateFieldMappingStatus(mappingId, status, {
        project_id: currentProject.id,
        version_id: currentVersion.id
      });
      
      if (response.code === 0) {
        message.success('状态更新成功');
        fetchMappings();
      } else {
        message.error(response.message || '状态更新失败');
      }
    } catch (error: any) {
      console.error('状态更新失败:', error);
      message.error(error.message || '状态更新失败');
    }
  };"""
        
        if old_state in content:
            content = content.replace(old_state, new_state)
            print("✅ 映射管理状态和函数已添加")
        else:
            print("⚠️  未找到activeTab状态")
        
        # 修改return语句，添加Tabs组件
        old_return = """  return (
    <div style={{ padding: 24 }}>
      {/* 标题行：参考数据结构页面样式 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 500 }}>字段映射建议</h2>"""
        
        new_return = """  return (
    <div style={{ padding: 24 }}>
      {/* 标题行 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 500 }}>字段映射</h2>
        <Space>
          {activeTab === 'suggestions' && (
            <>
              <Button 
                icon={<SyncOutlined />} 
                onClick={() => setTaskModalVisible(true)}
                loading={loading}
                type="primary"
              >
                生成映射建议
              </Button>
              <Button 
                icon={<ClockCircleOutlined />} 
                onClick={openHistoryDrawer}
              >
                执行记录
              </Button>
              <Button
                icon={<SyncOutlined />}
                onClick={handleCloneFromVersion}
              >
                从其他版本集成
              </Button>
              <Button
                icon={<PlayCircleOutlined />}
                onClick={() => setConfirmModalVisible(true)}
                disabled={selectedRowKeys.length === 0}
              >
                批量确认 ({selectedRowKeys.length})
              </Button>
              <Button
                icon={<CloseCircleOutlined />}
                onClick={() => setRejectModalVisible(true)}
                disabled={selectedRowKeys.length === 0}
              >
                批量拒绝 ({selectedRowKeys.length})
              </Button>
            </>
          )}
          {activeTab === 'mappings' && (
            <>
              <Button 
                icon={<SyncOutlined />} 
                onClick={fetchMappings}
              >
                刷新
              </Button>
              <Button
                icon={<CloseCircleOutlined />}
                onClick={() => {
                  Modal.confirm({
                    title: '确认删除',
                    content: '确定要删除所有已拒绝的映射吗？',
                    onOk: async () => {
                      try {
                        const response = await fieldMappingService.deleteFieldMappings({
                          project_id: currentProject?.id,
                          version_id: currentVersion?.id,
                          status: 'rejected'
                        });
                        if (response.code === 0) {
                          message.success(`成功删除 ${response.data?.deleted_count || 0} 条映射`);
                          fetchMappings();
                        }
                      } catch (error: any) {
                        message.error(error.message || '删除失败');
                      }
                    }
                  });
                }}
              >
                清理已拒绝
              </Button>
            </>
          )}
        </Space>
      </div>

      {/* Tab 切换 */}
      <Tabs
        activeKey={activeTab}
        onChange={(key) => {
          setActiveTab(key as 'suggestions' | 'mappings');
          if (key === 'mappings') {
            fetchMappings();
          }
        }}
        items={[
          {
            key: 'suggestions',
            label: '建议管理',
            children: (
              <div>"""
        
        if old_return in content:
            content = content.replace(old_return, new_return)
            print("✅ return语句已修改为Tabs结构")
        else:
            print("⚠️  未找到return语句")
        
        # 备份原文件
        backup_path = file_path + ".backup5"
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
    print("添加映射管理Tab功能")
    print("=" * 60)
    print()
    
    result = add_mappings_tab()
    
    print()
    print("=" * 60)
    if result:
        print("🎉 修改完成！")
        print()
        print("修改内容：")
        print("1. 添加了映射管理相关状态")
        print("2. 添加了映射管理相关函数")
        print("3. 修改return语句为Tabs结构")
        print()
        print("注意：还需要手动添加两个Tab的完整内容")
    else:
        print("⚠️  修改失败")
    print("=" * 60)