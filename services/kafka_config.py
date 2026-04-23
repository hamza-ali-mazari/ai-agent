"""
Kafka Configuration Handler for AI Code Review Engine

Optimized message suggestions and event streaming for code review workflows.
"""

import json
import logging
import re
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
from config.kafka_defaults import (
    KAFKA_CONFIG,
    SESSION_TIMEOUT_THRESHOLD_MS,
    SESSION_TIMEOUT_RECOMMENDED_MS,
    validate_kafka_broker_url,
)

logger = logging.getLogger(__name__)


class ReviewEventType(str, Enum):
    REVIEW_STARTED = "review:started"
    ANALYSIS_COMPLETE = "review:analysis_complete"
    SECURITY_ISSUE_FOUND = "review:security_issue"
    APPROVAL_READY = "review:approval_ready"
    MERGE_REQUESTED = "review:merge_requested"
    REVIEW_FAILED = "review:failed"


class KafkaConfigHandler:
    """Handles Kafka event streaming and optimized message suggestions."""

    def __init__(self, broker_url: Optional[str] = None):
        # Use provided URL, environment variable, or default from config
        self.broker_url = (
            broker_url
            or os.getenv('KAFKA_BROKER_URL')
            or KAFKA_CONFIG['broker_url']
        )
        
        # Validate broker URL format
        if not validate_kafka_broker_url(self.broker_url):
            raise ValueError(
                f'Invalid Kafka broker URL format: {self.broker_url}. '
                f'Expected format: "host:port" or "host1:port1,host2:port2". '
                f'Ports must be 1-65535. '
                f'Set KAFKA_BROKER_URL environment variable for custom values.'
            )
        
        self.topic_prefix = os.getenv('KAFKA_TOPIC_PREFIX') or KAFKA_CONFIG['topic_prefix']
        self.events = []
        self.config_validation = {}
        
        logger.info(f"Kafka broker configured: {self.broker_url}")
        logger.info(f"Kafka topic prefix: {self.topic_prefix}")

    def validate_kafka_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Kafka configuration and provide detailed feedback.
        
        Args:
            config: Dictionary with kafka configuration
            
        Returns:
            Dictionary with validation results and recommendations
        """
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "config_details": {},
            "failure_scenarios": []
        }
        
        # 1. Validate Broker URL
        broker_url = config.get("broker_url", "").strip()
        if not broker_url:
            validation_result["errors"].append({
                "field": "broker_url",
                "message": "Broker URL is required",
                "example": "localhost:9092 or kafka-broker.example.com:9092"
            })
            validation_result["is_valid"] = False
        else:
            broker_validation = self._validate_broker_url(broker_url)
            if not broker_validation["valid"]:
                validation_result["errors"].extend(broker_validation["errors"])
                validation_result["is_valid"] = False
            else:
                validation_result["config_details"]["broker_url"] = broker_validation["details"]
        
        # 2. Validate Topic Name
        topic = config.get("topic_prefix", "").strip()
        if not topic:
            validation_result["errors"].append({
                "field": "topic_prefix",
                "message": "Topic name is required",
                "example": "code-review or code_review_events"
            })
            validation_result["is_valid"] = False
        else:
            topic_validation = self._validate_topic_name(topic)
            if not topic_validation["valid"]:
                validation_result["errors"].extend(topic_validation["errors"])
                validation_result["is_valid"] = False
            else:
                validation_result["config_details"]["topic_prefix"] = topic_validation["details"]
        
        # 3. Validate Partitions (if provided)
        partitions = config.get("partitions")
        if partitions is not None:
            partition_validation = self._validate_partitions(partitions)
            if not partition_validation["valid"]:
                validation_result["errors"].extend(partition_validation["errors"])
                validation_result["is_valid"] = False
            else:
                validation_result["config_details"]["partitions"] = partition_validation["details"]
        else:
            validation_result["suggestions"].append({
                "field": "partitions",
                "message": "Partition count not specified (will use broker default)",
                "recommendation": "Set to 3 for production (allows parallel processing)"
            })
        
        # 4. Validate Replication Factor (if provided)
        replication = config.get("replication_factor")
        if replication is not None:
            replication_validation = self._validate_replication(replication)
            if not replication_validation["valid"]:
                validation_result["errors"].extend(replication_validation["errors"])
                validation_result["is_valid"] = False
            else:
                validation_result["config_details"]["replication_factor"] = replication_validation["details"]
        else:
            validation_result["suggestions"].append({
                "field": "replication_factor",
                "message": "Replication factor not specified",
                "recommendation": "Set to 2-3 for high availability (prevents data loss)"
            })
        
        # 5. Validate Timeout/Retry Settings (if provided)
        timeout = config.get("connection_timeout_ms")
        if timeout is not None:
            timeout_validation = self._validate_timeout(timeout)
            if not timeout_validation["valid"]:
                validation_result["warnings"].extend(timeout_validation["warnings"])
            else:
                validation_result["config_details"]["connection_timeout_ms"] = timeout_validation["details"]
        else:
            validation_result["suggestions"].append({
                "field": "connection_timeout_ms",
                "message": "Connection timeout not specified",
                "recommendation": "Set to 30000-60000 ms (30-60 seconds) for stable networks"
            })
        
        # 6. Validate Batch Settings (if provided)
        batch_size = config.get("batch_size")
        if batch_size is not None:
            batch_validation = self._validate_batch_size(batch_size)
            if not batch_validation["valid"]:
                validation_result["warnings"].extend(batch_validation["warnings"])
            else:
                validation_result["config_details"]["batch_size"] = batch_validation["details"]
        
        # 7. Validate Producer Configuration
        acks = config.get("acks")
        if acks is not None:
            if acks not in ['0', '1', 'all', 0, 1]:
                validation_result["warnings"].append({
                    "field": "acks",
                    "message": f"Invalid acks value: {acks}",
                    "valid_values": ['0', '1', 'all'],
                    "explanation": "0=no wait, 1=leader wait, all=all replicas wait"
                })
        else:
            validation_result["suggestions"].append({
                "field": "acks",
                "message": "Producer acks not configured",
                "recommendation": "Set to 'all' for durability (prevents data loss on broker failure)"
            })
        
        # Validate retries
        retries = config.get("retries")
        if retries is not None:
            try:
                retries_num = int(retries)
                if retries_num < 1:
                    validation_result["warnings"].append({
                        "field": "retries",
                        "message": f"Low retry count: {retries_num}",
                        "recommendation": "Set retries >= 3 for transient failure handling"
                    })
            except ValueError:
                validation_result["errors"].append({
                    "field": "retries",
                    "message": f"retries must be integer, got: {retries}"
                })
        else:
            validation_result["suggestions"].append({
                "field": "retries",
                "recommendation": "Set to 3-5 for production (handles transient failures)"
            })
        
        # Validate idempotence
        enable_idempotence = config.get("enable.idempotence")
        if enable_idempotence is False or enable_idempotence == "false":
            validation_result["warnings"].append({
                "field": "enable.idempotence",
                "severity": "HIGH",
                "message": "Idempotence disabled - duplicate messages possible on retries",
                "recommendation": "Enable for exactly-once-delivery semantics"
            })
        
        # 8. Validate Consumer Configuration
        auto_commit = config.get("enable.auto.commit")
        if auto_commit is True or auto_commit == "true":
            validation_result["failure_scenarios"].append({
                "severity": "HIGH",
                "scenario": "❌ Auto-commit without processing = data loss risk",
                "message": "Consumer commits offsets automatically but may crash before processing"
            })
        
        # 9. Validate Security Configuration
        security_protocol = config.get("security.protocol", "").upper()
        if not security_protocol or security_protocol == "PLAINTEXT":
            validation_result["warnings"].append({
                "field": "security.protocol",
                "severity": "HIGH",
                "message": "No encryption configured for Kafka messages",
                "recommendation": "Set security.protocol=SSL or SASL_SSL for production"
            })
        
        if security_protocol in ["SASL_SSL", "SASL_PLAINTEXT"]:
            if not config.get("sasl.mechanism"):
                validation_result["errors"].append({
                    "field": "sasl.mechanism",
                    "message": "SASL enabled but mechanism not set",
                    "valid_values": ["PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"]
                })
            
            if not config.get("sasl.username") or not config.get("sasl.password"):
                validation_result["errors"].append({
                    "field": "sasl.credentials",
                    "message": "SASL enabled but username/password not configured"
                })
        
        # 10. CRITICAL: Check for failure scenarios
        failure_checks = self._detect_failure_scenarios(config)
        if failure_checks["scenarios"]:
            validation_result["failure_scenarios"] = failure_checks["scenarios"]
            validation_result["warnings"].extend(failure_checks["critical_warnings"])
        
        # Add overall assessment
        validation_result["assessment"] = self._generate_assessment(validation_result)
        
        return validation_result
    
    def _detect_failure_scenarios(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect critical failure scenarios that could cause data loss or system failures.
        
        Checks for:
        - Wrong broker address (connectivity failure)
        - Weak durability (acks: '1')
        - No retries (message loss)
        - Auto-commit enabled (data loss on crash)
        - High session timeout (slow failure detection)
        """
        result = {"scenarios": [], "critical_warnings": []}
        
        # Scenario 1: Wrong Broker Address
        broker_url = config.get("broker_url", "").strip()
        if broker_url and ("wrong" in broker_url.lower() or "placeholder" in broker_url.lower()):
            result["scenarios"].append({
                "severity": "CRITICAL",
                "scenario": "❌ Wrong Broker Address",
                "current": f"'bootstrap.servers': '{broker_url}'",
                "problem": "This would break connectivity completely. Producer/consumer cannot reach the broker.",
                "impact": "COMPLETE SERVICE FAILURE - No messages can be sent or received",
                "ai_suggestion": {
                    "title": "Fix Broker Address",
                    "current_value": broker_url,
                    "recommended_value": "localhost:9092 or kafka.yourdomain.com:9092",
                    "example": "'bootstrap.servers': 'kafka.example.com:9092'",
                    "explanation": "Use actual hostname/IP and port where Kafka broker is running"
                }
            })
            result["critical_warnings"].append({
                "field": "broker_url",
                "message": "Broker address appears invalid or is a placeholder",
                "risk_level": "CRITICAL"
            })
        
        # Scenario 2: Weak Durability (acks: '1')
        acks = config.get("acks", "").strip()
        if acks == "1":
            result["scenarios"].append({
                "severity": "HIGH",
                "scenario": "❌ Weak Durability",
                "current": f"'acks': '1'",
                "problem": "Leader acknowledges but doesn't wait for replicas. Data loss if leader fails before replication.",
                "impact": "DATA LOSS RISK - If leader node crashes, messages may be lost even after acknowledgment",
                "ai_suggestion": {
                    "title": "Enable Full Durability",
                    "current_value": "1",
                    "recommended_value": "all",
                    "example": "'acks': 'all'",
                    "explanation": "Wait for all in-sync replicas to acknowledge before returning. Safer but slightly slower."
                }
            })
            result["critical_warnings"].append({
                "field": "acks",
                "message": "Using weak durability setting (acks=1). Risk of data loss.",
                "risk_level": "HIGH"
            })
        
        # Scenario 3: No Retries
        retries = config.get("retries")
        if retries == 0 or retries == "0":
            result["scenarios"].append({
                "severity": "HIGH",
                "scenario": "❌ No Retries on Failure",
                "current": f"'retries': 0",
                "problem": "Any transient failure (network blip, broker overload) will immediately fail the message.",
                "impact": "MESSAGE LOSS - Temporary network issues will cause permanent message loss",
                "ai_suggestion": {
                    "title": "Enable Retry Mechanism",
                    "current_value": "0",
                    "recommended_value": "5",
                    "example": "'retries': 5",
                    "explanation": "Retry up to 5 times with exponential backoff for transient failures. Standard for production."
                }
            })
            result["critical_warnings"].append({
                "field": "retries",
                "message": "No retries configured. Transient failures will cause message loss.",
                "risk_level": "HIGH"
            })
        
        # Scenario 4: Auto-commit Enabled (risky)
        auto_commit = config.get("enable.auto.commit")
        if auto_commit is True or auto_commit == "true" or auto_commit == "True":
            result["scenarios"].append({
                "severity": "HIGH",
                "scenario": "❌ Risky Auto-Commit",
                "current": f"'enable.auto.commit': True",
                "problem": "If consumer crashes after committing but before processing, messages are lost and never reprocessed.",
                "impact": "DATA LOSS - Messages marked as processed but not actually handled = silent failure",
                "ai_suggestion": {
                    "title": "Disable Auto-Commit (Handle Manually)",
                    "current_value": "True",
                    "recommended_value": "False",
                    "example": "'enable.auto.commit': False",
                    "implementation": "After successfully processing each message, manually call consumer.commit(). Only mark as processed when fully handled.",
                    "explanation": "Manual commits ensure messages are only marked as processed AFTER successful handling."
                }
            })
            result["critical_warnings"].append({
                "field": "enable.auto.commit",
                "message": "Auto-commit enabled. Risk of message loss on consumer crash.",
                "risk_level": "HIGH"
            })
        
        # Scenario 5: High Session Timeout
        session_timeout = config.get("session.timeout.ms")
        if session_timeout:
            try:
                timeout_ms = int(session_timeout)
                if timeout_ms > SESSION_TIMEOUT_THRESHOLD_MS:  # More than 10 seconds
                    result["scenarios"].append({
                        "severity": "MEDIUM",
                        "scenario": "❌ High Session Timeout",
                        "current": f"'session.timeout.ms': {timeout_ms}",
                        "problem": f"Takes {timeout_ms/1000:.1f} seconds to detect consumer failure. Slow rebalancing and recovery.",
                        "impact": "SLOW FAILURE DETECTION - Up to {:.1f} seconds of no processing during consumer failure".format(timeout_ms/1000),
                        "ai_suggestion": {
                            "title": "Reduce Session Timeout for Faster Detection",
                            "current_value": timeout_ms,
                            "recommended_value": SESSION_TIMEOUT_RECOMMENDED_MS,
                            "example": f"'session.timeout.ms': {SESSION_TIMEOUT_RECOMMENDED_MS}",
                            "explanation": f"{SESSION_TIMEOUT_RECOMMENDED_MS/1000:.1f} seconds allows faster failure detection and rebalancing. Standard for production systems."
                        }
                    })
                    result["critical_warnings"].append({
                        "field": "session.timeout.ms",
                        "message": f"Session timeout too high ({timeout_ms}ms). Slow failure detection.",
                        "risk_level": "MEDIUM"
                    })
            except (ValueError, TypeError):
                pass
        
        return result
    
    def _validate_broker_url(self, broker_url: str) -> Dict[str, Any]:
        """Validate Kafka broker URL format."""
        result = {"valid": True, "errors": [], "details": {}}
        
        # Check basic format: host:port or host:port,host:port
        broker_pattern = r'^[a-zA-Z0-9\.\-_]+:\d{1,5}(,[a-zA-Z0-9\.\-_]+:\d{1,5})*$'
        
        if not re.match(broker_pattern, broker_url):
            result["valid"] = False
            result["errors"].append({
                "field": "broker_url",
                "message": f"Invalid format: '{broker_url}'",
                "details": "Must be 'hostname:port' or 'host1:port1,host2:port2'",
                "examples": [
                    "localhost:9092",
                    "kafka.example.com:9092",
                    "broker1:9092,broker2:9092,broker3:9092"
                ]
            })
        else:
            brokers = broker_url.split(',')
            for broker in brokers:
                host, port = broker.split(':')
                port_num = int(port)
                
                if port_num < 1 or port_num > 65535:
                    result["valid"] = False
                    result["errors"].append({
                        "field": "broker_url",
                        "message": f"Invalid port number: {port_num}",
                        "details": "Port must be between 1 and 65535",
                        "correct_range": "1-65535"
                    })
                
                result["details"][broker] = {
                    "host": host,
                    "port": port_num,
                    "status": "✓ Valid format"
                }
        
        return result
    
    def _validate_topic_name(self, topic: str) -> Dict[str, Any]:
        """Validate Kafka topic name."""
        result = {"valid": True, "errors": [], "details": {}}
        
        # Topic name rules: alphanumeric, dash, underscore, dot
        topic_pattern = r'^[a-zA-Z0-9\.\-_]+$'
        
        if not re.match(topic_pattern, topic):
            result["valid"] = False
            result["errors"].append({
                "field": "topic_prefix",
                "message": f"Invalid topic name: '{topic}'",
                "details": "Topic names can only contain alphanumeric characters, dots, dashes, and underscores",
                "examples": ["code-review", "code_review_events", "code.review.v1"]
            })
        
        if len(topic) > 249:
            result["valid"] = False
            result["errors"].append({
                "field": "topic_prefix",
                "message": f"Topic name too long: {len(topic)} characters",
                "details": "Topic names must be less than 249 characters",
                "max_length": 249
            })
        
        if result["valid"]:
            result["details"] = {
                "name": topic,
                "length": len(topic),
                "status": "✓ Valid"
            }
        
        return result
    
    def _validate_partitions(self, partitions: Any) -> Dict[str, Any]:
        """Validate partition count."""
        result = {"valid": True, "errors": [], "warnings": [], "details": {}}
        
        try:
            partitions_num = int(partitions)
        except (ValueError, TypeError):
            result["valid"] = False
            result["errors"].append({
                "field": "partitions",
                "message": f"Invalid partition count: '{partitions}' (must be integer)",
                "details": "Partitions must be a whole number",
                "examples": ["1", "3", "6"]
            })
            return result
        
        if partitions_num < 1:
            result["valid"] = False
            result["errors"].append({
                "field": "partitions",
                "message": f"Invalid partition count: {partitions_num}",
                "details": "Must have at least 1 partition",
                "minimum": 1
            })
        
        if partitions_num > 1000:
            result["warnings"].append({
                "field": "partitions",
                "message": f"Very high partition count: {partitions_num}",
                "details": "Large partition counts can impact performance. Recommended: 3-100",
                "recommended_range": "3-100"
            })
        
        if result["valid"]:
            result["details"] = {
                "count": partitions_num,
                "recommendation": "3 for standard load, 6+ for high throughput",
                "use_case": "Higher partitions = better parallelism but more overhead",
                "status": "✓ Valid"
            }
        
        return result
    
    def _validate_replication(self, replication: Any) -> Dict[str, Any]:
        """Validate replication factor."""
        result = {"valid": True, "errors": [], "warnings": [], "details": {}}
        
        try:
            replication_num = int(replication)
        except (ValueError, TypeError):
            result["valid"] = False
            result["errors"].append({
                "field": "replication_factor",
                "message": f"Invalid replication factor: '{replication}' (must be integer)",
                "details": "Replication factor must be a whole number",
                "examples": ["1", "2", "3"]
            })
            return result
        
        if replication_num < 1:
            result["valid"] = False
            result["errors"].append({
                "field": "replication_factor",
                "message": f"Invalid replication factor: {replication_num}",
                "details": "Must have at least 1 replica (minimum for production: 2-3)",
                "minimum": 1
            })
        
        if replication_num == 1:
            result["warnings"].append({
                "field": "replication_factor",
                "message": "Replication factor is 1 (no redundancy)",
                "risk": "HIGH - If broker fails, data will be lost",
                "recommendation": "Use 2-3 for production environments",
                "production_minimum": 2
            })
        
        if replication_num > 10:
            result["warnings"].append({
                "field": "replication_factor",
                "message": f"Very high replication factor: {replication_num}",
                "risk": "Will use significant disk space and network bandwidth",
                "recommendation": "Typically 2-3 is sufficient",
                "typical_range": "2-3"
            })
        
        if result["valid"]:
            result["details"] = {
                "factor": replication_num,
                "redundancy_level": self._get_redundancy_level(replication_num),
                "data_safety": "✓ Safe" if replication_num >= 2 else "⚠️ At Risk",
                "status": "✓ Valid"
            }
        
        return result
    
    def _validate_timeout(self, timeout: Any) -> Dict[str, Any]:
        """Validate connection timeout."""
        result = {"valid": True, "warnings": [], "details": {}}
        
        try:
            timeout_ms = int(timeout)
        except (ValueError, TypeError):
            result["warnings"].append({
                "field": "connection_timeout_ms",
                "message": f"Invalid timeout: '{timeout}' (must be integer milliseconds)"
            })
            return result
        
        if timeout_ms < 1000:
            result["warnings"].append({
                "field": "connection_timeout_ms",
                "message": f"Very short timeout: {timeout_ms}ms",
                "risk": "Too short may cause connection failures",
                "recommendation": "Use 30000-60000 ms minimum"
            })
        
        if timeout_ms > 300000:
            result["warnings"].append({
                "field": "connection_timeout_ms",
                "message": f"Very long timeout: {timeout_ms}ms",
                "risk": "Long waits before detecting failures",
                "recommendation": "Use 30000-60000 ms for faster failure detection"
            })
        
        if result["valid"]:
            result["details"] = {
                "timeout_ms": timeout_ms,
                "timeout_seconds": timeout_ms / 1000,
                "status": "✓ Valid"
            }
        
        return result
    
    def _validate_batch_size(self, batch_size: Any) -> Dict[str, Any]:
        """Validate batch size."""
        result = {"valid": True, "warnings": [], "details": {}}
        
        try:
            size_bytes = int(batch_size)
        except (ValueError, TypeError):
            result["warnings"].append({
                "field": "batch_size",
                "message": f"Invalid batch size: '{batch_size}' (must be integer bytes)"
            })
            return result
        
        if size_bytes < 100:
            result["warnings"].append({
                "field": "batch_size",
                "message": f"Very small batch size: {size_bytes} bytes",
                "impact": "Poor throughput, many small messages",
                "recommendation": "Use 16384 bytes (16KB) or more"
            })
        
        if size_bytes > 1048576:
            result["warnings"].append({
                "field": "batch_size",
                "message": f"Very large batch size: {size_bytes} bytes (~{size_bytes / 1048576:.1f}MB)",
                "impact": "High memory usage, slower delivery",
                "recommendation": "Use 16384-65536 bytes for balance"
            })
        
        result["details"] = {
            "size_bytes": size_bytes,
            "size_kb": size_bytes / 1024,
            "status": "✓ Valid"
        }
        
        return result
    
    def _get_redundancy_level(self, replication_factor: int) -> str:
        """Get human-readable redundancy level."""
        if replication_factor == 1:
            return "NONE (data loss risk)"
        elif replication_factor == 2:
            return "BASIC (1 failover)"
        elif replication_factor == 3:
            return "HIGH (2 failovers)"
        else:
            return f"EXTREME ({replication_factor - 1} failovers)"
    
    def _generate_assessment(self, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall assessment and recommendations."""
        assessment = {
            "status": "✅ PASS" if validation_result["is_valid"] else "❌ FAIL",
            "errors_count": len(validation_result["errors"]),
            "warnings_count": len(validation_result["warnings"]),
            "failure_scenarios_count": len(validation_result.get("failure_scenarios", [])),
            "suggestions_count": len(validation_result["suggestions"]),
            "next_steps": [],
            "risk_level": "LOW"
        }
        
        # Determine overall risk level
        if validation_result.get("failure_scenarios"):
            high_severity_scenarios = [s for s in validation_result["failure_scenarios"] if s.get("severity") in ["CRITICAL", "HIGH"]]
            if high_severity_scenarios:
                assessment["risk_level"] = "CRITICAL" if any(s.get("severity") == "CRITICAL" for s in high_severity_scenarios) else "HIGH"
        
        if not validation_result["is_valid"]:
            assessment["next_steps"].append("🔴 Fix all errors before proceeding")
            assessment["risk_level"] = "CRITICAL"
        
        if validation_result.get("failure_scenarios"):
            assessment["next_steps"].append("⚠️ CRITICAL: Review and fix failure scenarios to prevent data loss")
            assessment["next_steps"].append("   - Review each scenario below for specific AI recommendations")
            assessment["next_steps"].append("   - Implement suggested changes before production deployment")
        
        if validation_result["warnings"]:
            assessment["next_steps"].append("⚠️ Review warnings - they indicate configuration risks")
        
        if validation_result["suggestions"]:
            assessment["next_steps"].append("💡 Consider implementing suggestions for better reliability")
        
        if not validation_result.get("failure_scenarios") and not validation_result["errors"]:
            assessment["next_steps"].append("✅ Configuration looks good")
        
        assessment["next_steps"].append("🧪 Test connection with: kafkacat -b <broker_url> -L")
        
        return assessment

    def create_review_event(
        self,
        event_type: ReviewEventType,
        review_id: str,
        pr_id: int,
        workspace: str,
        repo_slug: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create an optimized Kafka event for code review workflow."""
        event = {
            "event_type": event_type.value,
            "review_id": review_id,
            "pr_id": pr_id,
            "workspace": workspace,
            "repo_slug": repo_slug,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
            "version": "1.0"
        }
        self.events.append(event)
        logger.info(f"Created Kafka event: {event_type.value} for PR #{pr_id}")
        return event

    def create_review_started_event(
        self,
        review_id: str,
        pr_id: int,
        workspace: str,
        repo_slug: str,
        branch: str,
        files_count: int
    ) -> Dict[str, Any]:
        """Event when review analysis starts."""
        return self.create_review_event(
            ReviewEventType.REVIEW_STARTED,
            review_id,
            pr_id,
            workspace,
            repo_slug,
            {
                "branch": branch,
                "files_count": files_count,
                "status": "analyzing"
            }
        )

    def create_analysis_complete_event(
        self,
        review_id: str,
        pr_id: int,
        workspace: str,
        repo_slug: str,
        summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Event when analysis is complete."""
        return self.create_review_event(
            ReviewEventType.ANALYSIS_COMPLETE,
            review_id,
            pr_id,
            workspace,
            repo_slug,
            {
                "overall_score": summary.get("overall_score"),
                "total_comments": summary.get("total_comments"),
                "critical_issues": summary.get("critical_issues"),
                "status": "complete"
            }
        )

    def create_approval_ready_event(
        self,
        review_id: str,
        pr_id: int,
        workspace: str,
        repo_slug: str,
        destination_branch: str,
        can_merge: bool
    ) -> Dict[str, Any]:
        """Event when code is ready for approval/merge."""
        return self.create_review_event(
            ReviewEventType.APPROVAL_READY,
            review_id,
            pr_id,
            workspace,
            repo_slug,
            {
                "destination_branch": destination_branch,
                "can_merge": can_merge,
                "allowed_branches": ["master", "sit"],
                "status": "ready_for_approval"
            }
        )

    def create_security_issue_event(
        self,
        review_id: str,
        pr_id: int,
        workspace: str,
        repo_slug: str,
        issue: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Event when security issue is detected."""
        return self.create_review_event(
            ReviewEventType.SECURITY_ISSUE_FOUND,
            review_id,
            pr_id,
            workspace,
            repo_slug,
            {
                "severity": issue.get("severity"),
                "title": issue.get("title"),
                "file": issue.get("file_path"),
                "line": issue.get("line_start")
            }
        )

    def generate_optimized_suggestion(
        self,
        comment: Dict[str, Any],
        file_language: str
    ) -> str:
        """Generate optimized code suggestion for Kafka event."""
        suggestion = f"""
[{comment.get('severity', 'info').upper()}] {comment.get('title', 'Code Issue')}

File: {comment.get('location', {}).get('file_path', 'unknown')}
Line: {comment.get('location', {}).get('line_start', 'N/A')}

Issue: {comment.get('description', 'See details in review')}

Fix: {comment.get('suggestion', 'Apply inline suggestion')}

Inline Fix:
```{file_language}
{comment.get('inline_suggestion', 'N/A')}
```

Reference: {', '.join(comment.get('references', []))}
"""
        return suggestion.strip()

    def get_pending_events(self) -> List[Dict[str, Any]]:
        """Get all pending Kafka events."""
        return self.events.copy()

    def clear_events(self) -> None:
        """Clear pending events after publishing."""
        self.events.clear()

    def should_allow_approval(
        self,
        destination_branch: str,
        allowed_branches: List[str] = None
    ) -> bool:
        """Check if approval/merge is allowed for destination branch."""
        allowed = allowed_branches or ["master", "sit"]
        branch_name = destination_branch.lower().split('/')[-1]
        return branch_name in allowed

    def get_approval_status(
        self,
        pr_destination_branch: str,
        analysis_complete: bool,
        has_critical_issues: bool
    ) -> Dict[str, Any]:
        """Get current approval/merge status for PR."""
        is_valid_branch = self.should_allow_approval(pr_destination_branch)
        can_approve = analysis_complete and not has_critical_issues and is_valid_branch

        return {
            "can_approve": can_approve,
            "can_merge": can_approve,
            "destination_branch": pr_destination_branch,
            "analysis_complete": analysis_complete,
            "has_blocking_issues": has_critical_issues,
            "is_valid_destination": is_valid_branch,
            "allowed_destinations": ["master", "sit"],
            "reason": self._get_approval_reason(
                analysis_complete, has_critical_issues, is_valid_branch
            )
        }

    def _get_approval_reason(
        self,
        analysis_complete: bool,
        has_critical_issues: bool,
        is_valid_branch: bool
    ) -> str:
        """Generate human-readable reason for approval status."""
        if not analysis_complete:
            return "Analysis in progress - approval unavailable until complete"
        if has_critical_issues:
            return "Critical issues found - cannot approve until resolved"
        if not is_valid_branch:
            return "Merge only allowed to 'master' or 'sit' branches"
        return "Code ready for approval and merge"
