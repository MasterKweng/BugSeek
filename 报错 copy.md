✦ 字段映射建议生成方案

  一、整体架构

  生成映射建议采用异步任务+多阶段处理的架构，确保大规模数据处理的可观测性和用户体验。

  1.1 技术栈
   - 后端框架: FastAPI
   - 异步任务: 基于 AsyncTask 表的自定义异步任务系统
   - 并发处理: asyncio.gather 实现批处理并发
   - 进度追踪: 5阶段独立进度条 + 实时统计信息
   - 数据库: PostgreSQL

  1.2 核心组件
   ┌─────────────────┐
   │   前端界面       │ FieldMappingSuggestions.tsx
   └────────┬────────┘
            │ HTTP POST
   ┌────────▼────────┐
   │  API 接口层      │ field_mappings_async.py
   │  /field-mappings│
   │  /suggest       │
   └────────┬────────┘
            │ 创建任务
   ┌────────▼────────┐
   │  任务管理器      │ AsyncTaskManager
   └────────┬────────┘
            │ 执行任务
   ┌────────▼────────┐
   │  字段映射处理器   │ FieldMappingProcessor
   │  (5阶段流程)     │ processor.py
   └────────┬────────┘
            │ 各阶段处理
   ┌────────▼────────┐
   │  规则引擎        │ calculate_mapping_score()
   │  + AI 服务       │ AIService
   └─────────────────┘

  ---

  二、完整处理流程

  2.1 前端触发阶段

  位置: frontend/src/pages/FieldMappingSuggestions.tsx

   // 用户点击"生成映射建议"按钮
   const handleGenerateSuggestions = async () => {
     // 1. 数据结构验证
     const schemaValid = await validateDbSchema(projectId, versionId);
     if (!schemaValid) {
       message.error("请先导入有效的数据库结构");
       return;
     }

     // 2. 创建异步任务
     const response = await createFieldMappingSuggestionTask({
       project_id: projectId,
       version_id: versionId,
       use_ai: true,  // 启用AI优化
       include_paths: true,
       include_query: true,
       include_body: true
     });

     if (response.code === 0) {
       const taskId = response.data.task_id;
       // 3. 显示进度弹窗，开始轮询
       setShowProgressDialog(true);
       pollTaskProgress(taskId);
     }
   };

  API 请求: POST /api/v1/field-mappings/suggest

  ---

  2.2 异步任务创建阶段

  位置: backend/app/api/v1/field_mappings_async.py

   @router.post("/field-mappings/suggest", response_model=ApiResponse)
   async def create_field_mapping_suggestion_task(
       project_id: int,
       version_id: int,
       use_ai: bool = True,
       include_paths: bool = True,
       include_query: bool = True,
       include_body: bool = True,
       db: Session = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ):
       """创建字段映射建议生成任务"""

       # 1. 创建异步任务记录
       task = AsyncTask(
           project_id=project_id,
           user_id=current_user.id,
           task_type="field_mapping_suggest",
           status="pending",
           progress=0,
           task_config={
               "version_id": version_id,
               "use_ai": use_ai,
               "include_paths": include_paths,
               "include_query": include_query,
               "include_body": include_body
           }
       )
       db.add(task)
       db.commit()
       db.refresh(task)

       # 2. 提交到任务队列
       task_manager.submit_task(task.id, task.task_type)

       return ApiResponse(
           code=0,
           message="任务已创建",
           data={"task_id": task.id}
       )

  ---

  2.3 任务执行入口

  位置: backend/app/field_mapping/processor.py

   async def execute(self) -> Dict[str, Any]:
       """
       执行字段映射任务主流程
       5个阶段：字段提取 -> 规则评分 -> 智能筛选 -> AI优化 -> 结果合并
       """

       # 初始化5个阶段的进度条
       stages = [
           {"name": "字段提取", "status": "pending", "progress": 0},
           {"name": "规则评分", "status": "pending", "progress": 0},
           {"name": "智能筛选", "status": "pending", "progress": 0},
           {"name": "AI优化", "status": "pending", "progress": 0},
           {"name": "结果合并", "status": "pending", "progress": 0}
       ]

       # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       # 阶段1: 字段提取和去重 (0-10%)
       # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       self._update_stage_progress(stages, 0, "running", 10)
       self._update_progress(10, "正在提取字段...")

       field_registry = await self._extract_and_deduplicate_fields(
           project_id, version_id,
           include_paths, include_query, include_body
       )

       self._update_stage_progress(stages, 0, "completed", 100)
       self._update_statistics({"total_fields": len(field_registry)})

       # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       # 阶段2: 规则评分 (15-35%)
       # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       self._update_stage_progress(stages, 1, "running", 0)
       self._update_progress(15, "正在进行规则评分...")

       db_schema = self._get_db_schema(project_id, version_id)
       rule_results = await self._batch_rule_scoring(
           field_registry, db_schema, stages
       )

       self._update_stage_progress(stages, 1, "completed", 100)

       # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       # 阶段3: 智能筛选 (40%)
       # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       self._update_stage_progress(stages, 2, "running", 50)
       self._update_progress(40, "正在进行智能筛选...")

       categories = self._intelligent_screening(field_registry, rule_results)

       self._update_stage_progress(stages, 2, "completed", 100)
       self._update_statistics({
           "auto_confirmed": len(categories.get('auto_confirm', [])),
           "ai_high": len(categories.get('ai_high', [])),
           "ai_medium": len(categories.get('ai_medium', [])),
           "ai_low": len(categories.get('ai_low', []))
       })

       # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       # 阶段4: AI优化 (45-95%)
       # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       if params.get('use_ai', True):
           self._update_stage_progress(stages, 3, "running", 0)
           self._update_progress(45, "正在进行AI优化...")

           ai_results = await self._priority_ai_calling(
               field_registry, categories, stages
           )

           self._update_stage_progress(stages, 3, "completed", 100)
       else:
           ai_results = {}

       # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       # 阶段5: 结果合并 (98-100%)
       # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       self._update_stage_progress(stages, 4, "running", 50)
       self._update_progress(98, "正在合并结果...")

       suggestions = self._merge_results(field_registry, ai_results)

       self._update_stage_progress(stages, 4, "completed", 100)
       self._update_progress(100, "处理完成")

       # 返回结果
       return {
           "success": True,
           "total": len(suggestions),
           "statistics": self._calculate_statistics(field_registry, categories),
           "suggestions": [s.model_dump() for s in suggestions]
       }

  ---

  三、各阶段详细实现

  3.1 阶段1: 字段提取和去重

  核心功能: 从所有 API 定义中提取字段路径，进行全局去重

  关键代码: processor.py:_extract_and_deduplicate_fields()

   async def _extract_and_deduplicate_fields(
       self, project_id, version_id, include_paths, include_query, include_body
   ) -> Dict[str, FieldInfo]:
       """提取字段并进行全局去重"""

       field_registry: Dict[str, FieldInfo] = {}

       # 1. 获取所有API定义
       definitions = self.db.query(ApiDefinition).filter(
           ApiDefinition.project_id == project_id
       ).all()

       # 2. 遍历所有API定义，提取字段
       for definition in definitions:
           api_fields = _extract_api_fields(
               definition, include_paths, include_query, include_body
           )

           for field_path in api_fields:
               # 解析字段路径
               source_type, field_name = self._parse_field_path(field_path)

               # 3. 字段去重
               if field_name not in field_registry:
                   field_registry[field_name] = FieldInfo(
                       field_name=field_name,
                       field_path=field_path,
                       source_type=source_type,
                       apis=[],
                       total_count=0,
                       first_seen=f"{definition.method} {definition.path}"
                   )

               # 4. 记录该字段出现的API
               field_registry[field_name].apis.append({
                   'definition_id': definition.id,
                   'method': definition.method,
                   'path': definition.path,
                   'field_path': field_path
               })
               field_registry[field_name].total_count += 1

       # 5. 分析字段使用模式
       for field_name, field_info in field_registry.items():
           field_info.appears_in_multiple_apis = field_info.total_count >= 3
           common_names = ['data', 'info', 'result', 'content', 'item']
           field_info.field_name_common = field_name in common_names

       return field_registry

  字段提取工具函数: field_mappings.py:_extract_api_fields()

   def _extract_api_fields(
       definition: ApiDefinition,
       include_paths, include_query, include_body
   ) -> List[str]:
       """从API定义中提取待映射字段"""
       fields = []

       # 提取路径参数 (如 /api/orders/{order_id} -> path.order_id)
       if include_paths:
           path_params = extract_path_params(definition.path)
           for param in path_params:
               fields.append(f"path.{param}")

       # 提取查询参数
       if include_query and definition.parameters:
           for param in definition.parameters:
               if param.get("in") == "query":
                   fields.append(f"query.{param.get('name')}")

       # 提取请求体字段
       if include_body and definition.request_schema:
           body_fields = _extract_fields_from_schema(
               definition.request_schema, prefix="body"
           )
           fields.extend(body_fields)

       return fields

  ---

  3.2 阶段2: 规则评分

  核心功能: 使用规则引擎对每个字段进行数据库匹配评分

  批处理并发: 使用 asyncio.gather 实现批次并发处理

  关键代码: processor.py:_batch_rule_scoring()

   async def _batch_rule_scoring(
       self, field_registry, db_schema, stages
   ) -> Dict[str, List[FieldMappingCandidate]]:
       """批量规则评分（支持并发批处理）"""

       # 1. 将字段分批 (每批100个)
       field_items = list(field_registry.items())
       batches = [
           field_items[i:i + self.batch_size]
           for i in range(0, len(field_items), self.batch_size)
       ]

       all_results = {}

       # 2. 使用异步并发处理各批次
       batch_tasks = []
       for idx, batch in enumerate(batches):
           batch_task = asyncio.create_task(
               self._process_rule_scoring_batch_async(batch, db_schema, idx)
           )
           batch_tasks.append(batch_task)

       # 3. 等待所有批次完成
       batch_results_list = await asyncio.gather(*batch_tasks, return_exceptions=True)

       # 4. 收集结果并更新进度
       for idx, result in enumerate(batch_results_list):
           if isinstance(result, Exception):
               logger.error(f"批次{idx}处理失败: {str(result)}")
           elif result:
               all_results.update(result)
               # 更新进度
               stage_progress = int((idx + 1) / len(batches) * 100)
               self._update_stage_progress(stages, 1, "running", stage_progress)

       return all_results

  单个批次处理: processor.py:_process_rule_scoring_batch_async()

   async def _process_rule_scoring_batch_async(
       self, batch, db_schema, batch_idx
   ) -> Dict[str, List[FieldMappingCandidate]]:
       """异步处理一批字段的规则评分"""

       results = {}

       for field_name, field_info in batch:
           try:
               first_api = field_info.apis[0]
               version_id = self.task.task_params.get("version_id")

               # 生成候选映射（批处理阶段禁用AI，只使用规则评分）
               candidates = _generate_mapping_candidates(
                   self.db,
                   {"project_id": self.task.project_id, "version_id": version_id},
                   field_info.field_path,
                   first_api['method'],
                   first_api['path'],
                   db_schema,
                   use_ai=False  # 批处理阶段禁用AI调用
               )

               results[field_name] = candidates
           except Exception as e:
               logger.error(f"字段{field_name}处理失败: {str(e)}")
               results[field_name] = []

       return results

  规则评分引擎: field_mappings.py:_generate_mapping_candidates()

   def _generate_mapping_candidates(
       db: Session, ctx, api_field_path, api_method, api_path,
       schema_snapshot, use_ai=False
   ) -> List[FieldMappingCandidate]:
       """生成字段映射候选列表"""

       api_field_name = api_field_path.split('.')[-1]
       db_schema = _get_db_schema_for_project(db, ctx["project_id"], ctx["version_id"])

       rule_candidates = []

       # 遍历数据库中的表和字段，计算评分
       if db_schema and isinstance(db_schema, dict):
           # 支持两种格式：字典格式 {table_name: {...}} 和 列表格式 {tables: [...]}
           if "tables" in db_schema and isinstance(db_schema["tables"], list):
               # 列表格式（SQL解析器返回）
               for table_info in db_schema["tables"]:
                   table_name = table_info.get("name", "")
                   columns = table_info.get("columns", [])
                   for column_info in columns:
                       column_name = column_info.get("name", "")
                       is_primary_key = column_info.get("primary_key", False)

                       # 计算映射评分
                       scores = calculate_mapping_score(
                           api_field=api_field_name,
                           db_column=column_name,
                           db_table=table_name,
                           path=api_path,
                           is_primary_key=is_primary_key,
                           type_compatible=True
                       )

                       score = scores["total_score"]

                       # 只保留分数大于0.3的候选
                       if score > 0.3:
                           rule_candidates.append(FieldMappingCandidate(
                               db_table=table_name,
                               db_column=column_name,
                               score=score,
                               reasons=_build_reasons(scores)
                           ))

       # 按分数降序排列，返回前10个
       rule_candidates.sort(key=lambda x: x.score, reverse=True)
       return rule_candidates[:10]

  评分算法: field_mappings.py:calculate_mapping_score()

   def calculate_mapping_score(
       api_field, db_column, db_table, path, is_primary_key, type_compatible
   ) -> Dict[str, float]:
       """计算字段映射评分"""

       scores = {
           "field_score": 0.0,    # 字段名匹配分
           "table_score": 0.0,    # 表名匹配分
           "path_score": 0.0,     # 路径语义分
           "pk_score": 0.0,       # 主键优先分
           "type_score": 0.0      # 类型匹配分
       }

       # 1. 字段名匹配 (0-0.4)
       if api_field == db_column:
           scores["field_score"] = 0.4
       elif api_field in db_column or db_column in api_field:
           scores["field_score"] = 0.2
       elif api_field.replace('_', '') == db_column.replace('_', ''):
           scores["field_score"] = 0.15

       # 2. 表名匹配 (0-0.2)
       table_name_singular = db_table.rstrip('s')
       if table_name_singular in api_field:
           scores["table_score"] = 0.2
       elif db_table in api_field:
           scores["table_score"] = 0.15

       # 3. 路径语义 (0-0.2)
       path_segments = [seg for seg in path.split('/') if seg and not seg.startswith('{')]
       if path_segments and path_segments[-1] in db_table:
           scores["path_score"] = 0.2
       elif any(seg in db_table for seg in path_segments):
           scores["path_score"] = 0.1

       # 4. 主键优先 (0-0.15)
       if is_primary_key and 'id' in api_field.lower():
           scores["pk_score"] = 0.15

       # 5. 类型匹配 (0-0.05)
       if type_compatible:
           scores["type_score"] = 0.05

       # 总分 = 各项加权求和
       scores["total_score"] = sum(scores.values())

       return scores

  ---

  3.3 阶段3: 智能筛选

  核心功能: 根据规则评分结果，对字段进行分类，确定哪些需要AI优化

  分类标准:
   - auto_confirm: 规则评分≥0.85，无需AI
   - ai_high: 需要高优先级AI优化（评分低、候选少、ID字段等）
   - ai_medium: 中等优先级（评分中等、数组字段等）
   - ai_low: 低优先级（通用字段名）

  关键代码: processor.py:_intelligent_screening()

   def _intelligent_screening(
       self, field_registry, rule_results
   ) -> Dict[str, List[str]]:
       """智能筛选 - 对字段进行优先级分类"""

       categories = {
           'auto_confirm': [],
           'ai_high': [],
           'ai_medium': [],
           'ai_low': []
       }

       for field_name, field_info in field_registry.items():
           rule_candidates = rule_results.get(field_name, [])
           screening_result = self._screen_field(field_name, field_info, rule_candidates)

           # 更新字段信息
           field_info.rule_candidates = rule_candidates
           field_info.rule_top_score = rule_candidates[0].score if rule_candidates else 0.0
           field_info.ai_priority = screening_result.ai_priority
           field_info.screening_reasons = screening_result.reasons

           # 分类
           if screening_result.ai_priority == "none":
               categories['auto_confirm'].append(field_name)
           elif screening_result.ai_priority == "high":
               categories['ai_high'].append(field_name)
           elif screening_result.ai_priority == "medium":
               categories['ai_medium'].append(field_name)
           else:
               categories['ai_low'].append(field_name)

       return categories

  单字段筛选逻辑: processor.py:_screen_field()

   def _screen_field(self, field_name, field_info, rule_candidates) -> ScreeningResult:
       """对单个字段进行智能筛选"""

       reasons = []
       ai_priority = "none"
       top_score = rule_candidates[0].score if rule_candidates else 0.0

       # === 第一级：规则评分筛选 ===
       if top_score >= 0.85:
           ai_priority = "none"
           reasons.append("规则评分高(≥0.85)，无需AI确认")
           return ScreeningResult(ai_priority="none", reasons=reasons, action="auto_confirm")
       elif top_score >= 0.60:
           ai_priority = "medium"
           reasons.append("规则评分中等(0.60-0.85)，AI优化候选排序")
       else:
           ai_priority = "high"
           reasons.append("规则评分低(<0.60)，需要AI重新推荐")

       # === 第二级：候选数量筛选 ===
       candidate_count = len(rule_candidates)
       if candidate_count <= 1:
           ai_priority = "high"
           reasons.append(f"候选数量过少({candidate_count}个)，需要AI扩展")
       elif candidate_count >= 5:
           ai_priority = "high"
           reasons.append(f"候选数量过多({candidate_count}个)，需要AI筛选")

       # === 第三级：字段类型筛选 ===
       if self._is_id_field(field_name):
           ai_priority = "high"
           reasons.append("ID类字段，需要AI精确匹配")

       if self._is_complex_nested(field_info.field_path):
           ai_priority = "high"
           reasons.append("复杂嵌套字段，需要AI深度分析")

       # === 第四级：语义冲突筛选 ===
       if self._has_semantic_conflict(rule_candidates, field_name, field_info.apis[0]['path']):
           ai_priority = "high"
           reasons.append("路径语义与候选表名冲突，需要AI纠正")

       # === 第五级：使用模式筛选 ===
       if field_info.appears_in_multiple_apis:
           if ai_priority == "none":
               ai_priority = "low"
           reasons.append(f"字段在{field_info.total_count}个API中使用，AI可学习模式")

       return ScreeningResult(ai_priority=ai_priority, reasons=reasons, action="ai_optimize")

  ---

  3.4 阶段4: AI优化

  核心功能: 对筛选出的字段，使用AI服务进行智能推荐优化

  优先级队列: 高优先级优先处理，每批最多10个字段

  批量处理: 减少API调用次数，降低成本

  关键代码: processor.py:_priority_ai_calling()

   async def _priority_ai_calling(
       self, field_registry, categories, stages
   ) -> Dict[str, List[FieldMappingCandidate]]:
       """优先级AI调用"""

       # 1. 创建优先级队列
       priority_queue = PriorityAIQueue()

       # 2. 将字段按优先级加入队列
       for field_name in categories.get('ai_high', []):
           priority_queue.enqueue(field_name, field_registry[field_name])
       for field_name in categories.get('ai_medium', []):
           priority_queue.enqueue(field_name, field_registry[field_name])
       for field_name in categories.get('ai_low', []):
           priority_queue.enqueue(field_name, field_registry[field_name])

       all_results = {}

       # 3. 批量处理
       while not priority_queue.is_empty():
           priority, batch = priority_queue.get_next_batch()
           if not batch:
               break

           try:
               batch_results = await self._call_ai_batch(batch)
               all_results.update(batch_results)

               # 更新进度
               self._update_stage_progress(stages, 3, "running", ...)
               self._update_realtime_progress(...)

           except Exception as e:
               logger.error(f"AI批次处理失败: {str(e)}")
               # 返回规则结果作为降级方案
               for req in batch:
                   all_results[req.field_name] = req.rule_candidates

       return all_results

  AI批次调用: processor.py:_call_ai_batch()

   async def _call_ai_batch(
       self, requests: List[AIRequest]
   ) -> Dict[str, List[FieldMappingCandidate]]:
       """批量调用AI服务（带重试机制）"""

       # 1. 构建批量AI输入
       batch_input = {
           "field_mappings": [
               {
                   "api_field_path": req.field_path,
                   "method": req.api_context['method'],
                   "path": req.api_context['path'],
                   "field_name": req.field_name,
                   "rule_candidates": [
                       {
                           "db_table": c.db_table,
                           "db_column": c.db_column,
                           "score": c.score,
                           "reasons": c.reasons
                       }
                       for c in req.rule_candidates[:3]  # 只取前3个规则候选
                   ]
               }
               for req in requests
           ]
       }

       # 2. 重试逻辑（最多3次）
       for attempt in range(self.max_ai_retries):
           try:
               result = await self._execute_ai_call(batch_input)
               return self._parse_ai_result(result, requests)
           except concurrent.futures.TimeoutError:
               if attempt < self.max_ai_retries - 1:
                   await asyncio.sleep(self.ai_retry_delay)
               continue

       # 所有重试失败，返回规则结果作为降级方案
       return {req.field_name: req.rule_candidates for req in requests}

  AI服务调用: processor.py:_execute_ai_call()

   async def _execute_ai_call(self, batch_input: Dict[str, Any]) -> Any:
       """执行AI调用（在线程池中运行）"""

       import asyncio

       def _async_call():
           loop = asyncio.new_event_loop()
           asyncio.set_event_loop(loop)
           try:
               return loop.run_until_complete(
                   self.ai_service.execute(
                       task_type="field_mapping_recommendation_batch",
                       project_id=self.task.project_id,
                       input_data=batch_input
                   )
               )
           finally:
               loop.close()

       # 使用线程池执行AI调用
       with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
           future = executor.submit(_async_call)
           return future.result(timeout=self.ai_timeout)

  AI结果解析: processor.py:_parse_ai_result()

   def _parse_ai_result(self, ai_result, requests) -> Dict[str, List[FieldMappingCandidate]]:
       """解析AI返回结果"""

       if not ai_result.get("success"):
           return {req.field_name: req.rule_candidates for req in requests}

       result_data = ai_result.get("result", {})

       # 处理可能的markdown代码块格式
       if isinstance(result_data, str):
           if "```json" in result_data:
               start = result_data.find("```json") + 7
               end = result_data.find("```", start)
               if end > start:
                   result_data = result_data[start:end].strip()
           elif "```" in result_data:
               start = result_data.find("```") + 3
               end = result_data.find("```", start)
               if end > start:
                   result_data = result_data[start:end].strip()

           try:
               result_data = json.loads(result_data)
           except json.JSONDecodeError:
               return {req.field_name: req.rule_candidates for req in requests}

       # 提取批量结果
       results = {}
       if isinstance(result_data, dict) and "field_mappings" in result_data:
           for mapping_result in result_data["field_mappings"]:
               field_name = mapping_result.get("field_name")
               ai_candidates = mapping_result.get("candidates", [])

               # 转换为FieldMappingCandidate
               candidates = []
               for cand in ai_candidates:
                   candidates.append(FieldMappingCandidate(
                       db_table=cand.get("db_table", ""),
                       db_column=cand.get("db_column", ""),
                       score=cand.get("confidence", 0.0),
                       reasons=cand.get("reasons", [])
                   ))

               results[field_name] = candidates if candidates else []

       return results

  ---

  3.5 阶段5: 结果合并

  核心功能: 合并规则候选和AI候选，生成最终建议列表

  合并策略:
   - auto_confirm: 只使用规则候选
   - 有AI结果: 合并并去重，保留最高分数
   - 无AI结果: 使用规则候选

  关键代码: processor.py:_merge_results()

   def _merge_results(
       self, field_registry, ai_results
   ) -> List[FieldMappingSuggestion]:
       """合并规则结果和AI结果，生成最终建议列表"""

       suggestions = []

       for field_name, field_info in field_registry.items():
           ai_candidates = ai_results.get(field_name, [])
           rule_candidates = field_info.rule_candidates or []  # 确保不为None

           # 合并策略
           if field_info.ai_priority == "none":
               final_candidates = rule_candidates
           elif ai_candidates:
               merged = self._merge_candidates(rule_candidates, ai_candidates)
               final_candidates = merged
           else:
               final_candidates = rule_candidates

           # 为每个API生成建议
           for api_ref in field_info.apis:
               suggestion = FieldMappingSuggestion(
                   definition_id=api_ref['definition_id'],
                   definition_method=api_ref['method'],
                   definition_path=api_ref['path'],
                   api_field_path=api_ref['field_path'],
                   candidates=final_candidates
               )
               suggestions.append(suggestion)

       return suggestions

  候选合并: processor.py:_merge_candidates()

   def _merge_candidates(
       self, rule_candidates, ai_candidates
   ) -> List[FieldMappingCandidate]:
       """合并规则候选和AI候选"""

       all_candidates = rule_candidates + ai_candidates

       # 按字段去重，保留分数更高的
       unique = {}
       for cand in all_candidates:
           key = f"{cand.db_table}.{cand.db_column}"
           if key not in unique:
               unique[key] = cand
           else:
               if cand.score > unique[key].score:
                   unique[key] = cand

       # 按分数排序，返回前10个
       sorted_candidates = sorted(
           unique.values(),
           key=lambda x: x.score,
           reverse=True
       )

       return sorted_candidates[:10]

  ---

  四、进度追踪

  4.1 5阶段进度条

  位置: processor.py:_update_stage_progress()

   def _update_stage_progress(
       self, stages, stage_index, status, progress
   ):
       """更新单个阶段的进度"""

       if stage_index < len(stages):
           stages[stage_index]["status"] = status
           stages[stage_index]["progress"] = progress
           self.task.stages = stages
           self.db.commit()

  4.2 实时统计信息

  位置: processor.py:_update_statistics()

   def _update_statistics(self, statistics: Dict[str, Any]):
       """更新任务统计信息"""

       if not self.task.statistics:
           self.task.statistics = {}
       self.task.statistics.update(statistics)
       self.db.commit()

  4.3 前端进度查询

  API: GET /api/v1/async-tasks/{task_id}

  位置: backend/app/api/v1/field_mappings_async.py

   @router.get("/async-tasks/{task_id}", response_model=ApiResponse)
   async def get_async_task_progress(task_id: int, db: Session = Depends(get_db)):
       """获取异步任务进度（包含阶段和统计信息）"""

       task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()

       return ApiResponse(
           code=0,
           message="获取成功",
           data={
               "task_id": task.id,
               "status": task.status,
               "progress": task.progress,
               "progress_message": task.progress_message,
               "stages": task.stages or [],
               "statistics": task.statistics or {},
               "result": task.result if task.status == "completed" else None,
               "error": task.error if task.status == "failed" else None
           }
       )

  ---

  五、前端进度展示

  位置: frontend/src/pages/FieldMappingSuggestions.tsx

   // 5个独立进度条组件
   <div className="space-y-3">
     <ProgressItem
       name="字段提取"
       progress={getStageProgress(0)}
       status={getStageProgressStatus(0)}
     />
     <ProgressItem
       name="规则评分"
       progress={getStageProgress(1)}
       status={getStageProgressStatus(1)}
     />
     <ProgressItem
       name="智能筛选"
       progress={getStageProgress(2)}
       status={getStageProgressStatus(2)}
     />
     <ProgressItem
       name="AI优化"
       progress={getStageProgress(3)}
       status={getStageProgressStatus(3)}
     />
     <ProgressItem
       name="结果合并"
       progress={getStageProgress(4)}
       status={getStageProgressStatus(4)}
     />
   </div>

   // 实时统计信息展示
   <div className="mt-4 p-4 bg-gray-50 rounded">
     <div>总字段数: {statistics.total_fields || 0}</div>
     <div>自动确认: {statistics.auto_confirmed || 0}</div>
     <div>高优先级AI: {statistics.ai_high || 0}</div>
     <div>中优先级AI: {statistics.ai_medium || 0}</div>
     <div>低优先级AI: {statistics.ai_low || 0}</div>
   </div>

  ---

  六、技术亮点

  6.1 性能优化
   - 批处理并发: 使用 asyncio.gather 实现批次并发，显著提升处理速度
   - 智能筛选: 只对需要的字段调用AI，降低成本
   - 批量AI调用: 一次API调用处理多个字段，减少网络开销

  6.2 可靠性保障
   - 降级方案: AI调用失败时自动降级到规则结果
   - 重试机制: AI调用支持最多3次重试
   - 异常隔离: 单个字段处理失败不影响整体流程

✦ 6.3 可观测性
   - 5阶段进度条: 清晰展示处理进度
   - 实时统计: 动态显示字段分类统计
   - 详细日志: 关键节点记录日志，便于问题排查