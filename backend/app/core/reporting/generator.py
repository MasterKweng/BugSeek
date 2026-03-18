"""
报告生成器

BSK-SC-029: 报告输出接口

功能：
1. 生成 HTML 报告
2. 生成 PDF 报告（可选）
3. 支持 ECharts 图表
4. 集成 AI 根因分析（BSK-SC-030）
"""
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import json

from .aggregator import ReportData
from app.ai.prompts import PromptManager
from app.ai.adapters import ModelAdapterFactory

logger = logging.getLogger(__name__)


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def generate_html_report(
        self,
        report_data: ReportData,
        scenario_description: Optional[str] = None,
        include_rca: bool = True
    ) -> str:
        """
        生成 HTML 报告
        
        Args:
            report_data: 报告数据
            scenario_description: 场景描述（可选）
            include_rca: 是否包含 AI RCA 分析
            
        Returns:
            str: HTML 报告内容
        """
        logger.info(f"生成 HTML 报告: scenario_id={report_data.summary.scenario_id}")
        
        summary = report_data.summary
        pass_rate = report_data.metadata.get('pass_rate', 0)
        
        # 生成 RCA 分析（如果有失败节点且启用 RCA）
        rca_result = None
        if include_rca and summary.failed_node_keys:
            rca_result = await self.generate_rca_analysis(report_data, scenario_description)
        
        # 生成 HTML
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>场景执行报告 - {summary.scenario_name}</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #f0f0f0;
        }}
        .header h1 {{
            margin: 0;
            color: #1890ff;
        }}
        .header p {{
            color: #666;
            margin: 10px 0 0 0;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .summary-item {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #1890ff;
        }}
        .summary-item .label {{
            color: #666;
            font-size: 14px;
            margin-bottom: 8px;
        }}
        .summary-item .value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .summary-item .value.success {{
            color: #52c41a;
        }}
        .summary-item .value.failed {{
            color: #ff4d4f;
        }}
        .chart {{
            margin-bottom: 40px;
            height: 400px;
            border: 1px solid #f0f0f0;
            border-radius: 6px;
            padding: 20px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .node-list {{
            display: grid;
            gap: 12px;
        }}
        .node-item {{
            border: 1px solid #f0f0f0;
            border-radius: 6px;
            padding: 16px;
        }}
        .node-item.passed {{
            border-left: 4px solid #52c41a;
        }}
        .node-item.failed {{
            border-left: 4px solid #ff4d4f;
        }}
        .node-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .node-status {{
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .node-status.passed {{
            background-color: #f6ffed;
            color: #52c41a;
        }}
        .node-status.failed {{
            background-color: #fff1f0;
            color: #ff4d4f;
        }}
        .node-details {{
            color: #666;
            font-size: 14px;
        }}
        .node-details > div {{
            margin-bottom: 8px;
        }}
        .error-box {{
            background-color: #fff1f0;
            border: 1px solid #ffccc7;
            border-radius: 4px;
            padding: 12px;
            margin-top: 12px;
        }}
        .pre-block {{
            background-color: #f5f5f5;
            border-radius: 4px;
            padding: 12px;
            overflow-x: auto;
            font-size: 12px;
        }}
        .timestamp {{
            color: #999;
            font-size: 12px;
            margin-top: 40px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>场景执行报告</h1>
            <p>{summary.scenario_name} - {summary.environment_name}</p>
            <p>执行时间: {summary.started_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="summary">
            <div class="summary-item">
                <div class="label">执行状态</div>
                <div class="value {summary.status}">{summary.status}</div>
            </div>
            <div class="summary-item">
                <div class="label">总节点数</div>
                <div class="value">{summary.total_nodes}</div>
            </div>
            <div class="summary-item">
                <div class="label">成功</div>
                <div class="value success">{summary.passed_nodes}</div>
            </div>
            <div class="summary-item">
                <div class="label">失败</div>
                <div class="value failed">{summary.failed_nodes}</div>
            </div>
            <div class="summary-item">
                <div class="label">跳过</div>
                <div class="value">{summary.skipped_nodes}</div>
            </div>
            <div class="summary-item">
                <div class="label">通过率</div>
                <div class="value {pass_rate:.1f}%</div>
            </div>
            <div class="summary-item">
                <div class="label">总耗时</div>
                <div class="value">{summary.total_duration_ms}ms</div>
            </div>
        </div>

        <div class="section">
            <h2>执行结果分布</h2>
            <div id="chart" class="chart"></div>
        </div>

        <div class="section">
            <h2>节点执行详情</h2>
            <div class="node-list">
"""
        
        # 添加节点详情
        for node in report_data.node_results:
            status_class = node.status
            status_text = '通过' if node.status == 'passed' else '失败'
            
            html += f"""
                <div class="node-item {status_class}">
                    <div class="node-header">
                        <div>
                            <strong>{node.node_name}</strong>
                            <span style="margin-left: 12px; color: #999;">{node.node_type}</span>
                        </div>
                        <span class="node-status {status_class}">{status_text}</span>
                    </div>
                    <div class="node-details">
                        <div>耗时: {node.response_time}ms</div>
                        <div>状态码: {node.response_code}</div>
                        {node.extracted_variables and node.extracted_variables.keys() and f"<div>提取变量: {', '.join(node.extracted_variables.keys())}</div>"}
                    </div>
"""
            
            if node.status == 'failed' and node.error_message:
                html += f"""
                    <div class="error-box">
                        <strong>错误信息:</strong>
                        <div>{node.error_message}</div>
                    </div>
"""
        
        html += """
            </div>
        </div>
"""
        
        # 添加 RCA 部分（如果有失败节点且 RCA 分析成功）
        if rca_result:
            html += self._generate_rca_section(rca_result)
        
        html += """
        <div class="timestamp">
            报告生成时间: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """
        </div>
    </div>

    <script>
        // ECharts 图表
        var chartDom = document.getElementById('chart');
        var myChart = echarts.init(chartDom);

        var option = {{
            title: {{
                text: '执行结果分布',
                left: 'center'
            }},
            tooltip: {{
                trigger: 'item',
                formatter: '{{a}} <br/>{{b}}: {{c}} ({{d}}%)'
            }},
            legend: {{
                orient: 'vertical',
                left: 'left',
                data: ['通过', '失败', '跳过']
            }},
            series: [
                {{
                    name: '执行结果',
                    type: 'pie',
                    radius: ['40%', '70%'],
                    avoidLabelOverlap: false,
                    label: {{
                        show: true,
                        formatter: '{{b}}: {{c}} ({{d}}%)'
                    }},
                    emphasis: {{
                        label: {{
                            show: true,
                            fontSize: 20,
                            fontWeight: 'bold'
                        }}
                    }},
                    labelLine: {{
                        show: false
                    }},
                    data: [
                        {{ value: """ + str(summary.passed_nodes) + """, name: '通过', itemStyle: {{ color: '#52c41a' }} }},
                        {{ value: """ + str(summary.failed_nodes) + """, name: '失败', itemStyle: {{ color: '#ff4d4f' }} }},
                        {{ value: """ + str(summary.skipped_nodes) + """, name: '跳过', itemStyle: {{ color: '#faad14' }} }}
                    ]
                }}
            ]
        }};

        myChart.setOption(option);
    </script>
</body>
</html>
"""
        
        logger.info(f"HTML 报告生成完成: scenario_id={report_data.summary.scenario_id}")
        
        return html
    
    async def generate_pdf_report(
        self,
        report_data: ReportData,
        scenario_description: Optional[str] = None,
        include_rca: bool = True,
    ) -> bytes:
        """
        ?? PDF ??
        
        Args:
            report_data: ????
            scenario_description: ????????
            include_rca: ???? RCA ??
            
        Returns:
            bytes: PDF ????
        """
        logger.info(f"?? PDF ??: scenario_id={report_data.summary.scenario_id}")

        html_content = await self.generate_html_report(
            report_data,
            scenario_description=scenario_description,
            include_rca=include_rca,
        )

        try:
            return await self._render_pdf_via_playwright(html_content)
        except Exception as exc:
            logger.warning("Playwright PDF render failed, falling back to basic PDF: %s", exc)
            return self._render_basic_pdf(report_data)

    async def _render_pdf_via_playwright(self, html_content: str) -> bytes:
        """Render HTML into PDF with Playwright when browser runtime is available."""
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()
                await page.set_content(html_content, wait_until="load")
                return await page.pdf(
                    format="A4",
                    print_background=True,
                    margin={"top": "16mm", "right": "12mm", "bottom": "16mm", "left": "12mm"},
                )
            finally:
                await browser.close()

    def _render_basic_pdf(self, report_data: ReportData) -> bytes:
        """Generate a minimal PDF when HTML rendering is unavailable."""
        summary = report_data.summary
        lines = [
            f"BugSeek Scenario Report - {summary.scenario_name}",
            f"Environment: {summary.environment_name}",
            f"Status: {summary.status}",
            f"Nodes: total={summary.total_nodes}, passed={summary.passed_nodes}, failed={summary.failed_nodes}, skipped={summary.skipped_nodes}",
            f"Duration: {summary.total_duration_ms}ms",
            " ",
            "Node Results:",
        ]
        for node in report_data.node_results:
            error_suffix = f" | error={node.error_message}" if node.error_message else ""
            lines.append(
                f"- {node.node_name or node.node_key} [{node.status}] code={node.response_code} time={node.response_time}ms{error_suffix}"
            )

        return self._build_text_pdf(lines)

    def _build_text_pdf(self, lines: list[str]) -> bytes:
        """Build a small text-only PDF without external dependencies."""
        visible_lines = lines[:48]
        escaped_lines = [self._escape_pdf_text(line) for line in visible_lines]
        stream_lines = ["BT", "/F1 12 Tf", "50 790 Td", "15 TL"]
        for index, line in enumerate(escaped_lines):
            if index > 0:
                stream_lines.append("T*")
            stream_lines.append(f"({line}) Tj")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("latin-1", "replace")

        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 5 0 R /Resources << /Font << /F1 4 0 R >> >> >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream",
        ]

        output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(output))
            output.extend(f"{index} 0 obj\n".encode("ascii"))
            output.extend(obj)
            output.extend(b"\nendobj\n")

        xref_offset = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )
        return bytes(output)

    @staticmethod
    def _escape_pdf_text(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    async def generate_rca_analysis(
        self,
        report_data: ReportData,
        scenario_description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        生成 AI 根因分析（BSK-SC-030）
        
        Args:
            report_data: 报告数据
            scenario_description: 场景描述（可选）
            
        Returns:
            Optional[Dict]: RCA 分析结果，如果没有失败节点则返回 None
        """
        # 只有当有失败节点时才进行 RCA
        if not report_data.summary.failed_node_keys:
            logger.info(f"没有失败节点，跳过 RCA: scenario_id={report_data.summary.scenario_id}")
            return None
        
        logger.info(f"生成 AI RCA 分析: scenario_id={report_data.summary.scenario_id}")
        
        # 构建失败节点详情
        failure_details = []
        for node in report_data.node_results:
            if node.status == 'failed':
                failure_detail = f"""
节点: {node.node_name} ({node.node_key})
类型: {node.node_type}
错误信息: {node.error_message or '无'}
状态码: {node.response_code}
请求体: {json.dumps(node.request_body, ensure_ascii=False, indent=2) if node.request_body else '无'}
响应体: {json.dumps(node.response_body, ensure_ascii=False, indent=2) if node.response_body else '无'}
断言结果: {json.dumps(node.assertion_results, ensure_ascii=False, indent=2) if node.assertion_results else '无'}
"""
                failure_details.append(failure_detail)
        
        # 构建 prompt 上下文
        context = {
            "scenario_name": report_data.summary.scenario_name,
            "scenario_description": scenario_description or report_data.summary.scenario_name,
            "environment_name": report_data.summary.environment_name,
            "execution_time": report_data.summary.started_at.strftime('%Y-%m-%d %H:%M:%S'),
            "failure_details": "\n".join(failure_details),
            "total_nodes": report_data.summary.total_nodes,
            "passed_nodes": report_data.summary.passed_nodes,
            "failed_nodes": report_data.summary.failed_nodes,
            "total_duration_ms": report_data.summary.total_duration_ms,
            "failed_nodes_count": len(report_data.summary.failed_node_keys)
        }
        
        try:
            # 获取 prompt 模板
            template = PromptManager.get_template("scenario_failure_rca")
            
            # 渲染 prompt
            rendered = PromptManager.render(template, context, {})
            
            # 调用模型适配器
            adapter = ModelAdapterFactory.create()
            rca_response = await adapter.complete(
                prompt=rendered['user'],
                system_prompt=rendered['system']
            )
            
            # 检查是否有错误
            if rca_response.get("error"):
                logger.error(f"RCA 分析失败: {rca_response['error']}")
                return None
            
            # 解析 JSON 响应
            rca_result = json.loads(rca_response["result"])
            
            logger.info(f"RCA 分析完成: scenario_id={report_data.summary.scenario_id}")
            
            return rca_result
            
        except Exception as e:
            logger.error(f"RCA 分析失败: scenario_id={report_data.summary.scenario_id}, error={e}")
            return None
    
    def _generate_rca_section(self, rca_result: Dict[str, Any]) -> str:
        """
        生成 RCA 部分 HTML（BSK-SC-030）
        
        Args:
            rca_result: RCA 分析结果
            
        Returns:
            str: RCA 部分 HTML
        """
        summary = rca_result.get('summary', {})
        
        # 获取优先级样式
        priority = summary.get('priority', 'low')
        priority_color = {
            'high': '#ff4d4f',
            'medium': '#faad14',
            'low': '#52c41a'
        }.get(priority, '#666')
        
        html = f"""
        <div class="section">
            <h2>AI 根因分析</h2>
            
            <div class="rca-summary" style="background: #f9f9f9; padding: 20px; border-radius: 6px; border-left: 4px solid {priority_color}; margin-bottom: 20px;">
                <h3 style="margin-top: 0;">分析摘要</h3>
                <div style="margin-bottom: 12px;">
                    <strong>失败类型:</strong> {summary.get('failure_type', '未知')}
                </div>
                <div style="margin-bottom: 12px;">
                    <strong>失败节点数:</strong> {summary.get('failed_nodes_count', 0)}
                </div>
                <div style="margin-bottom: 12px;">
                    <strong>根本原因:</strong> {summary.get('root_cause', '未知')}
                </div>
                <div>
                    <strong>优先级:</strong> <span style="color: {priority_color}; font-weight: bold;">{priority.upper()}</span>
                </div>
            </div>
"""
        
        # 添加节点分析
        node_analysis = rca_result.get('node_analysis', [])
        if node_analysis:
            html += """
            <h3>节点分析</h3>
            <div class="node-list">
"""
            for node in node_analysis:
                html += f"""
                <div class="node-item failed">
                    <div class="node-header">
                        <div>
                            <strong>{node.get('node_name', '未知节点')}</strong>
                            <span style="margin-left: 12px; color: #999;">{node.get('node_key', '')}</span>
                        </div>
                    </div>
                    <div class="node-details">
                        <div><strong>失败类型:</strong> {node.get('failure_type', '未知')}</div>
                        <div><strong>根本原因:</strong> {node.get('root_cause', '未知')}</div>
"""
                # 添加证据信息
                evidence = node.get('evidence', {})
                if evidence:
                    html += '<div style="margin-top: 12px;"><strong>证据:</strong></div>'
                    for key, value in evidence.items():
                        html += f'<div style="margin-left: 20px;">- {key}: {value}</div>'
                
                # 添加修复建议
                fix_suggestion = node.get('fix_suggestion', '')
                if fix_suggestion:
                    html += f"""
                    <div class="error-box">
                        <strong>修复建议:</strong>
                        <div>{fix_suggestion}</div>
                    </div>
"""
                
                html += """
                </div>
"""
            
            html += """
            </div>
"""
        
        # 添加数据问题
        data_issues = rca_result.get('data_issues', [])
        if data_issues:
            html += """
            <h3>数据问题</h3>
            <div class="node-list">
"""
            for issue in data_issues:
                html += f"""
                <div class="node-item" style="border-left-color: #faad14;">
                    <div style="margin-bottom: 8px;"><strong>问题:</strong> {issue.get('issue', '未知')}</div>
                    <div style="margin-bottom: 8px;"><strong>影响节点:</strong> {', '.join(issue.get('affected_nodes', []))}</div>
                    <div style="margin-bottom: 8px;"><strong>建议:</strong> {issue.get('suggestion', '无')}</div>
                </div>
"""
            
            html += """
            </div>
"""
        
        # 添加环境问题
        env_issues = rca_result.get('environment_issues', [])
        if env_issues:
            html += """
            <h3>环境问题</h3>
            <div class="node-list">
"""
            for issue in env_issues:
                html += f"""
                <div class="node-item" style="border-left-color: #1890ff;">
                    <div style="margin-bottom: 8px;"><strong>问题:</strong> {issue.get('issue', '未知')}</div>
                    <div style="margin-bottom: 8px;"><strong>描述:</strong> {issue.get('description', '无')}</div>
                    <div style="margin-bottom: 8px;"><strong>建议:</strong> {issue.get('suggestion', '无')}</div>
                </div>
"""
            
            html += """
            </div>
"""
        
        # 添加行动计划
        action_plan = rca_result.get('action_plan', [])
        if action_plan:
            html += """
            <h3>行动计划</h3>
            <div class="node-list">
"""
            for action in action_plan:
                priority_color = {
                    'high': '#ff4d4f',
                    'medium': '#faad14',
                    'low': '#52c41a'
                }.get(action.get('priority', 'low'), '#666')
                
                html += f"""
                <div class="node-item" style="border-left-color: {priority_color};">
                    <div style="margin-bottom: 8px;">
                        <strong>步骤 {action.get('step', 1)}:</strong> {action.get('action', '未知')}
                        <span style="margin-left: 12px; color: {priority_color}; font-weight: bold;">({action.get('priority', 'low').upper()})</span>
                    </div>
                    <div style="margin-bottom: 8px;"><strong>详情:</strong> {action.get('details', '无')}</div>
                </div>
"""
            
            html += """
            </div>
"""
        
        html += """
        </div>
"""
        
        return html