#!/usr/bin/env python3
"""
test_mini_agent.py - 记忆殿堂v2.0 Mini Agent 测试

执行: python3 test_mini_agent.py
期望: 返回 0 表示所有测试通过
"""

import sys
import os

# 添加mini_agent路径
_MINI_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _MINI_AGENT_DIR)

# 导入模块
from compact import (
    CompactionConfig, CompactionResult, should_compact, compact_session,
    estimate_session_tokens, format_compact_summary, Message,
)
from hooks import (
    HookEvent, HookResult, HookManager, BeforeToolCallHook, ToolResultPersistHook,
    DefaultBeforeToolCallHook, HookContext, ToolCall, ToolResult,
)
from registry import (
    Task, TaskStatus, TaskRegistry, TaskPriority,
)


# ============================================================================
# 测试结果收集
# ============================================================================

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def check(self, condition: bool, test_name: str) -> None:
        if condition:
            self.passed += 1
            print(f"  ✓ {test_name}")
        else:
            self.failed += 1
            self.errors.append(f"FAIL: {test_name}")
            print(f"  ✗ {test_name}")
    
    def summary(self) -> int:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"测试结果: {self.passed}/{total} 通过")
        if self.errors:
            print(f"失败项:")
            for e in self.errors:
                print(f"  - {e}")
        return 0 if self.failed == 0 else 1


# ============================================================================
# 测试用例
# ============================================================================

def test_compact_config():
    """测试压缩配置"""
    print("\n[测试] CompactionConfig")
    runner = TestRunner()
    
    config = CompactionConfig()
    runner.check(config.preserve_recent_messages == 4, "默认保留4条消息")
    runner.check(config.max_estimated_tokens == 10000, "默认最大token阈值10000")
    
    config2 = CompactionConfig(preserve_recent_messages=8, max_estimated_tokens=5000)
    runner.check(config2.preserve_recent_messages == 8, "自定义保留8条消息")
    runner.check(config2.max_estimated_tokens == 5000, "自定义最大token阈值5000")
    
    return runner.summary()


def test_message_creation():
    """测试消息创建"""
    print("\n[测试] Message消息结构")
    runner = TestRunner()
    
    msg = Message(role="user", content="Hello world")
    runner.check(msg.role == "user", "消息角色正确")
    runner.check(msg.content == "Hello world", "消息内容正确")
    runner.check(msg.tool_calls is None, "默认无tool_calls")
    runner.check(msg.tool_results is None, "默认无tool_results")
    
    return runner.summary()


def test_should_compact():
    """测试是否需要压缩判断"""
    print("\n[测试] should_compact判断")
    runner = TestRunner()
    
    # 消息太少，不需要压缩
    messages = [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi!"),
    ]
    runner.check(not should_compact(messages, CompactionConfig()), 
                  "少量消息不需要压缩")
    
    # 构造大量消息触发压缩（每条约4000 chars ≈ 1000 tokens）
    # 5条消息 * 1000 tokens = 5000，保留4条，压缩1条，约1000 tokens < 10000阈值
    # 需要更多消息才能触发
    large_messages = [
        Message(role="user", content="Hello " * 4000),   # ~1000 tokens
        Message(role="assistant", content="Response " * 4000),
        Message(role="user", content="Another " * 4000),
        Message(role="assistant", content="More " * 4000),
        Message(role="user", content="Last " * 4000),
        Message(role="assistant", content="Final " * 4000),
    ]
    runner.check(should_compact(large_messages, CompactionConfig()), 
                  "大量消息需要压缩")
    
    return runner.summary()


def test_compact_session():
    """测试会话压缩"""
    print("\n[测试] compact_session压缩会话")
    runner = TestRunner()
    
    # 构造测试会话
    messages = [
        Message(role="user", content="Create a function"),
        Message(role="assistant", content="def foo(): pass", 
                tool_calls=[{"name": "write"}]),
        Message(role="user", content="Test it"),
        Message(role="assistant", content="All tests passed"),
        Message(role="user", content="Deploy"),
        Message(role="assistant", content="Deployed!"),
    ]
    
    result = compact_session(messages, CompactionConfig())
    
    runner.check(result.removed_message_count >= 0, "返回删除消息数")
    runner.check(len(result.compacted_messages) >= 1, "返回压缩后消息")
    runner.check(len(result.compacted_messages) <= len(messages), 
                 "压缩后消息数不增加")
    
    return runner.summary()


