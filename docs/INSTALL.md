# 记忆殿堂v2.0 安装指南

## 📋 系统要求

### 运行环境
- **Python**: 3.10+
- **操作系统**: Linux (已测试), macOS, Windows
- **内存**: 建议 4GB+
- **磁盘**: 建议 10GB+ 可用空间

### Python依赖

```
PyYAML>=6.0
pytest>=7.0
numpy>=1.24
```

## 🛠️ 安装步骤

### 1. 克隆/复制项目

```bash
# 项目位于
~/.openclaw/projects/记忆殿堂v2.0/
```

### 2. 设置Python环境

```bash
# 使用虚拟环境（推荐）
cd ~/.openclaw/projects/记忆殿堂v2.0
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install PyYAML pytest numpy
```

### 3. 验证安装

```bash
# 运行单元测试
python -m pytest tests/ -v

# 测试Gateway模块
python -c "from gateway import Gateway; print('Gateway OK')"

# 测试WAL模块
python -c "from base_wal import WALManager; print('WAL OK')"

# 测试权限模块
python -c "from permission import PermissionEngine; print('Permission OK')"
```

## 📁 目录结构

```
记忆殿堂v2.0/
├── docs/                 # 本文档目录
├── gateway/              # 网关核心
├── base_wal/             # WAL协议
├── permission/           # 权限引擎
├── config/               # 配置系统
│   └── config.yaml       # 主配置文件
├── sensory/              # 语义搜索
├── extractor/            # 内容萃取
├── normalizer/           # 去重归一化
├── classifier/           # 智能分类
├── fence/                # 安全围栏
├── health/               # 健康监控
├── cli/                   # 命令行工具
├── plugin/               # 插件系统
├── task/                 # 任务管理
├── audit/                # 审计日志
├── public/               # 公共记忆空间
├── private/              # 私有记忆空间
├── tests/                # 测试套件
└── library/              # 技能库
```

## ⚙️ 配置

### 主配置文件

配置文件位于 `config/config.yaml`:

```yaml
# 存储配置
storage:
  base_dir: "~/.openclaw/memory_hall"
  wal_dir: "wal"
  public_dir: "public"
  private_dir: "private"

# 缓存配置
cache:
  lru:
    max_size: 1000
    ttl_days: 7

# 权限配置
permission:
  default_level: "READ"
  allow_ssh_config: true
  deny_system_files: true

# 监控配置
health:
  check_interval: 300
  alert_threshold: 0.8
```

### 环境变量覆盖

配置支持环境变量覆盖，格式: `MEMORY_HALL_<SECTION>_<KEY>=value`

```bash
# 示例
export MEMORY_HALL_CACHE_LRU_TTL=7200
export MEMORY_HALL_STORAGE_BASE_DIR="/tmp/memory"
```

## 🔧 初始化数据库

```bash
# 初始化记忆存储
python -c "
from config import Config
from base_wal import WALManager
import os

config = Config()
wal_dir = os.path.expanduser(config.get('storage.wal_dir'))
os.makedirs(wal_dir, exist_ok=True)
print('初始化完成')
"
```

## ✅ 安装验证清单

- [ ] Python版本 >= 3.10
- [ ] 依赖包已安装
- [ ] 配置文件存在且有效
- [ ] 测试通过 (`python -m pytest tests/`)
- [ ] CLI工具可运行 (`python -m cli.main --help`)

## 🐛 常见问题

### 1. 导入错误

确保当前目录在Python路径中：
```bash
export PYTHONPATH="$PYTHONPATH:~/.openclaw/projects/记忆殿堂v2.0"
```

### 2. 权限错误

确保记忆目录有适当权限：
```bash
chmod -R 755 ~/.openclaw/memory_hall
```

### 3. WAL文件损坏

可以使用日志重放功能恢复：
```python
from base_wal import WALManager
wal = WALManager(...)
wal.replay()
```

---

**上一节**: [README](README.md)  
**下一节**: [使用指南](USAGE.md)
