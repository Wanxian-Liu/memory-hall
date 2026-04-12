#!/usr/bin/env python3
"""
接口契约验证脚本

验证 FileSystemAdapter 正确实现了 IMemoryVault 接口的所有方法。
"""

import sys
import os

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def verify_interface():
    """验证接口契约"""
    from interfaces.imemory_vault import IMemoryVault, SearchResult
    from interfaces.adapters.file_system_adapter import FileSystemAdapter
    from interfaces import FileSystemAdapter as ExportedAdapter
    
    print("=" * 60)
    print("接口契约验证")
    print("=" * 60)
    
    # 1. 验证SearchResult dataclass
    print("\n[1] 验证 SearchResult dataclass...")
    try:
        result = SearchResult(id="test123", score=0.95, content="test content")
        assert result.id == "test123"
        assert result.score == 0.95
        assert result.content == "test content"
        assert result.metadata is None
        print("    ✓ SearchResult dataclass 验证通过")
    except Exception as e:
        print(f"    ✗ SearchResult 验证失败: {e}")
        return False
    
    # 2. 验证 FileSystemAdapter 实现了 IMemoryVault
    print("\n[2] 验证 FileSystemAdapter 实现了 IMemoryVault...")
    try:
        assert issubclass(FileSystemAdapter, IMemoryVault)
        print("    ✓ FileSystemAdapter 是 IMemoryVault 的子类")
    except Exception as e:
        print(f"    ✗ 继承验证失败: {e}")
        return False
    
    # 3. 验证所有抽象方法都被实现
    print("\n[3] 验证所有抽象方法都被实现...")
    required_methods = ['read', 'write', 'delete', 'search', 'list_keys']
    
    for method_name in required_methods:
        method = getattr(FileSystemAdapter, method_name, None)
        if method is None:
            print(f"    ✗ 方法 {method_name} 不存在")
            return False
        
        # 检查是否是异步方法
        import asyncio
        if asyncio.iscoroutinefunction(method):
            print(f"    ✓ {method_name} (async)")
        else:
            print(f"    ✗ {method_name} 不是异步方法")
            return False
    
    # 4. 验证实例化
    print("\n[4] 验证 FileSystemAdapter 实例化...")
    try:
        adapter = FileSystemAdapter()
        assert adapter.vault_dir is not None
        print(f"    ✓ 实例化成功，vault_dir: {adapter.vault_dir}")
    except Exception as e:
        print(f"    ✗ 实例化失败: {e}")
        return False
    
    # 5. 验证导出
    print("\n[5] 验证接口导出...")
    try:
        assert ExportedAdapter is FileSystemAdapter
        print("    ✓ 接口正确导出")
    except Exception as e:
        print(f"    ✗ 导出验证失败: {e}")
        return False
    
    # 6. 验证功能（读写测试）
    print("\n[6] 验证读写功能...")
    import tempfile
    import asyncio
    
    async def test_crud():
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = FileSystemAdapter(vault_dir=tmpdir)
            
            # 写入
            write_result = await adapter.write("test_key", {"data": "test_value"})
            if not write_result:
                return False, "写入失败"
            
            # 读取
            value = await adapter.read("test_key")
            if value is None or value.get("data") != "test_value":
                return False, f"读取失败: {value}"
            
            # 列出键
            keys = await adapter.list_keys()
            if "test_key" not in keys:
                return False, f"list_keys失败: {keys}"
            
            # 删除
            delete_result = await adapter.delete("test_key")
            if not delete_result:
                return False, "删除失败"
            
            # 验证删除
            value = await adapter.read("test_key")
            if value is not None:
                return False, "删除后仍能读取"
            
            return True, "CRUD测试全部通过"
    
    try:
        success, message = asyncio.run(test_crud())
        if success:
            print(f"    ✓ {message}")
        else:
            print(f"    ✗ {message}")
            return False
    except Exception as e:
        print(f"    ✗ 功能测试异常: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("验证完成：所有测试通过 ✓")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = verify_interface()
    sys.exit(0 if success else 1)
