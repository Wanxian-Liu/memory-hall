"""
Mimir-Core 自我感知层 (Introspection)
=====================================

为Mimir-Core提供自我感知能力，让它能：
1. 知道自己的所有模块和接口
2. 知道每个模块的状态
3. 能检测和分类问题

## 目录结构

```
introspection/
├── __init__.py              # 包初始化
├── module_map_generator.py   # 模块地图生成器
├── dependency_graph.py      # 依赖关系图生成器
├── status_api.py             # 状态监控API
├── problem_detector.py       # 问题检测器
└── README.md                 # 本文档
```

## 快速开始

### 1. 生成模块地图

```python
from introspection.module_map_generator import ModuleMapGenerator

generator = ModuleMapGenerator()
result = generator.scan()
generator.save_json()
```

输出: `introspection/module_map.json`

### 2. 生成依赖关系图

```python
from introspection.dependency_graph import DependencyGraph

graph = DependencyGraph()
graph.scan()
dot_path = graph.save_dot()
```

输出: `introspection/dependency_graph.dot`

### 3. 检查模块状态

```python
from introspection.status_api import StatusAPI

api = StatusAPI()
status = api.get_system_status()

# 检查单个模块
result = api.check_module("gateway")

# 批量检查
results = api.check_batch(["gateway", "health", "agent"])
```

### 4. 检测问题

```python
from introspection.problem_detector import ProblemDetector

detector = ProblemDetector()
report = detector.generate_report(time_window_hours=24)

# 检测反复出现的问题
recurring = detector.detect_recurring(min_count=3)
```

## CLI 使用

```bash
# 生成模块地图
python -m introspection.module_map_generator

# 生成依赖图
python -m introspection.dependency_graph

# 检查状态
python -m introspection.status_api

# 检测问题
python -m introspection.problem_detector
```

## 设计参考

1. **模块地图生成器**: 借鉴OpenSpace的skill_engine结构
2. **依赖关系图**: 基于AST分析模块导入关系
3. **状态监控API**: 对标health/checker.py的六维指标体系
4. **问题检测器**: 借鉴claw-code的LaneFailureClass分类

## 问题分类体系

```
EXECUTION_TIMEOUT      - 执行超时
EXECUTION_FAILURE      - 执行失败
RESOURCE_EXHAUSTED     - 资源耗尽
MEMORY_LEAK            - 内存泄漏
NETWORK_TIMEOUT        - 网络超时
CONNECTION_REFUSED     - 连接被拒绝
CONFIG_ERROR           - 配置错误
MISSING_DEPENDENCY     - 缺少依赖
HEALTH_DEGRADED        - 健康降级
CIRCUIT_BREAKER_OPEN   - 断路器打开
PERMISSION_DENIED      - 权限不足
```

## 扩展方式

### 注册自定义状态检查器

```python
api = StatusAPI()

def my_checker(module_name):
    from introspection.status_api import HealthCheckResult, ModuleStatus
    return HealthCheckResult(
        module=module_name,
        status=ModuleStatus.HEALTHY,
        latency_ms=1.0,
        timestamp=datetime.now().isoformat()
    )

api.register_checker("my_module", my_checker)
```

### 添加自定义问题模式

```python
detector = ProblemDetector()
detector.PATTERNS.append(
    (r"custom.*error", ProblemCategory.CONFIG_ERROR, ProblemSeverity.ERROR)
)
```

## 版本历史

- v1.0.0 (2026-04-10): 初始版本，基础功能完成
"""
