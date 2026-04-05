# 记忆殿堂v2.0 使用指南

## 📖 概述

本指南介绍记忆殿堂v2.0的核心功能使用方法。

## 1. 基础模块使用

### 1.1 Gateway模块

Gateway是系统的核心入口：

```python
from gateway import Gateway

# 初始化Gateway
gateway = Gateway()

# 获取状态
status = gateway.get_status()
print(f"WAL条目数: {status['wal_entries']}")
print(f"活跃事务: {status['active_transactions']}")
```

### 1.2 WAL协议

Write-Ahead Log三段式提交流程：

```python
from base_wal import WALManager, begin, prepare, execute, commit

# 方式1: 手动事务
wal = WALManager()
tx_id = wal.begin_transaction()
wal.prepare_write(tx_id, "memory/notes", "Hello World")
wal.execute_write(tx_id)
wal.commit(tx_id)

# 方式2: 快捷函数
begin()          # 开始事务
prepare(...)     # 准备写入
execute(...)     # 执行写入
commit()         # 提交
```

### 1.3 权限引擎

五级权限检查：

```python
from permission import PermissionEngine, check_permission, PermissionLevel

engine = PermissionEngine()

# 检查权限
result = engine.check_permission(
    level=PermissionLevel.WRITE,
    operation="write",
    target="/home/user/memory/notes"
)

if result.allowed:
    print("权限已授权")
else:
    print(f"权限被拒绝: {result.reason}")
```

**权限级别（从低到高）**:
| 级别 | 值 | 说明 |
|------|-----|------|
| READONLY | 1 | 只读 |
| READ | 2 | 读取 |
| WRITE | 3 | 写入 |
| DANGER_WRITE | 4 | 危险写入 |
| DANGER_FULL_ACCESS | 5 | 完全访问 |

## 2. 核心功能

### 2.1 通感搜索 (语义搜索)

```python
from sensory import SemanticSearch

search = SemanticSearch()

# 添加记忆
search.add_memory("meeting_notes", "今天开会讨论了项目计划")

# 语义搜索
results = search.search("项目安排")
for result in results:
    print(f"{result['id']}: {result['score']:.2f}")
```

### 2.2 内容萃取

```python
from extractor import Extractor

extractor = Extractor()

# 萃取内容
content = """
记忆殿堂是一个智能记忆系统。
它可以存储、检索和分析信息。
"""

summary = extractor.extract_summary(content, max_length=50)
keywords = extractor.extract_keywords(content)
print(f"摘要: {summary}")
print(f"关键词: {keywords}")
```

### 2.3 去重归一化

```python
from normalizer import Deduplicator

dedup = Deduplicator()

# 检查重复
content1 = "这是测试内容"
content2 = "这是测试内容"  # 完全相同

hash1 = dedup.compute_hash(content1)
hash2 = dedup.compute_hash(content2)
is_dup = dedup.is_duplicate(hash1, hash2)
print(f"重复: {is_dup}")
```

### 2.4 智能分类

```python
from classifier import Classifier, KnowledgeType

classifier = Classifier()

# 分类记忆
result = classifier.classify("如何安装Python包")
print(f"类型: {result.type}")        # skill
print(f"置信度: {result.confidence:.2f}")  # 0.95
print(f"标签: {result.tags}")        # ["programming", "python"]
```

**知识类型**:
- `skill` - 技能/能力
- `document` - 文档
- `concept` - 概念
- `rule` - 规则
- `pattern` - 模式
- `workflow` - 工作流

### 2.5 安全围栏

```python
from fence import Fence, SpaceType

fence = Fence()

# 检查空间访问
result = fence.check_access(
    space=SpaceType.PRIVATE,
    user="assistant",
    operation="read"
)

if result.allowed:
    print("可以访问私有空间")
else:
    print(f"访问被拒绝: {result.reason}")
```

### 2.6 健康监控

```python
from health import HealthMonitor

monitor = HealthMonitor()

# 获取健康报告
report = monitor.get_report()
print(f"总体评分: {report.overall_score:.2f}")
print(f"各维度: {report.dimensions}")

# 检查具体指标
status = monitor.check_dimension("token_budget")
print(f"Token预算状态: {status}")
```

## 3. CLI工具

### 3.1 基本命令

```bash
# 查看帮助
python -m cli.main --help

# 查看状态
python -m cli.main status

# 搜索记忆
python -m cli.main search "项目计划"

# 添加记忆
python -m cli.main add --key notes --value "今天完成报告"

# 列出记忆
python -m cli.main list --space public
```

### 3.2 交互模式

```bash
# 启动交互式TUI
python -m cli.main tui
```

## 4. 插件系统

### 4.1 加载插件

```python
from plugin import PluginManager

manager = PluginManager()

# 加载插件
manager.load_plugin("my_plugin")

# 列出已加载插件
plugins = manager.list_plugins()
print(f"已加载: {plugins}")
```

### 4.2 创建插件

```python
# my_plugin.py
from plugin import Plugin

class MyPlugin(Plugin):
    name = "my_plugin"
    version = "1.0.0"
    
    def execute(self, context):
        print("插件执行中...")
        return {"result": "success"}
```

## 5. 审计日志

```python
from audit import AuditLogger, AuditEvent

logger = AuditLogger()

# 记录事件
logger.log(AuditEvent(
    event_type="memory_write",
    user="assistant",
    target="/memory/notes",
    result="success"
))

# 查询审计日志
events = logger.query(
    start_time="2026-04-01",
    end_time="2026-04-06",
    event_type="memory_write"
)
```

## 6. 最佳实践

### 6.1 记忆存储

```python
# 推荐：使用WAL协议确保数据一致性
wal = WALManager()
tx_id = wal.begin_transaction()
try:
    wal.prepare_write(tx_id, key, value)
    wal.execute_write(tx_id)
    wal.commit(tx_id)
except Exception as e:
    wal.rollback(tx_id)
    raise e
```

### 6.2 权限检查

```python
# 始终在敏感操作前检查权限
if not check_permission(PermissionLevel.WRITE, "write", target):
    raise PermissionError("无写权限")
```

### 6.3 搜索优化

```python
# 使用精确查询结合语义搜索
results = search.search(
    query="项目计划",
    filters={"space": "public"},
    limit=10
)
```

## 📚 相关文档

- [README](README.md) - 项目概述
- [安装指南](INSTALL.md) - 详细安装步骤
- [API参考](API.md) - 完整API文档
