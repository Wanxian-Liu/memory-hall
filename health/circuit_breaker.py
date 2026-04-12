"""
记忆殿堂-观自在 V3.0.0 - 断路器
"""

import os
import json
import time
import threading
from typing import Optional
from .enums import CircuitState
from .data_classes import CircuitBreakerInfo


# 路径配置
METADATA_DIR = os.path.expanduser("~/.openclaw/memory-vault/metadata")
CIRCUIT_FILE = os.path.join(METADATA_DIR, "circuit_breaker.json")


class CircuitBreaker:
    """
    断路器：防止级联故障
    
    状态：
    - CLOSED：正常，允许请求
    - OPEN：熔断，拒绝请求  
    - HALF_OPEN：半开，尝试恢复
    """
    
    def __init__(
        self, 
        name: str, 
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time: Optional[float] = None
        self._lock = threading.Lock()
        
        self._load_state()
    
    def _load_state(self):
        """从文件加载状态"""
        try:
            if os.path.exists(CIRCUIT_FILE):
                with open(CIRCUIT_FILE, 'r', encoding='utf-8') as f:
                    all_states = json.load(f)
                    if self.name in all_states:
                        state = all_states[self.name]
                        self.failure_count = state.get('failure_count', 0)
                        self.success_count = state.get('success_count', 0)
                        self.last_failure_time = state.get('last_failure_time')
                        self.state = CircuitState(state.get('state', 'closed'))
        except Exception:
            pass
    
    def _save_state(self):
        """保存状态到文件"""
        try:
            os.makedirs(os.path.dirname(CIRCUIT_FILE), exist_ok=True)
            all_states = {}
            if os.path.exists(CIRCUIT_FILE):
                with open(CIRCUIT_FILE, 'r', encoding='utf-8') as f:
                    all_states = json.load(f)
            
            all_states[self.name] = {
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'last_failure_time': self.last_failure_time,
                'state': self.state.value
            }
            
            with open(CIRCUIT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_states, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def call(self, func, *args, **kwargs):
        """带断路器的调用"""
        with self._lock:
            # 检查是否应该从OPEN转为HALF_OPEN
            if self.state == CircuitState.OPEN:
                if self.last_failure_time:
                    if time.time() - self.last_failure_time >= self.recovery_timeout:
                        self.state = CircuitState.HALF_OPEN
                        self.success_count = 0
                        self.failure_count = 0
            
            # 如果还是OPEN，拒绝请求
            if self.state == CircuitState.OPEN:
                return {
                    'success': False,
                    'error': f'Circuit breaker OPEN for {self.name}',
                    'state': self.state.value,
                    'bypassed': True  # 断路器熔断旁路
                }
        
        # 执行调用
        try:
            result = func(*args, **kwargs)
            self._on_success()
            result['bypassed'] = False
            return result
        except Exception as e:
            self._on_failure()
            return {
                'success': False,
                'error': str(e),
                'state': self.state.value,
                'bypassed': False
            }
    
    def _on_success(self):
        """成功处理"""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0
            self._save_state()
    
    def _on_failure(self):
        """失败处理"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
            elif self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            
            self._save_state()
    
    def get_info(self) -> CircuitBreakerInfo:
        """获取断路器信息"""
        return CircuitBreakerInfo(
            name=self.name,
            state=self.state,
            failure_count=self.failure_count,
            success_count=self.success_count,
            last_failure_time=self.last_failure_time,
            failure_threshold=self.failure_threshold,
            recovery_timeout=self.recovery_timeout,
            success_threshold=self.success_threshold
        )
    
    def reset(self):
        """重置断路器"""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self._save_state()


__all__ = ["CircuitBreaker"]
