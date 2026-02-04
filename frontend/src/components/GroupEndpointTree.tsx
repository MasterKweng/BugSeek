import React, { useState, useCallback, useEffect } from 'react';
import { Input, Space, Button, List, Empty, message, Tag } from 'antd';
import {
  FolderOutlined,
  FolderOpenOutlined,
  ApiOutlined,
  SearchOutlined,
  DownOutlined,
  RightOutlined,
} from '@ant-design/icons';

interface GroupNode {
  key: string;
  title: string;
  group_id?: number;
  endpoint_id?: number;
  endpoint_count?: number;
  description?: string;
}

interface GroupEndpointTreeProps {
  groups: any[];
  endpoints: any[];
  selectedGroupId: number | null;
  selectedEndpointId: number | null;
  onGroupSelect: (groupId: number | null) => void;
  onEndpointSelect: (endpointId: number | null) => void;
  showOnlyWithScripts?: boolean;  // 是否只显示有脚本的接口
}

const GroupEndpointTree: React.FC<GroupEndpointTreeProps> = ({
  groups,
  endpoints,
  selectedGroupId,
  selectedEndpointId,
  onGroupSelect,
  onEndpointSelect,
  showOnlyWithScripts = true,  // 默认只显示有脚本的接口
}) => {
  const [searchValue, setSearchValue] = useState('');
  const [expandedGroupIds, setExpandedGroupIds] = useState<number[]>([]);

  // 获取分组下的接口列表（根据脚本数量过滤）
  const getGroupEndpoints = (groupId: number) => {
    let groupEndpoints = endpoints.filter(e => e.group_id === groupId);

    // 如果启用了只显示有脚本的接口，则过滤
    if (showOnlyWithScripts) {
      groupEndpoints = groupEndpoints.filter(e => e.script_count > 0);
    }

    return groupEndpoints;
  };

  // 过滤分组和接口
  const filteredGroups = groups.map(group => {
    // 过滤掉"未分组"且接口数量为0的分组
    if (group.name === '未分组' && (group.endpoint_count || 0) === 0) {
      return null;
    }

    const groupEndpoints = getGroupEndpoints(group.id);

    // 如果启用只显示有脚本的接口，且该分组下没有有脚本的接口，则不显示该分组
    if (showOnlyWithScripts && groupEndpoints.length === 0) {
      return null;
    }

    if (!searchValue) {
      return { group, endpoints: groupEndpoints };
    }

    const lowerSearchValue = searchValue.toLowerCase();

    // 检查分组名称是否匹配
    const groupMatches = group.name.toLowerCase().includes(lowerSearchValue);

    // 检查接口路径是否匹配
    const matchingEndpoints = groupEndpoints.filter(e =>
      e.path.toLowerCase().includes(lowerSearchValue) ||
      e.summary?.toLowerCase().includes(lowerSearchValue)
    );

    // 如果分组名称匹配，或者有接口匹配，则显示该分组
    if (groupMatches || matchingEndpoints.length > 0) {
      return {
        group,
        endpoints: groupMatches ? groupEndpoints : matchingEndpoints
      };
    }

    return null;
  }).filter(item => item !== null);

  // 搜索过滤
  const handleSearch = (value: string) => {
    setSearchValue(value);
    
    // 如果有搜索内容，展开所有匹配的分组
    if (value) {
      const matchingGroupIds = filteredGroups.map(item => item.group.id);
      setExpandedGroupIds([...expandedGroupIds, ...matchingGroupIds]);
    }
  };

  // 处理分组点击
  const handleGroupClick = (groupId: number) => {
    // 切换展开/折叠状态
    if (expandedGroupIds.includes(groupId)) {
      setExpandedGroupIds(expandedGroupIds.filter(id => id !== groupId));
    } else {
      setExpandedGroupIds([...expandedGroupIds, groupId]);
    }
    // 同时选中该分组
    onGroupSelect(groupId);
  };

  // 处理接口点击
  const handleEndpointClick = (endpointId: number) => {
    onEndpointSelect(endpointId);
  };

  return (
    <div>
      {/* 搜索框 */}
      <div style={{ marginBottom: 12, flexShrink: 0 }}>
        <Input
          placeholder="搜索分组或接口..."
          prefix={<SearchOutlined />}
          value={searchValue}
          onChange={(e) => handleSearch(e.target.value)}
          allowClear
        />
      </div>

      {/* 分组和接口列表 */}
      <div>
        {filteredGroups.length === 0 ? (
          <Empty
            description={searchValue ? '未找到匹配的分组或接口' : '暂无分组'}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            style={{ marginTop: 40 }}
          />
        ) : (
          filteredGroups.map(({ group, endpoints: groupEndpoints }) => {
            const isExpanded = expandedGroupIds.includes(group.id);
            const isSelected = selectedGroupId === group.id;

            return (
              <div key={group.id}>
                {/* 分组项 */}
                <div
                  style={{
                    padding: '10px 12px',
                    cursor: 'pointer',
                    backgroundColor: isSelected ? '#e6f7ff' : 'transparent',
                    borderLeft: isSelected ? '3px solid #1890ff' : '3px solid transparent',
                    transition: 'all 0.3s ease',
                    marginBottom: '4px',
                    borderRadius: '4px',
                  }}
                  onClick={() => handleGroupClick(group.id)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                      {/* 展开/折叠图标 */}
                      {groupEndpoints.length > 0 && (
                        <span style={{ marginRight: 8, color: '#999' }}>
                          {isExpanded ? <DownOutlined /> : <RightOutlined />}
                        </span>
                      )}
                      {!groupEndpoints.length && (
                        <span style={{ width: 14, marginRight: 8 }} />
                      )}

                      {/* 文件夹图标 */}
                      <FolderOutlined style={{ color: '#1890ff', fontSize: 16, marginRight: 8 }} />

                      {/* 分组名称 */}
                      <span style={{ fontSize: 14 }}>{group.name}</span>
                    </div>

                    {/* 接口数量 */}
                    <Tag color="blue" style={{ marginLeft: 12 }}>{group.endpoint_count || 0}</Tag>
                  </div>
                </div>

                {/* 接口列表（展开时显示） */}
                {isExpanded && groupEndpoints.length > 0 && (
                  <div style={{ 
                    marginLeft: 12, 
                    marginBottom: '8px',
                  }}>
                    {groupEndpoints.map((endpoint: any) => (
                      <div
                        key={endpoint.id}
                        style={{
                          padding: '8px 12px',
                          cursor: 'pointer',
                          backgroundColor: selectedEndpointId === endpoint.id ? '#f6ffed' : 'transparent',
                          borderLeft: selectedEndpointId === endpoint.id ? '3px solid #52c41a' : '3px solid transparent',
                          transition: 'all 0.2s ease',
                          borderRadius: '4px',
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEndpointClick(endpoint.id);
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <div style={{ display: 'flex', alignItems: 'center' }}>
                            <ApiOutlined style={{ color: '#52c41a', fontSize: 14, marginRight: 8 }} />
                            <span style={{ fontSize: 13, fontWeight: selectedEndpointId === endpoint.id ? 500 : 400 }}>
                              {endpoint.method} {endpoint.path}
                            </span>
                          </div>
                          <span style={{ color: '#999', fontSize: 12 }}>
                            {endpoint.script_count || 0}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default GroupEndpointTree;