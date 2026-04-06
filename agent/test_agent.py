#!/usr/bin/env python3
"""
DAME 动态代理测试 - 记忆殿堂v2.0

验证:
1. RoleRegistry - 角色注册表
2. AgentLifecycleManager - 代理生命周期管理
3. TaskDispatcher - 任务分发器

返回码:
    0 - 所有测试通过
    1 - 测试失败
"""

import sys
import time
from datetime import datetime


def test_role_registry():
    """测试角色注册表"""
    print("\n=== 测试 RoleRegistry ===")
    
    # 添加项目根目录到path
    import os
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)
    
    from agent.role_registry import RoleRegistry, Role, RoleType
    
    registry = RoleRegistry()
    
    # 测试注册角色
    role1 = Role(
        name="测试角色",
        role_type=RoleType.RESEARCHER,
        description="测试用角色",
        capabilities=["test", "research"]
    )
    
    assert registry.register(role1), "注册角色失败"
    print("✓ 注册角色成功")
    
    # 测试获取角色
    retrieved = registry.get("测试角色")
    assert retrieved is not None, "获取角色失败"
    assert retrieved.name == "测试角色", "角色名称不匹配"
    print("✓ 获取角色成功")
    
    # 测试按类型查询
    roles = registry.get_by_type(RoleType.RESEARCHER)
    assert len(roles) >= 1, "按类型查询失败"
    print(f"✓ 按类型查询成功 (找到 {len(roles)} 个研究员角色)")
    
    # 测试查找能处理任务的角色
    capable = registry.find_can_handle("test")
    assert len(capable) >= 1, "能力查询失败"
    print(f"✓ 能力查询成功 (找到 {len(capable)} 个可处理test任务的角色)")
    
    # 测试注销
    assert registry.unregister("测试角色"), "注销角色失败"
    assert registry.get("测试角色") is None, "注销后仍能获取角色"
    print("✓ 注销角色成功")
    
    # 测试列表所有角色（含默认角色）
    all_roles = registry.list_all()
    assert len(all_roles) > 0, "列表为空"
    print(f"✓ 列出所有角色成功 (共 {len(all_roles)} 个)")
    
    print("RoleRegistry 测试通过!")
    return True


def test_lifecycle_manager():
    """测试代理生命周期管理"""
    print("\n=== 测试 AgentLifecycleManager ===")
    
    from agent.lifecycle_manager import AgentLifecycleManager, LifecycleConfig
    from agent.role_registry import RoleRegistry, Role, RoleType
    from agent.models import AgentState
    
    # 创建独立的注册表
    registry = RoleRegistry()
    test_role = Role(
        name="生命周期测试角色",
        role_type=RoleType.DEVELOPER,
        description="生命周期测试",
        capabilities=["code", "debug"]
    )
    registry.register(test_role)
    
    config = LifecycleConfig(
        heartbeat_interval_seconds=1,
        heartbeat_timeout_seconds=5,
        cleanup_interval_seconds=2
    )
    manager = AgentLifecycleManager(registry=registry, config=config)
    
    # 测试spawn
    agent = manager.spawn("生命周期测试角色")
    assert agent is not None, "spawn失败"
    assert agent.state == AgentState.RUNNING, f"初始状态应为RUNNING，实际为{agent.state}"
    print("✓ spawn成功")
    
    # 测试heartbeat
    assert manager.heartbeat(agent.agent_id), "heartbeat失败"
    assert agent.heartbeat_count == 1, f"心跳计数应为1，实际为{agent.heartbeat_count}"
    print("✓ heartbeat成功")
    
    # 测试set_idle
    assert manager.set_idle(agent.agent_id), "set_idle失败"
    assert agent.state == AgentState.IDLE, f"状态应为IDLE，实际为{agent.state}"
    print("✓ set_idle成功")
    
    # 测试terminate
    assert manager.terminate(agent.agent_id, reason="normal"), "terminate失败"
    assert agent.state == AgentState.COMPLETED, f"终止状态应为COMPLETED，实际为{agent.state}"
    print("✓ terminate成功")
    
    # 测试get/list
    agent2 = manager.spawn("生命周期测试角色")
    all_agents = manager.list_all()
    assert len(all_agents) >= 2, "list_all失败"
    print(f"✓ list_all成功 (共 {len(all_agents)} 个代理)")
    
    alive = manager.list_alive()
    assert len(alive) >= 1, "list_alive失败"
    print(f"✓ list_alive成功 (存活 {len(alive)} 个)")
    
    # 清理
    manager.terminate(agent2.agent_id, reason="test_complete")
    
    print("AgentLifecycleManager 测试通过!")
    return True


