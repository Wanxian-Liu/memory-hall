# 记忆殿堂v2.0 API参考

## 📋 模块总览

| 模块 | 路径 | 说明 |
|------|------|------|
| gateway | `gateway.gateway` | 网关核心 |
| base_wal | `base_wal.wal` | WAL协议 |
| permission | `permission.engine` | 权限引擎 |
| config | `config.loader` | 配置系统 |
| sensory | `sensory.semantic_search` | 语义搜索 |
| extractor | `extractor.extractor` | 内容萃取 |
| normalizer | `normalizer.deduplicator` | 去重归一化 |
| classifier | `classifier.classifier` | 智能分类 |
| fence | `fence.fence` | 安全围栏 |
| health | `health.health_check` | 健康监控 |
| cli | `cli.router` | CLI路由 |
| plugin | `plugin.plugin` | 插件系统 |
| task | `task.task_manager` | 任务管理 |
| audit | `audit.audit` | 审计日志 |

---

## gateway

### Gateway

系统核心网关类。

```python
from gateway import Gateway

gateway = Gateway(config_path: str = None)
```

#### 方法

##### `get_status() -> dict`

获取系统状态。

```python
status = gateway.get_status()
# 返回:
# {
#     "wal_entries": 100,
#     "active_transactions": 0,
#     "cache_size": 500,
#     "uptime_seconds": 3600
# }
```

##### `get_stats() -> dict`

获取详细统计信息。

```python
stats = gateway.get_stats()
```

---

## base_wal

### WALManager

Write-Ahead Log管理器。

```python
from base_wal import WALManager

wal = WALManager(
    wal_dir: str = "~/.openclaw/memory_hall/wal",
    max_file_size: int = 10 * 1024 * 1024
)
```

#### 方法

##### `begin_transaction() -> str`

开始新事务，返回事务ID。

```python
tx_id = wal.begin_transaction()
```

##### `prepare_write(tx_id: str, key: str, value: str) -> None`

准备写入操作（PREPARE阶段）。

```python
wal.prepare_write(tx_id, "memory/notes", "Hello World")
```

##### `execute_write(tx_id: str) -> None`

执行写入操作（EXECUTE阶段）。

```python
wal.execute_write(tx_id)
```

##### `commit(tx_id: str) -> None`

提交事务（COMMIT阶段）。

```python
wal.commit(tx_id)
```

##### `rollback(tx_id: str) -> None`

回滚事务。

```python
wal.rollback(tx_id)
```

##### `get_status() -> dict`

获取WAL状态。

```python
status = wal.get_status()
```

##### `replay() -> list`

重放WAL日志。

```python
entries = wal.replay()
```

---

## permission

### PermissionEngine

权限引擎类。

```python
from permission import PermissionEngine, PermissionLevel

engine = PermissionEngine(config_path: str = None)
```

#### PermissionLevel 枚举

```python
class PermissionLevel(IntEnum):
    READONLY = 1      # 只读
    READ = 2          # 读取
    WRITE = 3         # 写入
    DANGER_WRITE = 4  # 危险写入
    DANGER_FULL_ACCESS = 5  # 完全访问
```

#### 方法

##### `check_permission(level: PermissionLevel, operation: str, target: str) -> PermissionResult`

检查权限。

```python
result = engine.check_permission(
    level=PermissionLevel.WRITE,
    operation="write",
    target="/home/user/memory/notes"
)
# result.allowed: bool
# result.reason: str
```

##### `grant(user: str, level: PermissionLevel) -> None`

授予用户权限级别。

##### `revoke(user: str) -> None`

撤销用户权限。

---

## config

### Config

配置管理器（单例模式）。

```python
from config import Config

config = Config(config_path: str = None)
```

#### 方法

##### `get(key: str, default: Any = None) -> Any`

获取配置值（支持点号路径）。

```python
base_dir = config.get("storage.base_dir")
cache_size = config.get("cache.lru.max_size", 1000)
```

##### `set(key: str, value: Any) -> None`

设置配置值。

```python
config.set("cache.lru.max_size", 2000)
```

##### `reload() -> None`

重新加载配置。

---

## sensory

### SemanticSearch

语义搜索模块。

```python
from sensory import SemanticSearch

search = SemanticSearch(
    index_dir: str = "~/.openclaw/memory_hall/sensory"
)
```

#### 方法

##### `add_memory(id: str, content: str, metadata: dict = None) -> None`

添加记忆到索引。

```python
search.add_memory(
    id="note_001",
    content="今天开会讨论了项目计划",
    metadata={"space": "public", "tags": ["meeting"]}
)
```

##### `search(query: str, limit: int = 10, filters: dict = None) -> list`

语义搜索。

```python
results = search.search(
    query="项目安排",
    limit=5,
    filters={"space": "public"}
)
# 返回: [{"id": "...", "content": "...", "score": 0.95}, ...]
```

