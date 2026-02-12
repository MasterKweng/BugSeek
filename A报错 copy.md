  🚨 问题 1：asyncio.run() 嵌套调用（存在）

  原问题：在 call_ai_for_ambiguous_mapping 中使用了 ThreadPoolExecutor 并在线程中调用 asyncio.run()

  我的代码问题：

   # app/utils/vector_index.py
   def call_ai_for_ambiguous_mapping(...):  # ❌ 同步函数
       def run_ai():
           """在后台运行 AI 任务"""
           try:
               return asyncio.run(  # ❌ 致命错误：在新线程中创建新的事件循环
                   ai_service.execute(...)
               )

       with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
           future = executor.submit(run_ai)
           ai_result = future.result(timeout=30)

  后果：
   - ❌ 上下文丢失：新的事件循环无法传递 Request Context、Trace ID
   - ❌ 资源浪费：为每个 AI 请求创建新的 Event Loop
   - ❌ 兼容性问题：可能触发 RuntimeError: There is no current event loop in thread

  如何修改：将整个调用链改为全异步

  修改 1：app/utils/vector_index.py

   # 删除僵尸方法
   # def _build_ai_prompt(...):  # ❌ 删除整个方法

   # 修改为 async
   async def call_ai_for_ambiguous_mapping(
       self,
       api_field_name: str,
       gravity_table: str,
       candidates: List[Dict[str, Any]],
       top_k: int = 5
   ) -> Optional[Dict[str, Any]]:
       """对低置信度字段调用 AI 兜底（异步版本）"""
       if not candidates:
           return None

       top_score = candidates[0].get("final_score", 0)
       if top_score >= 0.7:
           return None

       logger.info(f"[{self.trace_id}] AI 兜底触发: api_field={api_field_name}, top_score={top_score:.2f}")

       top_candidates = candidates[:top_k]

       # 构造候选文本
       candidates_text = ""
       for i, cand in enumerate(top_candidates, 1):
           candidates_text += (
               f"{i}. 表:{cand.get('db_table', '')}, "
               f"列:{cand.get('db_column', '')}, "
               f"类型:{cand.get('column_type', '')}, "
               f"语义分:{cand.get('score', 0):.2f}\n"
           )

       # 直接调用 AI 服务（异步）
       try:
           from app.ai.service import AIService

           ai_service = AIService()

           ai_input = {
               "api_field_name": api_field_name,
               "gravity_table": gravity_table,
               "candidates_text": candidates_text,
               "num_candidates": len(top_candidates)
           }

           # ✅ 直接 await，不需要 ThreadPool
           ai_result = await ai_service.execute(
               task_type="field_mapping_rag",
               project_id=None,
               input_data=ai_input
           )

           # 解析 AI 返回结果
           if ai_result and ai_result.get("success"):
               result_data = ai_result.get("result", {})

               if isinstance(result_data, str):
                   try:
                       import json
                       result_data = json.loads(result_data)
                   except json.JSONDecodeError:
                       logger.warning(f"[{self.trace_id}] AI 结果 JSON 解析失败")
                       return None

               if isinstance(result_data, dict):
                   selected_index = result_data.get("selected_index")
                   reason = result_data.get("reason", "")

                   if selected_index is not None and 0 <= selected_index < len(top_candidates):
                       selected = top_candidates[selected_index].copy()
                       selected["ai_selected"] = True
                       selected["ai_reason"] = reason
                       logger.info(f"[{self.trace_id}] AI 选择: index={selected_index}, reason={reason}")
                       return selected

           return None

       except Exception as e:
           logger.warning(f"[{self.trace_id}] AI 兜底调用失败: {str(e)}")
           return None

   # 修改为 async
   async def batch_search_with_gravity(
       self,
       api_fields: List[str],
       top_k: int = 10,
       use_ai_fallback: bool = True,
       ai_confidence_threshold: float = 0.7
   ) -> Dict[str, Any]:
       """批量搜索字段映射（异步版本）"""
       if self.column_vectors is None or self.column_meta is None:
           return {
               "gravity_table": None,
               "results": {field: [] for field in api_fields},
               "ai_fallback_count": 0
           }

       field_names = [field.split('.')[-1] for field in api_fields]

       # 步骤A: 全量初筛
       all_candidates = []
       for field_name in field_names:
           candidates = self.search(field_name, top_k=top_k)
           all_candidates.append(candidates)

       # 步骤B: 计算重心表
       gravity_table = self.calculate_gravity_table(all_candidates)

       # 步骤C: 重排序 + AI 兜底
       results = {}
       ai_fallback_count = 0

       for i, (api_field, field_name) in enumerate(zip(api_fields, field_names)):
           candidates = all_candidates[i]
           if gravity_table:
               candidates = self.re_rank_candidates(candidates, gravity_table, field_name)

           # AI 兜底（异步调用）
           if use_ai_fallback and candidates:
               top_score = candidates[0].get("final_score", 0)
               if top_score < ai_confidence_threshold:
                   # ✅ 添加 await
                   ai_selected = await self.call_ai_for_ambiguous_mapping(
                       field_name, gravity_table, candidates
                   )
                   if ai_selected:
                       candidates.remove(ai_selected)
                       candidates.insert(0, ai_selected)
                       ai_fallback_count += 1

           results[api_field] = candidates

       logger.info(
           f"[{self.trace_id}] 批量向量搜索完成: 字段数={len(api_fields)}, "
           f"重心表={gravity_table}, AI兜底={ai_fallback_count}"
       )

       return {
           "gravity_table": gravity_table,
           "results": results,
           "ai_fallback_count": ai_fallback_count
       }

  修改 2：app/api/v1/field_mappings.py

   # 修改为 async
   async def _generate_mapping_candidates_with_gravity(
       db: Session,
       ctx: Dict[str, int],
       api_fields: List[str],
       api_method: str,
       api_path: str,
       schema_snapshot: Dict[str, Any],
       use_ai_fallback: bool = True,
       ai_confidence_threshold: float = 0.7
   ) -> Dict[str, List[FieldMappingCandidate]]:
       """使用重心算法批量生成字段映射候选 + AI 兜底（异步版本）"""
       field_names = [field.split('.')[-1] for field in api_fields]

       try:
           from app.utils.vector_index import get_vector_manager

           vector_manager = get_vector_manager()

           if vector_manager.column_vectors is None:
               raise ValueError("Vector index not initialized")

           # ✅ 添加 await
           result = await vector_manager.batch_search_with_gravity(
               api_fields,
               top_k=20,
               use_ai_fallback=use_ai_fallback,
               ai_confidence_threshold=ai_confidence_threshold
           )

           gravity_table = result.get("gravity_table")
           vector_results = result.get("results", {})
           ai_fallback_count = result.get("ai_fallback_count", 0)

           logger.info(
               f"[{get_trace_id()}] 重心算法 + AI 兜底映射完成: "
               f"字段数={len(api_fields)}, 重心表={gravity_table}, AI兜底={ai_fallback_count}"
           )

           final_results = {}
           for api_field in api_fields:
               candidates = vector_results.get(api_field, [])

               field_candidates = []
               for cand in candidates:
                   final_score = cand.get("final_score", cand.get("score", 0.0))
                   reasons = cand.get("reasons", [])

                   if not reasons:
                       reasons = ["语义匹配"]

                   if cand.get("ai_selected"):
                       reasons.append("AI 确认选择")

                   if final_score > 0.3:
                       field_candidates.append(FieldMappingCandidate(
                           db_table=cand.get("db_table", ""),
                           db_column=cand.get("db_column", ""),
                           score=final_score,
                           reasons=reasons
                       ))

               final_results[api_field] = field_candidates[:10]

           return final_results

       except Exception as e:
           logger.warning(f"[{get_trace_id()}] 重心算法不可用，回退到单独映射: {str(e)}")

           final_results = {}
           for api_field in api_fields:
               candidates = _generate_mapping_candidates(
                   db, ctx, api_field, api_method, api_path, schema_snapshot, use_ai=False
               )
               final_results[api_field] = candidates

           return final_results

   # 修改调用处（已经是 async）
   @router.post("/field-mappings/suggest", response_model=ApiResponse)
   async def suggest_field_mappings(...):
       # ...

       if request.use_gravity_algorithm:
           for definition in definitions:
               api_fields = _extract_api_fields(...)

               if not api_fields:
                   continue

               # ✅ 添加 await
               gravity_results = await _generate_mapping_candidates_with_gravity(
                   db,
                   ctx,
                   api_fields,
                   definition.method,
                   definition.path,
                   definition.schema_snapshot or {},
                   use_ai_fallback=request.use_ai_fallback,
                   ai_confidence_threshold=request.ai_confidence_threshold
               )

               # ...

  ---

  ⚠️ 问题 2：_build_ai_prompt 方法冗余（存在）

  原问题：僵尸方法，代码中未使用

  我的代码问题：

   # app/utils/vector_index.py
   def _build_ai_prompt(...):  # ❌ 僵尸方法，实际未使用
       prompt_parts = [...]
       return "\n".join(prompt_parts)

  如何修改：删除整个方法

   # app/utils/vector_index.py

   # ❌ 删除这个方法（约 30 行代码）
   # def _build_ai_prompt(...):
   #     ...

  ---

  总结


  ┌────────────────────────┬─────────┬────────────────────────┐
  │ 问题                   │ 状态    │ 需要修改               │
  ├────────────────────────┼─────────┼────────────────────────┤
  │ asyncio.run() 嵌套调用 │ ❌ 存在 │ 将整个调用链改为全异步 │
  │ _build_ai_prompt 冗余    │ ❌ 存在 │ 删除僵尸方法           │
  └────────────────────────┴─────────┴────────────────────────┘

  关键修改点：
   1. 删除 _build_ai_prompt 方法
   2. 将 call_ai_for_ambiguous_mapping 改为 async def
   3. 将 batch_search_with_gravity 改为 async def
   4. 将 _generate_mapping_candidates_with_gravity 改为 async def
   5. 所有调用处添加 await