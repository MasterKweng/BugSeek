#!/usr/bin/env python3
"""
将FieldMappingSuggestions页面的return语句修改为Tabs结构
"""
import os

def add_tabs_structure():
    """将return语句修改为Tabs结构"""
    file_path = r"D:\code\BugSeek\frontend\src\pages\FieldMappingSuggestions.tsx"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"开始修改文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        original_content = ''.join(lines)
        
        # 找到return语句的位置（行号1140，索引1139）
        return_start_idx = 1139  # 0-based
        
        # 找到return语句结束的位置（行号2142，索引2141）
        return_end_idx = 2141  # 0-based
        
        # 获取return语句的内容（不包含return本身）
        return_content = ''.join(lines[return_start_idx+1:return_end_idx])
        
        # 移除开头的缩进
        return_content = return_content.lstrip()
        
        # 移除结尾的缩进
        return_content = return_content.rstrip()
        
        # 创建新的return语句
        new_return = """  return (
    <div style={{ padding: 24 }}>
      {/* 标题行 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 500 }}>字段映射管理</h2>
      </div>

      {/* Tabs 组件 */}
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as 'suggestions' | 'mappings')}
        items={[
          {
            key: 'suggestions',
            label: '建议管理',
            children: (
              <>
""" + return_content + """
              </>
            )
          },
          {
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
          }
        ]}
      />
    </div>
  );"""
        
        # 创建新文件内容
        new_content = ''.join(lines[:return_start_idx]) + new_return + '\n};\n\nexport default FieldMappingSuggestions;'
        
        # 备份原文件
        backup_path = file_path + ".backup6"
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        print(f"✅ 已备份原文件到: {backup_path}")
        
        # 写入修改后的内容
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"✅ 已应用修改到: {file_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ 修改失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("将return语句修改为Tabs结构")
    print("=" * 60)
    print()
    
    result = add_tabs_structure()
    
    print()
    print("=" * 60)
    if result:
        print("🎉 修改完成！")
        print()
        print("修改内容：")
        print("1. 将原有内容包裹在 Tabs 组件中")
        print("2. 创建了两个Tab：建议管理、映射管理")
        print("3. 原有内容放在'建议管理'Tab中")
        print("4. '映射管理'Tab暂为空（待实现）")
        print()
        print("下一步：实现'映射管理'Tab的内容")
    else:
        print("⚠️  修改失败")
    print("=" * 60)