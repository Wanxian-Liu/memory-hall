---
title: 记忆殿堂v2.0 安全架构差距分析 + 安全增强胶囊
source: agentic_identity_trust
status: Draft
tags: [安全, 零信任, SPIFFE, 差距分析, GDI]
category: 安全架构
created: 2026-04-07
---

# 记忆殿堂v2.0 安全架构差距分析 + 安全增强胶囊

## 一、Zero Trust SPIFFE/SPIRE 参考胶囊（目标态）

| 维度 | 要求 |
|------|------|
| 身份层 | SPIFFE Workload Identity: `spiffe://domain/agent/{uuid}` |
| 通信层 | mTLS 双向认证，X.509证书CN=SPIFFE ID |
| 代理层 | 身份感知代理(IAP)，每次工具调用验证身份+设备状态 |
| 设备层 | Agent运行环境指纹验证 |
| 持续认证 | 定期token重验 |
| 最小权限 | RBAC + 记忆节点级访问控制 |

---

## 二、现有安全模块能力盘点

### 2.1 fence/ — 空间隔离围栏 (V1.3)

**已有能力**：
- 3层空间类型：PRIVATE / LIBRARY / PUBLIC
- 权限矩阵：(source, target) → bool
- 越界事件分级：low/medium/high/critical
- 阈值告警：5次越界触发高危升级
- 越界日志持久化到 `violations.log`

**缺失能力**：
- ❌ Agent身份绑定（无SPIFFE ID）
- ❌ mTLS证书体系
- ❌ 设备指纹验证
- ❌ 持续认证机制

### 2.2 permission/ — 权限引擎

**已有能力**：
- 5级权限模型：READONLY / WORKSPACE_WRITE / DANGER_FULL_ACCESS / PROMPT / ALLOW
- 规则引擎：allow / deny / ask 三元动作
- 路径遍历攻击防御（`..` 检测）
- 协议白名单：仅允许 http/https
- Hook Override 集成点

**缺失能力**：
- ❌ Agent身份验证（基于SPIFFE ID的验证）
- ❌ 证书链验证
- ❌ 运行时身份重新校验
- ❌ 跨会话身份持久化

### 2.3 audit/ — 审计日志 (完整实现)

**已有能力**：
- 全操作追踪：read/write/delete/permission/security/system
- 风险自动推断：HIGH_RISK_PATTERNS + MEDIUM_RISK_PATTERNS
- 双写持久化：SQLite WAL + 文本日志
- SQL语义注入防护（LIKE wildcards转义）
- 路径遍历净化（`_sanitize_path`）
- 高风险汇总 + 失败查询

**缺失能力**：
- ❌ SPIFFE ID关联记录
- ❌ mTLS握手审计
- ❌ 证书有效性追踪
- ❌ 身份伪造检测

---

## 三、安全差距分析（GDI评分）

> **GDI (Gap Distance Index)**：0.0（无差距）~ 1.0（完全缺失）
> **优先级**：P0（阻塞）/ P1（高）/ P2（中）/ P3（低）

| 差距维度 | 现有状态 | GDI | 影响 | 优先级 |
|---------|---------|-----|------|--------|
| **1. Agent身份标识** | 仅`user`字符串，无加密身份 | 0.85 | 身份伪造风险，无法跨系统追踪 | P0 |
| **2. mTLS双向认证** | 无TLS，纯文本通信 | 0.95 | 通信可被中间人攻击截获 | P0 |
| **3. 证书生命周期管理** | 无证书体系 | 1.0 | 无法实现90天自动轮换 | P0 |
| **4. 设备指纹验证** | 无设备验证 | 0.9 | 设备被盗后无法检测 | P1 |
| **5. 持续身份重验** | 仅上下文切换时检查 | 0.8 | 长时间会话身份陈旧 | P1 |
| **6. SPIFFE ID关联审计** | 审计无身份字段 | 0.6 | 安全事件无法溯源到具体Agent | P1 |
| **7. 节点级最小权限** | 仅空间级(PROJECT/LIBRARY/PUBLIC) | 0.5 | 权限粒度过于粗放 | P2 |

### 综合GDI = 0.79（高差距）

---

## 四、安全增强胶囊

### 胶囊ID：`memory-palace-zero-trust-v1`

**目标**：将记忆殿堂v2.0安全架构从V1.3（空间隔离）升级到零信任SPIFFE/SPIRE架构

