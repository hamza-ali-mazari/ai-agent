# Configuration Migration Guide

## Summary of Changes

This document describes the security and maintainability improvements made to the AI Code Review Engine's configuration system. All changes are backward-compatible with no breaking changes to public APIs or function signatures.

### **Issues Fixed**

#### 1. **Hardcoded Broker URLs Eliminated** ✅
- **Before**: `localhost:9092` was hardcoded in 8+ places across codebase
- **After**: Centralized in `config/kafka_defaults.py`, uses `KAFKA_BROKER_URL` env var
- **Impact**: Single point of configuration, deployment-time flexibility

#### 2. **CORS Security Vulnerability Fixed** ✅
- **Before**: `allow_origins=["*"]` exposed to CSRF attacks
- **After**: Environment-based whitelist with `ALLOWED_CORS_ORIGINS`
- **Impact**: Prevents cross-site request forgery attacks

#### 3. **Environment Variable Support** ✅
- **Before**: Services and Kafka had hardcoded defaults that couldn't be overridden
- **After**: All configuration reads from environment variables with sensible defaults
- **Impact**: Container/Kubernetes ready, no code changes needed for deployments

#### 4. **Kafka Configuration Validation Enhanced** ✅
- **Before**: Only validated basic broker/topic settings
- **After**: Added producer, consumer, and security validation
- **Impact**: Catches misconfigurations before they cause data loss

#### 5. **Kafka Security Configuration** ✅
- **Before**: No security protocol validation (PLAINTEXT was silent)
- **After**: Validates SSL/TLS and SASL authentication setup
- **Impact**: Enforces encryption in production

#### 6. **Sensitive Data Logging Removed** ✅
- **Before**: Azure OpenAI endpoint logged in plaintext
- **After**: Masked sensitive configuration in logs
- **Impact**: Reduces information disclosure risk

---

## New Configuration Files

- **config/kafka_defaults.py** - Centralized Kafka config (broker, producer, consumer, security)
- **config/service_endpoints.py** - Service URLs and CORS management

---

## Environment Variables - Complete Reference

### Kafka Core Configuration
```bash
# Broker connection (REQUIRED FOR PRODUCTION)
KAFKA_BROKER_URL=broker1:9092,broker2:9092,broker3:9092

# Topic settings
KAFKA_TOPIC_PREFIX=code-review
KAFKA_PARTITIONS=3
KAFKA_REPLICATION_FACTOR=2

# Connection timeouts
KAFKA_TIMEOUT_MS=30000
KAFKA_SOCKET_TIMEOUT_MS=60000
```

### Kafka Producer Configuration
```bash
# Durability and reliability
KAFKA_PRODUCER_ACKS=all           # Wait for all replicas
KAFKA_PRODUCER_RETRIES=3           # Retry transient failures
KAFKA_PRODUCER_BATCH_SIZE=16384    # 16KB batches
KAFKA_PRODUCER_LINGER_MS=100       # Max 100ms to accumulate batch
KAFKA_PRODUCER_COMPRESSION=snappy  # Compress batches
KAFKA_PRODUCER_IDEMPOTENCE=true    # Exactly-once delivery
```

### Kafka Consumer Configuration
```bash
# Auto-commit is DISABLED by default (requires manual commit)
KAFKA_CONSUMER_AUTO_COMMIT=false
KAFKA_CONSUMER_AUTO_COMMIT_INTERVAL=5000
KAFKA_CONSUMER_SESSION_TIMEOUT=6000
KAFKA_CONSUMER_GROUP_ID=ai-code-review-engine
```

### Kafka Security (Production Only)
```bash
# Security protocol
KAFKA_SECURITY_PROTOCOL=SASL_SSL

# SASL Authentication
KAFKA_SASL_MECHANISM=SCRAM-SHA-256
KAFKA_SASL_USERNAME=your_username
KAFKA_SASL_PASSWORD=your_password

# SSL Certificates
KAFKA_SSL_CAFILE=/etc/kafka/ssl/ca-cert
KAFKA_SSL_CERTFILE=/etc/kafka/ssl/client-cert
KAFKA_SSL_KEYFILE=/etc/kafka/ssl/client-key
```

### Service Endpoints
```bash
# API URLs (for inter-service communication)
AI_REVIEW_API_URL=http://localhost:8000
CHATBOT_API_URL=http://localhost:10000

# CORS Origins (comma-separated)
ALLOWED_CORS_ORIGINS=https://app.yourdomain.com,https://admin.yourdomain.com

# Environment
ENVIRONMENT=production
```

