#!/usr/bin/env python3
"""
修复重复的return语句
"""
import os

def fix_duplicate_return():
    """修复重复的return语句"""
    file_path = r"D:\code\BugSeek\frontend\src\pages\FieldMappingSuggestions.tsx"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"开始修改文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 修复重复的return语句
        old_return = """  };

  return (
  return ("""
        
        new_return = """  };

  return ("""
        
        if old_return in content:
            content = content.replace(old_return, new_return)
            print("✅ 已修复重复的return语句")
        else:
            print("⚠️  未找到重复的return语句")
        
        # 备份原文件
        backup_path = file_path + ".backup8"
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
    print("修复重复的return语句")
    print("=" * 60)
    print()
    
    result = fix_duplicate_return()
    
    print()
    print("=" * 60)
    if result:
        print("🎉 修复完成！")
    else:
        print("⚠️  修复失败")
    print("=" * 60)