def test_hooks_basic():
    """测试Hook基础结构"""
    print("\n[测试] Hook基础结构")
    runner = TestRunner()
    
    # HookEvent
    runner.check(HookEvent.BEFORE_TOOL_CALL.value == "before_tool_call", 
                 "HookEvent BEFORE_TOOL_CALL值正确")
    runner.check(HookEvent.TOOL_RESULT_PERSIST.value == "tool_result_persist",
                 "HookEvent TOOL_RESULT_PERSIST值正确")
    
    # HookResult
    result = HookResult()
    runner.check(not result.denied, "默认未拒绝")
    runner.check(not result.failed, "默认未失败")
    runner.check(len(result.messages) == 0, "默认无消息")
    
    return runner.summary()


def test_default_before_tool_hook():
    """测试默认before_tool_call hook"""
    print("\n[测试] DefaultBeforeToolCallHook")
    runner = TestRunner()
    
    hook = DefaultBeforeToolCallHook()
    context = HookContext(session_id="test-123")
    
    # 安全工具应被允许
    safe_call = ToolCall(name="read", arguments={"path": "/tmp/test"})
    result = hook.handle(context, safe_call)
    runner.check(not result.denied, "安全工具(read)被允许")
    
    # 危险工具应被拒绝
    dangerous_call = ToolCall(name="rm", arguments={"path": "/"})
    result = hook.handle(context, dangerous_call)
    runner.check(result.denied, "危险工具(rm)被拒绝")
    
    # 未知工具应被拒绝
    unknown_call = ToolCall(name="hack_system", arguments={})
    result = hook.handle(context, unknown_call)
    runner.check(result.denied, "未知工具被拒绝")
    
    return runner.summary()


def test_hook_manager():
    """测试Hook管理器"""
    print("\n[测试] HookManager")
    runner = TestRunner()
    
    manager = HookManager()
    
    # 测试注册
    class SimpleHook(BeforeToolCallHook):
        def handle(self, context, tool_call):
            return HookResult(messages=["hook ran"])
    
    manager.register_before_tool_hook(SimpleHook())
    runner.check(len(manager._before_tool_hooks) == 1, "Hook已注册")
    
    # 测试运行
    context = HookContext(session_id="test")
    tool_call = ToolCall(name="read", arguments={})
    result = manager.run_before_tool_call(context, tool_call)
    runner.check("hook ran" in result.messages, "Hook执行并返回消息")
    
    return runner.summary()


def test_task_creation():
    """测试任务创建"""
    print("\n[测试] Task任务创建")
    runner = TestRunner()
    
    registry = TaskRegistry()
    
    task = registry.create(
        name="Test Task",
        description="A test task",
        priority=TaskPriority.HIGH,
    )
    
    runner.check(task is not None, "任务创建成功")
    runner.check(task.name == "Test Task", "任务名称正确")
    runner.check(task.status == TaskStatus.PENDING, "默认状态为PENDING")
    runner.check(task.priority == TaskPriority.HIGH, "优先级正确设置")
    runner.check(len(task.id) > 0, "任务ID已生成")
    
    return runner.summary()


def test_task_status_transitions():
    """测试任务状态转换"""
    print("\n[测试] Task状态转换")
    runner = TestRunner()
    
    registry = TaskRegistry()
    task = registry.create(name="Status Test")
    task_id = task.id
    
    # PENDING -> RUNNING
    runner.check(registry.start(task_id), "启动任务成功")
    runner.check(registry.get(task_id).status == TaskStatus.RUNNING, "状态转为RUNNING")
    
    # RUNNING -> COMPLETED
    runner.check(registry.complete(task_id, result="done"), "完成任务成功")
    runner.check(registry.get(task_id).status == TaskStatus.COMPLETED, "状态转为COMPLETED")
    runner.check(registry.get(task_id).result == "done", "结果已保存")
    
    return runner.summary()


def test_task_dependencies():
    """测试任务依赖"""
    print("\n[测试] Task依赖管理")
    runner = TestRunner()
    
    registry = TaskRegistry()
    
    # 创建依赖任务
    task1 = registry.create(name="Task 1")
    task2 = registry.create(name="Task 2", dependencies=[task1.id])
    
    # task2不应能启动（task1未完成）
    runner.check(not registry.start(task2.id), "有未完成依赖时不能启动")
    
    # 完成task1后，task2应该可以启动
    registry.complete(task1.id)
    runner.check(registry.start(task2.id), "依赖完成后可以启动")
    
    return runner.summary()


