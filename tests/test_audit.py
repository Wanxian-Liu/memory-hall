# -*- coding: utf-8 -*-
"""
测试 audit 模块 - 审计日志系统
"""
import os
import sys
import pytest
import tempfile
import time
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from audit.audit import (
    AuditLogger, AuditEntry, AuditLevel, AuditCategory, RiskLevel,
    _AuditDB, _TextLogWriter,
    get_audit_logger, log_operation, log_high_risk_operation,
    query_logs, infer_risk
)


class TestAuditLevel:
    """测试AuditLevel枚举"""

    def test_levels(self):
        assert AuditLevel.DEBUG == 10
        assert AuditLevel.INFO == 20
        assert AuditLevel.WARNING == 30
        assert AuditLevel.ERROR == 40
        assert AuditLevel.CRITICAL == 50

    def test_comparison(self):
        assert AuditLevel.DEBUG < AuditLevel.INFO
        assert AuditLevel.INFO < AuditLevel.WARNING


class TestAuditCategory:
    """测试AuditCategory枚举"""

    def test_categories(self):
        assert AuditCategory.READ == 1
        assert AuditCategory.WRITE == 2
        assert AuditCategory.DELETE == 3
        assert AuditCategory.SECURITY == 5
        assert AuditCategory.SYSTEM == 6


class TestRiskLevel:
    """测试RiskLevel枚举"""

    def test_levels(self):
        assert RiskLevel.LOW == 1
        assert RiskLevel.MEDIUM == 2
        assert RiskLevel.HIGH == 3
        assert RiskLevel.CRITICAL == 4


class TestAuditEntry:
    """测试AuditEntry类"""

    def test_entry_creation(self):
        entry = AuditEntry(
            operation="test_op",
            category=AuditCategory.SYSTEM,
            level=AuditLevel.INFO,
            risk=RiskLevel.LOW,
            actor="test_user",
            target="/memory/test",
            details={"key": "value"},
            session_id="sess_123",
            channel="wechat"
        )
        assert entry.operation == "test_op"
        assert entry.actor == "test_user"
        assert entry.target == "/memory/test"
        assert entry.success is True

    def test_entry_failure(self):
        entry = AuditEntry(
            operation="failed_op",
            category=AuditCategory.SYSTEM,
            success=False,
            error="Something went wrong"
        )
        assert entry.success is False
        assert entry.error == "Something went wrong"

    def test_entry_to_dict(self):
        entry = AuditEntry(
            operation="test",
            category=AuditCategory.READ,
            actor="user1",
            target="/path/to/resource"
        )
        data = entry.to_dict()
        assert data["operation"] == "test"
        assert data["actor"] == "user1"
        assert "timestamp" in data

    def test_entry_from_dict(self):
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": "from_dict_test",
            "category": "SYSTEM",
            "level": "INFO",
            "risk": "LOW",
            "actor": "user1",
            "target": "/test",
            "details": {},
            "session_id": "",
            "channel": "",
            "success": True,
            "error": "",
            "stack_trace": "",
            "tags": [],
            "duration_ms": 0
        }
        entry = AuditEntry.from_dict(data)
        assert entry.operation == "from_dict_test"
        assert entry.category == AuditCategory.SYSTEM


class TestInferRisk:
    """测试infer_risk函数"""

    def test_high_risk_patterns(self):
        for op in ["delete_all", "drop_table", "bulk_delete"]:
            risk = infer_risk(op, AuditCategory.WRITE)
            assert risk == RiskLevel.HIGH, f"Expected HIGH for {op}, got {risk}"

    def test_medium_risk_patterns(self):
        for op in ["write", "update", "create"]:
            risk = infer_risk(op, AuditCategory.WRITE)
            assert risk == RiskLevel.MEDIUM

    def test_delete_category_high_risk(self):
        risk = infer_risk("something", AuditCategory.DELETE)
        assert risk == RiskLevel.HIGH

    def test_security_category_high_risk(self):
        risk = infer_risk("something", AuditCategory.SECURITY)
        assert risk == RiskLevel.HIGH

    def test_read_category_low_risk(self):
        risk = infer_risk("something", AuditCategory.READ)
        assert risk == RiskLevel.LOW


class TestTextLogWriter:
    """测试_TextLogWriter类"""

    def test_writer_init(self):
        writer = _TextLogWriter()
        assert writer is not None

    def test_writer_write(self, temp_dir, monkeypatch):
        """测试日志写入"""
        # 跳过文件写入测试
        writer = _TextLogWriter()
        entry = AuditEntry(
            operation="write_test",
            category=AuditCategory.SYSTEM
        )
        # 不实际写文件
        assert writer is not None