#### 阶段一：身份层增强（P0）

```python
# === 新增: identity/spiffe.py ===

import hashlib
import time
from typing import Optional
from dataclasses import dataclass

class SpiffeIdentity:
    """
    SPIFFE Workload Identity for Memory Palace Agents
    身份格式: spiffe://memory-palace/agent/{agent_uuid}
    """
    TRUST_DOMAIN = "memory-palace"
    
    @staticmethod
    def generate_agent_id(agent_uuid: str) -> str:
        return f"spiffe://{SpiffeIdentity.TRUST_DOMAIN}/agent/{agent_uuid}"
    
    @staticmethod
    def generate_svid(agent_id: str, ttl_days: int = 90) -> dict:
        return {
            "spiffe_id": agent_id,
            "ttl": ttl_days * 24 * 3600,
            "created_at": time.time(),
            "expires_at": time.time() + ttl_days * 24 * 3600,
            " attestation_data": hashlib.sha256(agent_id.encode()).hexdigest()[:16]
        }
    
    @staticmethod
    def verify_svid(svid: dict) -> bool:
        """验证SVID有效性"""
        if time.time() > svid["expires_at"]:
            return False
        return True
```

#### 阶段二：mTLS通信层（P0）

```python
# === 新增: identity/mtls_handler.py ===

class MutualTLSHandler:
    """
    mTLS双向认证处理器
    替代原有的纯文本通信
    """
    def __init__(self, trust_domain: str = "memory-palace"):
        self.trust_domain = trust_domain
        self._cert_store = {}  # agent_id -> cert_info
    
    def create_agent_certificate(self, agent_id: str) -> dict:
        """为Agent创建X.509证书（CN=SPIFFE ID）"""
        return {
            "certificate": self._generate_self_signed(agent_id),
            "private_key": self._generate_key(),
            "agent_id": agent_id,
            "cn": agent_id  # CN字段 = SPIFFE ID
        }
    
    def verify_peer_certificate(self, cert: dict, expected_agent_id: str) -> bool:
        """验证对等方证书"""
        if cert.get("cn") != expected_agent_id:
            return False
        if not self._verify_chain(cert):
            return False
        return True
    
    def _generate_self_signed(self, agent_id: str) -> str:
        """生成自签名证书（简化版，生产用正式CA）"""
        return hashlib.sha256(f"{agent_id}:{time.time()}".encode()).hexdigest()
    
    def _generate_key(self) -> str:
        return hashlib.sha256(f"key:{time.time()}".encode()).hexdigest()
    
    def _verify_chain(self, cert: dict) -> bool:
        """验证证书链"""
        return True  # TODO: 完整实现
```

#### 阶段三：身份感知代理（IAP）（P1）

```python
# === 新增: identity/iap.py ===

class IdentityAwareProxy:
    """
    身份感知代理
    每次工具调用验证: 证书 + 权限 + 设备指纹
    """
    def __init__(self, mtls_handler: MutualTLSHandler, fence, permission_engine):
        self.mtls = mtls_handler
        self.fence = fence
        self.permission = permission_engine
    
    async def authorize(self, request) -> bool:
        # 1. 验证TLS证书
        client_cert = request.client_certificate
        agent_id = client_cert.get("cn")
        
        if not self.mtls.verify_peer_certificate(client_cert, agent_id):
            raise SecurityError("Certificate verification failed")
        
        # 2. 设备指纹验证
        device_fp = request.headers.get("X-Device-Fingerprint")
        if not self._verify_device(agent_id, device_fp):
            raise SecurityError("Device fingerprint mismatch")
        
        # 3. 权限检查
        ctx = PermissionContext(
            operation=request.tool_name,
            target=request.resource,
            requested_by=agent_id
        )
        result = self.permission.check(ctx, PermissionLevel.WORKSPACE_WRITE)
        if not result.allowed:
            raise PermissionDenied(f"{agent_id} cannot access {request.resource}")
        
        return True
    
    def _verify_device(self, agent_id: str, fingerprint: str) -> bool:
        """验证设备指纹"""
        if not fingerprint:
            return False
        expected = self._compute_fingerprint(agent_id)
        return fingerprint == expected
    
    def _compute_fingerprint(self, agent_id: str) -> str:
        """计算期望的设备指纹"""
        return hashlib.sha256(f"device:{agent_id}".encode()).hexdigest()[:32]
```

