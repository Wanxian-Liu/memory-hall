#!/usr/bin/env python3
"""
Mimir Core 工具调用验证测试
============================
目标：验证Mimir Core是否能真实执行工具，而非仅在内存层面成功

测试内容：
1. Gateway write/read - 验证文件系统真实写入
2. WAL write - 验证WAL日志真实持久化
3. Plugin execute - 验证插件能真实执行代码
"""

import sys
import os
import time
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_gateway_file_io():
    """测试1: Gateway文件系统真实I/O"""
    print("\n" + "="*60)
    print("🔍 测试1: Gateway 文件系统真实I/O")
    print("="*60)
    
    from gateway.gateway import write, read
    
    # 创建唯一的测试内容
    test_content = f"VERIFICATION_TEST_{time.time()}_MIMIR_CORE"
    expected_hash = hashlib.sha256(test_content.encode()).hexdigest()[:16]
    
    print(f"📝 写入内容: {test_content[:50]}...")
    
    # 写入
    result = write(test_content, record_type="verify", user="verification", notify=False)
    
    if not result.get("success"):
        print(f"❌ Gateway write failed: {result}")
        return False
    
    record_id = result["record_id"]
    print(f"✅ 写入成功, record_id={record_id}")
    
    # 读取
    read_result = read(record_id=record_id)
    
    if read_result is None:
        print(f"❌ Gateway read failed: returned None")
        return False
    
    actual_content = read_result.get("content", "")
    actual_hash = hashlib.sha256(actual_content.encode()).hexdigest()[:16]
    
    print(f"📖 读取内容: {actual_content[:50]}...")
    
    if actual_hash != expected_hash:
        print(f"❌ 内容不匹配! expected={expected_hash}, actual={actual_hash}")
        return False
    
    print(f"✅ 内容匹配! hash={expected_hash}")
    
    # 验证文件确实存在于文件系统
    vault_dir = Path.home() / ".openclaw" / "memory-vault" / "data"
    potential_files = list(vault_dir.glob(f"{record_id[:16]}*.json"))
    
    if not potential_files:
        print(f"❌ 文件未在文件系统中创建!")
        return False
    
    print(f"✅ 文件存在于文件系统: {potential_files[0].name}")
    
    return True


def test_wal_real_persistence():
    """测试2: WAL真实持久化"""
    print("\n" + "="*60)
    print("🔍 测试2: WAL 真实持久化")
    print("="*60)
    
    from wal import wal_write, wal_delete, status
    
    # 获取测试前的WAL条目数
    before_status = status()
    before_count = before_status.get("entry_count", 0)
    print(f"📊 测试前WAL条目数: {before_count}")
    
    # 写入测试数据
    test_key = f"verify:test:wal_{time.time()}"
    test_value = {"verify": "wal", "timestamp": time.time()}
    
    entry = wal_write(test_key, test_value)
    
    if entry is None:
        print(f"❌ WAL write failed")
        return False
    
    print(f"✅ WAL write成功, entry_type={entry.entry_type}")
    
    # 验证WAL文件确实更新
    wal_dir = PROJECT_ROOT / "wal"
    wal_files = list(wal_dir.glob("wal_*.log"))
    
    if not wal_files:
        print(f"❌ WAL文件未创建!")
        return False
    
    latest_wal = max(wal_files, key=lambda p: p.stat().st_mtime)
    print(f"📁 最新WAL文件: {latest_wal.name}")
    
    # 读取WAL文件内容验证
    with open(latest_wal, 'r') as f:
        wal_content = f.read()
    
    if test_key in wal_content:
        print(f"✅ WAL文件包含测试数据")
    else:
        print(f"❌ WAL文件不包含测试数据")
        return False
    
    # 删除测试数据
    del_entry = wal_delete(test_key, {"deleted": True})
    print(f"✅ WAL delete成功, entry_type={del_entry.entry_type}")
    
    return True


