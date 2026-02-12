"""Prompt 模板管理"""
from typing import Dict, Any
import json


class PromptManager:
    """Prompt 模板管理器"""

    TEMPLATES = {
        # ========== API 资产库 - V2.0 AI 能力 ==========

        # AI 基准用例生成
        "api_case_generation": {
            "system": "你是一个专业的 API 测试专家，擅长生成高质量的 API 测试用例。你能够分析接口定义，自动生成包含入参、断言和变量提取的基准用例。",
            "user": """
请为以下 API 接口生成基准测试用例：

接口信息：
- 方法：{method}
- 路径：{path}
- 摘要：{summary}
- 描述：{description}

重要：用例名称必须使用接口的实际路径，格式为 "基准用例 - {path}"，不要使用示例中的路径。

请求参数 Schema：
{request_schema}

响应参数 Schema：
{response_schema}

请生成一个基准测试用例，要求：

1. 入参生成：
   - 必填字段生成合理的测试值（使用动态随机函数）
   - **ID/外键字段（id, *_id, *Id）不要用随机数**，应使用变量占位，如 {{user_id}} / {{order_id}}，并在 required_variables 中声明来源（数据库查询或前置业务创建）
   - 动态函数格式：使用双大括号 {{...}}
   - 字符串类型：使用 {{random_string(8)}} 或 {{random_string(16)}}
   - 整数类型：使用 {{random_int(1000, 9999)}} 或 {{random_int(1, 100)}}
   - 布尔类型：使用 true 或 false
   - 时间类型：使用 {{timestamp()}} 或特定时间
   - UUID 类型：使用 {{uuid()}}
   - 邮箱类型：使用格式如 test_{{random_string(6)}}@example.com

2. request_data 结构规范（根据 HTTP 方法）：
   
   GET/DELETE 请求：
   {{
     "path_params": {{
       // 路径参数，如 URL 中的 {id}
       "id": "{{id}}"
     }},
     // 查询参数请直接放在 request_data 顶层
     "limit": "{{random_int(10, 20)}}",
     "offset": "{{random_int(0, 50)}}"
   }}
   
   POST/PUT/PATCH 请求：
   {{
     "path_params": {{
       // 路径参数（如果 URL 中有 {id} 等）
       "id": "{{id}}"
     }},
     "headers": {{
       "Content-Type": "application/json"
     }},
     "body": {{
       // 请求体数据，包含所有必填字段
       "name": "测试名称{{random_string(6)}}",
       "quantity": {{random_int(1, 100)}}
     }}
   }}

3. 断言生成：
   - 状态码断言：断言返回 2xx 状态码（推荐 200）
   - code 字段断言：如果有 code 字段，断言其等于 0 或成功码
   - 关键字段非空断言：识别响应中的关键字段（如 id, token, data 等）并添加非空断言
   - 字段类型断言：验证关键字段的类型是否正确

4. 变量提取：
   - 提取响应中的关键字段作为变量
   - 如提取 token, userId, orderId 等
   - 使用 JSONPath 表达式（如 $.data.token）

返回格式（JSON）：
{{
  "name": "基准用例 - " + "{path}",
  "description": "该接口的基准测试用例",
  "priority": "P0",
  "request_data": {{
    // 根据请求方法选择正确的结构
    // GET/DELETE: path_params + query_params
    // POST/PUT/PATCH: path_params + headers + body
  }},
  "required_variables": [
    "id",
    "user_id"
  ],
  "data_prep": [
    "id: 需从数据库查询或通过前置业务创建",
    "user_id: 需从数据库查询或通过前置业务创建"
  ],
  "assertion_rules": [
    {{
      "source": "status",
      "property": null,
      "operator": "in",
      "value": [200, 201, 204],
      "description": "状态码应为 2xx"
    }},
    {{
      "source": "body",
      "property": "$.code",
      "operator": "==",
      "value": 0,
      "description": "响应码应为 0"
    }},
    // 更多断言...
  ],
  "extraction_rules": [
    {{
      "var_name": "变量名",
      "field": "$.data.field",
      "description": "描述"
    }}
  ],
  "ai_confidence": 0.9
}}
"""
        },

        # AI 断言生成
        "assertion_generation": {
            "system": "你是一个专业的测试断言生成专家，能够根据接口定义和响应数据自动生成全面的测试断言。",
            "user": """
请为以下接口生成测试断言规则：

接口信息：
- 方法：{method}
- 路径：{path}

响应参数 Schema：
{response_schema}

参考响应数据（可选）：
{response_sample}

请生成断言规则，要求：
1. 状态码断言：
   - 断言返回成功状态码（2xx）

2. 响应体断言：
   - 如果有 code/message 字段，断言其成功状态
   - 识别关键字段并添加非空断言
   - 为字段添加类型断言
   - 为数值字段添加范围断言（如 status 应为 0 或 1）
   - 为枚举字段添加枚举值断言

3. 响应头断言：
   - 断言 Content-Type 包含 json
   - 断言关键响应头存在

4. 响应时间断言：
   - 添加响应时间断言（建议 < 1000ms）

返回格式（JSON）：
{{
  "assertion_rules": [
    {{
      "source": "status|body|header|time",
      "property": "字段路径（如 $.data.id）",
      "operator": "==|!=|in|not_in|contains|not_contains|greater_than|less_than|greater_equal|less_equal|type|not_null|is_null|is_true|is_false|regex|length|empty|equals|not_equals",
      "value": "期望值",
      "description": "断言描述"
    }}
  ],
  "ai_confidence": 0.85
}}
"""
        },

        # AI 自动修复
        "auto_fix": {
            "system": "你是一个专业的测试用例修复专家，能够分析接口变更并自动修复受影响的测试用例。你擅长识别字段改名、类型变更等语义相似性。",
            "user": """
请分析以下接口变更并修复受影响的测试用例：

旧接口定义：
{old_definition}

新接口定义：
{new_definition}

变更详情：
{diff_data}

受影响的用例：
{affected_cases}

请分析：
1. 识别字段改名（如 userId → user_id）
2. 识别类型变更（如 string → integer）
3. 识别字段新增/删除

对于每个受影响的用例，生成修复方案：

返回格式（JSON）：
{{
  "fixes": [
    {{
      "case_id": "用例ID",
      "case_name": "用例名称",
      "fix_type": "rename|type_change|remove|add",
      "changes": [
        {{
          "field": "字段路径",
          "old_value": "旧值",
          "new_value": "新值",
          "confidence": 0.95
        }}
      ],
      "fixed_request_data": {{}},
      "fixed_assertion_rules": [],
      "fixed_extraction_rules": [],
      "confidence": 0.9
    }}
  ]
}}
"""
        },

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
        },

        # 模块7: 字段映射 - API字段到数据库字段映射推荐
        "field_mapping_recommendation": {
            "system": "你是数据库字段映射专家，任务是将 API 请求字段映射到数据库表字段。使用路径语义、字段名匹配、主键优先等规则给出推荐映射。",
            "user": """
请为以下 API 接口字段生成数据库字段映射推荐：

API 信息：
- method: {method}
- path: {path}
- summary: {summary}

待映射字段:
- api_field_path: {api_field_path}

数据库结构:
{schema_snapshot}

已有字段字典:
{field_dictionary}

请遵循以下规则：
1. 路径语义规则：
   - 识别路径中的资源段，如 /orders/{order_id}/items 中，order_id 应优先映射到 orders 表
   - 忽略动词段（create/update/batch/export等）
   - 路径参数优先映射到最近的资源段

2. 字段名匹配规则：
   - 字段名相似度匹配
   - 同义词匹配（如 usr → user, tel → phone 等）

3. 主键优先规则：
   - ID 字段优先映射到主键

4. 给出理由 (如路径语义、字段名匹配、主键优先)

5. 若无合适映射，返回空列表

返回格式（JSON）：
{{
  "candidates": [
    {{
      "db_table": "...",
      "db_column": "...",
      "confidence": 0.86,
      "reasons": ["path匹配","字段名相似"]
    }}
  ]
}}
"""
        },

        # 模块7扩展: 字段映射 - 批量字段映射推荐（用于处理多个字段的批量推荐）
        "field_mapping_recommendation_batch": {
            "system": "你是数据库字段映射专家，专门处理批量字段映射推荐任务。你需要同时分析多个API字段，为每个字段推荐最佳的数据库表字段映射。使用路径语义、字段名匹配、主键优先、上下文一致性等规则，并考虑字段之间的关联关系。",
            "user": """
请为以下多个API字段批量生成数据库字段映射推荐：

数据库结构:
{schema_snapshot}

已有字段字典:
{field_dictionary}

待映射字段列表:
{field_mappings}

请为每个字段分析并生成映射推荐，遵循以下规则：

1. 路径语义规则：
   - 识别路径中的资源段，如 /orders/{order_id}/items 中，order_id 应优先映射到 orders 表
   - 忽略动词段（create/update/batch/export等）
   - 路径参数优先映射到最近的资源段
   - 嵌套路径（如 path.order_id）应映射到主路径对应的表

2. 字段名匹配规则：
   - 精确匹配优先（如 order_id → orders.id）
   - 字段名相似度匹配（如 product_name → products.name）
   - 同义词映射（如 usr → user, tel → phone, addr → address 等）

3. 主键优先规则：
   - ID 字段优先映射到主键
   - 外键字段（*_id）优先映射到对应表的主键

4. 规则候选评估：
   - 分析提供的 rule_candidates，利用规则引擎的初步结果
   - 规则高评分（≥0.85）的候选应保持高置信度
   - 规则低评分的候选需要重新评估和重新排序

5. 上下文一致性：
   - 同一API的多个字段应映射到相关联的表（如 order_id → orders.id, user_id → users.id）
   - 避免矛盾映射（如一个字段的多个候选指向不相关的表）

6. 批量优化：
   - 利用批量信息进行模式识别
   - 相似路径的字段应使用一致的映射策略

返回格式（JSON）：
{{
  "field_mappings": [
    {{
      "field_name": "order_id",
      "api_field_path": "body.order_id",
      "candidates": [
        {{
          "db_table": "orders",
          "db_column": "id",
          "confidence": 0.92,
          "reasons": ["路径语义匹配", "字段名精确匹配", "主键优先"]
        }}
      ]
    }}
  ]
}}
"""
        },

        # 模块7扩展: 字段映射 - RAG 精准匹配（用于低置信度字段）
        "field_mapping_rag": {
            "system": "你是资深数据库架构师，擅长分析字段语义和上下文，从候选列表中选择最正确的映射关系。",
            "user": """
角色: 资深数据库架构师
任务: 将 API 字段映射到数据库列

[上下文]
- 当前接口推测主表: {gravity_table} (置信度高)
- 待映射字段: {api_field_name}

[候选列表 - 已按相关性排序]
{candidates_text}

[要求]
请分析字段语义和主表上下文。
- 如果候选 1-{num_candidates} 中有正确的，请返回其序号。
- 优先选择归属于 '{gravity_table}' 的列。
- 如果都不匹配，返回 None。
只返回 JSON 格式: {{"selected_index": 0, "reason": "..."}}
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
            Dict: 渲染后的 system 和 user �示词
        """
        from string import Template
        
        # 合并上下文和输入数据
        all_vars = {**context, **input_data}
        
        # 格式化 JSON 字段
        for key, value in all_vars.items():
            if isinstance(value, (dict, list)):
                all_vars[key] = json.dumps(value, indent=2, ensure_ascii=False)
        
        # 渲染提示词
        system_prompt = template.get("system", "")
        user_prompt = template.get("user", "")

        # 定义真正的占位符列表（这些需要被替换）
        real_placeholders = ['method', 'path', 'summary', 'description', 'request_schema', 'response_schema',
                            'response_sample', 'project_name', 'tech_stack', 'database', 'test_types_config',
                            'old_definition', 'new_definition', 'diff_data', 'affected_cases', 'git_diff',
                            'test_cases', 'error_message', 'logs', 'code', 'language', 'framework', 'input',
                            'api_field_path', 'schema_snapshot', 'field_dictionary', 'field_mappings',
                            'gravity_table', 'api_field_name', 'candidates_text', 'num_candidates']

        # 使用简单的字符串替换来替换真正的占位符
        # 只替换已定义的占位符，避免替换示例代码中的 {}
        for placeholder in real_placeholders:
            if placeholder in all_vars:
                # 使用正则表达式替换，只替换独立的 {placeholder}，不替换 {{placeholder}}
                import re
                pattern = r'\{' + re.escape(placeholder) + r'\}'
                user_prompt = re.sub(pattern, str(all_vars[placeholder]), user_prompt)

        return {
            "system": system_prompt,
            "user": user_prompt
        }
