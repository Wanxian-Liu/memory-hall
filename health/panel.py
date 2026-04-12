"""
记忆殿堂-观自在 V3.0.0 - 断路器状态面板
"""

from typing import Dict, Any, Optional
from .circuit_breaker import CircuitBreaker


class CircuitBreakerPanel:
    """
    V3.0.0新增：断路器状态面板
    
    统一管理和展示所有断路器状态
    """
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {
            '萃取': CircuitBreaker('萃取', failure_threshold=5, recovery_timeout=60),
            '归一': CircuitBreaker('归一', failure_threshold=5, recovery_timeout=60),
            '通感': CircuitBreaker('通感', failure_threshold=5, recovery_timeout=60),
            '分类': CircuitBreaker('分类', failure_threshold=5, recovery_timeout=60),
        }
    
    def get_panel_status(self) -> Dict[str, Any]:
        """获取面板状态"""
        breakers_info = {}
        all_ok = True
        any_open = False
        any_half_open = False
        
        for name, breaker in self.breakers.items():
            info = breaker.get_info()
            breakers_info[name] = {
                'name': info.name,
                'state': info.state.value,
                'failure_count': info.failure_count,
                'success_count': info.success_count,
                'last_failure_time': info.last_failure_time,
                'failure_threshold': info.failure_threshold,
                'recovery_timeout': info.recovery_timeout,
                'success_threshold': info.success_threshold,
            }
            
            if info.state.value == 'open':
                all_ok = False
                any_open = True
            elif info.state.value == 'half_open':
                all_ok = False
                any_half_open = True
        
        overall = "ok"
        if any_open:
            overall = "open"
        elif any_half_open:
            overall = "half_open"
        
        return {
            "overall": overall,
            "all_ok": all_ok,
            "breakers": breakers_info,
            "summary": {
                "total": len(self.breakers),
                "closed": sum(1 for b in breakers_info.values() if b['state'] == 'closed'),
                "open": sum(1 for b in breakers_info.values() if b['state'] == 'open'),
                "half_open": sum(1 for b in breakers_info.values() if b['state'] == 'half_open'),
            }
        }
    
    def get_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """获取特定断路器"""
        return self.breakers.get(name)
    
    def reset_breaker(self, name: str = None) -> Dict[str, Any]:
        """重置断路器"""
        if name:
            if name in self.breakers:
                self.breakers[name].reset()
                return {"success": True, "message": f"断路器 {name} 已重置"}
            return {"success": False, "message": f"断路器 {name} 不存在"}
        else:
            for breaker in self.breakers.values():
                breaker.reset()
            return {"success": True, "message": "所有断路器已重置"}
    
    def call_with_circuit(self, name: str, func, *args, **kwargs):
        """带断路器调用"""
        if name not in self.breakers:
            return {'success': False, 'error': f'Unknown circuit: {name}'}
        return self.breakers[name].call(func, *args, **kwargs)


__all__ = ["CircuitBreakerPanel"]
