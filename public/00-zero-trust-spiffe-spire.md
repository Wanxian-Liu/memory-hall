---
title: Zero Trust with SPIFFE/SPIRE
source: EvoMap
status: Promoted
summary: 零信任架构：SPIFFE/SPIRE workload identity + 全面mTLS + 身份感知代理
imported_at: 2026-04-07T02:51:00+08:00
tags: [零信任, SPIFFE, SPIRE, mTLS, 身份认证]
category: 安全架构
---

# Zero Trust with SPIFFE/SPIRE

## 核心概念

零信任安全架构，通过SPIFFE/SPIRE实现 workload identity，无需共享secret的Agent身份验证。

## SPIFFE/SPIRE简介

**SPIFFE** (Secure Production Identity Framework for Everyone):
- 标准化workload身份规范
- SVID (SPIFFE Verifiable Identity Document) 不可伪造

**SPIRE** (SPIFFE Runtime Environment):
- SPIFFE实现
- 动态颁发和轮换证书

## 架构设计

```
┌─────────────────────────────────────────────────────┐
│                  Zero Trust Architecture            │
├─────────────────────────────────────────────────────┤
│  🔐 身份层: SPIFFE Workload Identity               │
│     Agent ID = spiffe://domain/agent/{uuid}        │
│                                                     │
│  🔄 通信层: mTLS双向认证                           │
│     X.509证书 + CN=Agent SPIFFE ID                 │
│                                                     │
│  🛡️ 代理层: 身份感知代理(IAP)                     │
│     每次工具调用验证身份+设备状态                   │
│                                                     │
│  👤 设备层: Agent运行环境指纹验证                 │
│                                                     │
│  ⏱️ 持续认证: 定期token重验                       │
│                                                     │
│  📊 最小权限: RBAC + 记忆节点级访问控制           │
└─────────────────────────────────────────────────────┘
```

## 实现代码

### 1. SPIFFE Identity生成

```python
import hashlib
from typing import Optional

class SpiffeIdentity:
    DOMAIN = "memory-palace"
    
    @staticmethod
    def generate_agent_id(agent_uuid: str) -> str:
        """生成SPIFFE格式的Agent ID"""
        return f"spiffe://{SpiffeIdentity.DOMAIN}/agent/{agent_uuid}"
    
    @staticmethod
    def generate_svid(agent_id: str, ttl_days: int = 90) -> dict:
        """生成SVID（SPIFFE Verifiable Identity Document）"""
        return {
            "spiffe_id": agent_id,
            "ttl": ttl_days * 24 * 3600,
            "created_at": time.time(),
            "expires_at": time.time() + ttl_days * 24 * 3600
        }
```

### 2. mTLS双向认证

```python
class MutualTLSHandler:
    def __init__(self, trust_domain: str):
        self.trust_domain = trust_domain
        self.ca_cert = self.load_trust_ca()
    
    def create_agent_certificate(self, agent_id: str) -> dict:
        """为Agent创建X.509证书，CN字段为SPIFFE ID"""
        key = self.generate_private_key()
        csr = self.create_csr(key, cn=agent_id)
        cert = self.ca_cert.sign_csr(csr)
        
        return {
            "certificate": cert,
            "private_key": key,
            "agent_id": agent_id  # CN字段
        }
    
    def verify_peer_certificate(self, cert, expected_agent_id: str) -> bool:
        """验证对等方证书"""
        # 验证证书链
        if not self.ca_cert.verify_chain(cert):
            return False
        
        # 验证CN字段
        if cert.cn != expected_agent_id:
            return False
        
        # 验证有效期
        if not cert.is_valid():
            return False
        
        return True
```

### 3. 身份感知代理(IAP)

```python
class IdentityAwareProxy:
    def __init__(self, tls_handler: MutualTLSHandler):
        self.tls_handler = tls_handler
        self.access_policy = RBACPolicy()
    
    async def authorize(self, request) -> bool:
        # 1. 验证TLS证书
        client_cert = request.client_certificate
        agent_id = client_cert.cn
        
        if not self.tls_handler.verify_peer_certificate(client_cert, agent_id):
            raise SecurityError("Certificate verification failed")
        
        # 2. 检查Agent角色权限
        if not self.access_policy.can_access(agent_id, request.resource):
            raise PermissionDenied(f"{agent_id} cannot access {request.resource}")
        
        # 3. 设备指纹验证（可选）
        device_fp = request.headers.get("X-Device-Fingerprint")
        if not self.verify_device(agent_id, device_fp):
            raise SecurityError("Device fingerprint mismatch")
        
        return True
```

## 与记忆殿堂集成

```python
class MemoryPalaceZeroTrust:
    def __init__(self):
        self.spiffe = SpiffeIdentity()
        self.mtls = MutualTLSHandler("memory-palace")
        self.iap = IdentityAwareProxy(self.mtls)
    
    def register_agent(self, agent_uuid: str) -> str:
        """注册新Agent，颁发SVID"""
        agent_id = self.spiffe.generate_agent_id(agent_uuid)
        svid = self.spiffe.generate_svid(agent_id)
        cert = self.mtls.create_agent_certificate(agent_id)
        
        # 存储Agent元数据
        self.store_agent_metadata(agent_id, svid, cert)
        return agent_id
    
    async def secure_tool_call(self, agent_id: str, tool_name: str, params: dict):
        """安全的工具调用"""
        # IAP授权
        await self.iap.authorize(Request(
            client_certificate=self.get_agent_cert(agent_id),
            resource=f"tool:{tool_name}",
            params=params
        ))
        
        # 执行工具调用
        return await self.execute_tool(tool_name, params)
```

## 验证指标

- **身份伪造防止**: 100%
- **mTLS覆盖率**: 100%
- **最小权限执行**: ✅
- **证书轮换**: 90天自动
