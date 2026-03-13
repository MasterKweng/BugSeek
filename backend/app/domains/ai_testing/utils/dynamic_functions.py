"""动态随机函数库 - 用于 AI 生成的测试用例参数"""
import random
import string
import uuid
import time
from datetime import datetime
from typing import Any


class DynamicFunctions:
    """动态随机函数库"""

    @staticmethod
    def timestamp() -> int:
        """获取当前时间戳（毫秒）"""
        return int(time.time() * 1000)

    @staticmethod
    def timestamp_seconds() -> int:
        """获取当前时间戳（秒）"""
        return int(time.time())

    @staticmethod
    def random_string(length: int = 8) -> str:
        """生成随机字符串"""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    @staticmethod
    def random_int(min_val: int = 1, max_val: int = 10000) -> int:
        """生成随机整数"""
        return random.randint(min_val, max_val)

    @staticmethod
    def random_float(min_val: float = 0.0, max_val: float = 100.0, decimals: int = 2) -> float:
        """生成随机浮点数"""
        return round(random.uniform(min_val, max_val), decimals)

    @staticmethod
    def random_bool() -> bool:
        """生成随机布尔值"""
        return random.choice([True, False])

    @staticmethod
    def random_choice(choices: list) -> Any:
        """从列表中随机选择一个值"""
        return random.choice(choices)

    @staticmethod
    def random_date(start_year: int = 2020, end_year: int = 2030) -> str:
        """生成随机日期（ISO 8601 格式）"""
        start_date = datetime(start_year, 1, 1)
        end_date = datetime(end_year, 12, 31)
        random_date = start_date + (end_date - start_date) * random.random()
        return random_date.isoformat()

    @staticmethod
    def random_datetime(start_year: int = 2020, end_year: int = 2030) -> str:
        """生成随机日期时间（ISO 8601 格式）"""
        return DynamicFunctions.random_date(start_year, end_year) + 'T00:00:00Z'

    @staticmethod
    def uuid4() -> str:
        """生成 UUID v4"""
        return str(uuid.uuid4())

    @staticmethod
    def email() -> str:
        """生成随机邮箱"""
        return f"test_{DynamicFunctions.random_string(8)}@example.com"

    @staticmethod
    def phone() -> str:
        """生成随机手机号（中国格式）"""
        return f"1{random.choice([3, 5, 7, 8, 9])}{DynamicFunctions.random_string(9)}"

    @staticmethod
    def name() -> str:
        """生成随机姓名"""
        first_names = ["张", "李", "王", "刘", "陈", "杨", "赵", "黄", "周", "吴"]
        last_names = ["伟", "芳", "娜", "敏", "静", "强", "磊", "洋", "艳", "勇"]
        return random.choice(first_names) + random.choice(last_names)

    @staticmethod
    def username() -> str:
        """生成随机用户名"""
        return f"user_{DynamicFunctions.random_string(8)}"


class DynamicFunctionParser:
    """动态函数解析器"""

    # 函数映射
    FUNCTIONS = {
        "timestamp": lambda: DynamicFunctions.timestamp(),
        "timestamp_seconds": lambda: DynamicFunctions.timestamp_seconds(),
        "random_string": DynamicFunctions.random_string,
        "random_int": DynamicFunctions.random_int,
        "random_float": DynamicFunctions.random_float,
        "random_bool": lambda: DynamicFunctions.random_bool(),
        "random_choice": DynamicFunctions.random_choice,
        "random_date": DynamicFunctions.random_date,
        "random_datetime": DynamicFunctions.random_datetime,
        "uuid": lambda: DynamicFunctions.uuid4(),
        "uuid4": lambda: DynamicFunctions.uuid4(),
        "email": lambda: DynamicFunctions.email(),
        "phone": lambda: DynamicFunctions.phone(),
        "name": lambda: DynamicFunctions.name(),
        "username": lambda: DynamicFunctions.username(),
    }

    @classmethod
    def parse(cls, value: Any) -> Any:
        """
        解析包含动态函数的值

        Args:
            value: 可以是字符串、数字、布尔值、列表或字典

        Returns:
            Any: 解析后的值
        """
        if isinstance(value, str):
            return cls._parse_string(value)
        elif isinstance(value, list):
            return [cls.parse(item) for item in value]
        elif isinstance(value, dict):
            return {key: cls.parse(val) for key, val in value.items()}
        else:
            return value

    @classmethod
    def _parse_string(cls, text: str) -> str:
        """
        解析字符串中的动态函数调用

        支持的格式：
        - {{timestamp}}
        - {{random_string(8)}}
        - {{random_int(1, 100)}}
        - test_{{random_string(6)}}_suffix

        Args:
            text: 待解析的字符串

        Returns:
            str: 解析后的字符串
        """
        import re

        # 匹配 {{function_name(arg1, arg2, ...)}}
        pattern = r'\{\{(\w+)(?:\(([^)]*)\))?\}\}'

        def replace_func(match):
            func_name = match.group(1)
            args_str = match.group(2) or ""

            # 解析参数
            args = []
            if args_str.strip():
                # 简单参数解析（支持数字和字符串）
                for arg in args_str.split(','):
                    arg = arg.strip()
                    if not arg:
                        continue
                    # 尝试转换为数字
                    try:
                        if '.' in arg:
                            args.append(float(arg))
                        else:
                            args.append(int(arg))
                    except ValueError:
                        # 字符串，去除引号
                        if arg.startswith('"') and arg.endswith('"'):
                            args.append(arg[1:-1])
                        elif arg.startswith("'") and arg.endswith("'"):
                            args.append(arg[1:-1])
                        else:
                            args.append(arg)

            # 调用函数
            if func_name in cls.FUNCTIONS:
                try:
                    return str(cls.FUNCTIONS[func_name](*args))
                except Exception as e:
                    logger.warning(f"动态函数调用失败: {func_name}({args}), error: {e}")
                    return match.group(0)  # 返回原始字符串
            else:
                logger.warning(f"未知的动态函数: {func_name}")
                return match.group(0)  # 返回原始字符串

        return re.sub(pattern, replace_func, text)