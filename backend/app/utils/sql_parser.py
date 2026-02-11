"""
SQL解析器工具，用于将SQL文件解析为系统内部使用的数据库结构格式
遵循后端代码规范：数据强一致性、可观测性
"""
import re
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SQLParser:
    """
    SQL解析器
    将SQL DDL语句解析为JSON格式的数据库结构定义
    
    支持的语法：
    - CREATE TABLE
    - ALTER TABLE (ADD/MODIFY/DROP COLUMN)
    - CREATE INDEX
    - 单行注释（--）和多行注释（/* */）
    - 多语句分隔（;）
    """
    
    def __init__(self):
        # 编译正则表达式以提高性能
        self.table_pattern = re.compile(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:`?"?(\w+)"?`?\.)?`?"?(\w+)"?`?\s*\(\s*(.*?)\s*\)',
            re.IGNORECASE | re.DOTALL
        )
        self.column_pattern = re.compile(
            r'`?"?(\w+)"?`?\s+(\w+(?:\s*\([^)]+\))?(?:\s+\w+)*)',
            re.IGNORECASE
        )
        self.constraint_pattern = re.compile(
            r'(CONSTRAINT\s+\w+\s+)?(PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK)\s*\([^)]+\)',
            re.IGNORECASE
        )
        self.comment_pattern = re.compile(
            r'COMMENT\s+\'([^\']*)\'',
            re.IGNORECASE
        )
        # ALTER TABLE 模式
        self.alter_table_pattern = re.compile(
            r'ALTER\s+TABLE\s+(?:`?"?(\w+)"?`?\.)?`?"?(\w+)"?`?\s+(\w+)',
            re.IGNORECASE
        )
        self.alter_add_column_pattern = re.compile(
            r'ADD\s+(?:COLUMN\s+)?`?"?(\w+)"?`?\s+(\w+(?:\s*\([^)]+\))?)',
            re.IGNORECASE
        )
        self.alter_drop_column_pattern = re.compile(
            r'DROP\s+(?:COLUMN\s+)?`?"?(\w+)"?`?',
            re.IGNORECASE
        )
        self.alter_modify_column_pattern = re.compile(
            r'MODIFY\s+(?:COLUMN\s+)?`?"?(\w+)"?`?\s+(\w+(?:\s*\([^)]+\))?)',
            re.IGNORECASE
        )
        # CREATE INDEX 模式
        self.create_index_pattern = re.compile(
            r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:`?"?(\w+)"?`?\s+ON\s+)?(?:`?"?(\w+)"?`?\.)?`?"?(\w+)"?`?\s*\(\s*([^)]+)\s*\)',
            re.IGNORECASE
        )
    
    def parse(self, sql_content: str) -> Dict[str, Any]:
        """
        解析SQL内容为结构化数据
        
        Args:
            sql_content: SQL文件内容
            
        Returns:
            Dict: 解析后的数据库结构
        """
        logger.info("开始解析SQL内容")
        
        # 初始化结果结构
        result = {
            "tables": [],
            "indexes": [],
            "warnings": []
        }
        
        # 移除注释
        sql_content = self._remove_comments(sql_content)
        
        # 分割SQL语句
        statements = self._split_statements(sql_content)
        
        logger.info(f"SQL内容分割为 {len(statements)} 个语句")
        
        # 解析每个语句
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
            
            try:
                # 检查是否是CREATE TABLE
                if stmt.upper().startswith('CREATE TABLE'):
                    table_matches = self.table_pattern.findall(stmt)
                    for match in table_matches:
                        schema_name, table_name, table_def = match
                        table_info = self._parse_table(table_name, table_def)
                        if table_info:
                            result["tables"].append(table_info)
                
                # 检查是否是ALTER TABLE
                elif stmt.upper().startswith('ALTER TABLE'):
                    alter_result = self._parse_alter_table(stmt)
                    if alter_result:
                        if alter_result.get("warning"):
                            result["warnings"].append(alter_result["warning"])
                        else:
                            self._apply_alter_to_table(result["tables"], alter_result)
                
                # 检查是否是CREATE INDEX
                elif stmt.upper().startswith('CREATE INDEX') or stmt.upper().startswith('CREATE UNIQUE INDEX'):
                    index_info = self._parse_create_index(stmt)
                    if index_info:
                        result["indexes"].append(index_info)
                
                # 跳过其他不支持的语句
                else:
                    result["warnings"].append(f"跳过不支持的语句: {stmt[:50]}...")
            
            except Exception as e:
                logger.warning(f"解析语句时出错: {stmt[:50]}..., 错误: {str(e)}")
                result["warnings"].append(f"解析语句失败: {str(e)}")
        
        logger.info(f"SQL解析完成，共解析出 {len(result['tables'])} 个表, {len(result['indexes'])} 个索引")
        return result
    
    def _remove_comments(self, sql: str) -> str:
        """
        移除SQL注释
        
        Args:
            sql: SQL内容
            
        Returns:
            str: 移除注释后的SQL
        """
        # 移除多行注释 /* */
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        
        # 移除单行注释 --
        lines = sql.split('\n')
        cleaned_lines = []
        for line in lines:
            # 移除行内 -- 注释
            line = re.sub(r'--.*$', '', line)
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _split_statements(self, sql: str) -> List[str]:
        """
        分割多个SQL语句
        
        Args:
            sql: SQL内容
            
        Returns:
            List[str]: 分割后的语句列表
        """
        statements = []
        current_stmt = ""
        paren_count = 0
        in_string = False
        string_char = None
        i = 0
        
        while i < len(sql):
            char = sql[i]
            
            # 处理字符串
            if char in ('"', "'", '`') and (i == 0 or sql[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
            
            # 不在字符串中时处理特殊字符
            if not in_string:
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                elif char == ';' and paren_count == 0:
                    # 遇到分号且不在括号内，说明是语句分隔符
                    if current_stmt.strip():
                        statements.append(current_stmt.strip())
                    current_stmt = ""
                    i += 1
                    continue
            
            current_stmt += char
            i += 1
        
        # 添加最后一个语句
        if current_stmt.strip():
            statements.append(current_stmt.strip())
        
        return statements
    
    def _normalize_data_type(self, type_str: str) -> str:
        """
        标准化数据类型
        
        Args:
            type_str: 原始数据类型
            
        Returns:
            str: 标准化后的类型
        """
        type_str = type_str.upper()
        
        # 移除长度限制，保留类型名称
        type_str = re.sub(r'\([^)]+\)', '', type_str)
        
        # 统一类型名称
        type_mapping = {
            'INT': 'integer',
            'INTEGER': 'integer',
            'BIGINT': 'bigint',
            'SMALLINT': 'smallint',
            'TINYINT': 'tinyint',
            'VARCHAR': 'string',
            'CHAR': 'string',
            'TEXT': 'text',
            'LONGTEXT': 'text',
            'MEDIUMTEXT': 'text',
            'FLOAT': 'float',
            'DOUBLE': 'double',
            'DECIMAL': 'decimal',
            'BOOLEAN': 'boolean',
            'BOOL': 'boolean',
            'DATE': 'date',
            'DATETIME': 'datetime',
            'TIMESTAMP': 'timestamp',
            'TIME': 'time',
            'JSON': 'json',
            'BLOB': 'blob',
            'BINARY': 'binary',
        }
        
        return type_mapping.get(type_str, type_str.lower())
    
    def _parse_table(self, table_name: str, table_def: str) -> Optional[Dict[str, Any]]:
        """
        解析单个表的定义
        
        Args:
            table_name: 表名
            table_def: 表定义内容
            
        Returns:
            Dict: 表结构信息
        """
        try:
            table_info = {
                "name": table_name,
                "columns": [],
                "indexes": [],
                "constraints": []
            }
            
            # 分割表定义中的各个部分，处理可能的嵌套括号
            parts = self._split_table_definition(table_def)
            
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                
                # 检查是否是列定义
                if self._is_column_definition(part):
                    column_info = self._parse_column(part)
                    if column_info:
                        table_info["columns"].append(column_info)
                
                # 检查是否是约束定义
                elif self._is_constraint_definition(part):
                    constraint_info = self._parse_constraint(part)
                    if constraint_info:
                        table_info["constraints"].append(constraint_info)
            
            return table_info
        except Exception as e:
            logger.error(f"解析表 {table_name} 时出错: {str(e)}")
            return None
    
    def _split_table_definition(self, table_def: str) -> List[str]:
        """
        将表定义分割为独立的列和约束定义
        
        Args:
            table_def: 表定义内容
            
        Returns:
            List[str]: 分割后的定义列表
        """
        parts = []
        current_part = ""
        paren_count = 0
        i = 0
        
        while i < len(table_def):
            char = table_def[i]
            
            if char == '(':
                paren_count += 1
                current_part += char
            elif char == ')':
                paren_count -= 1
                current_part += char
            elif char == ',' and paren_count == 0:
                # 遇到逗号且不在括号内，说明是分隔符
                parts.append(current_part.strip())
                current_part = ""
            else:
                current_part += char
            
            i += 1
        
        # 添加最后一部分
        if current_part.strip():
            parts.append(current_part.strip())
        
        return parts
    
    def _is_column_definition(self, part: str) -> bool:
        """
        判断是否为列定义
        
        Args:
            part: 表定义的一部分
            
        Returns:
            bool: 是否为列定义
        """
        # 简单判断：以列名开头，后面跟数据类型
        return bool(self.column_pattern.match(part.strip()))
    
    def _is_constraint_definition(self, part: str) -> bool:
        """
        判断是否为约束定义
        
        Args:
            part: 表定义的一部分
            
        Returns:
            bool: 是否为约束定义
        """
        return bool(self.constraint_pattern.search(part.strip()))
    
    def _parse_column(self, column_def: str) -> Optional[Dict[str, Any]]:
        """
        解析列定义
        
        Args:
            column_def: 列定义字符串
            
        Returns:
            Dict: 列信息
        """
        try:
            # 匹配列名和类型
            match = self.column_pattern.match(column_def.strip())
            if not match:
                return None
            
            column_name, column_type = match.groups()
            
            # 标准化数据类型
            normalized_type = self._normalize_data_type(column_type)
            
            # 检查列属性
            column_info = {
                "name": column_name,
                "type": normalized_type,
                "nullable": True,  # 默认可为空
                "primary_key": False,
                "foreign_key": False,
                "unique": False,
                "default": None,
                "comment": None
            }
            
            # 检查是否有NOT NULL约束
            if 'NOT NULL' in column_def.upper():
                column_info["nullable"] = False
            
            # 检查是否有PRIMARY KEY约束
            if 'PRIMARY KEY' in column_def.upper():
                column_info["primary_key"] = True
            
            # 检查是否有UNIQUE约束
            if 'UNIQUE' in column_def.upper():
                column_info["unique"] = True
            
            # 检查是否有默认值
            default_match = re.search(r'DEFAULT\s+(.+?)(?:\s|,|$)', column_def, re.IGNORECASE)
            if default_match:
                column_info["default"] = default_match.group(1).strip()
            
            # 检查是否有注释
            comment_match = self.comment_pattern.search(column_def)
            if comment_match:
                column_info["comment"] = comment_match.group(1)
            
            return column_info
        except Exception as e:
            logger.warning(f"解析列定义时出错: {column_def}, 错误: {str(e)}")
            return None
    
    def _parse_alter_table(self, alter_stmt: str) -> Optional[Dict[str, Any]]:
        """
        解析ALTER TABLE语句
        
        支持的操作：
        - ADD COLUMN
        - DROP COLUMN
        - MODIFY COLUMN
        
        Args:
            alter_stmt: ALTER TABLE语句
            
        Returns:
            Dict: ALTER操作信息
        """
        try:
            # 提取表名和操作类型
            match = self.alter_table_pattern.match(alter_stmt.strip())
            if not match:
                return None
            
            schema_name, table_name, action = match.groups()
            
            alter_info = {
                "table_name": table_name,
                "action": action.upper(),
                "column_name": None,
                "column_def": None
            }
            
            # 解析不同的ALTER操作
            if action.upper() == 'ADD':
                # ADD COLUMN
                add_match = self.alter_add_column_pattern.search(alter_stmt)
                if add_match:
                    alter_info["column_name"] = add_match.group(1)
                    alter_info["column_def"] = add_match.group(2)
                else:
                    return {"warning": f"不支持的ADD操作: {alter_stmt[:50]}..."}
            
            elif action.upper() == 'DROP':
                # DROP COLUMN
                drop_match = self.alter_drop_column_pattern.search(alter_stmt)
                if drop_match:
                    alter_info["column_name"] = drop_match.group(1)
                else:
                    return {"warning": f"不支持的DROP操作: {alter_stmt[:50]}..."}
            
            elif action.upper() == 'MODIFY':
                # MODIFY COLUMN
                modify_match = self.alter_modify_column_pattern.search(alter_stmt)
                if modify_match:
                    alter_info["column_name"] = modify_match.group(1)
                    alter_info["column_def"] = modify_match.group(2)
                else:
                    return {"warning": f"不支持的MODIFY操作: {alter_stmt[:50]}..."}
            
            else:
                return {"warning": f"不支持的ALTER操作: {action} ({alter_stmt[:50]}...)"}
            
            return alter_info
        
        except Exception as e:
            logger.warning(f"解析ALTER TABLE时出错: {alter_stmt[:50]}..., 错误: {str(e)}")
            return {"warning": f"解析ALTER TABLE失败: {str(e)}"}
    
    def _apply_alter_to_table(self, tables: List[Dict[str, Any]], alter_info: Dict[str, Any]) -> bool:
        """
        将ALTER操作应用到表结构
        
        Args:
            tables: 表列表
            alter_info: ALTER操作信息
            
        Returns:
            bool: 是否成功应用
        """
        if "warning" in alter_info:
            return False
        
        table_name = alter_info["table_name"]
        action = alter_info["action"]
        column_name = alter_info["column_name"]
        
        # 查找目标表
        target_table = None
        for table in tables:
            if table["name"] == table_name:
                target_table = table
                break
        
        if not target_table:
            logger.warning(f"ALTER TABLE失败: 表 {table_name} 不存在")
            return False
        
        if action == 'ADD':
            # 添加列
            column_info = {
                "name": column_name,
                "type": self._normalize_data_type(alter_info["column_def"]),
                "nullable": True,
                "primary_key": False,
                "foreign_key": False,
                "unique": False,
                "default": None,
                "comment": None
            }
            target_table["columns"].append(column_info)
            logger.info(f"添加列: {table_name}.{column_name}")
        
        elif action == 'DROP':
            # 删除列
            target_table["columns"] = [
                col for col in target_table["columns"]
                if col["name"] != column_name
            ]
            logger.info(f"删除列: {table_name}.{column_name}")
        
        elif action == 'MODIFY':
            # 修改列
            for col in target_table["columns"]:
                if col["name"] == column_name:
                    col["type"] = self._normalize_data_type(alter_info["column_def"])
                    logger.info(f"修改列: {table_name}.{column_name}")
                    break
        
        return True
    
    def _parse_create_index(self, index_stmt: str) -> Optional[Dict[str, Any]]:
        """
        解析CREATE INDEX语句
        
        Args:
            index_stmt: CREATE INDEX语句
            
        Returns:
            Dict: 索引信息
        """
        try:
            match = self.create_index_pattern.match(index_stmt.strip())
            if not match:
                return None
            
            index_name, schema_name, table_name, columns = match
            
            index_info = {
                "name": index_name or f"idx_{table_name}_{hash(columns) % 1000}",
                "table_name": table_name,
                "columns": [col.strip().strip('`"') for col in columns.split(',')],
                "unique": 'UNIQUE' in index_stmt.upper()
            }
            
            return index_info
        
        except Exception as e:
            logger.warning(f"解析CREATE INDEX时出错: {index_stmt[:50]}..., 错误: {str(e)}")
            return None
    
    def _parse_constraint(self, constraint_def: str) -> Optional[Dict[str, Any]]:
        """
        解析约束定义
        
        Args:
            constraint_def: 约束定义字符串
            
        Returns:
            Dict: 约束信息
        """
        try:
            # 检查约束类型
            if 'PRIMARY KEY' in constraint_def.upper():
                return {
                    "type": "PRIMARY KEY",
                    "definition": constraint_def.strip()
                }
            elif 'FOREIGN KEY' in constraint_def.upper():
                return {
                    "type": "FOREIGN KEY",
                    "definition": constraint_def.strip()
                }
            elif 'UNIQUE' in constraint_def.upper():
                return {
                    "type": "UNIQUE",
                    "definition": constraint_def.strip()
                }
            elif 'CHECK' in constraint_def.upper():
                return {
                    "type": "CHECK",
                    "definition": constraint_def.strip()
                }
            else:
                # 尝试从定义中提取约束类型
                constraint_match = self.constraint_pattern.search(constraint_def)
                if constraint_match:
                    constraint_type = constraint_match.group(2)
                    return {
                        "type": constraint_type.upper(),
                        "definition": constraint_def.strip()
                    }
        
            return None
        except Exception as e:
            logger.warning(f"解析约束定义时出错: {constraint_def}, 错误: {str(e)}")
            return None


def parse_sql_file(sql_content: str) -> Dict[str, Any]:
    """
    解析SQL文件内容为结构化数据
    
    Args:
        sql_content: SQL文件内容
        
    Returns:
        Dict: 解析后的数据库结构
    """
    parser = SQLParser()
    return parser.parse(sql_content)