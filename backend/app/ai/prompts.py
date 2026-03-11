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

3. 字段描述匹配规则（重要）：
   - 仔细阅读字段描述，理解字段的实际含义
   - 字段描述优先级高于字段名匹配
   - 例如：字段名 "id" 但描述为"订单ID"，应映射到 orders.id 而非其他表的 id
   - 如果字段描述包含特定的业务术语，优先选择包含相同术语的表或列
   - 如果字段描述为空或模糊，参考字段名和其他上下文信息

4. 主键优先规则：
   - ID 字段优先映射到主键
   - 外键字段（*_id）优先映射到对应表的主键

5. 规则候选评估：
   - 分析提供的 rule_candidates，利用规则引擎的初步结果
   - 规则高评分（≥0.85）的候选应保持高置信度
   - 规则低评分的候选需要重新评估和重新排序
   - 注意：rule_candidates 中的 comment 字段是数据库列的注释，请参考

6. 上下文一致性：
   - 同一API的多个字段应映射到相关联的表（如 order_id → orders.id, user_id → users.id）
   - 避免矛盾映射（如一个字段的多个候选指向不相关的表）

7. 批量优化：
   - 利用批量信息进行模式识别
   - 相似路径的字段应使用一致的映射策略

返回格式（JSON）：
{{
  "field_mappings": [
    {{
      "field_name": "order_id",
      "api_field_path": "body.order_id",
      "field_description": "订单ID",
      "candidates": [
        {{
          "db_table": "orders",
          "db_column": "id",
          "confidence": 0.92,
          "reasons": ["路径语义匹配", "字段名精确匹配", "主键优先", "字段描述匹配"]
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
        },

        # ========== 意图生成场景 - BSK-SC-014 ==========
        "intent_scenario_generation": {
            "system": """你是一个专业的 API 测试架构师，擅长将自然语言业务意图转化为可执行的 API 测试场景。

【严格约束】：
1. 你只能从我提供的【候选 API 列表】中选择接口，绝对不允许凭空捏造或编造不存在的 API
2. ref_id 必须严格等于候选 API 列表中的 id，不允许创建虚拟的 ref_id
3. 如果用户的某个业务步骤在候选列表中找不到对应的 API，请生成一个占位符节点（修正陷阱三）：
   - ref_id: -1
   - node_type: "missing_api"
   - node_name: "待补齐：[步骤名称]"
   - 在 reasoning 中明确说明：缺少该接口，需要用户手动选择
4. 必须在 reasoning 中明确指出选择了哪些 API、缺少哪些接口

【违规处理】：
如果检测到你捏造了不在候选列表中的 API，整个回答将被视为无效。

请基于以上约束，分析用户意图，识别相关 API，并设计合理的执行顺序和变量传递机制。""",
            "user": """
请根据用户的业务意图，生成一个完整的 API 测试场景。

用户意图：
{user_intent}

项目信息：
- 项目名称：{project_name}
- 业务领域：{business_domain}
- 技术栈：{tech_stack}

候选 API 列表（已通过向量检索和关键词匹配筛选）：
{candidate_apis}

请分析用户意图，执行以下两个阶段：

阶段一：业务步骤识别
1. 将用户意图分解为具体的业务步骤
2. 识别每个步骤对应的 API 调用
3. 确定步骤之间的执行顺序（依赖关系）

阶段二：场景生成
基于业务步骤，生成可直接落库的场景数据结构：

返回格式（JSON）：
{{
  "scenario": {{
    "name": "场景名称（基于意图自动生成）",
    "description": "场景描述",
    "scenario_type": "business_flow",
    "source_type": "intent",
    "execution_mode": "dag",
    "timeout_seconds": 600,
    "retry_count": 0,
    "continue_on_failure": false
  }},
  "nodes": [
    {{
      "node_key": "step1",
      "node_name": "第一步：创建用户",
      "node_type": "api_call",
      "ref_type": "api_definition",
      "ref_id": 123,
      "step_order": 1,
      "depends_on": [],
      "input_mapping": {{
        // 从环境变量或全局变量映射
        "body.name": "{{random_string(8)}}",
        "body.email": "test_{{random_string(6)}}@example.com"
      }},
      "extract_rules": {{
        // 提取响应变量
        "user_id": "$.data.id"
      }},
      "assertion_overrides": [
        {{"field": "status", "operator": "equals", "value": 201}}
      ],
      "timeout_seconds": 30,
      "retry_count": 0,
      "continue_on_failure": false,
      "is_enabled": true
    }},
    {{
      "node_key": "step2",
      "node_name": "第二步：查询用户",
      "node_type": "api_call",
      "ref_type": "api_definition",
      "ref_id": 456,
      "step_order": 2,
      "depends_on": ["step1"],
      "input_mapping": {{
        // 使用上一步提取的变量
        "path_params.user_id": "{{user_id}}"
      }},
      "extract_rules": {},
      "assertion_overrides": [
        {{"field": "status", "operator": "equals", "value": 200}},
        {{"field": "body.data.id", "operator": "equals", "value": "{{user_id}}"}}
      ],
      "timeout_seconds": 30,
      "retry_count": 0,
      "continue_on_failure": false,
      "is_enabled": true
    }}
  ],
  "reasoning": "解释为什么选择这些 API 和这个执行顺序"
}}

要求：
1. 【核心】只能从候选 API 列表中选择，ref_id 必须等于候选 API 的 id，禁止创建任何 ref_id（除了占位符）
2. 【占位符机制】如果某个业务步骤在候选列表中找不到对应的 API，必须生成占位符节点：
   - ref_id: -1
   - node_type: "missing_api"
   - node_name: "待补齐：[步骤名称]"
3. 【reasoning】必须说明：选择了哪些 API、缺少哪些接口以及原因
4. 确保 depends_on 引用的 node_key 存在于当前场景中
5. 在 input_mapping 中使用 {{变量名}} 格式引用变量
6. 在 extract_rules 中使用 JSONPath 语法提取字段
7. ref_type 必须固定为 "api_definition"（占位符节点除外）
"""
        },

        # ========== API 检索重排 - BSK-SC-015 ==========
        "api_retrieval_ranking": {
            "system": "你是一个专业的 API 知识库检索专家，擅长根据用户意图对候选 API 进行智能排序和筛选。你能够理解 API 的语义、功能和上下文，判断其与用户意图的相关性。",
            "user": """
请根据用户意图，对候选 API 列表进行排序和筛选。

用户意图：
{user_intent}

项目信息：
- 项目名称：{project_name}
- 业务领域：{business_domain}

候选 API 列表（已通过向量检索初步筛选）：
{candidate_apis}

请执行以下任务：

1. **相关性评分**：对每个候选 API 进行 0-10 分的相关性评分
   - 10 分：完全匹配，直接使用
   - 8-9 分：高度相关，可能需要调整参数
   - 5-7 分：部分相关，可能需要组合使用
   - 0-4 分：不相关，应该排除

2. **排序**：按相关性评分从高到低排序

3. **筛选**：剔除相关性评分低于 5 分的 API

4. **补充说明**：对每个 API 提供评分理由

返回格式（JSON）：
{{
  "ranked_apis": [
    {{
      "id": 123,
      "method": "POST",
      "path": "/api/users",
      "summary": "创建用户",
      "relevance_score": 10,
      "reason": "完全匹配用户意图中的'创建用户'步骤"
    }},
    {{
      "id": 456,
      "method": "GET",
      "path": "/api/users/{id}",
      "summary": "获取用户详情",
      "relevance_score": 9,
      "reason": "高度相关，可用于验证用户创建结果"
    }}
  ],
  "excluded_apis": [
    {{
      "id": 789,
      "method": "DELETE",
      "path": "/api/users/{id}",
      "summary": "删除用户",
      "relevance_score": 3,
      "reason": "不相关，用户意图中未提及删除操作"
    }}
  ],
  "summary": {{
    "total_candidates": 10,
    "relevant_count": 7,
    "excluded_count": 3
  }}
}}

要求：
1. 评分要客观公正，基于 API 的 method、path、summary 和 description
2. 排序要准确，确保最相关的 API 排在前面
3. 理由要清晰，说明为什么给这个分数
4. 如果没有足够相关的 API，返回空列表并在 summary 中说明
"""
        },

        # ========== 意图 API 选择 - BSK-SC-014 ==========
        "intent_api_selection": {
            "system": "你是一个专业的 API 选择专家，擅长根据用户意图从候选 API 列表中筛选出最相关的核心 API。",
            "user": """
请根据用户意图，从候选 API 列表中选择 3-5 个最相关的 API。

用户意图：
{user_intent}

候选 API 列表（包含签名信息 + 关键参数）：
{candidate_apis}

任务：
1. 分析用户意图，识别需要的业务步骤
2. 从候选列表中选择最匹配的 API（3-5个）
3. 排除不相关或冗余的 API
4. 注意：同名或相似接口可能通过参数区分（如 B2C vs B2B 订单）

返回格式（JSON）：
{{
  "selected_ids": [123, 456, 789],  // 选中 API 的 ID 列表
  "rejected_ids": [111, 222],  // 排除的 API ID 列表
  "reasoning": "解释为什么选择这些 API，为什么排除其他 API"
}}

要求：
1. selected_ids 必须严格来源于候选列表
2. 优先选择核心业务流程的 API
3. 排除过于笼统或不相关的 API
4. 考虑参数差异，选择最匹配用户意图的接口
"""
        },

        # ========== 场景执行根因分析 - BSK-SC-030 ==========
        "scenario_failure_rca": {
            "system": "你是一个专业的测试根因分析专家，擅长分析 API 场景执行失败的根本原因，提供详细的诊断和修复建议。",
            "user": """
请分析以下场景执行失败的原因，提供详细的根因分析和修复建议。

场景信息：
- 场景名称：{scenario_name}
- 场景描述：{scenario_description}

环境信息：
- 环境名称：{environment_name}
- 执行时间：{execution_time}

失败节点详情：
{failure_details}

整体执行结果：
- 总节点数：{total_nodes}
- 成功节点：{passed_nodes}
- 失败节点：{failed_nodes}
- 总耗时：{total_duration_ms}ms

请执行以下分析：

1. **失败原因分类**：
   - 请求发送失败（连接错误、超时等）
   - 响应状态码不匹配（4xx、5xx 等）
   - 断言失败（预期值不匹配）
   - 变量提取失败（响应格式不符合预期）
   - 其他（请说明）

2. **根本原因定位**：
   - 分析失败节点的请求参数是否正确
   - 分析响应结果是否符合预期
   - 检查是否有前置依赖节点的问题
   - 检查数据准备是否充分

3. **修复建议**：
   - 提供具体的修复步骤
   - 如果是配置问题，指出需要修改的配置项
   - 如果是数据问题，指出需要准备的数据
   - 如果是场景逻辑问题，指出需要调整的步骤

4. **优先级评估**：
   - 高优先级：导致整个场景失败的致命问题
   - 中优先级：影响部分功能的重要问题
   - 低优先级：优化建议

返回格式（JSON）：
{{
  "summary": {{
    "failure_type": "请求发送失败/响应状态码不匹配/断言失败/变量提取失败/其他",
    "failed_nodes_count": {failed_nodes_count},
    "root_cause": "根本原因简述",
    "priority": "high/medium/low"
  }},
  "node_analysis": [
    {{
      "node_key": "node_1",
      "node_name": "创建用户",
      "failure_type": "响应状态码不匹配",
      "root_cause": "用户名已存在，返回 409 状态码",
      "evidence": {{
        "expected_status": 200,
        "actual_status": 409,
        "response_body": {{"error": "username already exists"}}
      }},
      "fix_suggestion": "在创建用户前，先检查用户名是否已存在，或者使用随机用户名"
    }}
  ],
  "data_issues": [
    {{
      "issue": "缺少必需的测试数据",
      "affected_nodes": ["node_1", "node_3"],
      "suggestion": "在场景开始前准备测试用户数据"
    }}
  ],
  "environment_issues": [
    {{
      "issue": "环境配置问题",
      "description": "测试环境的认证服务不可用",
      "suggestion": "检查认证服务状态，或使用 Mock 服务"
    }}
  ],
  "action_plan": [
    {{
      "step": 1,
      "action": "修复数据准备逻辑",
      "details": "在场景开始前添加数据清理步骤",
      "priority": "high"
    }},
    {{
      "step": 2,
      "action": "调整断言逻辑",
      "details": "对可能出现的 409 状态码添加特殊处理",
      "priority": "medium"
    }}
  ]
}}

要求：
1. 分析要深入，不能只停留在表面现象
2. 修复建议要具体可行，能够指导实际操作
3. 优先级评估要准确，帮助用户快速定位关键问题
4. 如果失败原因复杂，可以提供多个可能的原因并给出验证方法
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
                            'gravity_table', 'api_field_name', 'candidates_text', 'num_candidates',
                            'user_intent', 'candidate_apis', 'business_domain']

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