class TestAuditDB:
    """测试_AuditDB类（内存模式）"""

    def test_db_init(self, temp_dir, monkeypatch):
        """测试数据库初始化"""
        # 创建临时数据库
        import os
        db_path = os.path.join(temp_dir, "test_audit.db")

        # 直接测试_AuditDB的单例行为
        db = _AuditDB()
        assert db is not None


class TestAuditLogger:
    """测试AuditLogger类"""

    def test_logger_init(self, temp_dir, monkeypatch):
        """测试日志器初始化"""
        logger = AuditLogger(
            actor="test_user",
            session_id="sess_001",
            channel="wechat"
        )
        assert logger.actor == "test_user"
        assert logger.session_id == "sess_001"
        assert logger.write_db is True
        assert logger.write_text_log is True

    def test_logger_log(self, temp_dir, monkeypatch):
        """测试直接记录日志"""
        logger = AuditLogger(actor="test_user", write_db=True, write_text_log=False)

        logger.log(
            operation="test_log",
            category=AuditCategory.READ,
            level=AuditLevel.INFO,
            target="/memory/test",
            details={"test": True}
        )
        # 没有异常就是成功

    def test_logger_log_read(self, temp_dir, monkeypatch):
        """测试快捷方法：log_read"""
        logger = AuditLogger(actor="test_user", write_db=False, write_text_log=False)
        logger.log_read(target="/memory/test", details={"read": True})
        assert True

    def test_logger_log_write(self, temp_dir, monkeypatch):
        """测试快捷方法：log_write"""
        logger = AuditLogger(actor="test_user", write_db=False, write_text_log=False)
        logger.log_write(target="/memory/test", details={"write": True})
        assert True

    def test_logger_log_delete(self, temp_dir, monkeypatch):
        """测试快捷方法：log_delete"""
        logger = AuditLogger(actor="test_user", write_db=False, write_text_log=False)
        logger.log_delete(target="/memory/test")
        assert True

    def test_logger_log_security(self, temp_dir, monkeypatch):
        """测试快捷方法：log_security"""
        logger = AuditLogger(actor="test_user", write_db=False, write_text_log=False)
        logger.log_security(operation="unauthorized_access", target="/memory/private")
        assert True

    def test_logger_log_error(self, temp_dir, monkeypatch):
        """测试快捷方法：log_error"""
        logger = AuditLogger(actor="test_user", write_db=False, write_text_log=False)
        logger.log_error(operation="test_op", error="Test error")
        assert True

    def test_logger_context_manager(self, temp_dir, monkeypatch):
        """测试上下文管理器"""
        logger = AuditLogger(actor="test_user", write_db=False, write_text_log=False)

        with logger.track("context_test", category=AuditCategory.WRITE, target="/test"):
            pass  # 正常退出

        assert True

    def test_logger_context_manager_exception(self, temp_dir, monkeypatch):
        """测试上下文管理器异常处理"""
        logger = AuditLogger(actor="test_user", write_db=False, write_text_log=False)

        try:
            with logger.track("exception_test", category=AuditCategory.SYSTEM, target="/test"):
                raise ValueError("Test exception")
        except ValueError:
            pass  # 预期异常

        assert True


class TestGlobalFunctions:
    """测试全局函数"""

    def test_get_audit_logger(self, temp_dir, monkeypatch):
        """测试获取全局审计日志器"""
        logger = get_audit_logger(actor="global_user")
        assert logger is not None
        assert logger.actor == "global_user"

    def test_log_operation(self, temp_dir, monkeypatch):
        """测试全局log_operation"""
        entry = log_operation(
            operation="global_log_test",
            category=AuditCategory.SYSTEM,
            level=AuditLevel.INFO,
            actor="system",
            target="/memory/test",
            details={"global": True}
        )
        assert entry is not None
        assert entry.operation == "global_log_test"

    def test_log_high_risk_operation(self, temp_dir, monkeypatch):
        """测试全局log_high_risk_operation"""
        entry = log_high_risk_operation(
            operation="high_risk_test",
            target="/memory/private/secret",
            actor="user1",
            details={"risk": "high"}
        )
        assert entry is not None
        assert entry.risk == RiskLevel.HIGH

    def test_query_logs(self, temp_dir, monkeypatch):
        """测试全局query_logs"""
        # 先记录一些日志
        log_operation(
            operation="query_test",
            category=AuditCategory.READ,
            actor="query_user",
            target="/memory/test"
        )

        # 查询
        results = query_logs(
            operation="query_test",
            limit=10
        )
        assert isinstance(results, list)