##### `delete_memory(id: str) -> None`

删除记忆。

---

## extractor

### Extractor

内容萃取模块。

```python
from extractor import Extractor

extractor = Extractor()
```

#### 方法

##### `extract_summary(content: str, max_length: int = 100) -> str`

提取摘要。

```python
summary = extractor.extract_summary(long_text, max_length=50)
```

##### `extract_keywords(content: str, top_k: int = 5) -> list`

提取关键词。

```python
keywords = extractor.extract_keywords(content, top_k=5)
# 返回: ["关键词1", "关键词2", ...]
```

##### `extract_entities(content: str) -> list`

提取实体。

---

## normalizer

### Deduplicator

去重归一化模块。

```python
from normalizer import Deduplicator

dedup = Deduplicator()
```

#### 方法

##### `compute_hash(content: str) -> str`

计算内容哈希。

```python
hash_value = dedup.compute_hash(content)
```

##### `is_duplicate(hash1: str, hash2: str, threshold: float = 0.9) -> bool`

检查是否重复。

```python
is_dup = dedup.is_duplicate(hash1, hash2)
```

##### `normalize(content: str) -> str`

归一化内容。

---

## classifier

### Classifier

智能分类模块。

```python
from classifier import Classifier, KnowledgeType

classifier = Classifier()
```

#### KnowledgeType 枚举

```python
class KnowledgeType(Enum):
    SKILL = "skill"        # 技能
    DOCUMENT = "document"  # 文档
    CONCEPT = "concept"    # 概念
    RULE = "rule"          # 规则
    PATTERN = "pattern"    # 模式
    WORKFLOW = "workflow"  # 工作流
```

#### 方法

##### `classify(content: str) -> ClassificationResult`

分类内容。

```python
result = classifier.classify("如何安装Python包")
# result.type: KnowledgeType
# result.confidence: float
# result.tags: list
```

##### `batch_classify(contents: list) -> list`

批量分类。

---

## fence

### Fence

安全围栏模块。

```python
from fence import Fence, SpaceType

fence = Fence()
```

#### SpaceType 枚举

```python
class SpaceType(Enum):
    PUBLIC = "public"    # 公共空间
    PRIVATE = "private"  # 私有空间
```

#### 方法

##### `check_access(space: SpaceType, user: str, operation: str) -> AccessResult`

检查空间访问权限。

```python
result = fence.check_access(
    space=SpaceType.PRIVATE,
    user="assistant",
    operation="read"
)
```

##### `get_violations(user: str) -> list`

获取违规记录。

---

## health

### HealthMonitor

健康监控模块。

```python
from health import HealthMonitor

monitor = HealthMonitor()
```

#### 方法

##### `get_report() -> HealthReport`

获取健康报告。

```python
report = monitor.get_report()
# report.overall_score: float (0-1)
# report.dimensions: dict
```

##### `check_dimension(name: str) -> dict`

检查特定维度。

```python
status = monitor.check_dimension("token_budget")
```

##### `get_alerts() -> list`

获取告警列表。

---

## cli

### CLI

命令行接口。

```bash
# 查看帮助
python -m cli.main --help

# 查看状态
python -m cli.main status

# 搜索
python -m cli.main search <query>

# 添加记忆
python -m cli.main add --key <key> --value <value>

# 列出记忆
python -m cli.main list [--space public|private]

# TUI模式
python -m cli.main tui
```

---

## plugin

### PluginManager

插件管理器。

```python
from plugin import PluginManager

manager = PluginManager(plugin_dir: str = None)
```

#### 方法

##### `load_plugin(name: str) -> Plugin`

加载插件。

##### `unload_plugin(name: str) -> None`

卸载插件。

##### `list_plugins() -> list`

列出已加载插件。

---

## audit

### AuditLogger

审计日志模块。

```python
from audit import AuditLogger, AuditEvent

logger = AuditLogger(log_dir: str = None)
```

#### AuditEvent 类

```python
event = AuditEvent(
    event_type="memory_write",
    user="assistant",
    target="/memory/notes",
    result="success",
    metadata={}
)
```

#### 方法

##### `log(event: AuditEvent) -> None`

记录事件。

##### `query(start_time: str, end_time: str, event_type: str = None) -> list`

查询审计日志。

---

## 异常类

### MemoryHallError

基础异常类。

```python
from exceptions import MemoryHallError
```

### PermissionDeniedError

权限被拒绝。

```python
from exceptions import PermissionDeniedError
```

### ValidationError

验证错误。

```python
from exceptions import ValidationError
```

---

## 📚 相关文档

- [README](README.md) - 项目概述
- [安装指南](INSTALL.md) - 详细安装步骤
- [使用指南](USAGE.md) - 功能使用示例
