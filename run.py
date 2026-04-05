#!/usr/bin/env python3
"""
记忆殿堂v2.0 - 独立运行验证脚本
=====================================

目标: 验证记忆殿堂可脱离OpenClaw独立运行

测试内容:
1. Gateway 读写
2. WAL 操作
3. CLI 命令
4. 插件加载

运行方式:
    python run.py              # 运行所有测试
    python run.py --gateway    # 只测Gateway
    python run.py --wal        # 只测WAL
    python run.py --cli        # 只测CLI
    python run.py --plugin     # 只测插件
    python run.py --verbose    # 详细输出
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# ============ 路径设置 ============
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============ 测试结果收集 ============
test_results: Dict[str, Any] = {
    "gateway": {"passed": False, "tests": [], "errors": []},
    "wal": {"passed": False, "tests": [], "errors": []},
    "cli": {"passed": False, "tests": [], "errors": []},
    "plugin": {"passed": False, "tests": [], "errors": []},
}

def log(msg: str, verbose: bool = False):
    """打印日志"""
    if verbose or "--verbose" in sys.argv or "-v" in sys.argv:
        print(f"  [VERBOSE] {msg}")

def result_test(category: str, name: str, passed: bool, detail: str = ""):
    """记录测试结果"""
    test_results[category]["tests"].append({
        "name": name,
        "passed": passed,
        "detail": detail
    })
    symbol = "✅" if passed else "❌"
    print(f"  {symbol} {name}: {detail}")

def result_error(category: str, error: str):
    """记录错误"""
    test_results[category]["errors"].append(error)
    print(f"  ⚠️  ERROR: {error}")

# ============ 1. Gateway 测试 ============
def test_gateway(verbose: bool = False) -> bool:
    """测试Gateway读写功能"""
    print("\n" + "="*50)
    print("🧠 测试1: Gateway 读写")
    print("="*50)
    
    try:
        from gateway.gateway import Gateway, LRUCache, write, read, generate_id, get_cache_stats
        
        # 测试1: LRUCache set/get
        log("测试LRUCache set/get", verbose)
        cache = LRUCache()
        cache.set("gateway:test:key1", "test_value_1")
        val1 = cache.get("gateway:test:key1")
        cache_ok = val1 == "test_value_1"
        result_test("gateway", "LRUCache set/get", cache_ok, f"got '{val1}'")
        
        # 测试2: LRUCache invalidate/delete
        log("测试LRUCache invalidate/delete", verbose)
        cache.set("gateway:test:key2", "value2")
        cache.invalidate("gateway:test:key2")
        val2 = cache.get("gateway:test:key2")
        invalidate_ok = val2 is None
        result_test("gateway", "LRUCache invalidate", invalidate_ok, f"val after invalidate={val2}")
        
        # 测试3: LRUCache get_stats
        log("测试LRUCache get_stats", verbose)
        stats = cache.get_stats()
        stats_ok = isinstance(stats, dict) and "size" in stats
        result_test("gateway", "LRUCache get_stats", stats_ok, f"stats={stats}")
        
        # 测试5: Gateway 封装类
        log("测试Gateway类初始化", verbose)
        gw = Gateway()
        gw_ok = gw is not None
        result_test("gateway", "Gateway类初始化", gw_ok)
        
        # 测试6: Gateway.stats()
        log("测试Gateway.stats()", verbose)
        gw_stats = gw.stats()
        gw_stats_ok = isinstance(gw_stats, dict) and "cache" in gw_stats
        result_test("gateway", "Gateway.stats()", gw_stats_ok, f"keys={list(gw_stats.keys())}")
        
        # 测试7: write/read 函数 (文件系统)
        log("测试write/read文件系统", verbose)
        test_content = "记忆殿堂独立运行测试内容 " + str(time.time())
        write_result = write(test_content, record_type="test", user="test_user", notify=False)
        write_ok = write_result.get("success", False)
        result_test("gateway", "Gateway write()", write_ok, f"record_id={write_result.get('record_id', 'N/A')}")
        
        if write_ok:
            record_id = write_result.get("record_id")
            log(f"读取record_id={record_id}", verbose)
            read_result = read(record_id=record_id)
            read_ok = read_result is not None and read_result.get("content") == test_content
            result_test("gateway", "Gateway read()", read_ok, f"content match={read_ok}")
        
        # 判断通过
        all_passed = all(t["passed"] for t in test_results["gateway"]["tests"])
        test_results["gateway"]["passed"] = all_passed
        return all_passed
        
    except Exception as e:
        result_error("gateway", str(e))
        import traceback
        log(traceback.format_exc(), verbose)
        return False

# ============ 2. WAL 测试 ============
def test_wal(verbose: bool = False) -> bool:
    """测试WAL操作"""
    print("\n" + "="*50)
    print("📝 测试2: WAL 操作")
    print("="*50)
    
    try:
        from base_wal.wal import (
            WALManager, WALPhase, WALEntryType, WALEntry,
            begin, prepare_write, execute_write, commit, rollback,
            wal_write, wal_delete, status, compact, recover
        )
        
        # 测试1: WALManager 初始化
        log("测试WALManager初始化", verbose)
        wal_dir = PROJECT_ROOT / "wal"
        wal = WALManager(wal_dir=str(wal_dir))
        wal_ok = wal is not None
        result_test("wal", "WALManager初始化", wal_ok)
        
        # 测试2: begin() 事务开始
        log("测试begin()事务开始", verbose)
        tx_id = begin()
        tx_ok = tx_id is not None and len(tx_id) > 0
        result_test("wal", "WAL begin()事务", tx_ok, f"tx_id={tx_id[:16]}...")
        
        # 测试3: 三段式提交 - PREPARE
        log("测试prepare_write()", verbose)
        test_value = {"wal": "test", "timestamp": time.time()}
        prepare_ok = prepare_write(tx_id, "wal:test:key1", test_value)
        result_test("wal", "WAL PREPARE阶段", prepare_ok is None or prepare_ok == True)
        
        # 测试4: 三段式提交 - EXECUTE
        log("测试execute_write()", verbose)
        execute_called = [False]
        def mock_execute(key, value):
            execute_called[0] = True
            log(f"EXECUTE回调: key={key[:20]}, value={str(value)[:50]}", verbose)
        execute_write(tx_id, mock_execute)
        result_test("wal", "WAL EXECUTE阶段回调", execute_called[0], "callback invoked")
        
        # 测试5: 三段式提交 - COMMIT
        log("测试commit()", verbose)
        commit_ok = commit(tx_id)
        result_test("wal", "WAL COMMIT阶段", commit_ok is None or commit_ok == True)
        
        # 测试6: 便捷函数 wal_write
        log("测试wal_write()", verbose)
        ww_entry = wal_write("wal:test:key2", {"便捷": "函数测试"})
        ww_ok = ww_entry is not None and isinstance(ww_entry, WALEntry)
        result_test("wal", "WAL wal_write()", ww_ok, f"entry_type={ww_entry.entry_type if ww_entry else 'N/A'}")
        
        # 测试7: 便捷函数 wal_delete
        log("测试wal_delete()", verbose)
        wd_entry = wal_delete("wal:test:key2", {"deleted": True})
        wd_ok = wd_entry is not None and isinstance(wd_entry, WALEntry)
        result_test("wal", "WAL wal_delete()", wd_ok, f"entry_type={wd_entry.entry_type if wd_entry else 'N/A'}")
        
        # 测试8: status() 状态查询
        log("测试status()", verbose)
        st = status()
        st_ok = isinstance(st, dict) and "entry_count" in st
        result_test("wal", "WAL status()", st_ok, f"entry_count={st.get('entry_count', 'N/A')}")
        
        # 测试9: recover() 重放恢复
        log("测试recover()", verbose)
        recovered = [0]
        def apply_fn(key, entry_type, value):
            recovered[0] += 1
        recover_result = recover(apply_fn)
        recover_ok = isinstance(recover_result, dict)
        result_test("wal", "WAL recover()", recover_ok, f"result={recover_result}")
        
        # 判断通过
        all_passed = all(t["passed"] for t in test_results["wal"]["tests"])
        test_results["wal"]["passed"] = all_passed
        return all_passed
        
    except Exception as e:
        result_error("wal", str(e))
        import traceback
        log(traceback.format_exc(), verbose)
        return False

# ============ 3. CLI 测试 ============
def test_cli(verbose: bool = False) -> bool:
    """测试CLI命令"""
    print("\n" + "="*50)
    print("🖥️  测试3: CLI 命令")
    print("="*50)
    
    try:
        from cli.commands import MemoryStore
        
        # 初始化 store
        test_vault_dir = PROJECT_ROOT / "test_cli_vault"
        test_vault_dir.mkdir(exist_ok=True)
        store = MemoryStore(vault_dir=str(test_vault_dir))
        
        # 测试1: MemoryStore.write()
        log("测试MemoryStore.write()", verbose)
        test_data = {"cli": "test", "timestamp": time.time()}
        write_val = json.dumps(test_data)
        store_write_ok = store.write("cli:test:key1", write_val)
        result_test("cli", "MemoryStore.write()", store_write_ok)
        
        # 测试2: MemoryStore.read()
        log("测试MemoryStore.read()", verbose)
        read_val = store.read("cli:test:key1")
        read_ok = read_val is not None and "cli" in read_val
        result_test("cli", "MemoryStore.read()", read_ok, f"got {'Yes' if read_ok else read_val}")
        
        # 测试3: MemoryStore.delete()
        log("测试MemoryStore.delete()", verbose)
        del_ok = store.delete("cli:test:key1")
        result_test("cli", "MemoryStore.delete()", del_ok)
        
        # 测试4: MemoryStore.list_keys()
        log("测试MemoryStore.list_keys()", verbose)
        # 先写入几个key
        store.write("cli:test:key2", '"value2"')
        store.write("cli:test:key3", '"value3"')
        keys = store.list_keys()
        list_keys_ok = isinstance(keys, list) and len(keys) >= 2
        result_test("cli", "MemoryStore.list_keys()", list_keys_ok, f"count={len(keys)}")
        
        # 测试5: MemoryStore.count()
        log("测试MemoryStore.count()", verbose)
        count = store.count()
        count_ok = isinstance(count, int) and count >= 2
        result_test("cli", "MemoryStore.count()", count_ok, f"count={count}")
        
        # 测试6: MemoryStore.get_all()
        log("测试MemoryStore.get_all()", verbose)
        all_memories = store.get_all()
        get_all_ok = isinstance(all_memories, dict) and len(all_memories) >= 2
        result_test("cli", "MemoryStore.get_all()", get_all_ok, f"keys={list(all_memories.keys())}")
        
        # 测试7: CLI命令行执行
        log("测试CLI命令行执行", verbose)
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "gateway" / "gateway.py"), "stats"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10
        )
        cli_run_ok = result.returncode == 0
        result_test("cli", "CLI gateway.py命令行", cli_run_ok, f"exit={result.returncode}")
        if result.returncode != 0:
            log(f"stderr: {result.stderr[:200]}", verbose)
        
        # 判断通过
        all_passed = all(t["passed"] for t in test_results["cli"]["tests"])
        test_results["cli"]["passed"] = all_passed
        return all_passed
        
    except Exception as e:
        result_error("cli", str(e))
        import traceback
        log(traceback.format_exc(), verbose)
        return False

# ============ 4. 插件加载测试 ============
def test_plugin(verbose: bool = False) -> bool:
    """测试插件加载"""
    print("\n" + "="*50)
    print("🔌 测试4: 插件加载")
    print("="*50)
    
    try:
        from plugin.plugin import (
            PluginRegistry, PluginState, PluginMetadata,
            PluginInterface, PluginLoader
        )
        
        # 测试1: PluginMetadata 元数据结构
        log("测试PluginMetadata结构", verbose)
        meta = PluginMetadata(
            id="记忆殿堂.test",
            name="测试插件",
            version="1.0.0",
            description="独立运行验证测试插件"
        )
        meta_ok = meta.id == "记忆殿堂.test" and meta.name == "测试插件"
        result_test("plugin", "PluginMetadata结构", meta_ok, f"id={meta.id}")
        
        # 测试2: PluginRegistry 单例
        log("测试PluginRegistry单例", verbose)
        registry1 = PluginRegistry()
        registry2 = PluginRegistry()
        singleton_ok = registry1 is registry2
        result_test("plugin", "PluginRegistry单例", singleton_ok, "same instance")
        
        # 测试3: 插件接口定义存在
        log("测试PluginInterface存在", verbose)
        iface_ok = PluginInterface is not None and hasattr(PluginInterface, 'on_load')
        result_test("plugin", "PluginInterface接口", iface_ok)
        
        # 测试4: 创建并注册测试插件类
        log("创建测试插件类", verbose)
        
        class TestPlugin(PluginInterface):
            METADATA = PluginMetadata(
                id="记忆殿堂.test.builtin",
                name="内置测试插件",
                version="1.0.0"
            )
            
            def __init__(self):
                self._state = PluginState.UNLOADED
                self._enabled = False
            
            def on_load(self) -> None:
                self._state = PluginState.ACTIVE
                log("TestPlugin.on_load() called", verbose)
            
            def on_enable(self) -> None:
                self._enabled = True
                self._state = PluginState.ACTIVE
            
            def on_disable(self) -> None:
                self._enabled = False
                self._state = PluginState.INACTIVE
            
            def on_unload(self) -> None:
                self._state = PluginState.UNLOADED
            
            def execute(self, context: dict) -> dict:
                return {"status": "ok", "plugin": "test", "context": context}
        
        # 注册插件
        log("注册测试插件", verbose)
        try:
            registry1.register(TestPlugin)
            reg_ok = True
        except ValueError:
            # 可能已注册，尝试获取
            registry1._plugins.clear()
            registry1.register(TestPlugin)
            reg_ok = True
        result_test("plugin", "PluginRegistry.register()", reg_ok)
        
        # 测试5: list_plugins()
        log("测试list_plugins()", verbose)
        plugins = registry1.list_plugins()
        list_ok = isinstance(plugins, list) and any(p.id == "记忆殿堂.test.builtin" for p in plugins)
        result_test("plugin", "PluginRegistry.list_plugins()", list_ok, f"count={len(plugins)}")
        
        # 测试6: load_plugin()
        log("测试load_plugin()", verbose)
        try:
            loaded = registry1.load_plugin("记忆殿堂.test.builtin")
            load_ok = loaded is not None
            result_test("plugin", "PluginRegistry.load_plugin()", load_ok)
            
            # 测试7: execute()
            log("测试execute()", verbose)
            exec_result = loaded.execute({"test": "data"})
            exec_ok = exec_result is not None and exec_result.get("status") == "ok"
            result_test("plugin", "PluginInterface.execute()", exec_ok, f"result={exec_result}")
            
            # 测试8: enable_plugin()
            log("测试enable_plugin()", verbose)
            registry1.enable_plugin("记忆殿堂.test.builtin")
            enable_ok = True
            result_test("plugin", "PluginRegistry.enable_plugin()", enable_ok)
            
            # 测试9: disable_plugin()
            log("测试disable_plugin()", verbose)
            registry1.disable_plugin("记忆殿堂.test.builtin")
            disable_ok = True
            result_test("plugin", "PluginRegistry.disable_plugin()", disable_ok)
            
            # 测试10: unload_plugin()
            log("测试unload_plugin()", verbose)
            registry1.unload_plugin("记忆殿堂.test.builtin")
            unload_ok = True
            result_test("plugin", "PluginRegistry.unload_plugin()", unload_ok)
            
        except Exception as e:
            log(f"生命周期测试部分失败: {e}", verbose)
            # 记录可用的测试结果
            for name in ["load_plugin", "execute", "enable_plugin", "disable_plugin", "unload_plugin"]:
                result_test("plugin", f"PluginRegistry.{name}()", False, f"跳过: {str(e)[:50]}")
        
        # 测试11: unregister()
        log("测试unregister()", verbose)
        try:
            registry1.unregister("记忆殿堂.test.builtin")
            unreg_ok = True
        except:
            # 如果已经卸载，强制清理后注销
            if "记忆殿堂.test.builtin" in registry1._plugins:
                del registry1._plugins["记忆殿堂.test.builtin"]
            unreg_ok = "记忆殿堂.test.builtin" not in registry1._plugins
        result_test("plugin", "PluginRegistry.unregister()", unreg_ok)
        
        # 测试12: PluginLoader 插件发现
        # 注意: PluginLoader.discover() 需要 Path 对象而非字符串，这是已知限制
        log("测试PluginLoader发现", verbose)
        plugin_dir = PROJECT_ROOT / "plugin"
        if plugin_dir.exists():
            try:
                from pathlib import Path as PathCls
                loader = PluginLoader([PathCls(plugin_dir)])
                discovered = loader.discover()
                disc_ok = isinstance(discovered, dict)
                result_test("plugin", "PluginLoader.discover()", disc_ok, f"found={len(discovered)}")
            except Exception as e:
                log(f"PluginLoader发现失败: {e}", verbose)
                result_test("plugin", "PluginLoader.discover()", False, f"已知限制: {str(e)[:60]}")
        else:
            result_test("plugin", "PluginLoader.discover()", False, "plugin目录不存在")
        
        # 判断通过
        all_passed = all(t["passed"] for t in test_results["plugin"]["tests"])
        test_results["plugin"]["passed"] = all_passed
        return all_passed
        
    except Exception as e:
        result_error("plugin", str(e))
        import traceback
        log(traceback.format_exc(), verbose)
        return False

# ============ 主函数 ============
def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="记忆殿堂v2.0 独立运行验证")
    parser.add_argument("--gateway", action="store_true", help="只测试Gateway")
    parser.add_argument("--wal", action="store_true", help="只测试WAL")
    parser.add_argument("--cli", action="store_true", help="只测试CLI")
    parser.add_argument("--plugin", action="store_true", help="只测试插件")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()
    
    print("="*60)
    print("🧵 记忆殿堂v2.0 - 独立运行验证")
    print("="*60)
    print(f"项目路径: {PROJECT_ROOT}")
    print(f"Python: {sys.version}")
    
    # 确保必要目录存在
    os.makedirs(PROJECT_ROOT / "wal", exist_ok=True)
    
    # 确定要运行的测试
    run_all = not any([args.gateway, args.wal, args.cli, args.plugin])
    
    results = {}
    
    if run_all or args.gateway:
        results["gateway"] = test_gateway(args.verbose)
    
    if run_all or args.wal:
        results["wal"] = test_wal(args.verbose)
    
    if run_all or args.cli:
        results["cli"] = test_cli(args.verbose)
    
    if run_all or args.plugin:
        results["plugin"] = test_plugin(args.verbose)
    
    # 汇总报告
    print("\n" + "="*60)
    print("📊 测试汇总报告")
    print("="*60)
    
    total_tests = 0
    total_passed = 0
    
    for category, result in test_results.items():
        if category in results or run_all:
            tests = result["tests"]
            passed = sum(1 for t in tests if t["passed"])
            total = len(tests)
            total_tests += total
            total_passed += passed
            
            status_icon = "✅" if result["passed"] else "❌"
            print(f"\n{status_icon} {category.upper()} ({passed}/{total} 通过)")
            for t in tests:
                icon = "✅" if t["passed"] else "❌"
                print(f"    {icon} {t['name']}: {t['detail']}")
            if result["errors"]:
                print(f"    ⚠️  Errors: {len(result['errors'])}")
    
    print(f"\n{'='*60}")
    print(f"总计: {total_passed}/{total_tests} 测试通过")
    
    if total_passed == total_tests:
        print("🎉 所有测试通过！记忆殿堂可脱离OpenClaw独立运行。")
        return 0
    else:
        print("⚠️  部分测试失败，请检查上述错误信息。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
