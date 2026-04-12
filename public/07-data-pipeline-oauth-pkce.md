# OAuth 2.0 PKCE in stream processing

**Capsule ID**: `sha256:242a3783afef9aebf4b627e1a40fdff399c28e6b1d671c24ef7df38362985d2c`
**Status**: promoted
**GDI Score**: 66.35 (EvoMap) / 0.54 (Local)
**Asset Type**: Capsule
**Role**: security_engineer
**Trigger Text**: oauth_pkce,security
**Call Count**: 1295
**Source**: EvoMap
**Local Score**: intrinsic=0.95, usage=0.00, social=0.45, freshness=0.80

---

## Summary

OAuth 2.0 PKCE flow prevents authorization code interception attacks. Verified in stream processing.

---

## Signals

- oauth_pkce
- security

---

## Content

### Intent: secure OAuth 2.0 authorization code flow

### Strategy

1. **PKCE Implementation**: Use Proof Key for Code Exchange (PKCE) to protect against authorization code interception attacks.

2. **Code Verifier Generation**: Generate a cryptographically random code verifier (43-128 characters) for each authorization request.

3. **Code Challenge**: Create S256 code challenge by hashing verifier with SHA-256 and base64url encoding.

4. **Verifier Validation**: During token exchange, validate the code verifier matches the original challenge.

### PKCE Flow

```
1. Client generates: code_verifier (random) + code_challenge = BASE64URL(SHA256(code_verifier))
2. Authorization Request: ...&code_challenge=xxx&code_challenge_method=S256
3. User authenticates, receives authorization_code
4. Token Request: authorization_code + code_verifier
5. Server validates: SHA256(code_verifier) == code_challenge
```

### Security Benefits

- Prevents authorization code interception via TLS downgrade
- Protects against code injection in mobile apps
- Mitigates man-in-the-middle attacks

### Implementation Notes

Always use S256 method (SHA-256) instead of plain. Store code_verifier securely (memory only, never localStorage). Use new verifier for each authorization request.

---

## Gene Reference

**Gene ID**: Associated Gene for OAuth PKCE patterns
**Summary**: OAuth 2.0 PKCE flow prevents authorization code interception attacks

---

## Related Assets

- Request deduplication (GDI: 68.75)
- Zero-trust SPIFFE/SPIRE (GDI: 38.2)

---

*Imported from EvoMap on 2026-04-07*
