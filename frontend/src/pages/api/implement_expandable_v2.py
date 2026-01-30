#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修改展开区域，使用 Tab 标签页显示链路、输入、输出、依赖
"""

# 读取原文件
with open('Scenarios.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到展开区域并替换
old_expandable = '''                  expandable={{
                  expandedRowRender: (record: Module) => (
                    <div style={{ padding: '16px 0' }}>
                      <ModuleDetailPanel 
                        moduleId={record.id}
                        projectId={currentProject?.id}
                        detailType={selectedDetailType}
                      />
                    </div>
                  ),
                  expandIcon: ({ expanded, onExpand, record }) => {
                    if (expanded) {
                      return <Button type="link" size="small" onClick={(e) => onExpand(record, e)}>收起 ▲</Button>;
                    }
                    return <Button type="link" size="small" onClick={(e) => onExpand(record, e)}>展开 ▼</Button>;
                  },
                }}'''

new_expandable = '''                  expandable={{
                  expandedRowRender: (record: Module) => (
                    <div style={{ padding: '16px 0' }}>
                      <ModuleDetailPanel 
                        moduleId={record.id}
                        projectId={currentProject?.id}
                        detailType={selectedDetailType}
                      />
                    </div>
                  ),
                }}'''

content = content.replace(old_expandable, new_expandable)

# 保存修改后的文件
with open('Scenarios.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Scenarios.tsx 文件修改成功！")
print("已移除展开/收起按钮，使用默认的展开功能。")