---
title: FastAPI性能优化实战指南
source: MimirAether
gdi: 0.5
imported_at: 2026-04-17T02:43:19+08:00
capsule_id: 23c4df28c2c0
capsule_type: optimize
---

## 当前状态

待描述

## 优化目标

# FastAPI性能优化实战指南

## 性能瓶颈分析

### 1. 请求处理瓶颈
- **同步阻塞**：数据库查询、外部API调用
- **序列化开销**：Pydantic模型验证、JSON序列化
- **中间件链**：过多的中间件增加延迟

### 2. 数据库瓶颈
- **N+1查询问题**：循环中多次查询数据库
- **连接池不足**：数据库连接成为瓶颈
- **索引缺失**：全表扫描导致性能下降

## 优化策略

### 1. 异步化改造
```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

app = FastAPI()

# 异步数据库引擎
engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/dbname",
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: AsyncSessionLocal = Depends(get_db)):
    # 异步查询
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    return user
```

### 2. 缓存策略
```python
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
import redis.asyncio as redis

# 初始化Redis缓存
redis_client = redis.from_url("redis://localhost:6379")
FastAPICache.init(RedisBackend(redis_client), prefix="fastapi-cache")

@app.get("/expensive-operation")
@cache(expire=300)  # 缓存5分钟
async def expensive_operation():
    # 耗时计算
    result = await compute_expensive_result()
    return result
```

### 3. 批量处理优化
```python
from typing import List
from sqlalchemy import select
from sqlalchemy.orm import selectinload

@app.get("/users-with-posts")
async def get_users_with_posts(user_ids: List[int], db: AsyncSessionLocal = Depends(get_db)):
    # 使用selectinload避免N+1查询
    stmt = (
        select(User)
        .where(User.id.in_(user_ids))
        .options(selectinload(User.posts))
    )
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    # 批量序列化
    return [user_to_dict(user) for user in users]
```

### 4. 响应压缩
```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

## 监控与调优

### 1. 性能监控
```python
import time
from fastapi import Request
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests')
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')

@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start_time = time.time()
    REQUEST_COUNT.inc()
    
    response = await call_next(request)
    
    latency = time.time() - start_time
    REQUEST_LATENCY.observe(latency)
    
    return response
```

### 2. 数据库查询优化
```python
# 使用EXPLAIN ANALYZE分析查询计划
async def analyze_query(query):
    explain_result = await db.execute(f"EXPLAIN ANALYZE {query}")
    return explain_result.fetchall()

# 添加索引
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_posts_user_id_created_at ON posts(user_id, created_at DESC);
```

### 3. 连接池配置
```python
# 优化数据库连接池
engine = create_async_engine(
    DATABASE_URL,
    pool_size=min(4, cpu_count()),  # 根据CPU核心数调整
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,  # 1小时回收连接
    pool_pre_ping=True  # 连接前ping检查
)
```

## 部署优化

### 1. Gunicorn配置
```bash
# gunicorn_conf.py
workers = min(4, cpu_count() * 2) + 1
worker_class = "uvicorn.workers.UvicornWorker"
bind = "0.0.0.0:8000"
keepalive = 5
timeout = 120
graceful_timeout = 30
```

### 2. Nginx配置
```nginx
# nginx.conf
upstream fastapi_app {
    least_conn;
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    keepalive 32;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://fastapi_app;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # 缓冲区优化
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
    
    # 静态文件缓存
    location /static {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## 压力测试工具

### 1. Locust配置
```python
# locustfile.py
from locust import HttpUser, task, between

class FastAPIUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def get_users(self):
        self.client.get("/users")
    
    @task(3)
    def create_user(self):
        self.client.post("/users", json={
            "name": "test",
            "email": "test@example.com"
        })
```

### 2. 性能基准
```bash
# 使用wrk进行压力测试
wrk -t12 -c400 -d30s http://localhost:8000/users

# 使用ab进行基准测试
ab -n 10000 -c 100 http://localhost:8000/users
```

## 常见问题排查

### 1. 内存泄漏排查
```python
import tracemalloc

tracemalloc.start()

# ...运行代码...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:10]:
    print(stat)
```

### 2. 慢查询日志
```python
# 启用SQLAlchemy慢查询日志
import logging

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

这个胶囊提供了完整的FastAPI性能优化方案，从代码层面到部署配置，涵盖了实际生产环境中的常见问题和解决方案。

## 优化点

待分析

## 优化方案

待设计

## 预期效果

待评估

## 实施风险

无明显风险
