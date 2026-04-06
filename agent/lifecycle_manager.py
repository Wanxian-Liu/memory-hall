"""
代理生命周期管理器 (AgentLifecycleManager) - 记忆殿堂v2.0 DAME
基于claw-code worker_boot.rs和task_packet.rs设计

功能:
    - spawn: 启动新代理
    - heartbeat: 心跳保活
    - terminate: 终止代理
"""

import threading
import time
import uuid
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .models import Agent, AgentState, Role, RoleType
from .role_registry import RoleRegistry, get_global_registry


@dataclass
class LifecycleConfig:
    """生命周期配置"""
    heartbeat_interval_seconds: int = 30      # 心跳间隔
    heartbeat_timeout_seconds: int = 120      # 心跳超时
    max_idle_seconds: int = 300               # 最大空闲时间
    cleanup_interval_seconds: int = 60       # 清理检查间隔


class AgentLifecycleManager:
    """
    代理生命周期管理器
    
    管理代理的创建、运行、监控和终止。
    线程安全，支持并发访问。
    
    设计参考: claw-code runtime/worker_boot.rs
    """
    
    def __init__(
        self,
        registry: Optional[RoleRegistry] = None,
        config: Optional[LifecycleConfig] = None
    ):
        self.registry = registry or get_global_registry()
        self.config = config or LifecycleConfig()
        
        self._agents: Dict[str, Agent] = {}
        self._lock = threading.RLock()
        
        # 回调函数
        self._on_spawn: Optional[Callable[[Agent], None]] = None
        self._on_terminate: Optional[Callable[[Agent, str], None]] = None
        self._on_heartbeat: Optional[Callable[[Agent], None]] = None
        self._on_state_change: Optional[Callable[[Agent, AgentState, AgentState], None]] = None
        
        # 清理线程
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False
    
    def set_callbacks(
        self,
        on_spawn: Optional[Callable[[Agent], None]] = None,
        on_terminate: Optional[Callable[[Agent, str], None]] = None,
        on_heartbeat: Optional[Callable[[Agent], None]] = None,
        on_state_change: Optional[Callable[[Agent, AgentState, AgentState], None]] = None,
    ) -> None:
        """设置生命周期回调函数"""
        self._on_spawn = on_spawn
        self._on_terminate = on_terminate
        self._on_heartbeat = on_heartbeat
        self._on_state_change = on_state_change
    
    def spawn(
        self,
        role_name: str,
        agent_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Agent]:
        """
        启动一个新代理
        
        Args:
            role_name: 角色名称
            agent_id: 指定agent_id，不指定则自动生成
            context: 共享上下文
            
        Returns:
            Optional[Agent]: 新创建的代理或None（角色不存在）
        """
        role = self.registry.get(role_name)
        if role is None:
            return None
        
        with self._lock:
            # 生成agent_id
            if agent_id is None:
                agent_id = f"agent_{uuid.uuid4().hex[:12]}"
            
            # 检查是否已存在
            if agent_id in self._agents:
                return None
            
            # 创建代理
            agent = Agent(
                agent_id=agent_id,
                role=role,
                state=AgentState.CREATED,
                context=context or {}
            )
            
            self._agents[agent_id] = agent
            
            # 触发状态变更到RUNNING
            self._transition_state(agent, AgentState.RUNNING)
            agent.started_at = datetime.now()
            
            # 触发spawn回调
            if self._on_spawn:
                try:
                    self._on_spawn(agent)
                except Exception:
                    pass
        
        return agent
    
    def spawn_by_type(
        self,
        role_type: RoleType,
        agent_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Agent]:
        """
        根据角色类型启动代理（使用该类型的第一个角色）
        
        Args:
            role_type: 角色类型
            agent_id: 指定agent_id
            context: 共享上下文
            
        Returns:
            Optional[Agent]: 新创建的代理或None
        """
        roles = self.registry.get_by_type(role_type)
        if not roles:
            return None
        
        return self.spawn(roles[0].name, agent_id, context)
    
    def heartbeat(self, agent_id: str) -> bool:
        """
        发送心跳
        
        Args:
            agent_id: 代理ID
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None or not agent.is_alive():
                return False
            
            agent.mark_heartbeat()
            
            # 如果之前是IDLE，切换回RUNNING
            if agent.state == AgentState.IDLE:
                self._transition_state(agent, AgentState.RUNNING)
            
            # 触发heartbeat回调
            if self._on_heartbeat:
                try:
                    self._on_heartbeat(agent)
                except Exception:
                    pass
            
            return True
    
    def terminate(
        self,
        agent_id: str,
        reason: str = "normal",
        result: Optional[Any] = None
    ) -> bool:
        """
        终止代理
        
        Args:
            agent_id: 代理ID
            reason: 终止原因
            result: 执行结果
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                return False
            
            # 设置结果
            if result is not None:
                agent.result = result
            
            # 根据原因设置最终状态
            if reason == "normal" or reason == "completed":
                final_state = AgentState.COMPLETED
            elif reason == "failed":
                final_state = AgentState.FAILED
            else:
                final_state = AgentState.STOPPED
            
            old_state = agent.state
            agent.state = final_state
            agent.completed_at = datetime.now()
            
            # 触发state_change回调
            if self._on_state_change:
                try:
                    self._on_state_change(agent, old_state, final_state)
                except Exception:
                    pass
            
            # 触发terminate回调
            if self._on_terminate:
                try:
                    self._on_terminate(agent, reason)
                except Exception:
                    pass
            
            return True
    
    def set_idle(self, agent_id: str) -> bool:
        """
        设置代理为空闲状态
        
        Args:
            agent_id: 代理ID
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None or not agent.is_alive():
                return False
            
            self._transition_state(agent, AgentState.IDLE)
            return True
    
    def assign_task(self, agent_id: str, task_id: str) -> bool:
        """
        为代理分配任务
        
        Args:
            agent_id: 代理ID
            task_id: 任务ID
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None or not agent.is_alive():
                return False
            
            agent.current_task_id = task_id
            return True
    
    def get(self, agent_id: str) -> Optional[Agent]:
        """
        获取代理
        
        Args:
            agent_id: 代理ID
            
        Returns:
            Optional[Agent]: 代理对象或None
        """
        with self._lock:
            return self._agents.get(agent_id)
    
    def list_all(self) -> List[Agent]:
        """
        列出所有代理
        
        Returns:
            List[Agent]: 代理列表
        """
        with self._lock:
            return list(self._agents.values())
    
    def list_by_state(self, state: AgentState) -> List[Agent]:
        """
        列出指定状态的所有代理
        
        Args:
            state: 代理状态
            
        Returns:
            List[Agent]: 代理列表
        """
        with self._lock:
            return [a for a in self._agents.values() if a.state == state]
    
    def list_alive(self) -> List[Agent]:
        """
        列出所有存活的代理
        
        Returns:
            List[Agent]: 代理列表
        """
        with self._lock:
            return [a for a in self._agents.values() if a.is_alive()]
    
    def count(self) -> int:
        """获取代理总数"""
        with self._lock:
            return len(self._agents)
    
    def count_alive(self) -> int:
        """获取存活代理数量"""
        return len(self.list_alive())
    
    def _transition_state(self, agent: Agent, new_state: AgentState) -> None:
        """内部状态转换"""
        old_state = agent.state
        agent.state = new_state
        
        if self._on_state_change and old_state != new_state:
            try:
                self._on_state_change(agent, old_state, new_state)
            except Exception:
                pass
    
    def _cleanup_stale_agents(self) -> None:
        """清理超时的代理"""
        now = datetime.now()
        timeout = timedelta(seconds=self.config.heartbeat_timeout_seconds)
        
        with self._lock:
            stale_agents = []
            
            for agent in self._agents.values():
                if agent.is_alive() and agent.last_heartbeat:
                    if now - agent.last_heartbeat > timeout:
                        stale_agents.append(agent.agent_id)
            
            for agent_id in stale_agents:
                self.terminate(agent_id, reason="timeout")
    
    def start_cleanup_thread(self) -> None:
        """启动清理线程"""
        if self._running:
            return
        
        self._running = True
        
        def cleanup_loop():
            while self._running:
                time.sleep(self.config.cleanup_interval_seconds)
                if self._running:
                    self._cleanup_stale_agents()
        
        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def stop_cleanup_thread(self) -> None:
        """停止清理线程"""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
            self._cleanup_thread = None


# 全局单例
_global_lifecycle_manager: Optional[AgentLifecycleManager] = None
_manager_lock = threading.Lock()


def get_global_lifecycle_manager() -> AgentLifecycleManager:
    """获取全局生命周期管理器单例"""
    global _global_lifecycle_manager
    with _manager_lock:
        if _global_lifecycle_manager is None:
            _global_lifecycle_manager = AgentLifecycleManager()
        return _global_lifecycle_manager
