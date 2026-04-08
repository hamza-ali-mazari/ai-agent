"""
Deep Dependency Analyzer for Code Review

Identifies all dependencies, deep dependency chains, version conflicts,
and potential security risks in project files.
"""

import json
import re
import logging
from typing import Dict, List, Set, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class DependencyType(str, Enum):
    DIRECT = "direct"
    TRANSITIVE = "transitive"
    PEER = "peer"
    OPTIONAL = "optional"


class DeprecationLevel(str, Enum):
    MAINTAINED = "maintained"
    DEPRECATED = "deprecated"
    CRITICAL = "critical"
    EOL = "end_of_life"


class DependencyAnalyzer:
    """Analyzes dependencies across all files in a code review."""

    def __init__(self):
        self.dependencies: Dict[str, Dict[str, Any]] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.vulnerability_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.known_vulnerable_versions = self._load_vulnerability_database()

    def analyze_file_dependencies(
        self,
        file_path: str,
        file_content: str,
        language: str
    ) -> Dict[str, Any]:
        """Extract and analyze dependencies from a file."""
        deps = self._extract_dependencies(file_path, file_content, language)
        analysis = {
            "file_path": file_path,
            "language": language,
            "dependencies": deps,
            "issues": self._analyze_dependency_issues(deps, language)
        }
        return analysis

    def _extract_dependencies(
        self,
        file_path: str,
        content: str,
        language: str
    ) -> List[Dict[str, Any]]:
        """Extract dependencies based on language and file type."""
        if language == "python":
            return self._extract_python_deps(content)
        elif language in ["javascript", "typescript"]:
            return self._extract_npm_deps(content)
        elif language == "java":
            return self._extract_maven_deps(content)
        elif language in ["csharp"]:
            return self._extract_nuget_deps(content)
        elif language == "go":
            return self._extract_go_deps(content)
        elif language == "rust":
            return self._extract_cargo_deps(content)
        return []

    def _extract_python_deps(self, content: str) -> List[Dict[str, Any]]:
        """Extract Python dependencies from imports and requirements."""
        deps = []
        # Find import statements
        import_pattern = r'^\s*(from\s+(\S+)|import\s+(\S+))'
        for match in re.finditer(import_pattern, content, re.MULTILINE):
            full_match = match.group(2) or match.group(3)
            if full_match:
                package = full_match.split('.')[0]
                deps.append({
                    "name": package,
                    "version": "unknown",
                    "type": DependencyType.DIRECT.value,
                    "source": "import"
                })

        # Find requirements.txt style
        req_pattern = r'([a-zA-Z0-9\-_]+)([><=!~]+)?([0-9\.\*]+)?'
        for match in re.finditer(req_pattern, content):
            if match.group(1) and not match.group(1) in ['from', 'import']:
                deps.append({
                    "name": match.group(1),
                    "version": match.group(3) or "unspecified",
                    "type": DependencyType.DIRECT.value,
                    "source": "requirement"
                })

        return list({d['name']: d for d in deps}.values())

    def _extract_npm_deps(self, content: str) -> List[Dict[str, Any]]:
        """Extract NPM/Yarn dependencies from package.json."""
        deps = []
        try:
            data = json.loads(content)
            for dep_type in ['dependencies', 'devDependencies', 'peerDependencies']:
                if dep_type in data:
                    for name, version in data[dep_type].items():
                        deps.append({
                            "name": name,
                            "version": version,
                            "type": DependencyType.DIRECT.value if dep_type == 'dependencies' else DependencyType.OPTIONAL.value,
                            "source": dep_type
                        })
        except json.JSONDecodeError:
            logger.warning("Could not parse JSON for NPM dependencies")
        return deps

    def _extract_maven_deps(self, content: str) -> List[Dict[str, Any]]:
        """Extract Maven dependencies from pom.xml."""
        deps = []
        # Simple regex for Maven dependencies
        pattern = r'<dependency>\s*<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>\s*<version>([^<]+)</version>'
        for match in re.finditer(pattern, content, re.DOTALL):
            deps.append({
                "name": f"{match.group(1)}:{match.group(2)}",
                "version": match.group(3),
                "type": DependencyType.DIRECT.value,
                "source": "pom.xml"
            })
        return deps

    def _extract_nuget_deps(self, content: str) -> List[Dict[str, Any]]:
        """Extract NuGet dependencies from .csproj or packages.config."""
        deps = []
        # .csproj style
        pattern = r'<PackageReference\s+Include="([^"]+)"\s+Version="([^"]+)"'
        for match in re.finditer(pattern, content):
            deps.append({
                "name": match.group(1),
                "version": match.group(2),
                "type": DependencyType.DIRECT.value,
                "source": ".csproj"
            })
        return deps

    def _extract_go_deps(self, content: str) -> List[Dict[str, Any]]:
        """Extract Go module dependencies from go.mod."""
        deps = []
        # go.mod style
        pattern = r'^require\s+([^\s]+)\s+([^\s]+)$'
        for match in re.finditer(pattern, content, re.MULTILINE):
            deps.append({
                "name": match.group(1),
                "version": match.group(2),
                "type": DependencyType.DIRECT.value,
                "source": "go.mod"
            })
        return deps

    def _extract_cargo_deps(self, content: str) -> List[Dict[str, Any]]:
        """Extract Rust Cargo dependencies from Cargo.toml."""
        deps = []
        # Cargo.toml style
        pattern = r'(\w+)\s*=\s*"([^"]+)"'
        for match in re.finditer(pattern, content):
            deps.append({
                "name": match.group(1),
                "version": match.group(2),
                "type": DependencyType.DIRECT.value,
                "source": "Cargo.toml"
            })
        return deps

    def _analyze_dependency_issues(
        self,
        dependencies: List[Dict[str, Any]],
        language: str
    ) -> List[Dict[str, Any]]:
        """Identify issues with dependencies."""
        issues = []

        for dep in dependencies:
            # Check for known vulnerabilities
            vuln = self._check_vulnerability(dep['name'], dep['version'])
            if vuln:
                issues.extend(vuln)

            # Check for deprecated packages
            if self._is_deprecated(dep['name'], language):
                issues.append({
                    "type": "deprecated_package",
                    "severity": "high",
                    "package": dep['name'],
                    "message": f"Package '{dep['name']}' is deprecated - consider alternative",
                    "deprecation_level": DeprecationLevel.DEPRECATED.value
                })

            # Check for unspecified versions
            if dep['version'] in ["unknown", "unspecified", "*"]:
                issues.append({
                    "type": "unspecified_version",
                    "severity": "medium",
                    "package": dep['name'],
                    "message": f"Dependency '{dep['name']}' has unspecified version - pinning recommended"
                })

        return issues

    def build_dependency_graph(
        self,
        all_dependencies: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Build dependency graph for transitive dependency analysis."""
        graph = {}
        for dep in all_dependencies:
            if dep['name'] not in graph:
                graph[dep['name']] = []
        return graph

    def find_deep_dependencies(
        self,
        root_package: str,
        depth: int = 5
    ) -> Dict[str, Any]:
        """Find all deep dependencies of a package up to specified depth."""
        visited = set()
        depth_map = {}
        return self._dfs_dependencies(root_package, 0, depth, visited, depth_map)

    def _dfs_dependencies(
        self,
        package: str,
        current_depth: int,
        max_depth: int,
        visited: Set[str],
        depth_map: Dict[str, int]
    ) -> Dict[str, Any]:
        """DFS to find transitive dependencies."""
        if current_depth > max_depth or package in visited:
            return {}

        visited.add(package)
        depth_map[package] = current_depth

        children = {}
        if package in self.dependency_graph:
            for child in self.dependency_graph[package]:
                if child not in visited:
                    children[child] = self._dfs_dependencies(
                        child, current_depth + 1, max_depth, visited, depth_map
                    )

        return {
            "package": package,
            "depth": current_depth,
            "dependencies": children
        }

    def check_version_conflicts(
        self,
        dependencies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify version conflicts in dependencies."""
        conflicts = []
        name_versions: Dict[str, Set[str]] = {}

        for dep in dependencies:
            name = dep['name']
            version = dep['version']
            if name not in name_versions:
                name_versions[name] = set()
            name_versions[name].add(version)

        for name, versions in name_versions.items():
            if len(versions) > 1 and "unknown" not in versions:
                conflicts.append({
                    "type": "version_conflict",
                    "severity": "high",
                    "package": name,
                    "versions": list(versions),
                    "message": f"Package '{name}' has multiple versions: {', '.join(versions)}"
                })

        return conflicts

    def _check_vulnerability(
        self,
        package: str,
        version: str
    ) -> List[Dict[str, Any]]:
        """Check for known vulnerabilities."""
        issues = []
        if package in self.known_vulnerable_versions:
            vuln_list = self.known_vulnerable_versions[package]
            for vuln in vuln_list:
                if self._version_matches(version, vuln['affected_versions']):
                    issues.append({
                        "type": "security_vulnerability",
                        "severity": "critical",
                        "package": package,
                        "version": version,
                        "cve": vuln.get('cve'),
                        "message": vuln.get('description')
                    })
        return issues

    def _is_deprecated(self, package: str, language: str) -> bool:
        """Check if package is deprecated."""
        deprecated_packages = {
            "python": {"md5", "sha1", "pickle"},
            "javascript": {"bower", "grunt", "gulp"},
            "java": {"log4j:1.2"}
        }
        return package in deprecated_packages.get(language, set())

    def _version_matches(self, version: str, affected: List[str]) -> bool:
        """Check if version matches affected versions pattern."""
        # Simplified version matching
        return version in affected or "*" in affected

    def _load_vulnerability_database(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load known vulnerability database."""
        return {
            "log4j": [{
                "affected_versions": ["2.0", "2.1", "2.14", "2.14.1"],
                "cve": "CVE-2021-44228",
                "description": "Log4j Remote Code Execution - Immediate patch required"
            }],
            "struts2": [{
                "affected_versions": ["*"],
                "cve": "CVE-2017-5638",
                "description": "Apache Struts2 Remote Code Execution"
            }]
        }

    def generate_dependency_report(
        self,
        all_dependencies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate comprehensive dependency analysis report."""
        conflicts = self.check_version_conflicts(all_dependencies)
        issues_by_package = {}

        for dep in all_dependencies:
            issues = self._analyze_dependency_issues([dep], "python")
            if issues:
                issues_by_package[dep['name']] = issues

        return {
            "total_dependencies": len(all_dependencies),
            "unique_packages": len(set(d['name'] for d in all_dependencies)),
            "version_conflicts": conflicts,
            "issues_by_package": issues_by_package,
            "critical_issues": len([i for i in conflicts if i['severity'] == 'critical']),
            "recommendations": self._generate_recommendations(
                all_dependencies, conflicts, issues_by_package
            )
        }

    def _generate_recommendations(
        self,
        dependencies: List[Dict[str, Any]],
        conflicts: List[Dict[str, Any]],
        issues: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        if conflicts:
            recommendations.append(f"Resolve {len(conflicts)} version conflict(s) in dependencies")

        critical_vulns = sum(
            1 for pkg_issues in issues.values()
            for issue in pkg_issues.get('security_vulnerability', [])
        )
        if critical_vulns > 0:
            recommendations.append(f"Apply {critical_vulns} critical security patches")

        if any(d['version'] == "*" for d in dependencies):
            recommendations.append("Pin dependency versions - wildcard versions found")

        return recommendations
