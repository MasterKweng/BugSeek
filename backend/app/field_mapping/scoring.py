"""
评分模块

用于字段映射的加权概率评分（优化方案V2.0 阶段3）

解决报错.md 问题：
- #5 score混用
- #6 强行加分
- #7 粗暴Stopword
- #10 高频字段
"""
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class TokenWeightCalculator:
    """词权重计算器（配置化版本，解决报错.md 问题5）"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化词权重计算器

        Args:
            config_path: 配置文件路径，默认为 config/token_weights.yaml
        """
        if config_path is None:
            # 默认配置文件路径
            config_path = str(Path(__file__).parent.parent.parent / "config" / "token_weights.yaml")

        self.common_tokens = set()
        self.specific_tokens = set()
        self._load_config(config_path)

    def _load_config(self, config_path: str) -> None:
        """
        从配置文件加载词库

        Args:
            config_path: 配置文件路径
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            self.common_tokens = set(config.get('common_tokens', []))
            self.specific_tokens = set(config.get('specific_tokens', []))

            logger.info(f"词权重配置加载完成: {len(self.common_tokens)}个通用词, "
                       f"{len(self.specific_tokens)}个专有词")

        except FileNotFoundError:
            logger.warning(f"配置文件不存在: {config_path}，使用默认值")
            self._use_default_config()
        except yaml.YAMLError as e:
            logger.warning(f"配置文件解析失败: {e}，使用默认值")
            self._use_default_config()
        except Exception as e:
            logger.warning(f"加载词权重配置失败: {e}，使用默认值")
            self._use_default_config()

    def _use_default_config(self) -> None:
        """使用默认配置"""
        self.common_tokens = {
            'id', 'name', 'code', 'type', 'status', 'time', 'date',
            'user', 'created', 'updated', 'deleted', 'description',
            'content', 'data', 'info', 'result', 'item'
        }
        self.specific_tokens = {
            'serial', 'part', 'order', 'invoice', 'purchase', 'stock',
            'customer', 'supplier', 'category', 'brand', 'model',
            'product', 'payment', 'shipment', 'warehouse', 'price'
        }

    def get_token_weight(self, token: str) -> float:
        """
        获取词权重

        Args:
            token: 词

        Returns:
            权重值：
            - 通用词: 0.2
            - 专有词: 1.0
            - 其他: 0.6
        """
        if not token:
            return 0.6

        token_lower = token.lower()

        if token_lower in self.common_tokens:
            return 0.2
        elif token_lower in self.specific_tokens:
            return 1.0
        else:
            return 0.6

    def get_token_weights_dict(self, tokens: list) -> Dict[str, float]:
        """
        批量获取词权重

        Args:
            tokens: 词列表

        Returns:
            {token: weight} 字典
        """
        return {token: self.get_token_weight(token) for token in tokens}


def calculate_final_score_v2(
    candidate: Dict[str, Any],
    field_info: Any,
    graph_context: Dict[str, Any],
    token_weight_calc: Optional[TokenWeightCalculator] = None
) -> float:
    """
    V2版本评分公式

    解决报错.md 问题：
    - #5 score混用
    - #6 强行加分
    - #7 粗暴Stopword
    - #10 高频字段

    公式：
    final_score = 0.45*向量分 + 0.25*精确分*词权重 + 0.3*图谱分

    Args:
        candidate: 候选字段信息
        field_info: 字段信息
        graph_context: 图谱上下文
        token_weight_calc: 词权重计算器（可选）

    Returns:
        最终评分 (0.0 - 1.0)
    """
    # 1. 向量基础分 (0.0 - 1.0)
    s_vector = candidate.get('score', 0.0)

    # 2. 精确匹配分 (0.0 或 1.0)
    is_exact_match = candidate.get('db_column', '').lower() == field_info.field_name.lower()
    s_exact = 1.0 if is_exact_match else 0.0

    # 3. 词权重（TF-IDF思想）
    if token_weight_calc is None:
        token_weight_calc = TokenWeightCalculator()

    token_weight = token_weight_calc.get_token_weight(field_info.field_name)

    # 4. 图谱连通分 (0.0 或 1.0)
    candidate_table = candidate.get('db_table', '')
    is_in_graph = candidate_table in graph_context.get('valid_tables', set())
    s_graph = 1.0 if is_in_graph else 0.0

    # 5. 加权求和
    final_score = (
        s_vector * 0.45 +
        s_exact * 0.25 * token_weight +
        s_graph * 0.30
    )

    # 6. 封顶
    return min(1.0, final_score)


def calculate_final_scores_batch(
    candidates: list,
    field_info: Any,
    graph_context: Dict[str, Any],
    token_weight_calc: Optional[TokenWeightCalculator] = None
) -> list:
    """
    批量计算最终评分

    Args:
        candidates: 候选字段列表
        field_info: 字段信息
        graph_context: 图谱上下文
        token_weight_calc: 词权重计算器（可选）

    Returns:
        评分后的候选列表（已排序）
    """
    if token_weight_calc is None:
        token_weight_calc = TokenWeightCalculator()

    # 计算每个候选的最终评分
    scored_candidates = []
    for cand in candidates:
        final_score = calculate_final_score_v2(
            cand,
            field_info,
            graph_context,
            token_weight_calc
        )
        cand_copy = cand.copy()
        cand_copy['final_score'] = final_score
        scored_candidates.append(cand_copy)

    # 按最终评分排序（降序）
    scored_candidates.sort(key=lambda x: x.get('final_score', 0.0), reverse=True)

    return scored_candidates


def normalize_scores(candidates: list, score_key: str = 'score') -> list:
    """
    归一化评分

    Args:
        candidates: 候选列表
        score_key: 评分键名

    Returns:
        归一化后的候选列表
    """
    if not candidates:
        return candidates

    # 找到最大和最小值
    scores = [c.get(score_key, 0.0) for c in candidates]
    max_score = max(scores) if scores else 1.0
    min_score = min(scores) if scores else 0.0

    # 避免除以零
    if max_score == min_score:
        return candidates

    # 归一化
    for cand in candidates:
        original_score = cand.get(score_key, 0.0)
        normalized = (original_score - min_score) / (max_score - min_score)
        cand[f'{score_key}_normalized'] = normalized

    return candidates


def filter_by_threshold(
    candidates: list,
    threshold: float = 0.5,
    score_key: str = 'final_score'
) -> list:
    """
    按阈值过滤候选

    Args:
        candidates: 候选列表
        threshold: 阈值
        score_key: 评分键名

    Returns:
        过滤后的候选列表
    """
    return [c for c in candidates if c.get(score_key, 0.0) >= threshold]


def get_top_candidates(
    candidates: list,
    top_n: int = 5,
    score_key: str = 'final_score'
) -> list:
    """
    获取Top N候选

    Args:
        candidates: 候选列表
        top_n: 数量
        score_key: 评分键名

    Returns:
        Top N候选列表
    """
    # 确保已排序
    sorted_candidates = sorted(
        candidates,
        key=lambda x: x.get(score_key, 0.0),
        reverse=True
    )

    return sorted_candidates[:top_n]