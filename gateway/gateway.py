#!/usr/bin/env python3
"""
记忆殿堂 Gateway V2.0
独立Python模块 - 不依赖OpenClaw

特性：
- LRU缓存 (1000条目)
- TTL过期 (默认7天)
- 写时失效机制
- 审计日志
- IMemoryVault接口统一访问

配置：通过 config.yaml 管理
"""

import os
import sys
import json
import re
import hashlib
import time
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import OrderedDict

# ============ IMemoryVault接口 ============
# 注意：gateway需要完整逻辑，不能简单替换
# 这里添加组合而非继承，保持gateway所有逻辑

def _get_vault_adapter():
    """获取IMemoryVault适配器（延迟加载）"""
    if not hasattr(_get_vault_adapter, '_adapter'):
        # 延迟导入，避免循环依赖
        PROJECT_ROOT = Path(__file__).parent.parent
        sys.path.insert(0, str(PROJECT_ROOT))
        from interfaces.adapters import FileSystemAdapter
        _get_vault_adapter._adapter = FileSystemAdapter()
    return _get_vault_adapter._adapter

# ============ 配置管理 ============

class Config:
    """配置管理类"""
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """加载配置文件"""
        config_path = Path(__file__).parent / "config.yaml"
        if config_path.exists():
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self._default_config()
    
    def _default_config(self) -> dict:
        """默认配置"""
        return {
            "cache": {
                "enabled": True,
                "max_size": 1000,
                "ttl_days": 7,
                "persist": True,
                "persist_file": "gateway_cache.json"
            },
            "paths": {
                "vault_dir": "~/.openclaw/memory-vault/data",
                "log_dir": "~/.openclaw/memory-vault/logs",
                "audit_file": "audit.jsonl"
            },
            "security": {
                "max_content_length": 5242880,
                "max_field_length": 51200,
                "allowed_record_types": "^[a-zA-Z0-9_\\-]+$"
            },
            "coordinator": {
                "enabled": False,
                "url": "http://127.0.0.1:8091",
                "timeout": 10
            },
            "fence": {
                "enabled": False,
                "script_path": None
            }
        }
    
    def get(self, key: str, default=None):
        """获取配置值，支持点号路径如 'cache.max_size'"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def reload(self):
        """重新加载配置"""
        self._load_config()


# 全局配置实例
_config = Config()


# ============ 路径解析 ============

def _expand_path(path_str: str) -> Path:
    """展开路径中的~和环境变量"""
    return Path(os.path.expanduser(os.path.expandvars(path_str)))


def _get_vault_dir() -> Path:
    return _expand_path(_config.get("paths.vault_dir", "~/.openclaw/memory-vault/data"))


def _get_log_dir() -> Path:
    return _expand_path(_config.get("paths.log_dir", "~/.openclaw/memory-vault/logs"))


def _get_audit_file() -> Path:
    return _get_log_dir() / _config.get("paths.audit_file", "audit.jsonl")


def _get_cache_file() -> Path:
    return _get_log_dir() / _config.get("cache.persist_file", "gateway_cache.json")


# ============ LRU缓存实现 ============

class LRUCache:
    """
    LRU缓存实现
    
    特性：
    - LRU淘汰策略
    - TTL过期（按天配置）
    - 持久化到磁盘
    """
    
    def __init__(self, max_size: int = None, ttl_days: int = None):
        cfg = _config._config.get("cache", {})
        self.max_size = max_size or cfg.get("max_size", 1000)
        self.ttl_seconds = (ttl_days or cfg.get("ttl_days", 7)) * 86400
        self.persist = cfg.get("persist", True)
        self.enabled = cfg.get("enabled", True)
        self._cache: OrderedDict = OrderedDict()
        
        if self.persist and self.enabled:
            self._load_from_disk()
    
    def _load_from_disk(self):
        """从磁盘加载缓存"""
        cache_file = _get_cache_file()
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._cache = OrderedDict(data)
                    self._cleanup_expired()
            except Exception:
                self._cache = OrderedDict()
    
    def _save_to_disk(self):
        """持久化缓存到磁盘"""
        if not self.persist:
            return
        
        try:
            _get_log_dir().mkdir(parents=True, exist_ok=True)
            cache_file = _get_cache_file()
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(dict(self._cache), f, ensure_ascii=False)
        except Exception:
            pass
    
    def _is_expired(self, entry: dict) -> bool:
        """检查缓存条目是否过期"""
        if "timestamp" not in entry:
            return True
        return time.time() - entry["timestamp"] > self.ttl_seconds
    
    def _cleanup_expired(self):
        """清理过期条目"""
        expired_keys = [
            k for k, v in self._cache.items()
            if self._is_expired(v)
        ]
        for k in expired_keys:
            del self._cache[k]
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self.enabled:
            return None
        
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        if self._is_expired(entry):
            del self._cache[key]
            return None
        
        # 移到末尾（最新使用）
        self._cache.move_to_end(key)
        return entry["value"]
    
    def set(self, key: str, value: Any):
        """设置缓存"""
        if not self.enabled:
            return
        
        # 如果已存在，移到末尾
        if key in self._cache:
            self._cache.move_to_end(key)
        
        self._cache[key] = {
            "value": value,
            "timestamp": time.time()
        }
        
        # LRU淘汰
        while len(self._cache) > self.max_size:
            self._cache.popitem(last=False)
        
        # 定期保存（每10次写入）
        if self.persist and len(self._cache) % 10 == 0:
            self._save_to_disk()
    
    def invalidate(self, key: str = None):
        """失效缓存"""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()
        self._save_to_disk()
    
    def get_stats(self) -> dict:
        """获取缓存统计"""
        self._cleanup_expired()
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_days": self.ttl_seconds / 86400,
            "enabled": self.enabled,
            "persist": self.persist
        }


# 全局缓存实例
_gateway_cache = LRUCache()


# ============ 审计日志 ============

def audit_log(action: str, user: str, details: Dict = None):
    """记录审计日志"""
    _get_log_dir().mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "user": user,
        "details": details or {}
    }
    try:
        with open(_get_audit_file(), 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass
    return entry


# ============ 安全验证函数 ============

def _sanitize_string(s: str, max_len: int = None, field_max: int = None) -> str:
    """字符串安全清理"""
    sec = _config._config.get("security", {})
    max_len = max_len or sec.get("max_content_length", 5242880)
    field_max = field_max or sec.get("max_field_length", 51200)
    
    if not isinstance(s, str):
        s = str(s)
    
    # 去除null字节
    s = s.replace('\x00', '')
    
    # 限制总体长度
    if len(s) > max_len:
        s = s[:max_len]
    
    # 限制单行长度
    lines = s.split('\n')
    lines = [line[:field_max] for line in lines]
    s = '\n'.join(lines)
    
    return s


def _validate_path(path_str: str) -> bool:
    """验证路径安全性"""
    if not path_str:
        return False
    if '..' in path_str:
        return False
    if len(path_str) > 1000:
        return False
    return True


def _validate_record_type(record_type: str) -> bool:
    """验证记录类型"""
    sec = _config._config.get("security", {})
    pattern = sec.get("allowed_record_types", r"^[a-zA-Z0-9_\-]+$")
    return bool(re.match(pattern, record_type))


# ============ 文件读写 ============

def read_record(filepath: str) -> Optional[Dict]:
    """读取记录"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def write_record(filepath: str, data: Dict) -> bool:
    """写入记录"""
    try:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def generate_id(content: str) -> str:
    """生成内容ID"""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ============ 围栏检查点 ============

