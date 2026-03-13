"""
验证模块

用于字段映射的语义验证（优化方案V2.0 阶段5）

解决报错.md 问题：
- AI-4：Jaccard相似度不准确
"""
import logging
from typing import Optional, Any, Dict
from app.platform.vector.vector_index import VectorIndexManager

logger = logging.getLogger(__name__)


def validate_with_vector_similarity(
    field_description: str,
    column_comment: str,
    vector_manager: VectorIndexManager,
    threshold: float = 0.75
) -> bool:
    """
    使用向量相似度验证候选（修正版，解决报错.md 问题4）

    解决报错.md 问题 #4：向量验证的性能优化

    Args:
        field_description: 字段描述
        column_comment: 列注释
        vector_manager: 向量管理器（避免重复加载）
        threshold: 相似度阈值（默认0.75）

    Returns:
        是否通过验证
    """
    if not field_description or not column_comment:
        # 没有描述，无法验证，默认通过
        return True

    # 清理文本
    field_desc_clean = field_description.strip()
    column_comment_clean = column_comment.strip()

    if not field_desc_clean or not column_comment_clean:
        return True

    try:
        # 直接使用传入的vector_manager，避免重复加载模型（解决报错.md 问题4）
        similarity = vector_manager.calculate_similarity(
            field_desc_clean,
            column_comment_clean
        )

        logger.debug(f"向量相似度: {similarity:.3f} (阈值: {threshold})")

        return similarity >= threshold

    except Exception as e:
        logger.warning(f"向量相似度计算失败: {e}，默认通过验证")
        return True


def validate_candidates_batch(
    candidates: list,
    field_description: str,
    db_schema: Dict[str, Any],
    vector_manager: VectorIndexManager,
    threshold: float = 0.75
) -> list:
    """
    批量验证候选

    Args:
        candidates: 候选列表
        field_description: 字段描述
        db_schema: 数据库结构
        vector_manager: 向量管理器
        threshold: 相似度阈值

    Returns:
        通过验证的候选列表
    """
    validated = []

    for cand in candidates:
        # 获取列注释
        column_comment = get_column_comment(
            db_schema,
            cand.get('db_table', ''),
            cand.get('db_column', '')
        )

        # 向量验证
        is_valid = validate_with_vector_similarity(
            field_description or "",
            column_comment,
            vector_manager,
            threshold
        )

        if is_valid:
            validated.append(cand)
        else:
            logger.info(f"候选 {cand.get('db_table')}.{cand.get('db_column')} "
                       f"未通过向量验证 (相似度 < {threshold})")

    return validated


def get_column_comment(
    db_schema: Dict[str, Any],
    table_name: str,
    column_name: str
) -> str:
    """
    获取列注释

    Args:
        db_schema: 数据库结构
        table_name: 表名
        column_name: 列名

    Returns:
        列注释
    """
    try:
        tables = db_schema.get('tables', {})

        # 兼容两种格式：列表格式 [{"name": "table1", "columns": [...]}, ...] 和字典格式 {"table1": {"columns": [...]}, ...}
        table_info = None
        if isinstance(tables, list):
            # 列表格式：查找匹配的表
            for table in tables:
                if isinstance(table, dict) and table.get("name") == table_name:
                    table_info = table
                    break
        elif isinstance(tables, dict) and table_name in tables:
            # 字典格式：直接获取
            table_info = tables[table_name]

        if not table_info:
            return ""

        columns = table_info.get('columns', [])

        # 兼容两种格式：列表格式 [{"name": "col1", ...}, ...] 和字典格式 {"col1": {...}, ...}
        column_info = None
        if isinstance(columns, list):
            # 列表格式：查找匹配的列
            for col in columns:
                if isinstance(col, dict) and col.get("name") == column_name:
                    column_info = col
                    break
        elif isinstance(columns, dict) and column_name in columns:
            # 字典格式：直接获取
            column_info = columns[column_name]

        if not column_info:
            return ""

        comment = column_info.get('comment', '')

        return comment or ""

    except Exception as e:
        logger.warning(f"获取列注释失败: {e}")
        return ""


