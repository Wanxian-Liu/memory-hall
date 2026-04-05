#!/usr/bin/env python3
"""
记忆殿堂v2.0 集成测试运行器

用法:
    python run_tests.py              # 运行所有测试
    python run_tests.py --gateway    # 只运行Gateway测试
    python run_tests.py --wal        # 只运行WAL测试
    python run_tests.py --permission # 只运行Permission测试
    python run_tests.py --cli        # 只运行CLI测试
    python run_tests.py --plugin     # 只运行Plugin测试
    python run_tests.py --verbose    # 详细输出
"""

import os
import sys
import argparse

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 测试目录
TEST_DIR = os.path.join(PROJECT_ROOT, "tests", "integration")

# 导入测试模块
import unittest


def run_tests(module_name: str = None, verbose: bool = False):
    """运行测试"""
    
    # 确定要运行的测试模块
    if module_name:
        test_module = f"integration_test_{module_name}"
    else:
        test_module = None
    
    # 加载测试
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    if test_module:
        # 加载指定模块
        module_path = os.path.join(TEST_DIR, f"{test_module}.py")
        if os.path.exists(module_path):
            suite.addTests(loader.loadTestsFromName(test_module[:-3], 
                                                     importlib.import_module(f"integration_test_{module_name}")))
        else:
            print(f"测试模块不存在: {test_module}.py")
            return 1
    else:
        # 加载所有测试
        suite.addTests(loader.discover(TEST_DIR, pattern="integration_test_*.py"))
    
    # 运行测试
    verbosity = 2 if verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    # 返回状态码
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description="记忆殿堂v2.0 集成测试")
    parser.add_argument("--gateway", action="store_true", help="运行Gateway测试")
    parser.add_argument("--wal", action="store_true", help="运行WAL测试")
    parser.add_argument("--permission", action="store_true", help="运行Permission测试")
    parser.add_argument("--cli", action="store_true", help="运行CLI测试")
    parser.add_argument("--plugin", action="store_true", help="运行Plugin测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # 确定测试模块
    module_map = {
        "gateway": "gateway_wal",
        "wal": "gateway_wal",
        "permission": "gateway_permission",
        "cli": "cli_modules",
        "plugin": "plugin_modules"
    }
    
    # 确定要运行的模块
    module_name = None
    if args.gateway:
        module_name = "gateway_wal"
    elif args.wal:
        module_name = "gateway_wal"
    elif args.permission:
        module_name = "gateway_permission"
    elif args.cli:
        module_name = "cli_modules"
    elif args.plugin:
        module_name = "plugin_modules"
    
    print(f"=" * 60)
    print(f"记忆殿堂v2.0 集成测试")
    print(f"项目目录: {PROJECT_ROOT}")
    if module_name:
        print(f"测试模块: {module_name}")
    else:
        print("测试模块: 全部")
    print(f"=" * 60)
    
    return run_tests(module_name, args.verbose)


if __name__ == "__main__":
    import importlib
    sys.exit(main())
