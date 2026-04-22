"""
Code Smells Analyzer

Detects worst coding practices and anti-patterns including:
- Hardcoding and magic numbers
- Spaghetti code (complex control flow)
- Ignored DRY principles (code duplication)
- Poor naming conventions
- Monolithic functions (too many responsibilities)
- Deep nesting
- Improper exception handling
- Hardcoded passwords/secrets
- Unsanitized inputs
- Dead code
- Magic strings/numbers
"""

import re
import logging
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


class CodeSmellsAnalyzer:
    """Analyzes code for anti-patterns and code smells."""

    def __init__(self):
        """Initialize code smells analyzer with thresholds."""
        self.thresholds = {
            'function_length': {'ideal': 20, 'acceptable': 50, 'risky': 100},
            'nesting_depth': {'ideal': 2, 'acceptable': 4, 'risky': 6},
            'parameters': {'ideal': 3, 'acceptable': 5, 'risky': 7},
            'cyclomatic_complexity': {'ideal': 5, 'acceptable': 10, 'risky': 15},
            'duplicate_code': {'threshold': 3}  # 3+ identical lines
        }
        
        # Patterns for detecting code smells
        self.secret_patterns = [
            r'password\s*[=:]\s*["\']([^"\']*)["\']',
            r'api_key\s*[=:]\s*["\']([^"\']*)["\']',
            r'token\s*[=:]\s*["\']([^"\']*)["\']',
            r'secret\s*[=:]\s*["\']([^"\']*)["\']',
            r'aws_secret\s*[=:]\s*["\']([^"\']*)["\']',
            r'private_key\s*[=:]\s*["\']([^"\']*)["\']',
        ]
        
        self.magic_number_patterns = [
            r'[^a-zA-Z_]\d+[^a-zA-Z_.]',  # Numeric constants
        ]
        
        self.poor_naming_patterns = [
            r'\b(foo|bar|baz|qux|tmp|temp|data|val|x|y|z|i|j|k)\b\s*[=:]',  # Bad variable names
        ]

    def analyze_code_smells(
        self,
        changed_files: List[Dict[str, Any]],
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze code for smells and anti-patterns.

        Args:
            changed_files: List of changed files with content
            language: Programming language (optional)

        Returns:
            Dictionary with code smells analysis
        """
        analysis = {
            "has_smells": False,
            "files_analyzed": 0,
            "total_smells_found": 0,
            "critical_smells": [],
            "high_smells": [],
            "medium_smells": [],
            "smells_by_category": defaultdict(list),
            "severity_breakdown": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0
            },
            "recommendations": []
        }

        for changed_file in changed_files:
            file_path = changed_file.get('path', '')
            content = changed_file.get('content', '')

            if not content or not self._is_code_file(file_path):
                continue

            analysis["files_analyzed"] += 1
            file_smells = self._analyze_file_smells(file_path, content, language)

            for smell in file_smells:
                analysis["total_smells_found"] += 1
                analysis["has_smells"] = True
                
                category = smell['category']
                severity = smell['severity']
                
                analysis["smells_by_category"][category].append(smell)
                analysis["severity_breakdown"][severity] += 1

                if severity == "critical":
                    analysis["critical_smells"].append(smell)
                elif severity == "high":
                    analysis["high_smells"].append(smell)

        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(analysis)
        
        # Convert defaultdict to regular dict for JSON serialization
        analysis["smells_by_category"] = dict(analysis["smells_by_category"])

        return analysis

    def _analyze_file_smells(
        self,
        file_path: str,
        content: str,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Analyze a single file for code smells."""
        smells = []
        lines = content.split('\n')

        # Detect hardcoded secrets
        smells.extend(self._detect_hardcoded_secrets(file_path, lines))
        
        # Detect magic numbers and strings
        smells.extend(self._detect_magic_numbers(file_path, lines))
        
        # Detect poor naming conventions
        smells.extend(self._detect_poor_naming(file_path, lines))
        
        # Detect long functions
        smells.extend(self._detect_long_functions(file_path, lines))
        
        # Detect deep nesting
        smells.extend(self._detect_deep_nesting(file_path, lines))
        
        # Detect improper exception handling
        smells.extend(self._detect_exception_handling(file_path, lines))
        
        # Detect code duplication
        smells.extend(self._detect_duplication(file_path, lines))
        
        # Detect missing input validation
        smells.extend(self._detect_missing_validation(file_path, lines))
        
        # Detect missing error handling
        smells.extend(self._detect_missing_error_handling(file_path, lines))
        
        # Detect DRY violations
        smells.extend(self._detect_dry_violations(file_path, lines))

        return smells

    def _detect_hardcoded_secrets(
        self,
        file_path: str,
        lines: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect hardcoded passwords, API keys, and other secrets."""
        smells = []

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('#'):
                continue

            for pattern in self.secret_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Check if it's not a placeholder value
                    if not re.search(r'(xxx|todo|fixme|example|placeholder)', line, re.IGNORECASE):
                        smells.append({
                            "file": file_path,
                            "line": line_num,
                            "category": "security",
                            "type": "hardcoded_secret",
                            "severity": "critical",
                            "title": "Hardcoded Secret/Credential Detected",
                            "description": f"Hardcoded credentials found on line {line_num}. Secrets should never be committed to source code.",
                            "code_snippet": line.strip(),
                            "suggestion": "Use environment variables, secrets management services (AWS Secrets Manager, Azure Key Vault), or configuration files excluded from version control.",
                            "impact": "CRITICAL: Exposed credentials can be used to compromise systems, access sensitive data, or escalate privileges."
                        })

        return smells

    def _detect_magic_numbers(
        self,
        file_path: str,
        lines: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect magic numbers and unexplained constants."""
        smells = []
        magic_number_threshold = 3  # Numbers appearing multiple times

        # Look for unexplained numeric constants
        for line_num, line in enumerate(lines, 1):
            # Skip comments and strings
            if line.strip().startswith('#') or line.strip().startswith('//'):
                continue

            # Find numeric constants not in strings
            # Match numbers that look like magic numbers (not clear constants)
            matches = re.finditer(r'\b(?!0x|0b)(\d+)\b(?!\s*\*\s*|\s*\/\s*)', line)
            
            for match in matches:
                number = match.group(1)
                
                # Skip line numbers, port numbers, and small constants
                if len(number) <= 1 or int(number) < 100:
                    continue
                
                # Skip if it's clearly a constant (all uppercase nearby)
                if 'CONSTANT' in line or '_COUNT' in line or '_LENGTH' in line:
                    continue

                smells.append({
                    "file": file_path,
                    "line": line_num,
                    "category": "maintainability",
                    "type": "magic_number",
                    "severity": "medium",
                    "title": "Magic Number Detected",
                    "description": f"Unexplained numeric constant '{number}' on line {line_num}. Numbers should be named constants for clarity.",
                    "code_snippet": line.strip(),
                    "suggestion": f"Extract to a named constant: {number.upper()}_VALUE = {number}",
                    "impact": "Makes code harder to maintain and understand intent. Future modifications become risky."
                })
                break  # One issue per line

        return smells

    def _detect_poor_naming(
        self,
        file_path: str,
        lines: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect variables with poor names (single letters, foo, bar, etc)."""
        smells = []

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('#') or line.strip().startswith('//'):
                continue

            # Find poor variable names
            for pattern in self.poor_naming_patterns:
                match = re.search(pattern, line)
                if match:
                    var_name = match.group(1)
                    smells.append({
                        "file": file_path,
                        "line": line_num,
                        "category": "maintainability",
                        "type": "poor_naming",
                        "severity": "medium",
                        "title": f"Poor Variable Name: '{var_name}'",
                        "description": f"Variable '{var_name}' on line {line_num} is not descriptive. Use meaningful names that convey intent.",
                        "code_snippet": line.strip(),
                        "suggestion": f"Rename '{var_name}' to a descriptive name (e.g., 'user_count', 'item_data', 'result_value')",
                        "impact": "Reduces code readability and makes maintenance harder for other developers."
                    })
                    break

        return smells

    def _detect_long_functions(
        self,
        file_path: str,
        lines: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect functions that are too long (too many responsibilities)."""
        smells = []

        # Language-specific function detection
        function_pattern = r'^\s*(def|function|void|public|private|protected|func)\s+(\w+)'
        current_function = None
        function_start = 0
        indent_level = 0

        for line_num, line in enumerate(lines, 1):
            match = re.match(function_pattern, line)
            
            if match:
                # Save previous function if it was too long
                if current_function and (line_num - function_start) > self.thresholds['function_length']['risky']:
                    smells.append({
                        "file": file_path,
                        "line": function_start,
                        "category": "maintainability",
                        "type": "long_function",
                        "severity": "high",
                        "title": f"Monolithic Function: '{current_function}'",
                        "description": f"Function '{current_function}' at line {function_start} has {line_num - function_start} lines. Functions should be shorter and focused (ideal: <50 lines).",
                        "code_snippet": f"Function spans {line_num - function_start} lines",
                        "suggestion": "Break the function into smaller, single-responsibility functions. Extract complex logic into helper functions.",
                        "impact": "Large functions are hard to test, understand, and maintain. They often have multiple responsibilities."
                    })

                current_function = match.group(2)
                function_start = line_num
                indent_level = len(line) - len(line.lstrip())

        return smells

    def _detect_deep_nesting(
        self,
        file_path: str,
        lines: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect deeply nested control structures."""
        smells = []

        for line_num, line in enumerate(lines, 1):
            # Calculate nesting depth
            indent = len(line) - len(line.lstrip())
            # Assume 4 spaces per indent level (Python convention)
            nesting_depth = indent // 4

            # Check for deeply nested code
            if nesting_depth > self.thresholds['nesting_depth']['risky']:
                smells.append({
                    "file": file_path,
                    "line": line_num,
                    "category": "maintainability",
                    "type": "deep_nesting",
                    "severity": "high",
                    "title": "Deep Nesting Detected",
                    "description": f"Line {line_num} has nesting depth of {nesting_depth} levels (threshold: {self.thresholds['nesting_depth']['risky']}). Deep nesting makes code hard to follow and test.",
                    "code_snippet": line.strip(),
                    "suggestion": "Extract nested logic into separate functions or use early returns to flatten the structure.",
                    "impact": "Reduces readability, increases cognitive load, and makes testing harder."
                })
                break  # One issue per function block

        return smells

    def _detect_exception_handling(
        self,
        file_path: str,
        lines: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect improper exception handling."""
        smells = []

        for line_num, line in enumerate(lines, 1):
            # Detect bare except clauses
            if re.search(r'except\s*:\s*(pass|$)', line):
                smells.append({
                    "file": file_path,
                    "line": line_num,
                    "category": "reliability",
                    "type": "bare_except",
                    "severity": "high",
                    "title": "Bare Except Clause Found",
                    "description": f"Bare 'except:' clause on line {line_num} catches all exceptions, including system exits and keyboard interrupts.",
                    "code_snippet": line.strip(),
                    "suggestion": "Catch specific exceptions (e.g., 'except ValueError, KeyError:') to handle only expected errors.",
                    "impact": "Can hide bugs and make debugging difficult. May mask critical errors like SystemExit or KeyboardInterrupt."
                })

            # Detect caught exceptions being ignored
            if re.search(r'except.*:\s*pass', line):
                smells.append({
                    "file": file_path,
                    "line": line_num,
                    "category": "reliability",
                    "type": "ignored_exception",
                    "severity": "high",
                    "title": "Exception Silently Ignored",
                    "description": f"Exception on line {line_num} is caught and silently ignored with 'pass'. This can hide bugs.",
                    "code_snippet": line.strip(),
                    "suggestion": "Log the exception or handle it appropriately (e.g., 'except ValueError as e: logger.error(f\"Error: {e}\")')",
                    "impact": "Silent failures make debugging difficult and can lead to unexpected behavior."
                })

        return smells

    def _detect_duplication(
        self,
        file_path: str,
        lines: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect code duplication (DRY violations) including exact duplicate functions and code blocks."""
        smells = []
        seen_blocks = defaultdict(list)
        seen_multi_blocks = {}

        # First: Detect exact duplicate FUNCTIONS/METHODS
        smells.extend(self._detect_duplicate_functions(file_path, lines))

        # Second: Detect consecutive MULTI-LINE blocks (3+ lines) that repeat
        clean_lines = []
        line_map = []
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip empty lines and comments for block detection
            if stripped and not stripped.startswith('#') and not stripped.startswith('//'):
                clean_lines.append(stripped)
                line_map.append(line_num)
        
        # Check for repeated code blocks (min 3 consecutive lines)
        if len(clean_lines) >= 3:
            for block_size in range(3, min(10, len(clean_lines) // 2 + 1)):  # Check blocks of 3-10 lines
                for start_idx in range(len(clean_lines) - block_size + 1):
                    block = tuple(clean_lines[start_idx:start_idx + block_size])
                    if block not in seen_multi_blocks:
                        seen_multi_blocks[block] = []
                    seen_multi_blocks[block].append(start_idx)
        
        # Report duplicate multi-line blocks
        for block, occurrences in seen_multi_blocks.items():
            if len(occurrences) >= 2:  # Found duplicate block
                # Get line numbers for the first occurrence
                first_occurrence = occurrences[0]
                block_start_line = line_map[first_occurrence]
                block_end_line = line_map[first_occurrence + len(block) - 1]
                
                # Get all occurrence line numbers
                all_occurrences = []
                for occ_idx in occurrences:
                    start = line_map[occ_idx]
                    end = line_map[occ_idx + len(block) - 1]
                    all_occurrences.append(f"{start}-{end}")
                
                code_block = '\n'.join(block)
                smells.append({
                    "file": file_path,
                    "line": block_start_line,
                    "category": "maintainability",
                    "type": "duplicate_code_block",
                    "severity": "high" if len(block) >= 5 else "medium",
                    "title": f"🔴 DUPLICATE CODE BLOCK: {len(block)} lines repeated {len(occurrences)} times!",
                    "description": f"This {len(block)}-line code block appears {len(occurrences)} times at lines: {', '.join(all_occurrences)}. Likely copy-paste error.",
                    "code_snippet": code_block[:200] + "..." if len(code_block) > 200 else code_block,
                    "suggestion": f"Extract this logic into a reusable function. Remove redundant copies from lines: {', '.join(all_occurrences[1:])}.",
                    "impact": "CRITICAL: Code duplication reduces maintainability, increases bug risk, and wastes memory."
                })

        # Third: Look for duplicate individual lines
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Skip empty lines and comments
            if not stripped or stripped.startswith('#') or stripped.startswith('//'):
                continue

            # Track lines that appear multiple times
            seen_blocks[stripped].append(line_num)

        # Report individual line duplicates (but not if already caught as block)
        for code_line, occurrences in seen_blocks.items():
            if len(occurrences) >= self.thresholds['duplicate_code']['threshold']:
                # Only report if not part of a larger block we already reported
                is_part_of_block = False
                for block, _ in seen_multi_blocks.items():
                    if code_line in block:
                        is_part_of_block = True
                        break
                
                if not is_part_of_block:
                    smells.append({
                        "file": file_path,
                        "line": occurrences[0],
                        "category": "maintainability",
                        "type": "code_duplication",
                        "severity": "medium",
                        "title": "Code Duplication (DRY Violation)",
                        "description": f"Code appears {len(occurrences)} times in the file at lines {occurrences}. Violates DRY principle.",
                        "code_snippet": code_line,
                        "suggestion": "Extract common logic into a reusable function or utility.",
                        "impact": "Maintenance nightmare: when fixing bugs, every copy must be updated. Risk of inconsistencies."
                    })

        return smells

    def _detect_duplicate_functions(
        self,
        file_path: str,
        lines: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect exact duplicate functions/methods (entire function definitions)."""
        smells = []
        
        # Extract all functions/methods from the code
        functions = self._extract_functions(lines)
        
        # Look for duplicate function definitions
        function_signatures = defaultdict(list)
        
        for func_name, func_content, start_line, end_line in functions:
            # Use function content as key to detect exact duplicates
            func_key = func_content.strip()
            function_signatures[func_key].append({
                'name': func_name,
                'start': start_line,
                'end': end_line,
                'content': func_content
            })
        
        # Report exact duplicate functions
        for func_content, occurrences in function_signatures.items():
            if len(occurrences) >= 2:  # Exact duplicate found
                # Extract function name for better reporting
                func_name = occurrences[0]['name']
                line_numbers = [f"{o['start']}-{o['end']}" for o in occurrences]
                
                smells.append({
                    "file": file_path,
                    "line": occurrences[0]['start'],
                    "category": "maintainability",
                    "type": "duplicate_function",
                    "severity": "high",
                    "title": f"🔴 DUPLICATE FUNCTION: '{func_name}' defined {len(occurrences)} times!",
                    "description": f"Function/method '{func_name}' is defined identically {len(occurrences)} times at lines: {', '.join(line_numbers)}. This is likely a copy-paste error.",
                    "code_snippet": f"Function '{func_name}' appears at:\n" + "\n".join([f"  Lines {o['start']}-{o['end']}" for o in occurrences]),
                    "suggestion": f"Remove the duplicate definitions at lines {', '.join(line_numbers[1:])}. Keep only the first definition at line {occurrences[0]['start']}.",
                    "impact": "HIGH: Wastes memory, creates maintenance burden, and causes confusion. Any future changes must be made in multiple places."
                })
        
        return smells

    def _extract_functions(self, lines: List[str]) -> List[Tuple[str, str, int, int]]:
        """
        Extract all function/method definitions from code.
        
        Returns:
            List of tuples: (function_name, function_content, start_line, end_line)
        """
        functions = []
        
        # Patterns for function definitions (Python, JavaScript, Java, Go, etc.)
        function_start_pattern = r'^\s*(async\s+)?(def|function|func|public|private|protected)?\s*(\w+)\s*\('
        
        i = 0
        while i < len(lines):
            line = lines[i]
            match = re.match(function_start_pattern, line)
            
            if match:
                func_name = match.group(3)
                start_line = i + 1  # 1-indexed
                
                # Determine the indentation level of this function
                base_indent = len(line) - len(line.lstrip())
                
                # Extract function body
                func_lines = [line]
                i += 1
                
                # Continue collecting lines until we find a line at same/lower indent level
                # (or end of file)
                while i < len(lines):
                    current_line = lines[i]
                    
                    # Skip empty lines within function
                    if current_line.strip() == '':
                        func_lines.append(current_line)
                        i += 1
                        continue
                    
                    current_indent = len(current_line) - len(current_line.lstrip())
                    
                    # If we find a line at the same or lower indent level, we're done
                    if current_indent <= base_indent and current_line.strip() != '':
                        break
                    
                    func_lines.append(current_line)
                    i += 1
                
                end_line = i  # 1-indexed end
                func_content = '\n'.join(func_lines)
                
                functions.append((func_name, func_content, start_line, end_line))
            else:
                i += 1
        
        return functions

    def _detect_missing_validation(
        self,
        file_path: str,
        lines: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect missing input validation."""
        smells = []

        for line_num, line in enumerate(lines, 1):
            # Look for SQL queries without parameterization
            if re.search(r'(query|sql|select|insert|update|delete).*[f"\'].*\{.*\}', line, re.IGNORECASE):
                smells.append({
                    "file": file_path,
                    "line": line_num,
                    "category": "security",
                    "type": "missing_validation",
                    "severity": "critical",
                    "title": "SQL Injection Risk - No Input Validation",
                    "description": f"Line {line_num} uses string interpolation in SQL query. Vulnerable to SQL injection attacks.",
                    "code_snippet": line.strip(),
                    "suggestion": "Use parameterized queries or prepared statements (e.g., db.execute('SELECT * FROM users WHERE id = ?', (user_id,)))",
                    "impact": "CRITICAL: Attacker can inject malicious SQL to access, modify, or delete data."
                })

            # Look for HTML concatenation without escaping
            if re.search(r'html.*=.*[+].*|f["\'].*<.*>.*\{', line, re.IGNORECASE):
                smells.append({
                    "file": file_path,
                    "line": line_num,
                    "category": "security",
                    "type": "xss_risk",
                    "severity": "critical",
                    "title": "XSS Risk - Unsanitized HTML Output",
                    "description": f"Line {line_num} generates HTML from user input without escaping. XSS vulnerability.",
                    "code_snippet": line.strip(),
                    "suggestion": "Use HTML escaping functions (e.g., html.escape() in Python, DomPurify in JavaScript)",
                    "impact": "CRITICAL: Attacker can inject JavaScript to steal sessions, redirect users, or deface content."
                })

        return smells

    def _detect_missing_error_handling(
        self,
        file_path: str,
        lines: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect missing error handling for risky operations."""
        smells = []
        risky_operations = [
            ('open(', 'file_operation'),
            ('requests.get', 'network_call'),
            ('requests.post', 'network_call'),
            ('.json()', 'json_parse'),
            ('db.execute', 'database_operation'),
            ('os.system', 'system_call'),
        ]

        for line_num, line in enumerate(lines, 1):
            for operation, op_type in risky_operations:
                if operation in line:
                    # Check if next few lines have try/except
                    has_error_handling = False
                    
                    # Look back for try statement
                    for prev_line_num in range(max(0, line_num - 5), line_num):
                        if 'try' in lines[prev_line_num]:
                            has_error_handling = True
                            break
                    
                    # Look forward for except
                    for next_line_num in range(line_num, min(len(lines), line_num + 10)):
                        if 'except' in lines[next_line_num]:
                            has_error_handling = True
                            break
                    
                    if not has_error_handling:
                        smells.append({
                            "file": file_path,
                            "line": line_num,
                            "category": "reliability",
                            "type": "missing_error_handling",
                            "severity": "high",
                            "title": f"Missing Error Handling: {op_type.replace('_', ' ').title()}",
                            "description": f"Line {line_num} performs a risky '{op_type}' operation without error handling.",
                            "code_snippet": line.strip(),
                            "suggestion": f"Wrap in try/except block to handle potential failures (IOError, ConnectionError, JSONDecodeError, etc.)",
                            "impact": "Unhandled errors can crash the application or leave it in an inconsistent state."
                        })

        return smells

    def _detect_dry_violations(
        self,
        file_path: str,
        lines: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect DRY (Don't Repeat Yourself) principle violations."""
        smells = []

        # Look for repeated patterns (simplified)
        pattern_lines = defaultdict(list)
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if not stripped or stripped.startswith('#'):
                continue
            
            # Look for similar patterns (same first 10 chars)
            if len(stripped) > 10:
                pattern = stripped[:10]
                pattern_lines[pattern].append((line_num, stripped))

        for pattern, occurrences in pattern_lines.items():
            if len(occurrences) >= 3:
                line_numbers = [occ[0] for occ in occurrences]
                smells.append({
                    "file": file_path,
                    "line": line_numbers[0],
                    "category": "maintainability",
                    "type": "dry_violation",
                    "severity": "medium",
                    "title": "DRY Principle Violation",
                    "description": f"Similar code patterns found at lines {line_numbers}. Violates the DRY principle.",
                    "code_snippet": occurrences[0][1],
                    "suggestion": "Extract repeated logic into a reusable function or loop.",
                    "impact": "Makes code harder to maintain. Bug fixes must be applied in multiple places."
                })

        return smells

    def _is_code_file(self, file_path: str) -> bool:
        """Check if file is a code file (not binary, docs, etc)."""
        skip_extensions = {'.txt', '.md', '.json', '.yaml', '.yml', '.xml', '.html', '.css'}
        skip_patterns = {'node_modules', '.git', '__pycache__', '.venv', 'venv'}

        # Skip if matches any skip pattern
        for pattern in skip_patterns:
            if pattern in file_path:
                return False

        # Include if it's a code file
        ext = Path(file_path).suffix.lower()
        code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.go', '.rb', '.php', '.rs', '.kt', '.scala'}
        
        return ext in code_extensions

    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        if analysis["severity_breakdown"]["critical"] > 0:
            recommendations.append("[CRITICAL] Address security vulnerabilities immediately before merging.")

        if analysis["severity_breakdown"]["high"] > 3:
            recommendations.append("[HIGH] Multiple high-severity issues found. Consider refactoring before merge.")

        if len(analysis["smells_by_category"].get("maintainability", [])) > 5:
            recommendations.append("[MAINTAINABILITY] Extract functions, improve naming, and reduce nesting depth.")

        if len(analysis["smells_by_category"].get("security", [])) > 0:
            recommendations.append("[SECURITY] Review and apply security best practices. Never commit secrets.")

        if analysis["total_smells_found"] == 0:
            recommendations.append("[SUCCESS] Excellent: No code smells detected!")

        return recommendations


# Create singleton instance
code_smells_analyzer = CodeSmellsAnalyzer()