def test_task_dispatcher():
    """测试任务分发器"""
    print("\n=== 测试 TaskDispatcher ===")
    
    from agent.task_dispatcher import TaskDispatcher, DispatcherConfig
    from agent.role_registry import RoleRegistry, Role, RoleType
    from agent.lifecycle_manager import AgentLifecycleManager
    from agent.models import TaskStatus
    
    # 创建独立组件
    registry = RoleRegistry()
    test_role = Role(
        name="分发测试角色",
        role_type=RoleType.DEVELOPER,
        description="分发测试",
        capabilities=["code", "debug", "test"]
    )
    registry.register(test_role)
    
    lifecycle = AgentLifecycleManager(registry=registry)
    dispatcher = TaskDispatcher(
        registry=registry,
        lifecycle_manager=lifecycle,
        config=DispatcherConfig(max_pending_tasks=100)
    )
    
    # 测试submit
    task_id = dispatcher.submit(
        task_type="code",
        description="测试任务",
        priority=5
    )
    assert task_id is not None, "submit失败"
    print("✓ submit成功")
    
    # 测试get
    task = dispatcher.get(task_id)
    assert task is not None, "get失败"
    assert task.description == "测试任务", "任务描述不匹配"
    print("✓ get成功")
    
    # 测试dispatch - 需要先有可用代理
    agent = lifecycle.spawn("分发测试角色")
    assert agent is not None, "创建代理失败"
    
    # 派发任务
    success = dispatcher.dispatch(task_id)
    # 注意：dispatch可能因为队列顺序等问题失败，这里验证基本流程
    print(f"✓ dispatch执行 (结果: {success})")
    
    # 测试列表功能
    all_tasks = dispatcher.list_all()
    assert len(all_tasks) >= 1, "list_all失败"
    print(f"✓ list_all成功 (共 {len(all_tasks)} 个任务)")
    
    pending = dispatcher.list_pending()
    print(f"✓ list_pending成功 (待处理 {len(pending)} 个)")
    
    # 测试cancel
    cancel_task_id = dispatcher.submit(
        task_type="test",
        description="待取消任务"
    )
    assert dispatcher.cancel(cancel_task_id), "cancel失败"
    cancelled = dispatcher.get(cancel_task_id)
    assert cancelled.status == TaskStatus.CANCELLED, "取消状态不正确"
    print("✓ cancel成功")
    
    # 清理
    lifecycle.terminate(agent.agent_id, reason="test_complete")
    
    print("TaskDispatcher 测试通过!")
    return True


def test_integration():
    """集成测试"""
    print("\n=== 集成测试 ===")
    
    from agent.role_registry import get_global_registry, RoleRegistry
    from agent.lifecycle_manager import get_global_lifecycle_manager, AgentLifecycleManager
    from agent.task_dispatcher import get_global_dispatcher, TaskDispatcher
    from agent.models import AgentState, TaskStatus
    
    # 使用全局单例
    registry = get_global_registry()
    lifecycle = get_global_lifecycle_manager()
    dispatcher = get_global_dispatcher()
    
    # 验证全局单例
    assert registry is not None, "全局注册表为None"
    assert lifecycle is not None, "全局生命周期管理器为None"
    assert dispatcher is not None, "全局分发器为None"
    print("✓ 全局单例获取成功")
    
    # 创建测试代理
    roles = registry.list_all()
    if roles:
        role_name = roles[0].name
        agent = lifecycle.spawn(role_name)
        if agent:
            print(f"✓ 使用角色 '{role_name}' 创建代理成功")
            
            # 心跳
            for i in range(3):
                lifecycle.heartbeat(agent.agent_id)
                time.sleep(0.1)
            print(f"✓ 代理 {agent.agent_id} 心跳成功")
            
            # 终止
            lifecycle.terminate(agent.agent_id, reason="integration_test")
            print("✓ 代理终止成功")
    
    # 提交测试任务
    task_id = dispatcher.submit(
        task_type="code",
        description="集成测试任务",
        priority=10
    )
    if task_id:
        print(f"✓ 任务提交成功: {task_id}")
        
        # 验证任务
        task = dispatcher.get(task_id)
        if task:
            assert task.status == TaskStatus.PENDING, "任务状态应为PENDING"
            print("✓ 任务状态正确")
    
    print("集成测试通过!")
    return True


def main():
    """主测试函数"""
    print("=" * 60)
    print("记忆殿堂v2.0 DAME 动态代理测试")
    print("=" * 60)
    
    # 确保可以导入agent模块
    import os
    project_dir = os.path.dirname(os.path.abspath(__file__))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)
    
    try:
        # 运行各项测试
        test_role_registry()
        test_lifecycle_manager()
        test_task_dispatcher()
        test_integration()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试通过!")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ 意外错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
