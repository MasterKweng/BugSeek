"""
更新 Scenarios.tsx，添加链路列表入口
"""

import re

def update_scenarios_tsx():
    """更新 Scenarios.tsx，添加链路列表入口"""
    scenarios_file_path = r'D:\code\BugSeek\frontend\src\pages\api\Scenarios.tsx'
    
    with open(scenarios_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已添加
    if 'LinkOutlined' in content and '/api/chains' in content:
        print("Scenarios.tsx 已添加链路列表入口，跳过")
        return
    
    # 1. 添加 LinkOutlined 图标导入
    import_pattern = r'from ".*ant-design/icons"'
    if import_pattern in content:
        content = content.replace(
            import_pattern,
            r'\1, LinkOutlined'
        )
    
    # 2. 在模块分析标签页顶部添加按钮
    button_pattern = r'(<TabPane tab="模块分析" key="modules">)'
    if button_pattern in content:
        button_code = r'''
            <div style={{ marginBottom: 16 }}>
              <Space>
                <Button icon={<LinkOutlined />} onClick={() => navigate('/api/chains')}>
                  查看链路列表
                </Button>
              </Space>
            </div>
'''
        content = content.replace(
            button_pattern,
            button_code + r'\1'
        )
    
    with open(scenarios_file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Scenarios.tsx 已更新，添加链路列表入口")

if __name__ == "__main__":
    update_scenarios_tsx()