---

## Migration Steps for Existing Deployments

### Step 1: Update Your .env File
Copy from `.env.example` and add your specific values:
```bash
KAFKA_BROKER_URL=your-kafka-cluster:9092
KAFKA_PRODUCER_ACKS=all
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=SCRAM-SHA-256
```

### Step 2: Test Configuration
```bash
# The configuration will be validated on startup
python app.py

# Look for log messages:
# INFO - Kafka broker configured: your-kafka-cluster:9092
# INFO - Kafka topic prefix: code-review
```

### Step 3: Docker Deployment
No code changes needed! Pass environment variables at runtime:
```bash
docker run -e KAFKA_BROKER_URL=kafka:9092 \
           -e KAFKA_SECURITY_PROTOCOL=SASL_SSL \
           -e KAFKA_SASL_MECHANISM=SCRAM-SHA-256 \
           ai-code-review:latest
```

### Step 4: Kubernetes Deployment
Use ConfigMap for non-secrets and Secrets for credentials:

```bash
kubectl create configmap kafka-config \
  --from-literal=KAFKA_BROKER_URL=kafka-cluster:9092 \
  --from-literal=KAFKA_SECURITY_PROTOCOL=SASL_SSL

kubectl create secret generic kafka-secrets \
  --from-literal=KAFKA_SASL_USERNAME=user \
  --from-literal=KAFKA_SASL_PASSWORD=pass
```

Then reference in your deployment:
```yaml
envFrom:
  - configMapRef:
      name: kafka-config
  - secretRef:
      name: kafka-secrets
```

---

## Production Checklist

Kafka configuration is validated on startup. Review validation errors in logs if startup fails.

- [ ] `ENVIRONMENT=production` set
- [ ] `KAFKA_BROKER_URL` configured with actual cluster
- [ ] `KAFKA_SECURITY_PROTOCOL=SASL_SSL` or `SSL`
- [ ] SASL credentials configured securely (via secrets manager)
- [ ] `KAFKA_PRODUCER_ACKS=all` for durability
- [ ] `KAFKA_CONSUMER_AUTO_COMMIT=false` (manual commits)
- [ ] `ALLOWED_CORS_ORIGINS` whitelist set (not `*`)
- [ ] SSL certificates mounted for KAFKA_SSL_* variables
- [ ] Application logs reviewed for `Kafka broker configured` message

---

## Troubleshooting

If configuration fails on startup:
1. Check application logs for validation error messages
2. Verify all required environment variables are set
3. Review the environment variable reference in sections above

### "Invalid Kafka broker URL format"
**Cause**: Broker URL format incorrect
**Fix**: Use `host:port` or `host1:port1,host2:port2`
```bash
# ✅ Valid
KAFKA_BROKER_URL=localhost:9092
KAFKA_BROKER_URL=kafka1:9092,kafka2:9092,kafka3:9092

# ❌ Invalid
KAFKA_BROKER_URL=localhost  # Missing port
KAFKA_BROKER_URL=localhost:invalid  # Invalid port
```

### "SASL enabled but mechanism not set"
**Cause**: SASL_SSL protocol configured but no SASL_MECHANISM
**Fix**: Add SASL configuration
```bash
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=SCRAM-SHA-256
KAFKA_SASL_USERNAME=user
KAFKA_SASL_PASSWORD=pass
```

### "No encryption configured for Kafka messages"
**Cause**: Running in PLAINTEXT mode (development default)
**Fix**: For production, enable SSL
```bash
KAFKA_SECURITY_PROTOCOL=SSL
KAFKA_SSL_CAFILE=/path/to/ca-cert
```

---

## Security Best Practices

1. **Never commit secrets to Git**
   - Use `.env` (git-ignored)
   - Use secrets manager in production
   - Use Kubernetes Secrets

2. **CORS Configuration**
   - Development: `http://localhost:3000`
   - Production: Specific domain list
   - Never use `*` in production

3. **Kafka Security**
   - Development: PLAINTEXT OK
   - Production: SASL_SSL + certificates required
   - Monitor broker logs for auth failures

4. **Logging**
   - Set `LOG_LEVEL=WARNING` in production
   - Monitor for `Critical issues found` warnings
   - Review Kafka validation output on startup


