"""Deep Merge 算法（V2.0 层级一 - API 资产库）
用于合并接口定义的基准数据和用例的覆写数据
"""
import copy
from typing import Dict, Any, List


class DeepMerge:
    """Deep Merge 算法实现"""

    @staticmethod
    def merge(base: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
        """
        深度合并两个字典

        Args:
            base: 基础数据（接口定义的 request_schema）
            delta: 增量数据（用例的 request_data）

        Returns:
            Dict: 合并后的数据
        """
        # 深拷贝基础数据，避免修改原数据
        result = copy.deepcopy(base)

        if not delta:
            return result

        return DeepMerge._merge_recursive(result, delta)

    @staticmethod
    def _merge_recursive(base: Any, delta: Any) -> Any:
        """
        递归合并

        Args:
            base: 基础值
            delta: 增量值

        Returns:
            Any: 合并后的值
        """
        # 如果 delta 是 null，删除该字段
        if delta is None:
            return None

        # 如果 base 是 null 或 delta 不是 dict，直接替换
        if base is None or not isinstance(delta, dict):
            return delta

        # 如果都是 dict，递归合并
        if isinstance(base, dict):
            result = copy.deepcopy(base)

            for key, value in delta.items():
                if value is None:
                    # 如果 delta 中的值为 null，删除该字段
                    result.pop(key, None)
                elif key in result:
                    # 如果 key 存在，递归合并
                    result[key] = DeepMerge._merge_recursive(result[key], value)
                else:
                    # 如果 key 不存在，直接添加
                    result[key] = value

            return result

        # 如果 base 不是 dict，直接替换
        return delta

    @staticmethod
    def merge_array(base: List[Any], delta: List[Any], mode: str = "replace") -> List[Any]:
        """
        合并数组

        Args:
            base: 基础数组
            delta: 增量数组
            mode: 合并模式
                - "replace": 完全替换
                - "append": 追加
                - "merge": 按索引合并（如果元素是 dict）

        Returns:
            List: 合并后的数组
        """
        if mode == "replace":
            return delta if delta is not None else base
        elif mode == "append":
            if delta is None:
                return base
            return base + delta
        elif mode == "merge":
            if delta is None:
                return base
            result = copy.deepcopy(base)

            # 按索引合并
            for i, item in enumerate(delta):
                if i < len(result):
                    if isinstance(result[i], dict) and isinstance(item, dict):
                        result[i] = DeepMerge.merge(result[i], item)
                    else:
                        result[i] = item
                else:
                    result.append(item)

            return result
        else:
            raise ValueError(f"不支持的数组合并模式: {mode}")

    @staticmethod
    def get_delta(base: Dict[str, Any], merged: Dict[str, Any]) -> Dict[str, Any]:
        """
        从合并后的数据中提取 delta

        Args:
            base: 基础数据
            merged: 合并后的数据

        Returns:
            Dict: 提取的 delta
        """
        delta = {}

        def extract_delta_recursive(b: Any, m: Any, path: str = ""):
            if b == m:
                return

            if isinstance(m, dict):
                if not isinstance(b, dict):
                    delta[path] = m
                    return

                # 遍历 m 的所有 key
                for key in m.keys():
                    new_path = f"{path}.{key}" if path else key

                    if key not in b:
                        # 新增的 key
                        delta[new_path] = m[key]
                    elif b[key] != m[key]:
                        # 不同的值
                        extract_delta_recursive(b[key], m[key], new_path)

            elif isinstance(m, list):
                if not isinstance(b, list) or b != m:
                    delta[path] = m
            else:
                # 基本类型不同
                delta[path] = m

        extract_delta_recursive(base, merged)

        # 将扁平的 delta 转换为嵌套结构
        return DeepMerge._flatten_to_nested(delta)

    @staticmethod
    def _flatten_to_nested(flat: Dict[str, Any]) -> Dict[str, Any]:
        """
        将扁平的 delta 转换为嵌套结构

        Args:
            flat: 扁平的 delta

        Returns:
            Dict: 嵌套的 delta
        """
        result = {}

        for path, value in flat.items():
            keys = path.split(".")
            current = result

            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            current[keys[-1]] = value

        return result