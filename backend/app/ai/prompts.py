"""Prompt 模板管理"""
from typing import Dict, Any
import json


class PromptManager:
    """Prompt 模板管理器"""
    
    TEMPLATES = {
        # 模块3: 接口集成 - 测试脚本生成
        "api_test_generation": {
            "system": "你是一个专业的接口测试专家，擅长生成高质量的接口测试用例。",
            "user": """
请为以下接口生成测试脚本：

项目信息：
- 项目名称：{project_name}
- 技术栈：{tech_stack}
- 数据库：{database}

接口信息：
- 路径：{path}
- 方法：{method}
- 描述：{description}

请求参数 Schema：
{request_schema}

响应参数 Schema：
{response_schema}

测试类型配置：
{test_types_config}

请根据以上测试类型配置，为每个类型生成对应的测试脚本。

返回格式（JSON）：
{{
  "scripts": [
    {{
      "name": "测试用例名称",
      "test_type": "positive|negative|boundary|exception|custom",
      "test_type_description": "该测试类型的具体要求",
      "description": "测试描述",
      "request_body": {{...}},
      "assertions": [...]
    }}
  ]
}}
"""
        },
        
        # 模块2: 代码质量 - 代码审查
        "code_review": {
            "system": "你是一个资深的代码审查专家，擅长发现代码中的安全隐患和逻辑错误。",
            "user": """
请审查以下代码：

项目信息：
- 项目名称：{project_name}
- 编程语言：{language}
- 框架：{framework}

代码内容：
```{language}
{code}
```

请分析：
1. 代码规范性问题
2. 安全隐患
3. 潜在的逻辑错误
4. 性能优化建议

返回格式（JSON）：
{{
  "issues": [
    {{
      "type": "style|security|logic|performance",
      "severity": "high|medium|low",
      "message": "问题描述",
      "line": 行号,
      "suggestion": "修复建议"
    }}
  ]
}}
"""
        },
        
        # 模块2: 代码质量 - 单测生成
        "unit_test_generation": {
            "system": "你是一个单元测试生成专家，能够生成高覆盖率的测试代码。",
            "user": """
请为以下代码生成单元测试：

项目信息：
- 项目名称：{project_name}
- 编程语言：{language}
- 框架：{framework}

代码内容：
```{language}
{code}
```

请生成测试代码，要求：
1. 覆盖所有分支
2. 包含边界测试
3. 包含异常测试

返回格式（JSON）：
{{
  "test_code": "完整的测试代码",
  "coverage_estimate": 预估覆盖率
}}
"""
        },
        
        # 模块5: 流程编排 - TIA 分析
        "tia_analysis": {
            "system": "你是一个测试影响分析专家，擅长分析代码变更对测试用例的影响。",
            "user": """
请分析以下代码变更影响的测试用例：

项目信息：
- 项目名称：{project_name}

代码变更：
{git_diff}

测试用例列表：
{test_cases}

请分析：
1. 受影响的测试用例
2. 影响程度（high/medium/low）
3. 是否需要重新执行

返回格式（JSON）：
{{
  "affected_cases": [
    {{
      "test_case_id": "用例ID",
      "name": "用例名称",
      "impact_level": "high|medium|low",
      "reason": "影响原因",
      "recommended": true
    }}
  ]
}}
"""
        },
        
        # 模块6: 基础设施 - 根因分析
        "root_cause_analysis": {
            "system": "你是一个缺陷根因分析专家，擅长结合日志和代码定位问题。",
            "user": """
请分析以下测试失败的原因：

项目信息：
- 项目名称：{project_name}

错误信息：
{error_message}

相关日志：
{logs}

相关代码：
{code}

请分析：
1. 失败的根本原因
2. 定位到具体的代码行
3. 修复建议

返回格式（JSON）：
{{
  "root_cause": "根本原因",
  "code_location": "文件路径:行号",
  "fix_suggestion": "修复建议"
}}
"""
        }
    }
    
    @classmethod
    def get_template(cls, task_type: str) -> Dict[str, str]:
        """
        获取 Prompt 模板
        
        Args:
            task_type: 任务类型
            
        Returns:
            Dict: 包含 system 和 user 提示词
        """
        return cls.TEMPLATES.get(task_type, {
            "system": "你是一个AI助手。",
            "user": "{input}"
        })
    
    @classmethod
    def render(cls, template: Dict[str, str], context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, str]:
        """
        渲染 Prompt
        
        Args:
            template: 模板（包含 system 和 user）
            context: 上下文信息
            input_data: 输入数据
            
        Returns:
            Dict: 渲染后的 system 和 user 提示词
        """
        # 合并上下文和输入数据
        all_vars = {**context, **input_data}
        
        # 格式化 JSON 字段
        for key, value in all_vars.items():
            if isinstance(value, (dict, list)):
                all_vars[key] = json.dumps(value, indent=2, ensure_ascii=False)
        
        # 渲染提示词
        system_prompt = template.get("system", "")
        user_prompt = template.get("user", "").format(**all_vars)
        
        return {
            "system": system_prompt,
            "user": user_prompt
        }