"""字段标准化和相似度计算工具"""
import re
from typing import List, Dict, Set
from difflib import SequenceMatcher
from app.utils.name_normalizer import normalize_name


def normalize_field_name(field_name: str) -> str:
    """
    标准化字段名
    - 转换为小写
    - 统一使用下划线分隔
    - 去除特殊字符
    """
    # 处理驼峰命名 - 在大写字母前插入下划线
    field_name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', field_name)
    # 转换为小写
    field_name = field_name.lower()
    # 只保留字母、数字和下划线
    field_name = re.sub(r'[^a-z0-9_]', '_', field_name)
    # 去除连续的下划线
    field_name = re.sub(r'_+', '_', field_name)
    # 去除首尾下划线
    field_name = field_name.strip('_')
    return field_name


def tokenize_field(field_name: str) -> List[str]:
    """
    将字段名分词
    """
    normalized = normalize_field_name(field_name)
    tokens = normalized.split('_')
    # 过滤空字符串
    tokens = [token for token in tokens if token]
    
    # 词形还原（处理常见同义词）
    synonyms = {
        'usr': 'user',
        'acct': 'account',
        'org': 'organization',
        'dept': 'department',
        'addr': 'address',
        'tel': 'tel',
        'phone': 'tel',
        'mobile': 'tel',
        'pwd': 'password',
        'passwd': 'password',
        'auth': 'authentication',
        'authn': 'authentication',
        'authz': 'authorization',
        'config': 'configuration',
        'cfg': 'configuration',
        'param': 'parameter',
        'params': 'parameter',
        'req': 'request',
        'resp': 'response',
        'cfg': 'config',
        'conf': 'config',
        'qty': 'quantity',
        'amt': 'amount',
        'ts': 'timestamp',
        'dt': 'date',
        'tm': 'time',
        'id': 'id',
        'pk': 'id',
        'key': 'id',
        'uuid': 'id',
        'guid': 'id'
    }
    
    tokens = [synonyms.get(token, token) for token in tokens]
    return tokens


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """
    计算Jaccard相似度
    """
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    
    intersection = set_a.intersection(set_b)
    union = set_a.union(set_b)
    
    return len(intersection) / len(union)


def levenshtein_similarity(str_a: str, str_b: str) -> float:
    """
    计算编辑距离相似度
    """
    if not str_a and not str_b:
        return 1.0
    if not str_a or not str_b:
        return 0.0
    
    return SequenceMatcher(None, str_a, str_b).ratio()


def field_similarity_score(api_field: str, db_column: str) -> float:
    """
    计算字段相似度评分
    """
    # 特殊情况处理
    if api_field == 'id' and db_column in ['id', '*_id']:
        return 0.9
    
    # 获取标准化字段名
    norm_api = normalize_field_name(api_field)
    norm_db = normalize_field_name(db_column)
    
    # 获取分词
    tokens_api = set(tokenize_field(api_field))
    tokens_db = set(tokenize_field(db_column))
    
    # Jaccard相似度
    jaccard_sim = jaccard_similarity(tokens_api, tokens_db)
    
    # 编辑距离相似度
    edit_sim = levenshtein_similarity(norm_api, norm_db)
    
    # 综合评分：Jaccard权重70%，编辑距离权重30%
    final_score = 0.7 * jaccard_sim + 0.3 * edit_sim
    return final_score


def table_similarity_score(api_field: str, table_name: str) -> float:
    """
    计算表名相似度评分
    """
    tokens_api = set(tokenize_field(api_field))
    normalized_table_name = normalize_name(table_name)
    tokens_table = set(tokenize_field(normalized_table_name or table_name))
    
    return jaccard_similarity(tokens_api, tokens_table)


def extract_path_params(path: str) -> List[str]:
    """
    从路径中提取参数
    """
    # 例如: /orders/{order_id}/items/{item_id} -> ['order_id', 'item_id']
    pattern = r'\{([^}]+)\}'
    params = re.findall(pattern, path)
    return params


def parse_path_segments(path: str) -> List[str]:
    """
    解析路径分段
    """
    # 例如: /orders/{order_id}/items -> ['orders', '{order_id}', 'items']
    segments = path.strip('/').split('/')
    return [seg.strip() for seg in segments]


def path_semantic_score(api_field: str, path: str, table_name: str) -> float:
    """
    计算路径语义匹配度
    """
    segments = parse_path_segments(path)
    
    # 提取路径参数
    path_params = extract_path_params(path)
    
    # 如果api_field是路径参数，计算与路径语义的匹配度
    if api_field in path_params:
        # 查找该参数在路径中的位置
        param_idx = -1
        for i, seg in enumerate(segments):
            if seg.startswith('{') and seg.endswith('}') and api_field in seg:
                param_idx = i
                break
        
        if param_idx != -1:
            # 查找最近的资源段（通常是参数前一个段）
            resource_idx = param_idx - 1
            while resource_idx >= 0:
                segment = segments[resource_idx]
                # 跳过动词段
                verb_segments = {'create', 'update', 'delete', 'get', 'list', 'batch', 
                               'export', 'import', 'login', 'logout', 'register'}
                if segment.lower() not in verb_segments:
                    # 检查路径段与表名的匹配
                    path_segment = normalize_name(segment)
                    normalized_table = normalize_name(table_name)
                    if path_segment and normalized_table and path_segment == normalized_table:
                        # 距离越近权重越高
                        distance_weight = 1.0 - min(param_idx - resource_idx, 2) * 0.1
                        return 0.8 * distance_weight
                resource_idx -= 1
    
    return 0.0


def calculate_mapping_score(
    api_field: str,
    db_column: str,
    db_table: str,
    path: str = None,
    is_primary_key: bool = False,
    type_compatible: bool = True
) -> Dict[str, float]:
    """
    计算映射评分
    """
    # 字段名相似度 (权重 30%)
    field_sim = field_similarity_score(api_field, db_column)
    field_score = field_sim * 0.30
    
    # 表名相似度 (权重 25%)
    table_sim = table_similarity_score(api_field, db_table)
    table_score = table_sim * 0.25
    
    # 路径语义匹配 (权重 20%)
    path_score = 0.0
    if path:
        path_score = path_semantic_score(api_field, path, db_table) * 0.20
    
    # 主键优先 (权重 15%)
    pk_score = 0.15 if is_primary_key else 0.05
    
    # 类型匹配 (权重 10%)
    type_score = 0.10 if type_compatible else 0.02
    
    total_score = field_score + table_score + path_score + pk_score + type_score
    
    # 限制在 [0, 1] 范围内
    total_score = min(1.0, max(0.0, total_score))
    
    return {
        "total_score": total_score,
        "field_score": field_score,
        "table_score": table_score,
        "path_score": path_score,
        "pk_score": pk_score,
        "type_score": type_score,
        "field_similarity": field_sim,
        "table_similarity": table_sim
    }
