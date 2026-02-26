#!/usr/bin/env python3
"""
添加 Tab 组件重构页面
"""
import os
import re

def add_tabs_import():
    """添加 Tabs 组件导入"""
    file_path = "D:\\code\\BugSeek\\frontend\\src\\pages\\FieldMappingSuggestions.tsx"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"开始修改文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 添加 Tabs 导入
        old_import = """  Card, 
  Table, 
  Button, 
  Space, 
  Tag, 
  Modal, 
  message, 
  Spin, 
  Descriptions,
  Badge,
  Checkbox,
  Drawer,
  Progress,
  Steps,
  Statistic,
  Row,
  Col,
  Switch,
  Form,
  Alert,
  List,
  Empty,
  Result,
  Divider,
  Slider,
  Select"""
        
        new_import = """  Card, 
  Table, 
  Button, 
  Space, 
  Tag, 
  Modal, 
  message, 
  Spin, 
  Descriptions,
  Badge,
  Checkbox,
  Drawer,
  Progress,
  Steps,
  Statistic,
  Row,
  Col,
  Switch,
  Form,
  Alert,
  List,
  Empty,
  Result,
  Divider,
  Slider,
  Select,
  Tabs"""
        
        if old_import in content:
            content = content.replace(old_import, new_import)
            print("✅ Tabs 导入已添加")
        else:
            print("⚠️  未找到导入声明")
        
        # 添加 activeTab 状态
        old_state = """  // ==================== 新增：分页状态 ====================
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0
  });"""
        
        new_state = """  // ==================== 新增：分页状态 ====================
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0
  });
  
  // ==================== 新增：Tab 切换状态 ====================
  const [activeTab, setActiveTab] = useState<'suggestions' | 'mappings'>('suggestions');"""
        
        if old_state in content:
            content = content.replace(old_state, new_state)
            print("✅ activeTab 状态已添加")
        else:
            print("⚠️  未找到分页状态声明")
        
        # 备份原文件
        backup_path = file_path + ".backup4"
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
    print("添加 Tab 组件重构页面")
    print("=" * 60)
    print()
    
    result = add_tabs_import()
    
    print()
    print("=" * 60)
    if result:
        print("🎉 修改完成！")
    else:
        print("⚠️  修改失败")
    print("=" * 60)