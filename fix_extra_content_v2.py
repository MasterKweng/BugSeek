#!/usr/bin/env python3
"""
修复Tabs组件外的多余内容 - 修复版
"""
import os

def fix_extra_content_v2():
    """修复Tabs组件外的多余内容 - 修复版"""
    file_path = r"D:\code\BugSeek\frontend\src\pages\FieldMappingSuggestions.tsx"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"开始修改文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        original_content = ''.join(lines)
        
        # 找到需要删除的内容开始位置
        delete_start_idx = None
        for i, line in enumerate(lines):
            if '{/* ==================== 根据 pageState 渲染不同内容 ==================== */}' in line:
                delete_start_idx = i
                break
        
        if delete_start_idx is None:
            print("❌ 未找到需要删除的内容开始位置")
            return False
        
        print(f"✅ 找到需要删除的内容开始位置：第{delete_start_idx + 1}行")
        
        # 找到模态框开始位置
        modal_start_idx = None
        for i, line in enumerate(lines):
            if '{/* 任务创建模态框 */}' in line:
                modal_start_idx = i
                break
        
        if modal_start_idx is None:
            print("❌ 未找到模态框开始位置")
            return False
        
        print(f"✅ 找到模态框开始位置：第{modal_start_idx + 1}行")
        
        # 创建新的文件内容，删除中间的内容
        new_lines = lines[:delete_start_idx] + lines[modal_start_idx:]
        
        # 备份原文件
        backup_path = file_path + ".backup13"
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
    print("修复Tabs组件外的多余内容 - 修复版")
    print("=" * 60)
    print()
    
    result = fix_extra_content_v2()
    
    print()
    print("=" * 60)
    if result:
        print("🎉 修复完成！")
        print()
        print("修改内容：")
        print("1. 删除Tabs组件外的多余pageState内容")
        print()
        print("下一步：验证编译")
    else:
        print("⚠️  修复失败")
    print("=" * 60)