def fence_checkpoint(filepath: str, operation: str, user: str = "system") -> Dict[str, Any]:
    """围栏检查点"""
    fence_cfg = _config._config.get("fence", {})
    if not fence_cfg.get("enabled", False):
        return {"allowed": True, "reason": "Fence disabled"}
    
    script_path = fence_cfg.get("script_path")
    if not script_path:
        return {"allowed": True, "reason": "Fence script not configured"}
    
    script = Path(script_path)
    if not script.exists():
        return {"allowed": True, "reason": "Fence script not found"}
    
    # P0-2: 验证filepath不包含特殊字符，防止命令注入
    filepath_resolved = Path(filepath).resolve()
    special_chars = set('\x00\n\r\'";|&$<>`')
    if any(c in str(filepath_resolved) for c in special_chars):
        return {"allowed": False, "reason": "Filepath contains invalid characters"}
    
    try:
        result = subprocess.run(
            [sys.executable, str(script), "check", operation, str(filepath_resolved)],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout.strip()
        return json.loads(output) if output else {"allowed": False}
    except Exception as e:
        return {"allowed": False, "error": str(e)}


# ============ 协调器通知 ============

def notify_coordinator(filepath: str, source: str = "gateway") -> bool:
    """通知基座协调器"""
    coord_cfg = _config._config.get("coordinator", {})
    if not coord_cfg.get("enabled", False):
        return False
    
    try:
        import urllib.request
        url = coord_cfg.get("url", "http://127.0.0.1:8091")
        timeout = coord_cfg.get("timeout", 10)
        data = json.dumps({"filepath": filepath, "source": source}).encode('utf-8')
        req = urllib.request.Request(
            f"{url}/notify",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


# ============ 核心功能 ============

def write(
    content: str,
    record_type: str = "general",
    user: str = "system",
    metadata: Dict = None,
    notify: bool = True
) -> Dict[str, Any]:
    """
    写入记忆殿堂
    
    Args:
        content: 内容
        record_type: 类型（目录）
        user: 用户
        metadata: 元数据
        notify: 是否通知协调器
    
    Returns:
        写入结果
    """
    # 安全验证
    safe_content = _sanitize_string(content)
    if len(safe_content) == 0:
        return {"success": False, "error": "Content is empty or invalid"}
    
    record_id = generate_id(safe_content)
    timestamp = datetime.now().isoformat()
    
    # 类型验证
    safe_record_type = _sanitize_string(record_type, 100, 50)
    if not _validate_record_type(safe_record_type):
        safe_record_type = "general"
    
    # 准备记录
    record = {
        "id": record_id,
        "type": safe_record_type,
        "content": safe_content,
        "metadata": metadata or {},
        "created_at": timestamp,
        "updated_at": timestamp,
        "coordinator_notified": False
    }
    
    # 存储路径
    type_dir = _get_vault_dir() / safe_record_type
    type_dir.mkdir(parents=True, exist_ok=True)
    filepath = type_dir / f"{record_id}.json"
    
    # 围栏检查
    fence_result = fence_checkpoint(str(filepath), "write", user)
    
    # 计算内容Hash
    content_hash = hashlib.sha256(safe_content.encode()).hexdigest()
    record["content_hash"] = content_hash
    
    # 写入文件
    success = write_record(str(filepath), record)
    if not success:
        return {"success": False, "error": "Failed to write file"}
    
    # 写时失效缓存
    _gateway_cache.invalidate(record_id)
    _gateway_cache.invalidate(str(filepath))
    
    # 审计日志
    audit_log("write", user, {
        "record_id": record_id,
        "type": safe_record_type,
        "filepath": str(filepath),
        "fence_passed": fence_result.get("allowed", True)
    })
    
    # 通知协调器
    if notify:
        coordinator_notified = notify_coordinator(str(filepath), "gateway")
        if coordinator_notified:
            record["coordinator_notified"] = True
            write_record(str(filepath), record)
    
    return {
        "success": True,
        "record_id": record_id,
        "filepath": str(filepath),
        "timestamp": timestamp,
        "coordinator_notified": record["coordinator_notified"]
    }


def read(record_id: str = None, filepath: str = None) -> Optional[Dict]:
    """
    读取记忆殿堂记录
    
    Args:
        record_id: 记录ID (16位hex)
        filepath: 文件路径
    
    Returns:
        记录内容或None
    """
    # 参数验证
    cache_key = filepath or record_id or ""
    if not cache_key:
        return None
    
    if record_id and not re.match(r'^[a-f0-9]{16}$', record_id):
        return None
    
    if filepath and not _validate_path(filepath):
        return None
    
    # 尝试从缓存读取
    cached = _gateway_cache.get(cache_key)
    if cached is not None:
        return cached
    
    target = filepath
    
    if not target and record_id:
        # 搜索vault
        for type_dir in _get_vault_dir().iterdir():
            if type_dir.is_dir():
                candidate = type_dir / f"{record_id}.json"
                if candidate.exists():
                    target = str(candidate)
                    break
    
    if not target:
        return None
    
    record = read_record(target)
    if record:
        audit_log("read", "system", {"record_id": record_id, "filepath": target})
        _gateway_cache.set(cache_key, record)
    
    return record


def search(query: str, record_type: str = None, limit: int = 10) -> List[Dict]:
    """
    搜索记忆殿堂
    
    注意：V2.0独立版需要外部搜索引擎支持
    """
    safe_query = _sanitize_string(query, 500, 200)
    if not safe_query:
        return []
    
    limit = min(max(int(limit) if limit else 10, 1), 100)
    
    audit_log("search", "system", {"query": safe_query, "limit": limit})
    
    # V2.0：搜索功能需要外部服务
    # 返回空列表，由调用方实现搜索服务
    return []


def delete(record_id: str = None, filepath: str = None) -> bool:
    """删除记忆殿堂记录"""
    if record_id and not re.match(r'^[a-f0-9]{16}$', record_id):
        return False
    
    if filepath and not _validate_path(filepath):
        return False
    
    target = filepath
    
    if not target and record_id:
        for type_dir in _get_vault_dir().iterdir():
            if type_dir.is_dir():
                candidate = type_dir / f"{record_id}.json"
                if candidate.exists():
                    target = str(candidate)
                    break
    
    if not target:
        return False
    
    # 围栏检查
    fence_result = fence_checkpoint(target, "cleanup", "system")
    if not fence_result.get("allowed", True):
        audit_log("delete_denied", "system", {
            "filepath": target,
            "reason": fence_result.get("reason", "Fence denied")
        })
        return False
    
    try:
        # 删除前失效缓存
        _gateway_cache.invalidate(record_id)
        _gateway_cache.invalidate(target)
        
        Path(target).unlink()
        audit_log("delete", "system", {"filepath": target})
        return True
    except Exception:
        return False


def get_audit_logs(limit: int = 100) -> List[Dict]:
    """获取审计日志"""
    try:
        audit_file = _get_audit_file()
        if not audit_file.exists():
            return []
        
        with open(audit_file, 'r', encoding='utf-8') as f:
            logs = [json.loads(line) for line in f if line.strip()]
        return logs[-limit:] if limit > 0 else logs
    except Exception:
        return []


def get_cache_stats() -> dict:
    """获取缓存统计"""
    return _gateway_cache.get_stats()


def clear_cache():
    """清空缓存"""
    _gateway_cache.invalidate()
    return {"success": True}


# ============ Gateway类封装 ============

class Gateway:
    """
    Gateway封装类
    
    提供面向对象的接口
    """
    
    def __init__(self):
        self.cache = _gateway_cache
        self.config = _config
    
    def put(self, content: str, record_type: str = "general", user: str = "system") -> Dict:
        """写入记录"""
        return write(content, record_type, user)
    
    def get(self, record_id: str = None, filepath: str = None) -> Optional[Dict]:
        """读取记录"""
        return read(record_id, filepath)
    
    def find(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索记录"""
        return search(query, limit=limit)
    
    def remove(self, record_id: str = None, filepath: str = None) -> bool:
        """删除记录"""
        return delete(record_id, filepath)
    
    def logs(self, limit: int = 100) -> List[Dict]:
        """获取审计日志"""
        return get_audit_logs(limit)
    
    def stats(self) -> dict:
        """获取统计"""
        return {
            "cache": get_cache_stats(),
            "vault": str(_get_vault_dir()),
            "audit": str(_get_audit_file())
        }


# ============ CLI入口 ============

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: gateway.py <command> [args...]",
            "commands": ["write", "read", "search", "delete", "audit", "stats"]
        }, ensure_ascii=False))
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "write":
        content = sys.argv[2] if len(sys.argv) > 2 else ""
        record_type = sys.argv[3] if len(sys.argv) > 3 else "general"
        user = sys.argv[4] if len(sys.argv) > 4 else "system"
        result = write(content, record_type, user)
        print(json.dumps(result, ensure_ascii=False))
    
    elif command == "read":
        arg = sys.argv[2] if len(sys.argv) > 2 else ""
        if arg.startswith("/"):
            result = read(filepath=arg)
        else:
            result = read(record_id=arg)
        print(json.dumps(result or {"error": "Not found"}, ensure_ascii=False))
    
    elif command == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        results = search(query, limit=limit)
        print(json.dumps(results, ensure_ascii=False))
    
    elif command == "delete":
        arg = sys.argv[2] if len(sys.argv) > 2 else ""
        if arg.startswith("/"):
            success = delete(filepath=arg)
        else:
            success = delete(record_id=arg)
        print(json.dumps({"success": success}, ensure_ascii=False))
    
    elif command == "audit":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        logs = get_audit_logs(limit)
        print(json.dumps(logs, ensure_ascii=False))
    
    elif command == "stats":
        stats = Gateway().stats()
        print(json.dumps(stats, ensure_ascii=False))
    
    elif command == "clear-cache":
        result = clear_cache()
        print(json.dumps(result, ensure_ascii=False))
    
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}, ensure_ascii=False))
        sys.exit(1)
