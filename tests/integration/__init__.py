#!/usr/bin/env python3
"""
记忆殿堂v2.0 集成测试套件

测试模块间协作:
1. Gateway + WAL 协作
2. Gateway + Permission 协作
3. CLI + 各模块 协作
4. Plugin + 各模块 协作

运行方式:
    cd ~/.openclaw/projects/记忆殿堂v2.0/tests/integration
    python -m pytest -v
    python -m pytest integration_test_gateway_wal.py -v
"""

import os
import sys
import json
import tempfile
import shutil
import time
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import unittest

# 测试配置
TEST_DIR = os.path.join(PROJECT_ROOT, "tests")
INTEGRATION_DIR = os.path.join(TEST_DIR, "integration")
FIXTURES_DIR = os.path.join(INTEGRATION_DIR, "fixtures")


def setup_test_vault(tmp_dir: str) -> None:
    """创建测试用vault目录"""
    os.makedirs(os.path.join(tmp_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(tmp_dir, "logs"), exist_ok=True)


def cleanup_test_vault(tmp_dir: str) -> None:
    """清理测试用vault目录"""
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir, ignore_errors=True)


class BaseIntegrationTest(unittest.TestCase):
    """集成测试基类"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.project_root = PROJECT_ROOT
        cls.test_vault_dir = tempfile.mkdtemp(prefix="记忆殿堂_test_")
        setup_test_vault(cls.test_vault_dir)
    
    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        cleanup_test_vault(cls.test_vault_dir)
    
    def setUp(self):
        """每个测试前初始化"""
        self.start_time = time.time()
    
    def tearDown(self):
        """每个测试后清理"""
        elapsed = time.time() - self.start_time
        print(f"  [{self.__class__.__name__}.{self._testMethodName}] 耗时: {elapsed:.3f}s")
    
    def assert_wal_entry(self, entry: Dict, expected_type: str) -> None:
        """验证WAL条目结构"""
        self.assertIn("entry_id", entry)
        self.assertIn("entry_type", entry)
        self.assertIn("transaction_id", entry)
        self.assertIn("phase", entry)
        self.assertEqual(entry["entry_type"], expected_type)
    
    def assert_record_structure(self, record: Dict) -> None:
        """验证记录结构"""
        self.assertIn("id", record)
        self.assertIn("type", record)
        self.assertIn("content", record)
        self.assertIn("created_at", record)
        self.assertIn("updated_at", record)
