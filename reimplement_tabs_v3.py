#!/usr/bin/env python3
"""
重新设计并实现Tab结构 - 修复版2
"""
import os

def reimplement_tabs_v3():
    """重新设计并实现Tab结构 - 修复版2"""
    file_path = r"D:\code\BugSeek\frontend\src\pages\FieldMappingSuggestions.tsx"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"开始修改文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        original_content = ''.join(lines)
        
        # 找到标题行
        title_line_idx = None
        for i, line in enumerate(lines):
            if '<h2 style={{ margin: 0, fontSize: 20, fontWeight: 500 }}>字段映射建议</h2>' in line:
                title_line_idx = i
                break
        
        if title_line_idx is None:
            print("❌ 未找到标题行")
            return False
        
        print(f"✅ 找到标题行：第{title_line_idx + 1}行")
        
        # 找到标题行的div结束位置
        space_end_idx = None
        for i in range(title_line_idx, min(title_line_idx + 50, len(lines))):
            if '</Space>' in lines[i]:
                space_end_idx = i
                # 继续寻找后面的</div>
                for j in range(i + 1, min(i + 10, len(lines))):
                    if '</div>' in lines[j]:
                        space_end_idx = j
                        break
                break
        
        if space_end_idx is None:
            print("❌ 未找到标题行div的结束位置")
            return False
        
        print(f"✅ 找到标题行div的结束位置：第{space_end_idx + 1}行")
        
        # 找到pageState === 'IDLE'块的开始和结束位置
        idle_start_idx = None
        idle_end_idx = None
        for i in range(space_end_idx, min(space_end_idx + 150, len(lines))):
            if "pageState === 'IDLE'" in lines[i]:
                idle_start_idx = i
                # 寻找对应的 )
                depth = 0
                for j in range(i, len(lines)):
                    if '(' in lines[j]:
                        depth += 1
                    if ')' in lines[j]:
                        depth -= 1
                        if depth == 0:
                            idle_end_idx = j
                            break
                if idle_end_idx is not None:
                    break
        
        if idle_start_idx is None or idle_end_idx is None:
            print("❌ 未找到pageState === 'IDLE'块")
            return False
        
        print(f"✅ 找到pageState === 'IDLE'块：第{idle_start_idx + 1}行 - 第{idle_end_idx + 1}行")
        
        # 找到return语句的结束位置（主div的结束位置）
        # 主div在第1062行开始，我们需要找到对应的 </div>
        main_div_end_idx = None
        main_div_indent = len(lines[1061]) - len(lines[1061].lstrip())
        for i in range(len(lines) - 1, 1061, -1):
            if '</div>' in lines[i]:
                current_indent = len(lines[i]) - len(lines[i].lstrip())
                if current_indent == main_div_indent:
                    main_div_end_idx = i
                    break
        
        if main_div_end_idx is None:
            print("❌ 未找到主div的结束位置")
            return False
        
        print(f"✅ 找到主div的结束位置：第{main_div_end_idx + 1}行")
        
        # 创建新的文件内容
        new_lines = []
        
        # 1. 添加return语句开始到标题行div结束
        new_lines.extend(lines[:space_end_idx + 1])
        
        # 2. 添加Tabs组件开始
        new_lines.append('\n')
        new_lines.append('      {/* Tabs 组件 */}\n')
        new_lines.append('      <Tabs\n')
        new_lines.append('        activeKey={activeTab}\n')
        new_lines.append('        onChange={(key) => setActiveTab(key as \'suggestions\' | \'mappings\')}\n')
        new_lines.append('        items={[\n')
        new_lines.append('          {\n')
        new_lines.append('            key: \'suggestions\',\n')
        new_lines.append('            label: \'建议管理\',\n')
        new_lines.append('            children: (\n')
        new_lines.append('              <>\n')
        
        # 3. 添加pageState === 'IDLE'块
        new_lines.extend(lines[idle_start_idx:idle_end_idx + 1])
        
        # 4. 添加建议管理Tab结束
        new_lines.append('              </>\n')
        new_lines.append('            )\n')
        new_lines.append('          },\n')
        new_lines.append('          {\n')
        new_lines.append('            key: \'mappings\',\n')
        new_lines.append('            label: \'映射管理\',\n')
        new_lines.append('            children: (\n')
        new_lines.append('              <div>\n')
        new_lines.append('                {/* 映射管理Tab的内容 */}\n')
        new_lines.append('                <div style={{ padding: 40, textAlign: \'center\', color: \'#999\' }}>\n')
        new_lines.append('                  <Empty description="映射管理功能开发中..." />\n')
        new_lines.append('                </div>\n')
        new_lines.append('              </div>\n')
        new_lines.append('            )\n')
        new_lines.append('          }\n')
        new_lines.append('        ]}\n')
        new_lines.append('      />\n')
        
        # 5. 添加模态框和Drawer（从idle_end_idx+1到main_div_end_idx）
        new_lines.extend(lines[idle_end_idx + 1:main_div_end_idx + 1])
        
        # 6. 添加主div和return语句结束
        new_lines.append('  );\n')
        new_lines.append('};\n\n')
        new_lines.append('export default FieldMappingSuggestions;\n')
        
        # 备份原文件
        backup_path = file_path + ".backup11"
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        print(f"✅ 已备份原文件到: {backup_path}")
        
        # 写入修改后的内容
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"✅ 已应用修改到: {file_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ 修改失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("重新设计并实现Tab结构 - 修复版2")
    print("=" * 60)
    print()
    
    result = reimplement_tabs_v3()
    
    print()
    print("=" * 60)
    if result:
        print("🎉 修改完成！")
        print()
        print("修改内容：")
        print("1. 在标题行后添加Tabs组件")
        print("2. 将pageState === 'IDLE'块放在建议管理Tab中")
        print("3. 创建映射管理Tab（暂为空）")
        print()
        print("下一步：验证编译并实现映射管理Tab的内容")
    else:
        print("⚠️  修改失败")
    print("=" * 60)