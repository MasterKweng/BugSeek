import React, { useState, useMemo, memo, useCallback } from 'react';
import { Space, Tag, Button, Empty, Collapse, Pagination, Card } from 'antd';
import { PlayCircleOutlined, HistoryOutlined, FolderOutlined, FileOutlined, DownOutlined, UpOutlined } from '@ant-design/icons';

interface VirtualScriptListProps {
  groups: any[];
  onExecuteScript: (script: any) => void;
  onExecuteAll: (endpoint: any) => void;
  onViewExecutions: (endpoint: any) => void;
  onViewDetail: (script: any) => void;
  environments: any[];
}

interface ScriptItemProps {
  script: any;
  onExecuteScript: (script: any) => void;
  onViewDetail: (script: any) => void;
  onViewExecutions: (script: any) => void;
  environments: any[];
}

const ScriptItem: React.FC<ScriptItemProps> = memo(({ 
  script, 
  onExecuteScript, 
  onViewDetail,
  onViewExecutions,
  environments 
}) => {
  return (
    <div style={{ padding: '10px 0', borderBottom: '1px dashed #eee' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <strong style={{ fontSize: 14 }}>{script.name}</strong>
        <Tag color={
          script.test_type === 'positive' ? 'green' :
          script.test_type === 'negative' ? 'red' :
          script.test_type === 'boundary' ? 'orange' : 'purple'
        }>{script.test_type}</Tag>
      </div>
      <div style={{ marginTop: 8 }}>
        <Space>
          <Button
            size="small"
            icon={<PlayCircleOutlined />}
            disabled={environments.length === 0}
            onClick={() => {
              if (environments.length === 0) return;
              onExecuteScript(script);
            }}
          >
            执行
          </Button>
          <Button
            size="small"
            icon={<HistoryOutlined />}
            onClick={() => onViewExecutions(script)}
          >
            记录
          </Button>
          <Button
            size="small"
            onClick={() => onViewDetail(script)}
          >
            详情
          </Button>
        </Space>
      </div>
    </div>
  );
});

ScriptItem.displayName = 'ScriptItem';

interface EndpointGroupProps {
  endpoint: any;
  expanded: boolean;
  onToggle: () => void;
  onExecuteScript: (script: any) => void;
  onExecuteAll: (endpoint: any) => void;
  onViewExecutions: (endpoint: any) => void;
  onViewDetail: (script: any) => void;
  environments: any[];
}

const EndpointGroup: React.FC<EndpointGroupProps> = memo(({
  endpoint,
  expanded,
  onToggle,
  onExecuteScript,
  onExecuteAll,
  onViewExecutions,
  onViewDetail,
  environments
}) => {
  const scripts = endpoint.scripts || [];
  const positiveCount = scripts.filter((s: any) => s.test_type === 'positive').length;
  const negativeCount = scripts.filter((s: any) => s.test_type === 'negative').length;
  const otherCount = scripts.length - positiveCount - negativeCount;

  return (
    <div style={{ marginBottom: 24 }}>
      <div 
        style={{
          background: '#f1f3f5',
          padding: '12px 16px',
          borderRadius: 6,
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontWeight: 600,
          transition: 'background 0.2s'
        }}
        onClick={onToggle}
        onMouseEnter={(e) => e.currentTarget.style.background = '#e9ecef'}
        onMouseLeave={(e) => e.currentTarget.style.background = '#f1f3f5'}
      >
        <Space>
          {expanded ? <UpOutlined /> : <DownOutlined />}
          <FileOutlined />
          <span>{endpoint.method} {endpoint.path}</span>
        </Space>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 12, color: '#666' }}>
            ✅{positiveCount} / ❌{negativeCount} / ⚠️{otherCount}
          </span>
          <Space>
            <Button
              size="small"
              icon={<PlayCircleOutlined />}
              disabled={environments.length === 0}
              onClick={(e) => {
                e.stopPropagation();
                if (environments.length === 0) return;
                onExecuteAll(endpoint);
              }}
            >
              执行
            </Button>
            <Button
              size="small"
              icon={<HistoryOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                onViewExecutions(endpoint);
              }}
            >
              记录
            </Button>
          </Space>
        </div>
      </div>
      
      {expanded && (
        <div style={{ padding: '0 16px 16px 32px', borderLeft: '2px solid #dee2e6', marginTop: 12 }}>
          {scripts.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', color: '#999' }}>
              暂无脚本
            </div>
          ) : (
            scripts.map((script: any) => (
              <ScriptItem
                key={script.id}
                script={script}
                onExecuteScript={onExecuteScript}
                onViewDetail={onViewDetail}
                onViewExecutions={onViewExecutions}
                environments={environments}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
});

EndpointGroup.displayName = 'EndpointGroup';

interface ScriptGroupProps {
  group: any;
  expanded: boolean;
  onToggle: () => void;
  expandedEndpoints: Set<number>;
  onToggleEndpoint: (endpointId: number) => void;
  onExecuteScript: (script: any) => void;
  onExecuteAll: (endpoint: any) => void;
  onViewExecutions: (endpoint: any) => void;
  onViewDetail: (script: any) => void;
  environments: any[];
}

const ScriptGroup: React.FC<ScriptGroupProps> = memo(({
  group,
  expanded,
  onToggle,
  expandedEndpoints,
  onToggleEndpoint,
  onExecuteScript,
  onExecuteAll,
  onViewExecutions,
  onViewDetail,
  environments
}) => {
  const endpoints = group.endpoints || [];
  const totalScripts = endpoints.reduce((acc: number, e: any) => acc + (e.scripts?.length || 0), 0);

  return (
    <Card 
      style={{ marginBottom: 16 }}
      title={
        <div 
          style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}
          onClick={onToggle}
        >
          {expanded ? <UpOutlined /> : <DownOutlined />}
          <FolderOutlined />
          <strong>{group.group_name}</strong>
          <Tag color="blue">{totalScripts} 个脚本</Tag>
        </div>
      }
      size="small"
    >
      {expanded && (
        <div style={{ marginTop: 16 }}>
          {endpoints.map((endpoint: any) => (
            <EndpointGroup
              key={endpoint.endpoint_id}
              endpoint={endpoint}
              expanded={expandedEndpoints.has(endpoint.endpoint_id)}
              onToggle={() => onToggleEndpoint(endpoint.endpoint_id)}
              onExecuteScript={onExecuteScript}
              onExecuteAll={onExecuteAll}
              onViewExecutions={onViewExecutions}
              onViewDetail={onViewDetail}
              environments={environments}
            />
          ))}
          {endpoints.length === 0 && (
            <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>
              该分组下暂无接口
            </div>
          )}
        </div>
      )}
    </Card>
  );
});

ScriptGroup.displayName = 'ScriptGroup';

const VirtualScriptList: React.FC<VirtualScriptListProps> = ({
  groups,
  onExecuteScript,
  onExecuteAll,
  onViewExecutions,
  onViewDetail,
  environments
}) => {
  const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set());
  const [expandedEndpoints, setExpandedEndpoints] = useState<Set<number>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);

  // 默认展开第一个分组
  React.useEffect(() => {
    if (groups.length > 0) {
      setExpandedGroups(new Set([groups[0].group_id]));
    }
  }, [groups]);

  // 处理分组展开/收起
  const handleToggleGroup = useCallback((groupId: number) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(groupId)) {
        next.delete(groupId);
      } else {
        next.add(groupId);
      }
      return next;
    });
  }, []);

  // 处理接口展开/收起
  const handleToggleEndpoint = useCallback((endpointId: number) => {
    setExpandedEndpoints(prev => {
      const next = new Set(prev);
      if (next.has(endpointId)) {
        next.delete(endpointId);
      } else {
        next.add(endpointId);
      }
      return next;
    });
  }, []);

  // 处理全部展开/收起
  const handleToggleAll = useCallback((expand: boolean) => {
    if (expand) {
      setExpandedGroups(new Set(groups.map(g => g.group_id)));
      // 展开所有接口
      const allEndpointIds = groups.flatMap(g => 
        (g.endpoints || []).map((e: any) => e.endpoint_id)
      );
      setExpandedEndpoints(new Set(allEndpointIds));
    } else {
      setExpandedGroups(new Set());
      setExpandedEndpoints(new Set());
    }
  }, [groups]);

  // 分页
  const paginatedGroups = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return groups.slice(start, start + pageSize);
  }, [groups, currentPage, pageSize]);

  const totalGroups = groups.length;

  if (groups.length === 0) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <Empty description="暂无测试脚本" />
      </div>
    );
  }

  return (
    <div>
      {/* 控制栏 */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <span style={{ color: '#666' }}>
            共 {groups.length} 个分组
          </span>
        </Space>
        <Space>
          <Button size="small" onClick={() => handleToggleAll(true)}>
            全部展开
          </Button>
          <Button size="small" onClick={() => handleToggleAll(false)}>
            全部收起
          </Button>
        </Space>
      </div>
  
      {/* 分组列表 - 添加固定高度滚动 */}
      <div style={{ overflowY: 'auto', maxHeight: 500 }}>
        {paginatedGroups.map(group => (
          <ScriptGroup
            key={group.group_id}
            group={group}
            expanded={expandedGroups.has(group.group_id)}
            onToggle={() => handleToggleGroup(group.group_id)}
            expandedEndpoints={expandedEndpoints}
            onToggleEndpoint={handleToggleEndpoint}
            onExecuteScript={onExecuteScript}
            onExecuteAll={onExecuteAll}
            onViewExecutions={onViewExecutions}
            onViewDetail={onViewDetail}
            environments={environments}
          />
        ))}
      </div>
  
      {/* 分页 */}
      {totalGroups > pageSize && (
        <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination
            current={currentPage}
            total={totalGroups}
            pageSize={pageSize}
            onChange={(page, size) => {
              setCurrentPage(page);
              setPageSize(size);
            }}
            showSizeChanger
            showTotal={(total) => `共 ${total} 个分组`}
          />
        </div>
      )}
    </div>
  );};

export default memo(VirtualScriptList);