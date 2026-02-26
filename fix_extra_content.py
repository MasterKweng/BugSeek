#!/usr/bin/env python3
"""
修复Tabs组件外的多余内容
"""
import os

def fix_extra_content():
    """修复Tabs组件外的多余内容"""
    file_path = r"D:\code\BugSeek\frontend\src\pages\FieldMappingSuggestions.tsx"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"开始修改文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 找到需要删除的内容开始位置
        # 从"根据 pageState 渲染不同内容"到模态框开始
        delete_start = '        {/* ==================== 根据 pageState 渲染不同内容 ==================== */}'
        
        # 找到模态框开始位置
        modal_start = '      {/* 任务模态框 */}'
        
        if delete_start in content and modal_start in content:
            # 删除这两部分之间的内容
            parts = content.split(modal_start)
            before_modal = parts[0]
            after_modal = modal_start + parts[1]
            
            # 在before_modal中删除从delete_start开始的内容
            before_parts = before_modal.split(delete_start)
            new_content = before_parts[0] + after_modal
            
            print("✅ 已删除Tabs组件外的多余内容")
        else:
            print("⚠️  未找到需要删除的内容")
            return False
        
        # 备份原文件
        backup_path = file_path + ".backup12"
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
    print("修复Tabs组件外的多余内容")
    print("=" * 60)
    print()
    
    result = fix_extra_content()
    
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