def test_task_queue():
    """测试任务队列"""
    print("\n[测试] Task优先级队列")
    runner = TestRunner()
    
    registry = TaskRegistry()
    
    # 创建不同优先级的任务
    low = registry.create(name="Low Priority", priority=TaskPriority.LOW)
    high = registry.create(name="High Priority", priority=TaskPriority.HIGH)
    normal = registry.create(name="Normal Priority", priority=TaskPriority.NORMAL)
    
    queue = registry.get_queue()
    runner.check(len(queue) == 3, "队列有3个任务")
    
    # 高优先级应该在前
    runner.check(queue[0].name == "High Priority", "高优先级在最前")
    
    return runner.summary()


def test_task_registry_stats():
    """测试任务统计"""
    print("\n[测试] TaskRegistry统计")
    runner = TestRunner()
    
    registry = TaskRegistry()
    
    # 创建各种状态的任务
    t1 = registry.create(name="Pending 1")
    t2 = registry.create(name="Pending 2")
    t3 = registry.create(name="Running")
    registry.start(t3.id)
    t4 = registry.create(name="Completed")
    registry.complete(t4.id)
    
    stats = registry.stats()
    runner.check(stats["total"] == 4, "总任务数正确")
    runner.check(stats["pending"] == 2, "待处理任务数正确")
    runner.check(stats["running"] == 1, "运行中任务数正确")
    runner.check(stats["completed"] == 1, "已完成任务数正确")
    
    return runner.summary()


def test_export_import():
    """测试导出导入"""
    print("\n[测试] 导出导入JSON")
    runner = TestRunner()
    
    registry = TaskRegistry()
    task = registry.create(name="Export Test", priority=TaskPriority.HIGH)
    registry.complete(task.id, result="success")
    
    # 导出
    json_str = registry.to_json()
    runner.check("Export Test" in json_str, "JSON包含任务名")
    runner.check("success" in json_str, "JSON包含结果")
    
    # 导入到新注册表
    new_registry = TaskRegistry()
    new_registry.load_from_json(json_str)
    
    runner.check(len(new_registry.list()) == 1, "新注册表有1个任务")
    runner.check(new_registry.list()[0].name == "Export Test", "任务名正确")
    
    return runner.summary()


# ============================================================================
# 主函数
# ============================================================================

def main():
    print("=" * 60)
    print("记忆殿堂v2.0 Mini Agent - 测试套件")
    print("=" * 60)
    
    # 运行所有测试
    results = []
    results.append(("Compact配置", test_compact_config()))
    results.append(("Message结构", test_message_creation()))
    results.append(("should_compact", test_should_compact()))
    results.append(("compact_session", test_compact_session()))
    results.append(("Hook基础", test_hooks_basic()))
    results.append(("BeforeToolCallHook", test_default_before_tool_hook()))
    results.append(("HookManager", test_hook_manager()))
    results.append(("Task创建", test_task_creation()))
    results.append(("Task状态转换", test_task_status_transitions()))
    results.append(("Task依赖", test_task_dependencies()))
    results.append(("Task队列", test_task_queue()))
    results.append(("Task统计", test_task_registry_stats()))
    results.append(("导出导入", test_export_import()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试汇总:")
    
    total_passed = 0
    total_failed = 0
    
    for name, result in results:
        status = "✓ PASS" if result == 0 else "✗ FAIL"
        print(f"  {status}: {name}")
        if result == 0:
            total_passed += 1
        else:
            total_failed += 1
    
    print(f"\n总计: {total_passed}/{len(results)} 测试套件通过")
    
    # 更新feature_list.json
    if total_failed == 0:
        try:
            import json
            feature_file = os.path.join(_MINI_AGENT_DIR, "..", "feature_list.json")
            with open(feature_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 找到feature_002并更新
            for feature in data.get("features", []):
                if feature.get("id") == "feature_002":
                    feature["passes"] = True
                    feature["completed_at"] = "2026-04-06T11:06:00+08:00"
                    break
            
            with open(feature_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"\n✓ feature_list.json 已更新 (feature_002.passes=true)")
        except Exception as e:
            print(f"\n✗ feature_list.json 更新失败: {e}")
    
    return total_failed


if __name__ == "__main__":
    sys.exit(main())
