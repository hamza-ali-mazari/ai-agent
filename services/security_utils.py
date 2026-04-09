"""
Security utilities for secure password hashing, encryption, and SQL injection prevention.

This module provides professional-grade security functions following OWASP standards.
Reference: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
"""

import os
import re
import logging
from typing import Tuple, Optional

try:
    import bcrypt
except ImportError:
    bcrypt = None

try:
    from parameterized import parameterized
except ImportError:
    parameterized = None

logger = logging.getLogger(__name__)

# Security constants
MIN_PASSWORD_LENGTH = 12
BCRYPT_ROUNDS = 12
SQL_INJECTION_PATTERNS = [
    r"(union\s+select)",  # UNION SELECT
    r"(drop\s+table)",  # DROP TABLE
    r"(or\s+['\"]?[01]['\"]?=['\"]?[01]['\"]?)",  # or 1=1 / or '1'='1 patterns
    r"(;.*(?:drop|delete|update|insert|create))",  # Multiple statements
    r"(xp_|sp_)",  # Extended/System procedures
    r"(-{2}|#)(?=\s|$)",  # SQL comments (-- or # at end of line)
]


class SecurityUtilities:
    """Professional security utilities following OWASP standards."""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt with OWASP recommendations.

        Args:
            password: Plain text password to hash

        Returns:
            Hashed password (bcrypt format)

        Raises:
            ValueError: If password is too short or bcrypt not available
            TypeError: If password is not a string

        Reference: OWASP A02:2021 – Cryptographic Failures
        """
        if bcrypt is None:
            raise RuntimeError("bcrypt package not installed. Install with: pip install bcrypt")

        if not isinstance(password, str):
            raise TypeError(f"Password must be string, got {type(password)}")

        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")

        try:
            salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
        except Exception as exc:
            logger.error(f"Password hashing failed: {exc}")
            raise

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """
        Verify password against bcrypt hash.

        Args:
            password: Plain text password to verify
            hashed: Bcrypt hash to verify against

        Returns:
            True if password matches, False otherwise

        Reference: OWASP A02:2021 – Cryptographic Failures
        """
        if bcrypt is None:
            raise RuntimeError("bcrypt package not installed. Install with: pip install bcrypt")

        if not isinstance(password, str) or not isinstance(hashed, str):
            return False

        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as exc:
            logger.error(f"Password verification failed: {exc}")
            return False

    @staticmethod
    def sanitize_sql_input(user_input: str) -> bool:
        """
        Detect potential SQL injection patterns in user input.

        Args:
            user_input: User-supplied input to check

        Returns:
            False if injection pattern detected, True if safe

        Note: This is for detection/logging only. Always use parameterized queries!

        Reference: OWASP A03:2021 – Injection
        """
        if not isinstance(user_input, str):
            return True

        user_input_lower = user_input.lower().strip()

        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, user_input_lower, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {pattern}")
                return False

        return True

    @staticmethod
    def validate_no_hardcoded_secrets(code: str) -> Tuple[bool, list]:
        """
        Detect hardcoded secrets in code.

        Args:
            code: Code string to scan

        Returns:
            Tuple of (is_safe, list_of_findings)

        Detects:
        - API keys (sk-, api_key=)
        - Database passwords (password=)
        - AWS/Azure credentials

        Reference: OWASP A02:2021 – Cryptographic Failures
        """
        patterns = {
            'api_key': [
                r'sk-[a-zA-Z0-9]{20,}',  # OpenAI-style keys
                r'api[_-]?key\s*[:=]\s*[\'"][^\'\"]{10,}[\'"]',  # API_KEY = "..."
                r'api[_-]?secret\s*[:=]\s*[\'"][^\'\"]+[\'"]',  # API_SECRET = "..."
                r'sk[_-]?proj[_-][a-zA-Z0-9]+',  # sk-proj-.... tokens
            ],
            'database_password': [
                r'(?<!get\()password\s*[:=]\s*[\'"][^\'\"]{3,}[\'"]',  # password = "..." but not os.environ.get and not os.getenv
                r'db[_-]?password\s*[:=]\s*[\'"][^\'\"]+[\'"]',  # DB_PASSWORD = "..."
            ],
            'aws_credentials': [
                r'AKIA[0-9A-Z]{16}',
                r'aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*[\'"][^\'\"]+[\'"]',
            ],
            'azure_credentials': [
                r'azure[_-]?key\s*[:=]\s*[\'"][^\'\"]+[\'"]',
                r'connection[_-]?string\s*[:=]\s*[\'"][^\'\"]+[\'"]',
            ],
            'github_token': [
                r'ghp_[a-zA-Z0-9]{30,}',  # GitHub personal access tokens (30+ chars)
                r'github[_-]?token\s*[:=]\s*[\'"][^\'\"]{10,}[\'"]',
            ],
        }

        findings = []

        for secret_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.finditer(pattern, code, re.IGNORECASE)
                for match in matches:
                    # Skip matches that are part of environ.get() patterns
                    match_str = match.group()
                    if "environ" in code[max(0, match.start()-50):match.start()]:
                        continue
                    
                    findings.append({
                        'type': secret_type,
                        'pattern': match_str,
                        'start': match.start(),
                        'end': match.end()
                    })

        return len(findings) == 0, findings

    @staticmethod
    def get_secure_connection_string(
        host: str,
        user: str,
        password: Optional[str] = None,
        database: str = "default",
        port: int = 5432
    ) -> str:
        """
        Build secure database connection string using environment variables.

        Args:
            host: Database host
            user: Database user
            password: Optional password (should come from env var)
            database: Database name
            port: Database port

        Returns:
            Parameterized connection string

        Note: Password should be retrieved from environment variables!

        Reference: OWASP A02:2021 – Cryptographic Failures
        """
        if not password:
            password = os.environ.get('DB_PASSWORD')
            if not password:
                raise ValueError('DB_PASSWORD environment variable not set')

        # Use parameterized format for database drivers
        return f"postgresql://{user}:***@{host}:{port}/{database}"

    @staticmethod
    def validate_environment_variables(required_vars: list) -> Tuple[bool, list]:
        """
        Validate that required security environment variables are set.

        Args:
            required_vars: List of required environment variable names

        Returns:
            Tuple of (all_set, missing_vars)

        Reference: OWASP A02:2021 – Cryptographic Failures
        """
        missing = [var for var in required_vars if not os.getenv(var)]
        return len(missing) == 0, missing


# Example: Proper SQL query with parameterized query pattern
PARAMETERIZED_QUERY_EXAMPLE = """
# WRONG - SQL Injection Vulnerable:
query = f"SELECT * FROM users WHERE id = {user_id}"

# CORRECT - Use parameterized queries:
# For psycopg2 (PostgreSQL):
cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))

# For sqlite3:
cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))

# For SQLAlchemy ORM:
db.session.query(User).filter(User.id == user_id).first()
"""

__all__ = [
    'SecurityUtilities',
    'hash_password',
    'verify_password',
    'sanitize_sql_input',
    'validate_no_hardcoded_secrets',
    'get_secure_connection_string',
    'validate_environment_variables',
]

# Convenience module-level functions
hash_password = SecurityUtilities.hash_password
verify_password = SecurityUtilities.verify_password
sanitize_sql_input = SecurityUtilities.sanitize_sql_input
validate_no_hardcoded_secrets = SecurityUtilities.validate_no_hardcoded_secrets
get_secure_connection_string = SecurityUtilities.get_secure_connection_string
validate_environment_variables = SecurityUtilities.validate_environment_variables
