"""
Centralized Kafka configuration defaults.

All Kafka broker URLs, topics, and default settings are managed here.
This eliminates hardcoded values and enables deployment-time configuration.
"""

import os
from typing import Dict, Any

# Session timeout thresholds
SESSION_TIMEOUT_THRESHOLD_MS = 10000  # 10 seconds - threshold for warning
SESSION_TIMEOUT_RECOMMENDED_MS = 6000  # 6 seconds - recommended for production
SESSION_TIMEOUT_MIN_MS = 3000  # 3 seconds - minimum acceptable
SESSION_TIMEOUT_MAX_MS = 300000  # 5 minutes - maximum acceptable

# Kafka core configuration
KAFKA_CONFIG: Dict[str, Any] = {
    # Bootstrap servers - REQUIRED
    'broker_url': os.getenv('KAFKA_BROKER_URL', 'localhost:9092'),
    
    # Topic configuration
    'topic_prefix': os.getenv('KAFKA_TOPIC_PREFIX', 'code-review'),
    'default_partitions': int(os.getenv('KAFKA_PARTITIONS', '1')),
    'default_replication_factor': int(os.getenv('KAFKA_REPLICATION_FACTOR', '1')),
    
    # Connection settings
    'connection_timeout_ms': int(os.getenv('KAFKA_TIMEOUT_MS', '30000')),
    'socket_timeout_ms': int(os.getenv('KAFKA_SOCKET_TIMEOUT_MS', '60000')),
    
    # Producer configuration
    'producer_acks': os.getenv('KAFKA_PRODUCER_ACKS', 'all'),
    'producer_retries': int(os.getenv('KAFKA_PRODUCER_RETRIES', '3')),
    'producer_batch_size': int(os.getenv('KAFKA_PRODUCER_BATCH_SIZE', '16384')),
    'producer_linger_ms': int(os.getenv('KAFKA_PRODUCER_LINGER_MS', '100')),
    'producer_compression_type': os.getenv('KAFKA_PRODUCER_COMPRESSION', 'snappy'),
    'producer_enable_idempotence': os.getenv('KAFKA_PRODUCER_IDEMPOTENCE', 'true').lower() == 'true',
    
    # Consumer configuration
    'consumer_enable_auto_commit': os.getenv('KAFKA_CONSUMER_AUTO_COMMIT', 'false').lower() == 'true',
    'consumer_auto_commit_interval_ms': int(os.getenv('KAFKA_CONSUMER_AUTO_COMMIT_INTERVAL', '5000')),
    'consumer_session_timeout_ms': int(os.getenv('KAFKA_CONSUMER_SESSION_TIMEOUT', '6000')),
    'consumer_group_id': os.getenv('KAFKA_CONSUMER_GROUP_ID', 'ai-code-review-engine'),
    
    # Security configuration
    'security_protocol': os.getenv('KAFKA_SECURITY_PROTOCOL', 'PLAINTEXT'),  # PLAINTEXT, SSL, SASL_PLAINTEXT, SASL_SSL
    'sasl_mechanism': os.getenv('KAFKA_SASL_MECHANISM', ''),  # PLAIN, SCRAM-SHA-256, SCRAM-SHA-512
    'sasl_username': os.getenv('KAFKA_SASL_USERNAME', ''),
    'sasl_password': os.getenv('KAFKA_SASL_PASSWORD', ''),
    'ssl_cafile': os.getenv('KAFKA_SSL_CAFILE', ''),
    'ssl_certfile': os.getenv('KAFKA_SSL_CERTFILE', ''),
    'ssl_keyfile': os.getenv('KAFKA_SSL_KEYFILE', ''),
}

# Kafka producer configuration ready for use
KAFKA_PRODUCER_CONFIG: Dict[str, Any] = {
    'acks': KAFKA_CONFIG['producer_acks'],
    'retries': KAFKA_CONFIG['producer_retries'],
    'batch.size': KAFKA_CONFIG['producer_batch_size'],
    'linger.ms': KAFKA_CONFIG['producer_linger_ms'],
    'compression.type': KAFKA_CONFIG['producer_compression_type'],
    'enable.idempotence': KAFKA_CONFIG['producer_enable_idempotence'],
    'bootstrap.servers': KAFKA_CONFIG['broker_url'],
}

# Kafka consumer configuration ready for use
KAFKA_CONSUMER_CONFIG: Dict[str, Any] = {
    'bootstrap.servers': KAFKA_CONFIG['broker_url'],
    'group.id': KAFKA_CONFIG['consumer_group_id'],
    'enable.auto.commit': KAFKA_CONFIG['consumer_enable_auto_commit'],
    'auto.commit.interval.ms': KAFKA_CONFIG['consumer_auto_commit_interval_ms'],
    'session.timeout.ms': KAFKA_CONFIG['consumer_session_timeout_ms'],
}

# Security configuration if needed
if KAFKA_CONFIG['security_protocol'] != 'PLAINTEXT':
    _security_config = {
        'security.protocol': KAFKA_CONFIG['security_protocol'],
    }
    
    if KAFKA_CONFIG['sasl_mechanism']:
        _security_config['sasl.mechanism'] = KAFKA_CONFIG['sasl_mechanism']
        _security_config['sasl.username'] = KAFKA_CONFIG['sasl_username']
        _security_config['sasl.password'] = KAFKA_CONFIG['sasl_password']
    
    if 'SSL' in KAFKA_CONFIG['security_protocol']:
        if KAFKA_CONFIG['ssl_cafile']:
            _security_config['ssl.ca.location'] = KAFKA_CONFIG['ssl_cafile']
        if KAFKA_CONFIG['ssl_certfile']:
            _security_config['ssl.certificate.location'] = KAFKA_CONFIG['ssl_certfile']
        if KAFKA_CONFIG['ssl_keyfile']:
            _security_config['ssl.key.location'] = KAFKA_CONFIG['ssl_keyfile']
    
    KAFKA_PRODUCER_CONFIG.update(_security_config)
    KAFKA_CONSUMER_CONFIG.update(_security_config)


def get_kafka_config() -> Dict[str, Any]:
    """
    Get current Kafka configuration.
    
    Returns:
        Dictionary with all Kafka configuration values
    """
    return KAFKA_CONFIG.copy()


def validate_kafka_broker_url(broker_url: str) -> bool:
    """
    Validate Kafka broker URL format.
    
    Args:
        broker_url: Broker URL to validate (format: host:port or host1:port1,host2:port2)
    
    Returns:
        True if valid, False otherwise
    """
    import re
    
    pattern = r'^[a-zA-Z0-9\.\-_]+:\d{1,5}(,[a-zA-Z0-9\.\-_]+:\d{1,5})*$'
    return bool(re.match(pattern, broker_url))
