#!/usr/bin/env python3
"""
自动应用前端修改 - 阶段三
"""
import os
import re

def apply_changes():
    """应用前端修改"""
    
    file_path = "frontend/src/pages/FieldMappingSuggestions.tsx"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"开始修改文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 修改 1: 添加分页状态
        print("修改 1: 添加分页状态...")
        pattern1 = r"(const \[includeBody, setIncludeBody\] = useState\(true\);)\n\n(\s*// ==================== 异步任务相关状态 ====================)"
        replacement1 = r"\1\n\n  // ==================== 新增：分页状态 ====================\n  const [pagination, setPagination] = useState({\n    current: 1,\n    pageSize: 20,\n    total: 0\n  });\n\n  \2"
        content = re.sub(pattern1, replacement1, content)
        
        # 修改 2: 修改 loadTaskResults 函数
        print("修改 2: 修改 loadTaskResults 函数...")
        pattern2 = r"(// 加载任务结果\(使用缓存优化\)\n  const loadTaskResults = async \(taskId: number\) => \{)\n(    try \{\n      // 使用带缓存的服务函数\n      const suggestions = await fieldMappingService\.getFieldMappingSuggestionsCached\(taskId\);\n      setSuggestions\(suggestions \|\| \[\]\);)\n    \} catch \(error: any\) \{\n      console\.error\('加载任务结果失败:', error\);\n      message\.error\(error\.message \|\| '加载结果失败'\);\n    \}\n  \};)"
        replacement2 = r"\1\n  try {\n    const response = await fieldMappingService.getFieldMappingSuggestions(taskId, {\n      page,\n      page_size: size\n    });\n    \n    if (response.code === 0 && response.data) {\n      setSuggestions(response.data.items || []);\n      setPagination({\n        current: page,\n        pageSize: size,\n        total: response.data.total || 0\n      });\n    }\n  } catch (error: any) {\n    console.error('加载任务结果失败:', error);\n    message.error(error.message || '加载结果失败');\n  }\n};"
        content = re.sub(pattern2, replacement2, content)
        
        # 检查是否有修改
        if content == original_content:
            print("⚠️  没有应用任何修改（可能文件已经被修改过）")
            return False
        
        # 备份原文件
        backup_path = file_path + ".backup"
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
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("前端修改自动应用工具 - 阶段三")
    print("=" * 60)
    print()
    
    result = apply_changes()
    
    print()
    print("=" * 60)
    if result:
        print("🎉 修改完成！")
        print()
        print("下一步：")
        print("1. 检查修改是否正确")
        print("2. 重启前端开发服务器")
        print("3. 测试分页功能")
    else:
        print("⚠️  修改失败或无需修改")
        print()
        print("请参考《前端修改详细说明.md》手动修改")
    print("=" * 60)