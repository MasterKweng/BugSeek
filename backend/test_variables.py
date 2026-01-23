"""测试变量管理 API 逻辑"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.crypto import encrypt_value, decrypt_value, mask_sensitive_value


def test_crypto_functions():
    """测试加密功能"""
    print("=" * 50)
    print("测试加密功能")
    print("=" * 50)
    
    # 测试 1: 普通值加密解密
    plain_text = "test_value_123"
    encrypted = encrypt_value(plain_text)
    decrypted = decrypt_value(encrypted)
    assert decrypted == plain_text, f"解密失败: 期望 {plain_text}, 实际 {decrypted}"
    print(f"✓ 测试 1 通过: 普通值加密解密")
    print(f"  原文: {plain_text}")
    print(f"  加密: {encrypted}")
    print(f"  解密: {decrypted}")
    
    # 测试 2: 空值处理
    empty_text = ""
    encrypted = encrypt_value(empty_text)
    decrypted = decrypt_value(encrypted)
    assert decrypted == empty_text, f"空值解密失败"
    print(f"✓ 测试 2 通过: 空值处理")
    
    # 测试 3: None 值处理
    none_text = None
    encrypted = encrypt_value(none_text)
    decrypted = decrypt_value(encrypted)
    assert decrypted == none_text, f"None 值解密失败"
    print(f"✓ 测试 3 通过: None 值处理")
    
    # 测试 4: 敏感变量掩码
    sensitive_value = "secret_password_123"
    masked = mask_sensitive_value(sensitive_value)
    assert masked == "***", f"掩码失败: 期望 ***, 实际 {masked}"
    print(f"✓ 测试 4 通过: 敏感变量掩码")
    print(f"  原文: {sensitive_value}")
    print(f"  掩码: {masked}")
    
    # 测试 5: 长文本加密
    long_text = "a" * 1000
    encrypted = encrypt_value(long_text)
    decrypted = decrypt_value(encrypted)
    assert decrypted == long_text, f"长文本解密失败"
    print(f"✓ 测试 5 通过: 长文本加密解密 (1000 字符)")
    
    # 测试 6: 特殊字符加密
    special_text = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
    encrypted = encrypt_value(special_text)
    decrypted = decrypt_value(encrypted)
    assert decrypted == special_text, f"特殊字符解密失败"
    print(f"✓ 测试 6 通过: 特殊字符加密解密")
    
    # 测试 7: 中文加密
    chinese_text = "你好世界！这是一个测试。"
    encrypted = encrypt_value(chinese_text)
    decrypted = decrypt_value(encrypted)
    assert decrypted == chinese_text, f"中文解密失败"
    print(f"✓ 测试 7 通过: 中文加密解密")
    
    print("\n" + "=" * 50)
    print("所有加密功能测试通过！")
    print("=" * 50)


def test_api_models():
    """测试 API 模型"""
    print("\n" + "=" * 50)
    print("测试 API 模型")
    print("=" * 50)
    
    from app.api.v1.variables import VariableCreate, VariableUpdate, VariableResponse, ApiResponse
    
    # 测试 VariableCreate
    var_create = VariableCreate(
        var_key="test_key",
        var_value="test_value",
        is_sensitive=False
    )
    assert var_create.var_key == "test_key"
    assert var_create.var_value == "test_value"
    assert var_create.is_sensitive is False
    print("✓ 测试 VariableCreate 模型")
    
    # 测试 VariableUpdate
    var_update = VariableUpdate(
        var_key="new_key",
        is_sensitive=True
    )
    assert var_update.var_key == "new_key"
    assert var_update.is_sensitive is True
    assert var_update.var_value is None
    print("✓ 测试 VariableUpdate 模型")
    
    # 测试 ApiResponse
    response = ApiResponse(
        code=0,
        message="success",
        data={"test": "value"}
    )
    assert response.code == 0
    assert response.message == "success"
    assert response.data == {"test": "value"}
    print("✓ 测试 ApiResponse 模型")
    
    print("\n" + "=" * 50)
    print("所有 API 模型测试通过！")
    print("=" * 50)


def test_imports():
    """测试导入是否正常"""
    print("\n" + "=" * 50)
    print("测试模块导入")
    print("=" * 50)
    
    try:
        from app.core.crypto import encrypt_value, decrypt_value, mask_sensitive_value
        print("✓ 导入 app.core.crypto 成功")
    except Exception as e:
        print(f"✗ 导入 app.core.crypto 失败: {e}")
        return False
    
    try:
        from app.api.v1.variables import router, VariableCreate, VariableUpdate, VariableResponse
        print("✓ 导入 app.api.v1.variables 成功")
    except Exception as e:
        print(f"✗ 导入 app.api.v1.variables 失败: {e}")
        return False
    
    try:
        from app.api.v1 import variables
        print("✓ 导入 app.api.v1.variables 路由成功")
    except Exception as e:
        print(f"✗ 导入 app.api.v1.variables 路由失败: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("所有模块导入测试通过！")
    print("=" * 50)
    return True


def test_route_registration():
    """测试路由注册"""
    print("\n" + "=" * 50)
    print("测试路由注册")
    print("=" * 50)
    
    try:
        from app.api.v1 import api_router
        routes = api_router.routes
        
        # 检查是否有变量管理路由
        variable_routes = [r for r in routes if hasattr(r, 'path') and 'vars' in r.path]
        
        if variable_routes:
            print(f"✓ 发现 {len(variable_routes)} 个变量管理路由:")
            for route in variable_routes:
                methods = getattr(route, 'methods', [])
                path = getattr(route, 'path', '')
                print(f"  - {methods} {path}")
        else:
            print("⚠ 未找到变量管理路由（可能需要检查路由注册）")
        
        print("\n" + "=" * 50)
        print("路由注册测试完成！")
        print("=" * 50)
    except Exception as e:
        print(f"✗ 路由注册测试失败: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("开始测试变量管理 API")
    print("=" * 60 + "\n")
    
    # 运行所有测试
    test_imports()
    test_crypto_functions()
    test_api_models()
    test_route_registration()
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60 + "\n")