• 已修复并补齐你提到的全部问题，覆盖后端/前端/AI 模板与执行器一致性。核心改动如下：

  已修复问题与对应改动
  1. 用例提取规则字段不匹配
      - 影响文件：backend/app/ai/prompts.py、backend/app/core/test_execution.py、frontend/src/pages/api-hub/CasesList.tsx
      - 执行器兼容 query_params 并合并到 query。
      - Prompt 改为“查询参数顶层”。
      - 影响文件：backend/app/core/test_execution.py、backend/app/ai/prompts.py
  3. 时间占位符不一致
      - Prompt 统一为 {{timestamp()}}，执行器兼容 {{timestamp}}。
      - 影响文件：backend/app/ai/prompts.py、backend/app/core/test_execution.py
  4. AI 断言 operator/source 不兼容
      - 执行器扩展：equals/not_equals/greater_than/...、header/time 等均可执行；增加 regex/length/empty/type。
      - 响应耗时 elapsed_ms 已加入响应结构用于 time 断言。
      - 影响文件：backend/app/core/test_execution.py
  5. AI 用例保存未标记 ai_generated/ai_confidence
      - API 支持写入 ai_generated/ai_confidence；前端保存时写入。
      - 影响文件：backend/app/api/v1/api_cases.py、frontend/src/pages/api-hub/CasesList.tsx
  6. AIAssistedExecutor.generate_test_cases 未实现
      - 直接调用 AIService.generate_base_case 实现。
      - 影响文件：backend/app/core/test_execution.py

  ———

  具体修改文件

  - backend/app/ai/prompts.py
      - 修正 timestamp()、GET/DELETE 查询参数结构、extraction_rules 字段名、断言 operator 列表。
  - backend/app/core/test_execution.py
      - 支持 query_params、timestamp 兼容、提取规则字段兼容、断言扩展、elapsed_ms。
      - 实现 AIAssistedExecutor.generate_test_cases。
  - backend/app/api/v1/api_cases.py
      - ApiCaseCreate/Update 增加 ai_generated/ai_confidence，创建时写入。
  - frontend/src/pages/api-hub/CasesList.tsx
      - 保存 AI 用例时写入 ai_generated/ai_confidence。
      - 预览兼容旧字段名。

  ———

  建议下一步

  1. 你可以跑一遍用例生成 + 执行，确认断言/提取是否正确落库。
  2. 如果要我补上测试或增加断言模板适配规则，可继续指示。