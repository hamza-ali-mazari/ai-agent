"""
Project Context Analyzer

Analyzes full project context to understand dependencies and impact
of code changes on other files in the repository.
"""

import os
import logging
import re
from typing import Dict, List, Set, Any, Optional, Tuple
from pathlib import Path
import requests
from collections import defaultdict

logger = logging.getLogger(__name__)


class ProjectContextAnalyzer:
    """Analyzes project structure and dependencies."""

    def __init__(self):
        self.bitbucket_username = os.getenv("BITBUCKET_USERNAME")
        self.bitbucket_app_password = os.getenv("BITBUCKET_APP_PASSWORD")
        self.bitbucket_oauth_token = os.getenv("BITBUCKET_OAUTH_TOKEN")
        self.api_base = "https://api.bitbucket.org/2.0"
        
        # Language-specific import patterns
        self.import_patterns = {
            'python': [
                r'from\s+([\w\.]+)\s+import',
                r'import\s+([\w\.]+)',
            ],
            'javascript': [
                r"require\('([\w\./]+)'\)",
                r'require\("([\w\./]+)"\)',
                r'from\s+["\']?([\w\./]+)["\']?\s+import',
                r'import\s+.*\s+from\s+["\']?([\w\./]+)["\']?',
            ],
            'java': [
                r'import\s+([\w\.]+)(?:\.\*)?;',
            ],
            'csharp': [
                r'using\s+([\w\.]+);',
            ],
        }

    def get_auth_headers(self) -> Dict[str, str]:
        """Get Bitbucket API authentication headers."""
        headers = {}
        if self.bitbucket_oauth_token:
            headers["Authorization"] = f"Bearer {self.bitbucket_oauth_token}"
        elif self.bitbucket_username and self.bitbucket_app_password:
            import base64
            credentials = base64.b64encode(
                f"{self.bitbucket_username}:{self.bitbucket_app_password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {credentials}"
        return headers

    def fetch_project_files(
        self,
        workspace: str,
        repo_slug: str,
        branch: str = "master"
    ) -> Dict[str, str]:
        """
        Fetch all project files from Bitbucket repository.
        
        Args:
            workspace: Bitbucket workspace
            repo_slug: Repository slug
            branch: Branch to fetch from
            
        Returns:
            Dict mapping file paths to their contents
        """
        files = {}
        try:
            # Fetch repository structure recursively
            url = f"{self.api_base}/repositories/{workspace}/{repo_slug}/src/{branch}"
            headers = self.get_auth_headers()
            
            def fetch_directory(path: str = "") -> None:
                """Recursively fetch files from a directory."""
                params = {"pagelen": 100}
                if path:
                    full_url = f"{url}/{path}"
                else:
                    full_url = url
                    
                try:
                    response = requests.get(full_url, headers=headers, params=params, timeout=30)
                    response.raise_for_status()
                    data = response.json()
                    
                    for item in data.get("values", []):
                        if item["type"] == "commit_file":
                            # It's a file - fetch its content
                            file_path = item["path"]
                            
                            # Skip common non-code files
                            if self._should_skip_file(file_path):
                                continue
                                
                            content_url = f"{self.api_base}/repositories/{workspace}/{repo_slug}/src/{branch}/{file_path}"
                            try:
                                content_resp = requests.get(
                                    content_url,
                                    headers=headers,
                                    timeout=10
                                )
                                if content_resp.status_code == 200:
                                    files[file_path] = content_resp.text
                                    logger.info(f"Fetched file: {file_path}")
                            except Exception as e:
                                logger.warning(f"Failed to fetch file {file_path}: {e}")
                                
                        elif item["type"] == "commit_directory":
                            # It's a directory - recurse
                            dir_path = item["path"]
                            if not self._should_skip_directory(dir_path):
                                fetch_directory(dir_path)
                                
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error fetching directory {path}: {e}")
            
            fetch_directory()
            logger.info(f"Fetched {len(files)} files from project")
            
        except Exception as e:
            logger.error(f"Error fetching project files: {e}")
            
        return files

    def analyze_dependencies(
        self,
        changed_files: List[str],
        all_files: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Analyze which files depend on the changed files.
        
        Args:
            changed_files: List of modified file paths
            all_files: Dict of all project files and their contents
            
        Returns:
            Dict with dependency analysis
        """
        affected_files = set()
        dependency_graph = defaultdict(list)
        
        # Build index of what each file exports/defines
        exports_by_file = self._extract_exports(all_files)
        
        # For each changed file, find what it exports
        changed_exports = {}
        for changed_file in changed_files:
            if changed_file in exports_by_file:
                changed_exports[changed_file] = exports_by_file[changed_file]
        
        # Find which files import from changed files
        for file_path, content in all_files.items():
            if file_path in changed_files:
                continue
                
            imports = self._extract_imports(file_path, content)
            
            for import_name in imports:
                # Check if this import references a changed file
                for changed_file, exports in changed_exports.items():
                    if self._matches_import(import_name, changed_file, exports):
                        affected_files.add(file_path)
                        dependency_graph[changed_file].append(file_path)
                        
        return {
            "affected_files": list(affected_files),
            "dependency_graph": dict(dependency_graph),
            "changed_exports": changed_exports,
            "impact_level": self._calculate_impact_level(affected_files, len(all_files))
        }

    def _extract_exports(self, files: Dict[str, str]) -> Dict[str, Set[str]]:
        """Extract function/class names defined in each file."""
        exports = defaultdict(set)
        
        for file_path, content in files.items():
            lang = self._detect_language(file_path)
            
            if lang == "python":
                # Extract function and class definitions
                exports[file_path].update(self._extract_python_exports(content))
            elif lang == "javascript":
                # Extract exports and function definitions
                exports[file_path].update(self._extract_js_exports(content))
            elif lang == "java":
                # Extract class definitions
                exports[file_path].update(self._extract_java_exports(content))
                
        return exports

    def _extract_python_exports(self, content: str) -> Set[str]:
        """Extract Python function and class names."""
        exports = set()
        
        # Match function definitions
        func_pattern = r'^def\s+(\w+)\s*\('
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            exports.add(match.group(1))
            
        # Match class definitions
        class_pattern = r'^class\s+(\w+)\s*[\(:]'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            exports.add(match.group(1))
            
        # Match __all__ exports
        all_pattern = r'__all__\s*=\s*\[(.*?)\]'
        for match in re.finditer(all_pattern, content, re.DOTALL):
            names = re.findall(r"['\"](\w+)['\"]", match.group(1))
            exports.update(names)
            
        return exports

    def _extract_js_exports(self, content: str) -> Set[str]:
        """Extract JavaScript exports."""
        exports = set()
        
        # Match export default
        exports_pattern = r'(?:export\s+(?:default\s+)?(?:function|class|const|let|var)\s+)?(\w+)'
        for match in re.finditer(exports_pattern, content):
            name = match.group(1)
            if name not in ['export', 'function', 'class', 'const', 'let', 'var']:
                exports.add(name)
                
        # Match module.exports
        module_pattern = r'module\.exports\.(\w+)|exports\.(\w+)'
        for match in re.finditer(module_pattern, content):
            name = match.group(1) or match.group(2)
            if name:
                exports.add(name)
                
        return exports

    def _extract_java_exports(self, content: str) -> Set[str]:
        """Extract Java class and method names."""
        exports = set()
        
        # Match class definitions
        class_pattern = r'(?:public\s+)?class\s+(\w+)'
        for match in re.finditer(class_pattern, content):
            exports.add(match.group(1))
            
        # Match public methods
        method_pattern = r'public\s+(?:static\s+)?(?:\w+\s+)+(\w+)\s*\('
        for match in re.finditer(method_pattern, content):
            exports.add(match.group(1))
            
        return exports

    def _extract_imports(self, file_path: str, content: str) -> Set[str]:
        """Extract import names from a file."""
        imports = set()
        lang = self._detect_language(file_path)
        
        if lang not in self.import_patterns:
            return imports
            
        patterns = self.import_patterns[lang]
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                import_name = match.group(1)
                if import_name:
                    imports.add(import_name)
                    
        return imports

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'javascript',
            '.jsx': 'javascript',
            '.tsx': 'javascript',
            '.java': 'java',
            '.cs': 'csharp',
        }
        
        ext = Path(file_path).suffix.lower()
        return ext_to_lang.get(ext, 'unknown')

    def _matches_import(self, import_name: str, file_path: str, exports: Set[str]) -> bool:
        """Check if an import matches a file or its exports."""
        # Remove extension
        file_without_ext = Path(file_path).stem
        
        # Direct file match
        if import_name == file_without_ext:
            return True
            
        # Check if imported name is in file's exports
        if import_name in exports:
            return True
            
        # Module path match (e.g., 'utils.helpers' matches 'utils/helpers.py')
        if '.' in import_name:
            path_version = import_name.replace('.', '/')
            if path_version in file_path or f"{path_version}.py" in file_path:
                return True
                
        return False

    def _calculate_impact_level(self, affected_files: Set, total_files: int) -> str:
        """Calculate impact level of changes."""
        if not total_files:
            return "unknown"
            
        impact_ratio = len(affected_files) / total_files
        
        if impact_ratio > 0.5:
            return "critical"
        elif impact_ratio > 0.25:
            return "high"
        elif impact_ratio > 0.1:
            return "medium"
        elif impact_ratio > 0:
            return "low"
        else:
            return "isolated"

    def _should_skip_file(self, file_path: str) -> bool:
        """Check if file should be skipped."""
        skip_patterns = [
            r'\.git',
            r'\.venv',
            r'__pycache__',
            r'node_modules',
            r'\.egg-info',
            r'\.pyc$',
            r'\.map$',
            r'package-lock\.json',
            r'\.lock$',
            r'README',
            r'LICENSE',
            r'\.md$',
        ]
        
        for pattern in skip_patterns:
            if re.search(pattern, file_path, re.IGNORECASE):
                return True
                
        return False

    def _should_skip_directory(self, dir_path: str) -> bool:
        """Check if directory should be skipped."""
        skip_dirs = [
            '.git', '.venv', '__pycache__', 'node_modules',
            '.egg-info', '.pytest_cache', 'dist', 'build',
            '.next', '.nuxt', '.cache', 'coverage', '.env'
        ]
        
        for skip_dir in skip_dirs:
            if skip_dir in dir_path.split('/'):
                return True
                
        return False

    def generate_impact_report(
        self,
        changed_files: List[str],
        dependency_analysis: Dict[str, Any]
    ) -> str:
        """Generate a human-readable impact report."""
        report = []
        report.append("## 📊 Project Impact Analysis\n")
        
        impact_level = dependency_analysis.get("impact_level", "unknown")
        affected_count = len(dependency_analysis.get("affected_files", []))
        
        level_emoji = {
            "critical": "🚨",
            "high": "⚠️",
            "medium": "🟡",
            "low": "🔵",
            "isolated": "✅"
        }
        
        emoji = level_emoji.get(impact_level, "❓")
        report.append(f"**Impact Level:** {emoji} {impact_level.upper()}")
        report.append(f"**Affected Files:** {affected_count}")
        report.append("")
        
        if affected_count > 0:
            report.append("**Files that may be affected by your changes:**")
            for file in dependency_analysis.get("affected_files", [])[:10]:
                report.append(f"- {file}")
            if affected_count > 10:
                report.append(f"- ... and {affected_count - 10} more files")
            report.append("")
        
        # Show dependency graph
        dep_graph = dependency_analysis.get("dependency_graph", {})
        if dep_graph:
            report.append("**Dependency Graph:**")
            for changed_file, dependents in dep_graph.items():
                report.append(f"- **{changed_file}** is used by:")
                for dependent in dependents[:3]:
                    report.append(f"  - {dependent}")
                if len(dependents) > 3:
                    report.append(f"  - ... and {len(dependents) - 3} more files")
            report.append("")
        
        report.append("**Recommendation:** Review affected files to ensure compatibility with your changes.")
        
        return "\n".join(report)


# Global instance
project_analyzer = ProjectContextAnalyzer()