def validate_with_rules(
    field_name: str,
    field_description: str,
    candidate: Dict[str, Any],
    db_schema: Dict[str, Any]
) -> tuple:
    """
    基于规则的验证（补充验证）

    Args:
        field_name: 字段名
        field_description: 字段描述
        candidate: 候选信息
        db_schema: 数据库结构

    Returns:
        (is_valid, reason)
    """
    table_name = candidate.get('db_table', '')
    column_name = candidate.get('db_column', '')

    # 规则1：精确匹配加分
    if column_name.lower() == field_name.lower():
        return True, "字段名精确匹配"

    # 规则2：包含关系
    if field_name.lower() in column_name.lower() or column_name.lower() in field_name.lower():
        return True, "字段名包含关系"

    # 规则3：获取列注释进行简单匹配
    column_comment = get_column_comment(db_schema, table_name, column_name)

    if column_comment:
        # 检查字段描述是否包含在列注释中
        if field_description and field_description.lower() in column_comment.lower():
            return True, "描述与注释匹配"

        # 检查字段名是否包含在列注释中
        if field_name.lower() in column_comment.lower():
            return True, "字段名与注释匹配"

    # 默认不通过规则验证
    return False, ""


def comprehensive_validation(
    field_name: str,
    field_description: str,
    candidate: Dict[str, Any],
    db_schema: Dict[str, Any],
    vector_manager: VectorIndexManager,
    vector_threshold: float = 0.75
) -> Dict[str, Any]:
    """
    综合验证（向量 + 规则）

    Args:
        field_name: 字段名
        field_description: 字段描述
        candidate: 候选信息
        db_schema: 数据库结构
        vector_manager: 向量管理器
        vector_threshold: 向量相似度阈值

    Returns:
        验证结果字典
    """
    table_name = candidate.get('db_table', '')
    column_name = candidate.get('db_column', '')

    # 1. 向量验证
    column_comment = get_column_comment(db_schema, table_name, column_name)
    vector_valid = validate_with_vector_similarity(
        field_description or "",
        column_comment,
        vector_manager,
        vector_threshold
    )

    # 2. 规则验证
    rule_valid, rule_reason = validate_with_rules(
        field_name,
        field_description or "",
        candidate,
        db_schema
    )

    # 3. 综合判断
    # 向量验证通过 或 规则验证通过
    is_valid = vector_valid or rule_valid

    # 4. 记录验证详情
    validation_details = {
        'vector_valid': vector_valid,
        'rule_valid': rule_valid,
        'rule_reason': rule_reason,
        'column_comment': column_comment,
        'is_valid': is_valid
    }

    return validation_details


def filter_candidates_by_validation(
    candidates: list,
    field_name: str,
    field_description: str,
    db_schema: Dict[str, Any],
    vector_manager: VectorIndexManager,
    vector_threshold: float = 0.75
) -> list:
    """
    根据验证结果过滤候选

    Args:
        candidates: 候选列表
        field_name: 字段名
        field_description: 字段描述
        db_schema: 数据库结构
        vector_manager: 向量管理器
        vector_threshold: 向量相似度阈值

    Returns:
        通过验证的候选列表（包含验证详情）
    """
    validated = []

    for cand in candidates:
        # 综合验证
        validation_result = comprehensive_validation(
            field_name,
            field_description,
            cand,
            db_schema,
            vector_manager,
            vector_threshold
        )

        # 如果通过验证，添加到结果中
        if validation_result['is_valid']:
            cand_copy = cand.copy()
            cand_copy['validation'] = validation_result
            validated.append(cand_copy)
        else:
            logger.debug(f"候选 {cand.get('db_table')}.{cand.get('db_column')} "
                        f"未通过综合验证")

    return validated
