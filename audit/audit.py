"""
记忆殿堂v2.0 - 审计日志核心实现
Full operation tracking, high-risk operation auditing, log persistence and querying.
"""

import json
import os
import sqlite3
import threading
import traceback
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# ==============================================================================
# 配置与路径
# ==============================================================================

PROJECT_DIR = Path.home() / ".openclaw" / "projects" / "记忆殿堂v2.0"
AUDIT_DIR = PROJECT_DIR / "audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = AUDIT_DIR / "audit.db"
LOG_TEXT_DIR = AUDIT_DIR / "logs"
LOG_TEXT_DIR.mkdir(exist_ok=True)

# ==============================================================================
# 枚举定义
# ==============================================================================

class AuditLevel(IntEnum):
    """审计日志级别"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class AuditCategory(IntEnum):
    """操作类别"""
    READ = 1          # 读取操作
    WRITE = 2         # 写入操作
    DELETE = 3        # 删除操作
    PERMISSION = 4   # 权限变更
    SECURITY = 5      # 安全相关
    SYSTEM = 6        # 系统操作
    QUERY = 7         # 查询操作
    EXPORT = 8        # 导出操作
    IMPORT = 9        # 导入操作
    CONFIG = 10       # 配置变更


class RiskLevel(IntEnum):
    """风险等级"""
    LOW = 1           # 低风险：常规读取、查询
    MEDIUM = 2        # 中风险：写入、配置变更
    HIGH = 3          # 高风险：删除、权限变更、安全操作
    CRITICAL = 4      # 极高风险：批量删除、安全事件

# ==============================================================================
# 审计条目
# ==============================================================================

class AuditEntry:
    """单条审计日志条目"""

    def __init__(
        self,
        operation: str,
        category: Union[AuditCategory, int],
        level: Union[AuditLevel, int] = AuditLevel.INFO,
        risk: Union[RiskLevel, int] = RiskLevel.LOW,
        actor: str = "system",
        target: str = "",
        details: Optional[Dict[str, Any]] = None,
        session_id: str = "",
        channel: str = "",
        success: bool = True,
        error: str = "",
        stack_trace: str = "",
        tags: Optional[List[str]] = None,
        duration_ms: int = 0,
    ):
        self.timestamp = datetime.now(timezone.utc)
        self.operation = operation
        self.category = AuditCategory(category) if isinstance(category, int) else category
        self.level = AuditLevel(level) if isinstance(level, int) else level
        self.risk = RiskLevel(risk) if isinstance(risk, int) else risk
        self.actor = actor
        self.target = target
        self.details = details or {}
        self.session_id = session_id
        self.channel = channel
        self.success = success
        self.error = error
        self.stack_trace = stack_trace
        self.tags = tags or []
        self.duration_ms = duration_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation,
            "category": self.category.name,
            "level": self.level.name,
            "risk": self.risk.name,
            "actor": self.actor,
            "target": self.target,
            "details": self.details,
            "session_id": self.session_id,
            "channel": self.channel,
            "success": self.success,
            "error": self.error,
            "stack_trace": self.stack_trace,
            "tags": self.tags,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuditEntry":
        entry = cls(
            operation=d["operation"],
            category=getattr(AuditCategory, d["category"], AuditCategory.SYSTEM),
            level=getattr(AuditLevel, d["level"], AuditLevel.INFO),
            risk=getattr(RiskLevel, d["risk"], RiskLevel.LOW),
            actor=d.get("actor", "system"),
            target=d.get("target", ""),
            details=d.get("details", {}),
            session_id=d.get("session_id", ""),
            channel=d.get("channel", ""),
            success=d.get("success", True),
            error=d.get("error", ""),
            stack_trace=d.get("stack_trace", ""),
            tags=d.get("tags", []),
            duration_ms=d.get("duration_ms", 0),
        )
        if "timestamp" in d:
            ts = d["timestamp"]
            if isinstance(ts, str):
                entry.timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                entry.timestamp = ts
        return entry

# ==============================================================================
# 高风险操作映射
# ==============================================================================

# 自动判定高风险的关键词/模式
HIGH_RISK_PATTERNS = {
    "delete_all", "drop_table", "truncate", "force_delete",
    "revoke", "grant_admin", "change_permission", "set_admin",
    "bypass_security", "disable_audit", "clear_logs",
    "export_all", "bulk_delete", "mass_update",
    "security_violation", "unauthorized_access", "permission_denied",
}

MEDIUM_RISK_PATTERNS = {
    "write", "update", "create", "edit", "modify",
    "config_change", "setting_update", "permission_update",
    "import_data", "batch_import",
}

def infer_risk(operation: str, category: AuditCategory) -> RiskLevel:
    """根据操作名称和类别自动推断风险等级"""
    op_lower = operation.lower()
    for pattern in HIGH_RISK_PATTERNS:
        if pattern in op_lower:
            return RiskLevel.HIGH
    for pattern in MEDIUM_RISK_PATTERNS:
        if pattern in op_lower:
            return RiskLevel.MEDIUM
    if category == AuditCategory.DELETE:
        return RiskLevel.HIGH
    if category == AuditCategory.SECURITY:
        return RiskLevel.HIGH
    if category == AuditCategory.PERMISSION:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW

# ==============================================================================
# 数据库管理器
# ==============================================================================

class _AuditDB:
    """SQLite数据库管理（单例）"""

    _lock = threading.Lock()
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_db()
        return cls._instance

    def _get_conn(self):
        """获取配置好的数据库连接"""
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        """初始化数据库表"""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    category TEXT NOT NULL,
                    level TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    target TEXT DEFAULT '',
                    details TEXT DEFAULT '{}',
                    session_id TEXT DEFAULT '',
                    channel TEXT DEFAULT '',
                    success INTEGER DEFAULT 1,
                    error TEXT DEFAULT '',
                    stack_trace TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]',
                    duration_ms INTEGER DEFAULT 0,
                    is_high_risk INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_risk ON audit_log(is_high_risk)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_operation ON audit_log(operation)
            """)
            conn.commit()

    def insert(self, entry: AuditEntry):
        """写入单条审计日志"""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO audit_log (
                    timestamp, operation, category, level, risk, actor, target,
                    details, session_id, channel, success, error, stack_trace,
                    tags, duration_ms, is_high_risk
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.timestamp.isoformat(),
                entry.operation,
                entry.category.name,
                entry.level.name,
                entry.risk.name,
                entry.actor,
                entry.target,
                json.dumps(entry.details, ensure_ascii=False),
                entry.session_id,
                entry.channel,
                int(entry.success),
                entry.error,
                entry.stack_trace,
                json.dumps(entry.tags, ensure_ascii=False),
                entry.duration_ms,
                int(entry.risk >= RiskLevel.HIGH),
            ))
            conn.commit()

    def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        operation: Optional[str] = None,
        category: Optional[AuditCategory] = None,
        level: Optional[AuditLevel] = None,
        risk: Optional[RiskLevel] = None,
        actor: Optional[str] = None,
        target: Optional[str] = None,
        session_id: Optional[str] = None,
        success: Optional[bool] = None,
        high_risk_only: bool = False,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[AuditEntry]:
        """查询审计日志"""
        conditions = []
        params = []

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())
        if operation:
            # Escape LIKE wildcards to prevent semantic SQL injection
            # Use ESCAPE clause so \% and \_ are treated as literals
            safe_op = operation.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
            conditions.append("operation LIKE ? ESCAPE ?")
            params.append(f"%{safe_op}%")
            params.append("\\")
        if category:
            conditions.append("category = ?")
            params.append(category.name)
        if level:
            conditions.append("level >= ?")
            params.append(level.name)
        if risk:
            conditions.append("risk >= ?")
            params.append(risk.name)
        if actor:
            conditions.append("actor = ?")
            params.append(actor)
        if target:
            # Escape LIKE wildcards to prevent semantic SQL injection
            safe_target = target.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
            conditions.append("target LIKE ? ESCAPE ?")
            params.append(f"%{safe_target}%")
            params.append("\\")
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if success is not None:
            conditions.append("success = ?")
            params.append(int(success))
        if high_risk_only:
            conditions.append("is_high_risk = 1")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT timestamp, operation, category, level, risk, actor, target,
                   details, session_id, channel, success, error, stack_trace,
                   tags, duration_ms
            FROM audit_log
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()

        entries = []
        for row in rows:
            d = dict(row)
            d["details"] = json.loads(d["details"])
            d["tags"] = json.loads(d["tags"])
            entries.append(AuditEntry.from_dict(d))
        return entries

    def count(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        high_risk_only: bool = False,
    ) -> int:
        """统计审计日志数量"""
        conditions = []
        params = []
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())
        if high_risk_only:
            conditions.append("is_high_risk = 1")
        where = " AND ".join(conditions) if conditions else "1=1"
        with self._get_conn() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM audit_log WHERE {where}", params
            ).fetchone()
        return row[0] if row else 0

    def get_high_risk_summary(
        self, days: int = 7
    ) -> Dict[str, Any]:
        """获取高风险操作汇总"""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT operation, COUNT(*) as count, MAX(timestamp) as last_time
                FROM audit_log
                WHERE timestamp >= ? AND is_high_risk = 1
                GROUP BY operation
                ORDER BY count DESC
                LIMIT 50
            """, (since.isoformat(),)).fetchall()
        return [dict(r) for r in rows]

    def get_recent_failures(self, hours: int = 24, limit: int = 100) -> List[AuditEntry]:
        """获取最近失败的操作"""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return self.query(
            start_time=since,
            success=False,
            limit=limit,
        )

# ==============================================================================
# 文本日志写入器
# ==============================================================================

def _sanitize_path(path: str) -> str:
    """Sanitize a file path to prevent path traversal attacks.
    
    Removes leading slashes, dots, and null bytes that could be used
    for path traversal (e.g., ../../etc/passwd).
    """
    if not path:
        return path
    # Replace common path traversal patterns
    sanitized = path.replace('../', '').replace('..\\', '')
    # Remove leading slashes/dots that could escape the log directory
    sanitized = sanitized.lstrip('/\\')
    # Remove null bytes
    sanitized = sanitized.replace('\x00', '')
    return sanitized


def _sanitize_entry_for_log(entry: AuditEntry) -> Dict[str, Any]:
    """Sanitize an audit entry for safe logging.
    
    Prevents path traversal attacks in log content by sanitizing
    target paths and any file paths in details.
    """
    d = entry.to_dict()
    # Sanitize target field (common path carrier)
    if d.get('target'):
        d['target'] = _sanitize_path(d['target'])
    # Sanitize details dict (may contain file paths)
    if d.get('details') and isinstance(d['details'], dict):
        for key, value in d['details'].items():
            if isinstance(value, str) and ('/' in value or '\\' in value):
                # Likely a path - sanitize it
                d['details'][key] = _sanitize_path(value)
    return d


class _TextLogWriter:
    """文本日志写入（按日分割）"""

    _lock = threading.Lock()

    def write(self, entry: AuditEntry):
        with self._lock:
            date_str = entry.timestamp.strftime("%Y-%m-%d")
            log_file = LOG_TEXT_DIR / f"audit_{date_str}.log"
            # Sanitize entry to prevent path traversal via log content
            safe_entry = _sanitize_entry_for_log(entry)
            line = json.dumps(safe_entry, ensure_ascii=False)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

# ==============================================================================
# 审计日志器（主接口）
# ==============================================================================

class AuditLogger:
    """
    审计日志器 - 全操作追踪、高风险审计、持久化
    """

    def __init__(
        self,
        actor: str = "system",
        session_id: str = "",
        channel: str = "",
        write_text_log: bool = True,
        write_db: bool = True,
    ):
        self.actor = actor
        self.session_id = session_id
        self.channel = channel
        self.write_text_log = write_text_log
        self.write_db = write_db
        self._db = _AuditDB()
        self._text_writer = _TextLogWriter()
        self._current_entry: Optional[AuditEntry] = None
        self._start_time: Optional[float] = None

    # ---- 上下文管理器 ----

    def track(self, operation: str, target: str = "", category: Union[AuditCategory, int] = AuditCategory.SYSTEM, **kwargs) -> "AuditLogger":
        """开始追踪一个操作（支持上下文管理器）"""
        self._current_entry = AuditEntry(
            operation=operation,
            category=category,
            actor=self.actor,
            target=target,
            session_id=self.session_id,
            channel=self.channel,
            **kwargs,
        )
        self._current_entry.risk = infer_risk(operation, self._current_entry.category)
        self._start_time = None
        return self

    def __enter__(self) -> "AuditLogger":
        self._start_time = datetime.now(timezone.utc).timestamp() * 1000
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._current_entry is None:
            return
        if exc_type is not None:
            self._current_entry.success = False
            self._current_entry.error = f"{exc_type.__name__}: {exc_val}"
            self._current_entry.stack_trace = traceback.format_exc()
            self._current_entry.level = AuditLevel.ERROR
        if self._start_time:
            self._current_entry.duration_ms = int(
                datetime.now(timezone.utc).timestamp() * 1000 - self._start_time
            )
        self._flush(self._current_entry)
        self._current_entry = None
        self._start_time = None

    # ---- 直接记录 ----

    def log(
        self,
        operation: str,
        category: Union[AuditCategory, int] = AuditCategory.SYSTEM,
        level: Union[AuditLevel, int] = AuditLevel.INFO,
        risk: Optional[Union[RiskLevel, int]] = None,
        target: str = "",
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: str = "",
        tags: Optional[List[str]] = None,
        duration_ms: int = 0,
    ):
        """直接记录一条审计日志"""
        if risk is None:
            risk = infer_risk(operation, AuditCategory(category) if isinstance(category, int) else category)
        entry = AuditEntry(
            operation=operation,
            category=AuditCategory(category) if isinstance(category, int) else category,
            level=AuditLevel(level) if isinstance(level, int) else level,
            risk=RiskLevel(risk) if isinstance(risk, int) else risk,
            actor=self.actor,
            target=target,
            details=details or {},
            session_id=self.session_id,
            channel=self.channel,
            success=success,
            error=error,
            tags=tags or [],
            duration_ms=duration_ms,
        )
        self._flush(entry)

    def _flush(self, entry: AuditEntry):
        """持久化审计条目"""
        if self.write_db:
            self._db.insert(entry)
        if self.write_text_log:
            self._text_writer.write(entry)

    # ---- 快捷方法 ----

    def log_read(self, target: str, details: Optional[Dict[str, Any]] = None):
        self.log("read", AuditCategory.READ, target=target, details=details)

    def log_write(self, target: str, details: Optional[Dict[str, Any]] = None):
        self.log("write", AuditCategory.WRITE, target=target, details=details)

    def log_delete(self, target: str, details: Optional[Dict[str, Any]] = None):
        self.log("delete", AuditCategory.DELETE, risk=RiskLevel.HIGH, target=target, details=details)

    def log_security(self, operation: str, target: str = "", details: Optional[Dict[str, Any]] = None):
        self.log(operation, AuditCategory.SECURITY, risk=RiskLevel.HIGH, level=AuditLevel.WARNING, target=target, details=details)

    def log_permission(self, action: str, target: str, details: Optional[Dict[str, Any]] = None):
        self.log(f"permission_{action}", AuditCategory.PERMISSION, risk=RiskLevel.MEDIUM, target=target, details=details)

    def log_error(self, operation: str, error: str, target: str = ""):
        self.log(operation, level=AuditLevel.ERROR, success=False, error=error, target=target)

    # ---- 查询 ----

    def query(self, **kwargs) -> List[AuditEntry]:
        return self._db.query(**kwargs)

    def query_high_risk(self, **kwargs) -> List[AuditEntry]:
        return self._db.query(high_risk_only=True, **kwargs)

    def count(self, **kwargs) -> int:
        return self._db.count(**kwargs)

    def get_high_risk_summary(self, days: int = 7) -> Dict[str, Any]:
        return self._db.get_high_risk_summary(days)

    def get_recent_failures(self, hours: int = 24) -> List[AuditEntry]:
        return self._db.get_recent_failures(hours)


# ==============================================================================
# 全局审计日志器
# ==============================================================================

_global_logger: Optional[AuditLogger] = None
_global_lock = threading.Lock()


def get_audit_logger(
    actor: str = "system",
    session_id: str = "",
    channel: str = "",
) -> AuditLogger:
    """获取全局审计日志器实例"""
    global _global_logger
    with _global_lock:
        if _global_logger is None:
            _global_logger = AuditLogger(actor=actor, session_id=session_id, channel=channel)
        return _global_logger


def log_operation(
    operation: str,
    category: Union[AuditCategory, int] = AuditCategory.SYSTEM,
    level: Union[AuditLevel, int] = AuditLevel.INFO,
    target: str = "",
    details: Optional[Dict[str, Any]] = None,
    actor: str = "system",
    session_id: str = "",
    channel: str = "",
    success: bool = True,
    error: str = "",
    tags: Optional[List[str]] = None,
) -> AuditEntry:
    """全局快捷记录接口"""
    logger = get_audit_logger(actor=actor, session_id=session_id, channel=channel)
    entry = AuditEntry(
        operation=operation,
        category=AuditCategory(category) if isinstance(category, int) else category,
        level=AuditLevel(level) if isinstance(level, int) else level,
        risk=RiskLevel.LOW,
        actor=actor,
        target=target,
        details=details or {},
        session_id=session_id,
        channel=channel,
        success=success,
        error=error,
        tags=tags or [],
    )
    entry.risk = infer_risk(operation, entry.category)
    logger._flush(entry)
    return entry


def log_high_risk_operation(
    operation: str,
    target: str = "",
    details: Optional[Dict[str, Any]] = None,
    actor: str = "system",
    session_id: str = "",
    channel: str = "",
    success: bool = True,
    error: str = "",
    tags: Optional[List[str]] = None,
) -> AuditEntry:
    """全局快捷记录高风险操作"""
    entry = AuditEntry(
        operation=operation,
        category=AuditCategory.SECURITY,
        level=AuditLevel.WARNING,
        risk=RiskLevel.HIGH,
        actor=actor,
        target=target,
        details=details or {},
        session_id=session_id,
        channel=channel,
        success=success,
        error=error,
        tags=["high_risk"] + (tags or []),
    )
    logger = get_audit_logger(actor=actor, session_id=session_id, channel=channel)
    logger._flush(entry)
    return entry


def query_logs(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    operation: Optional[str] = None,
    category: Optional[AuditCategory] = None,
    level: Optional[AuditLevel] = None,
    risk: Optional[RiskLevel] = None,
    actor: Optional[str] = None,
    target: Optional[str] = None,
    session_id: Optional[str] = None,
    success: Optional[bool] = None,
    high_risk_only: bool = False,
    limit: int = 1000,
    offset: int = 0,
) -> List[AuditEntry]:
    """全局快捷查询接口"""
    db = _AuditDB()
    return db.query(
        start_time=start_time,
        end_time=end_time,
        operation=operation,
        category=category,
        level=level,
        risk=risk,
        actor=actor,
        target=target,
        session_id=session_id,
        success=success,
        high_risk_only=high_risk_only,
        limit=limit,
        offset=offset,
    )
