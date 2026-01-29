/**
 * 模块依赖图组件
 */
import React, { useEffect, useRef } from 'react';
import { Card, Empty } from 'antd';
import * as d3 from 'd3';
import { ModuleDependency } from '@/pages/api/Modules';

interface DependencyGraphProps {
  dependencies: ModuleDependency[];
}

interface Node {
  id: string;
  name: string;
}

interface Link {
  source: string;
  target: string;
  strength: number;
}

const DependencyGraph: React.FC<DependencyGraphProps> = ({ dependencies }) => {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!dependencies || dependencies.length === 0) {
      return;
    }

    // 构建图数据
    const nodes = new Map<string, Node>();
    const links: Link[] = [];

    dependencies.forEach(dep => {
      const sourceId = dep.source_group_id.toString();
      const targetId = dep.target_group_id.toString();

      if (!nodes.has(sourceId)) {
        nodes.set(sourceId, { id: sourceId, name: dep.source_group_name });
      }
      if (!nodes.has(targetId)) {
        nodes.set(targetId, { id: targetId, name: dep.target_group_name });
      }

      links.push({
        source: sourceId,
        target: targetId,
        strength: dep.dependency_strength
      });
    });

    // 清空画布
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = 1000;
    const height = 600;

    // 创建力导向图
    const simulation = d3
      .forceSimulation(Array.from(nodes.values()) as any)
      .force('link', d3.forceLink(links).id((d: any) => d.id).distance(200))
      .force('charge', d3.forceManyBody().strength(-500))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(50));

    // 创建箭头标记
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('path')
      .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
      .attr('fill', '#999');

    // 绘制连线
    const link = svg.append('g')
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('stroke', (d: Link) => {
        const strength = d.strength;
        if (strength > 0.7) return '#ff4d4f';
        if (strength > 0.4) return '#faad14';
        return '#52c41a';
      })
      .attr('stroke-width', (d: Link) => Math.max(1, d.strength * 3))
      .attr('marker-end', 'url(#arrowhead)');

    // 绘制节点
    const node = svg.append('g')
      .selectAll('g')
      .data(Array.from(nodes.values()))
      .enter()
      .append('g')
      .call(d3.drag<any, any, any>()
        .on('start', (event, d: any) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d: any) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d: any) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }));

    // 节点圆形
    node.append('circle')
      .attr('r', 30)
      .attr('fill', '#1890ff')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2);

    // 节点文字
    node.append('text')
      .attr('dy', 5)
      .attr('text-anchor', 'middle')
      .attr('fill', '#fff')
      .style('font-size', '12px')
      .style('font-weight', 'bold')
      .text((d: Node) => d.name.length > 4 ? d.name.substring(0, 4) + '...' : d.name);

    // 节点标签（完整名称）
    node.append('text')
      .attr('dy', 45)
      .attr('text-anchor', 'middle')
      .attr('fill', '#333')
      .style('font-size', '14px')
      .text((d: Node) => d.name);

    // 更新位置
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node
        .attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    // 缩放和平移
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 3])
      .on('zoom', (event) => {
        svg.select('g').attr('transform', event.transform);
      });

    svg.call(zoom as any);

    return () => {
      simulation.stop();
    };
  }, [dependencies]);

  if (!dependencies || dependencies.length === 0) {
    return (
      <Card>
        <Empty description="暂无模块依赖数据" />
      </Card>
    );
  }

  return (
    <Card>
      <svg
        ref={svgRef}
        width="100%"
        height={600}
        style={{ border: '1px solid #f0f0f0', borderRadius: '4px' }}
      />
    </Card>
  );
};

export default DependencyGraph;