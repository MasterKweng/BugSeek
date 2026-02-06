"""
测试解析器输出
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.parsers import ParserFactory
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_parser():
    """测试解析器"""
    # 使用一个示例 Swagger URL (InvenTree 的 OpenAPI JSON)
    source_url = "http://127.0.0.1:1337/api-docs.json"
    source_type = "swagger"
    
    try:
        logger.info(f"测试解析器: {source_url}")
        
        # 获取文档内容
        import requests
        response = requests.get(source_url, timeout=30)
        
        # 检查是否是 HTML 页面
        content_type = response.headers.get('content-type', '')
        if 'text/html' in content_type or '<!DOCTYPE html>' in response.text:
            logger.info("检测到 HTML 页面，尝试提取 JSON URL")
            import re
            # 尝试从 HTML 中提取 JSON URL
            patterns = [
                r'url:\s*[\'"]([^\'"]+\.json)[\'"]',
                r'spec:\s*[\'"]([^\'"]+\.json)[\'"]',
            ]
            for pattern in patterns:
                match = re.search(pattern, response.text)
                if match:
                    json_url = match.group(1)
                    # 处理相对路径
                    if json_url.startswith('/'):
                        source_url = f"http://127.0.0.1:1337{json_url}"
                    else:
                        source_url = json_url
                    logger.info(f"提取到 JSON URL: {source_url}")
                    response = requests.get(source_url, timeout=30)
                    break
        
        response.raise_for_status()
        content = response.text
        
        # 解析文档
        parser = ParserFactory.create(source_type, content, source_url)
        parse_result = parser.parse()
        
        if parse_result.success:
            logger.info(f"解析成功: {len(parse_result.endpoints)} 个接口")
            
            # 检查第一个接口
            if parse_result.endpoints:
                first_endpoint = parse_result.endpoints[0]
                logger.info(f"第一个接口:")
                logger.info(f"  所有键: {list(first_endpoint.keys())}")
                logger.info(f"  完整数据: {json.dumps(first_endpoint, indent=2, ensure_ascii=False)}")
                
                # 检查关键字段
                if 'parameters' in first_endpoint:
                    logger.info(f"  ✓ 有 parameters: {len(first_endpoint['parameters'])} 个")
                else:
                    logger.warning(f"  ✗ 没有 parameters")
                
                if 'responses' in first_endpoint:
                    logger.info(f"  ✓ 有 responses")
                else:
                    logger.warning(f"  ✗ 没有 responses")
                
                if 'request_schema' in first_endpoint:
                    logger.info(f"  ✓ 有 request_schema")
                else:
                    logger.warning(f"  ✗ 没有 request_schema")
                
                if 'response_schema' in first_endpoint:
                    logger.info(f"  ✓ 有 response_schema")
                else:
                    logger.warning(f"  ✗ 没有 response_schema")
        else:
            logger.error(f"解析失败: {parse_result.error}")
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}", exc_info=True)


if __name__ == "__main__":
    test_parser()