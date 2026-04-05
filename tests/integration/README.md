# 记忆殿堂v2.0 集成测试

本目录包含记忆殿堂v2.0各模块间协作的集成测试。

## 测试结构

```
tests/integration/
├── __init__.py                      # 测试基类和配置
├── conftest.py                       # pytest配置
├── run_tests.py                      # 测试运行脚本
├── README.md                         # 本文件
├── fixtures/                         # 测试fixtures
│   └── README.md
├── integration_test_gateway_wal.py   # Gateway + WAL 协作测试
├── integration_test_gateway_permission.py  # Gateway + Permission 协作测试
├── integration_test_cli_modules.py   # CLI + 各模块 协作测试
└── integration_test_plugin_modules.py # Plugin + 各模块 协作测试
```

## 测试覆盖

### 1. Gateway + WAL 协作 (`integration_test_gateway_wal.py`)

| 测试场景 | 描述 |
|---------|------|
| WAL事务完整流程 | BEGIN → PREPARE → EXECUTE → COMMIT |
| 缓存失效联动 | WAL写入触发Gateway缓存失效 |
| WAL恢复重建 | WAL重放恢复Gateway缓存状态 |
| 审计日志关联 | Gateway审计日志与WAL事务关联 |
| WAL压缩与缓存 | WAL压缩不影响Gateway活跃缓存 |
| 并发事务 | 多并发WAL事务处理 |
| 完整生命周期 | 写入→读取→更新→删除全流程 |

### 2. Gateway + Permission 协作 (`integration_test_gateway_permission.py`)

| 测试场景 | 描述 |
|---------|------|
| 读取权限检查 | Gateway.read() → Permission.check() |
| 写入权限检查 | 不同权限级别对写入的影响 |
| 删除确认机制 | 删除操作需要用户确认 |
| 外部网络权限 | http/https请求权限控制 |
| SSH配置访问 | 高危路径权限控制 |
| 权限拒绝审计 | 权限检查失败记录审计日志 |
| Permission Hook | claw-code hook override机制 |
| 围栏与权限联动 | Gateway围栏检查与权限级别 |
| 自定义规则 | 用户自定义权限规则 |
| 权限上下文构建 | Gateway构建PermissionContext |

### 3. CLI + 各模块 协作 (`integration_test_cli_modules.py`)

| 测试场景 | 描述 |
|---------|------|
| CLI Write + WAL | /memory write → WAL三段式提交 |
| CLI Read | /memory read → 存储读取 |
| CLI Search | /memory search → 搜索引擎 |
| CLI Stats | /memory stats → 各模块统计 |
| CLI Health | /memory health → 健康检查 |
| Write/Read一致性 | 写入后正确读取 |
| WAL事务回滚 | 事务失败正确回滚 |
| 批量操作 | 连续多次操作正确性 |
| CLI + Gateway缓存 | CLI操作触发Gateway缓存 |
| CLI + Gateway审计 | CLI操作记录审计日志 |
| CLI权限检查 | CLI操作前权限检查 |

### 4. Plugin + 各模块 协作 (`integration_test_plugin_modules.py`)

| 测试场景 | 描述 |
|---------|------|
| 插件注册/加载 | register → load_plugin |
| 启用/停用 | enable → disable |
| 卸载 | unload流程 |
| 重载 | reload → unload + load |
| 多插件管理 | 注册表管理多个插件 |
| Plugin调用Gateway | Plugin触发Gateway操作 |
| Plugin + Gateway缓存 | Plugin触发缓存失效 |
| Plugin + Gateway审计 | Plugin操作记录审计 |
| Plugin权限检查 | Plugin执行前权限检查 |
| Plugin权限Hook | Plugin注册自定义权限逻辑 |
| Plugin WAL事务 | Plugin执行WAL三段式提交 |
| Plugin WAL恢复 | Plugin触发WAL重放恢复 |
| Plugin WAL压缩 | Plugin触发WAL compact |
| 生命周期钩子 | 全局钩子正确触发 |
| 插件查询API | list_plugins, get_metadata |
| 插件发现机制 | PluginLoader动态发现 |

## 运行测试

### 使用pytest

```bash
cd ~/.openclaw/projects/记忆殿堂v2.0/tests/integration

# 运行所有测试
pytest -v

# 运行指定模块测试
pytest integration_test_gateway_wal.py -v

# 运行指定测试类
pytest integration_test_gateway_wal.py::TestGatewayWALCollaboration -v

# 运行指定测试用例
pytest integration_test_gateway_wal.py::TestGatewayWALCollaboration::test_gateway_wal_transaction_flow -v

# 按标记运行
pytest -m gateway -v
pytest -m wal -v
pytest -m plugin -v

# 生成覆盖率报告
pytest --cov=../../.. --cov-report=html -v
```

### 使用测试运行脚本

```bash
cd ~/.openclaw/projects/记忆殿堂v2.0/tests/integration

# 运行所有测试
python run_tests.py

# 运行指定模块测试
python run_tests.py --gateway
python run_tests.py --wal
python run_tests.py --permission
python run_tests.py --cli
python run_tests.py --plugin

# 详细输出
python run_tests.py --verbose
```

### 直接运行测试模块

```bash
cd ~/.openclaw/projects/记忆殿堂v2.0

# 运行Gateway+WAL测试
python -m tests.integration.integration_test_gateway_wal

# 运行Gateway+Permission测试
python -m tests.integration.integration_test_gateway_permission

# 运行CLI测试
python -m tests.integration.integration_test_cli_modules

# 运行Plugin测试
python -m tests.integration.integration_test_plugin_modules
```

## 测试设计原则

1. **隔离性**: 每个测试使用独立的临时目录
2. **可重复性**: 测试可以多次运行，结果一致
3. **独立性**: 测试之间没有依赖关系
4. **可观测性**: 测试输出清晰的执行信息
5. **真实性**: 测试模拟真实使用场景

## 预期结果

所有集成测试应该**全部通过**。如果有任何测试失败，说明对应模块间的协作存在问题，需要修复。

## 扩展测试

如果需要添加新的集成测试:

1. 在 `tests/integration/` 创建新的测试文件 `integration_test_<module>.py`
2. 继承 `BaseIntegrationTest` 基类
3. 实现具体的测试方法（以 `test_` 开头）
4. 使用 `assert_*` 断言验证预期行为