def test_plugin_real_execution():
    """测试3: 插件真实执行"""
    print("\n" + "="*60)
    print("🔍 测试3: Plugin 真实执行")
    print("="*60)
    
    from plugin.plugin import PluginRegistry, PluginMetadata, PluginInterface, PluginState
    
    # 创建会执行真实代码的测试插件
    class RealExecutionPlugin(PluginInterface):
        METADATA = PluginMetadata(
            id="记忆殿堂.verify.real",
            name="真实执行验证插件",
            version="1.0.0"
        )
        
        def __init__(self):
            super().__init__()
            self._state = PluginState.UNLOADED
            self._executions = 0
            self._temp_file = PROJECT_ROOT / "verify_plugin_temp.txt"
        
        def on_load(self) -> None:
            self._state = PluginState.ACTIVE
            print("   [Plugin] on_load called")
        
        def on_enable(self) -> None:
            self._state = PluginState.ACTIVE
            print("   [Plugin] on_enable called")
        
        def on_disable(self) -> None:
            self._state = PluginState.INACTIVE
        
        def on_unload(self) -> None:
            self._state = PluginState.UNLOADED
            # 清理临时文件
            if self._temp_file.exists():
                self._temp_file.unlink()
        
        def execute(self, context: dict) -> dict:
            """真实执行：写入文件"""
            self._executions += 1
            
            # 创建一个真实的文件系统操作
            with open(self._temp_file, 'w') as f:
                f.write(f"Plugin executed at {time.time()}\n")
                f.write(f"Context: {context}\n")
            
            # 读取验证
            with open(self._temp_file, 'r') as f:
                written = f.read()
            
            return {
                "status": "executed",
                "executions": self._executions,
                "file_written": self._temp_file.name,
                "file_content": written,
                "filesystem_verified": self._temp_file.exists()
            }
    
    registry = PluginRegistry()
    
    # 注册
    try:
        registry.register(RealExecutionPlugin)
    except ValueError:
        # 可能已注册，清理后重试
        if "记忆殿堂.verify.real" in [p.id for p in registry.list_plugins()]:
            registry.unregister("记忆殿堂.verify.real")
            registry.register(RealExecutionPlugin)
    
    print("✅ 插件注册成功")
    
    # 加载
    plugin = registry.load_plugin("记忆殿堂.verify.real")
    print(f"✅ 插件加载成功, state={plugin.state}")
    
    # 执行
    result = plugin.execute({"test": "data", "timestamp": time.time()})
    print(f"✅ 插件执行完成")
    
    # 验证文件系统操作真实发生
    if not result.get("filesystem_verified"):
        print(f"❌ 插件未执行真实文件系统操作!")
        return False
    
    print(f"✅ 插件执行了真实文件系统操作")
    print(f"   - 执行次数: {result['executions']}")
    print(f"   - 文件写入: {result['file_written']}")
    print(f"   - 文件内容: {result['file_content'][:60]}...")
    
    # 清理
    registry.unload_plugin("记忆殿堂.verify.real")
    registry.unregister("记忆殿堂.verify.real")
    print(f"✅ 插件卸载并注销")
    
    return True


def test_agent_lifecycle_real():
    """测试4: Agent生命周期真实管理"""
    print("\n" + "="*60)
    print("🔍 测试4: Agent 生命周期真实管理")
    print("="*60)
    
    from agent import RoleRegistry, RoleType, AgentLifecycleManager, AgentState
    from agent.role_registry import get_global_registry, get_global_lifecycle_manager
    
    registry = get_global_registry()
    lifecycle = get_global_lifecycle_manager()
    
    # 注册测试角色
    test_role_name = f"VerifyTestRole_{int(time.time())}"
    
    from agent.role_registry import Role
    role = Role(
        name=test_role_name,
        role_type=RoleType.DEVELOPER,
        description="验证测试角色",
        capabilities=["test", "verify"]
    )
    
    registry.register(role)
    print(f"✅ 角色注册: {test_role_name}")
    
    # spawn代理
    agent = lifecycle.spawn(test_role_name)
    
    if agent is None:
        print(f"❌ Agent spawn失败!")
        return False
    
    agent_id = agent.agent_id
    print(f"✅ Agent spawn成功, id={agent_id[:20]}...")
    
    # 验证agent状态
    if agent.state != AgentState.RUNNING:
        print(f"❌ Agent状态错误: {agent.state}")
        return False
    print(f"✅ Agent状态正确: RUNNING")
    
    # heartbeat
    hb_ok = lifecycle.heartbeat(agent_id)
    if not hb_ok:
        print(f"❌ heartbeat失败!")
        return False
    print(f"✅ heartbeat成功, count={agent.heartbeat_count}")
    
    # terminate
    term_ok = lifecycle.terminate(agent_id, reason="verification_complete")
    if not term_ok:
        print(f"❌ terminate失败!")
        return False
    print(f"✅ terminate成功")
    
    if agent.state != AgentState.COMPLETED:
        print(f"❌ Agent最终状态错误: {agent.state}")
        return False
    print(f"✅ Agent最终状态: COMPLETED")
    
    # 清理
    registry.unregister(test_role_name)
    print(f"✅ 角色已注销")
    
    return True


def main():
    print("="*60)
    print("🧪 Mimir Core 工具调用验证测试")
    print("="*60)
    print(f"项目路径: {PROJECT_ROOT}")
    print(f"Python: {sys.version}")
    
    results = {}
    
    # 测试1: Gateway文件I/O
    results["gateway_file_io"] = test_gateway_file_io()
    
    # 测试2: WAL持久化
    results["wal_persistence"] = test_wal_real_persistence()
    
    # 测试3: 插件真实执行
    results["plugin_execution"] = test_plugin_real_execution()
    
    # 测试4: Agent生命周期
    results["agent_lifecycle"] = test_agent_lifecycle_real()
    
    # 汇总
    print("\n" + "="*60)
    print("📊 验证结果汇总")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        icon = "✅" if result else "❌"
        print(f"  {icon} {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 结论: Mimir Core 能够真实执行工具操作!")
        return 0
    else:
        print("\n⚠️  结论: 部分测试失败，Mimir Core 工具调用存在限制")
        return 1


if __name__ == "__main__":
    sys.exit(main())