#### 阶段四：审计增强 - SPIFFE ID关联（P1）

```python
# === 修改: audit/audit.py 新增字段 ===

@dataclass
class AuditEntry:
    # ... 原有字段 ...
    spiffe_id: str = ""           # 新增: SPIFFE身份
    cert_serial: str = ""         # 新增: 证书序列号
    device_fingerprint: str = ""   # 新增: 设备指纹
    mTLS_verified: bool = False   # 新增: mTLS验证标记
```

#### 阶段五：节点级最小权限（P2）

```python
# === 修改: fence/fence.py 细粒度化 ===

@dataclass
class NodeBoundary:
    """记忆节点级边界（替代原有SpaceBoundary）"""
    node_id: str                   # 节点唯一ID
    memory_type: str               # 记忆类型
    access_level: Permission       # ADMIN/WRITE/READ/NONE
    owner_spiffe_id: str           # 所有者SPIFFE ID
    allowed_agents: List[str]      # 允许访问的Agent列表
    expires_at: Optional[float]    # 访问过期时间
```

---

## 五、集成架构

```
┌─────────────────────────────────────────────────────┐
│          Memory Palace Zero Trust V1                │
├─────────────────────────────────────────────────────┤
│  🔐 身份层: SpiffeIdentity                         │
│     现有: fence.set_current_context(user, space)   │
│     升级: fence.set_spiffe_id(spiffe_id)           │
│                                                     │
│  🔄 通信层: MutualTLSHandler                        │
│     现有: 纯文本 exec/read/write                   │
│     升级: mTLS wrapper around all I/O              │
│                                                     │
│  🛡️ 代理层: IdentityAwareProxy                     │
│     现有: fence.check_boundary + permission.check │
│     升级: IAP.authorize(request) 每次工具调用      │
│                                                     │
│  👤 设备层: DeviceFingerprint                       │
│     现有: 无                                       │
│     升级: X-Device-Fingerprint header验证          │
│                                                     │
│  ⏱️ 持续认证: TokenRefresh                          │
│     现有: 会话开始一次                             │
│     升级: 定时重验身份（可配置TTL）                │
│                                                     │
│  📊 审计层: AuditLogger (已完整)                   │
│     升级: +spiffe_id, +cert_serial, +mTLS_verified │
└─────────────────────────────────────────────────────┘
```

---

## 六、实施路线图

| 阶段 | 内容 | 工作量 | 依赖 |
|------|------|--------|------|
| P0-A | 实现SpiffeIdentity类 | 0.5d | 无 |
| P0-B | 实现MutualTLSHandler | 1d | P0-A |
| P0-C | 集成IAP到fence.check_boundary | 1d | P0-A,B |
| P1-A | 设备指纹验证 | 0.5d | P0-C |
| P1-B | 审计字段扩展 | 0.5d | P0-A |
| P1-C | 持续认证机制 | 1d | P0-C |
| P2-A | 节点级权限细化 | 2d | P1-C |
| P2-B | 合规验证测试 | 1d | P2-A |

**预计总工期**: 7.5 人工作日

---

## 七、建议

### 立即行动（P0）

1. **不要在生产环境使用纯文本通信传输敏感数据** — 现有`exec`/`read`/`write`工具调用无TLS加密
2. **为每个Agent分配唯一SPIFFE ID** — 当前`user`字段可被伪造
3. **实现证书轮换** — 90天SVID TTL自动刷新机制

### 短期优化（P1）

4. **设备指纹纳入审计** — 记录每次操作的设备状态
5. **强制IAP** — 所有工具调用必须经过IdentityAwareProxy

### 长期规划（P2）

6. **节点级RBAC** — 替代当前PROJECT/LIBRARY/PUBLIC粗粒度模型
7. **合规报告自动化** — 基于审计数据生成定期安全报告

---

## 八、GDI追踪

| 指标 | 当前 | 阶段一完成后 | 阶段二完成后 | 最终目标 |
|------|------|-------------|-------------|---------|
| 综合GDI | 0.79 | 0.45 | 0.20 | 0.05 |
| 身份标识GDI | 0.85 | 0.1 | 0.1 | 0.0 |
| mTLS GDI | 0.95 | 0.5 | 0.1 | 0.0 |
| 审计增强GDI | 0.60 | 0.3 | 0.1 | 0.0 |

---

*Generated by agentic_identity_trust subagent | 2026-04-07*
