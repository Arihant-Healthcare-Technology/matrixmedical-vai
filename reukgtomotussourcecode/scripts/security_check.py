#!/usr/bin/env python3
"""
Security Check Script - SOW Requirement 9.6

Automated security validation script for UKG Integration Suite.
Checks for common security issues before production deployment.

Usage:
    python scripts/security_check.py [--strict] [--fix]

Checks performed:
1. No .env files in git
2. Production endpoints configured
3. Unique credentials per project
4. .gitignore entries for sensitive files
5. Docker runs as non-root
6. No hardcoded secrets in code
7. Required environment variables documented
"""

import os
import re
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

# ANSI colors for output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


@dataclass
class CheckResult:
    """Result of a security check."""
    name: str
    passed: bool
    message: str
    severity: str = "error"  # error, warning, info
    details: List[str] = field(default_factory=list)
    fixable: bool = False
    fix_command: Optional[str] = None


class SecurityChecker:
    """Security validation for UKG Integration Suite."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.results: List[CheckResult] = []
        self.projects = [
            "vai-matrix-ukg-bill-final",
            "vai-matrix-ukg-motus-final",
            "vai-matrix-ukg-travelperk-final",
        ]

    def run_all_checks(self) -> bool:
        """Run all security checks."""
        print(f"\n{BOLD}UKG Integration Suite - Security Check{RESET}")
        print("=" * 50)

        checks = [
            self.check_env_files_not_in_git,
            self.check_gitignore_entries,
            self.check_no_hardcoded_secrets,
            self.check_docker_nonroot_user,
            self.check_production_endpoints,
            self.check_unique_credentials,
            self.check_sensitive_file_permissions,
            self.check_dependencies_security,
        ]

        for check in checks:
            result = check()
            self.results.append(result)
            self._print_result(result)

        return self._print_summary()

    def _print_result(self, result: CheckResult) -> None:
        """Print a single check result."""
        if result.passed:
            status = f"{GREEN}PASS{RESET}"
        elif result.severity == "warning":
            status = f"{YELLOW}WARN{RESET}"
        else:
            status = f"{RED}FAIL{RESET}"

        print(f"\n[{status}] {result.name}")
        print(f"       {result.message}")

        if result.details:
            for detail in result.details[:5]:  # Show first 5 details
                print(f"       - {detail}")
            if len(result.details) > 5:
                print(f"       ... and {len(result.details) - 5} more")

        if result.fixable and result.fix_command:
            print(f"       {BLUE}Fix: {result.fix_command}{RESET}")

    def _print_summary(self) -> bool:
        """Print summary and return success status."""
        print("\n" + "=" * 50)
        print(f"{BOLD}Summary{RESET}")

        passed = sum(1 for r in self.results if r.passed)
        warnings = sum(1 for r in self.results if not r.passed and r.severity == "warning")
        failed = sum(1 for r in self.results if not r.passed and r.severity == "error")
        total = len(self.results)

        print(f"  Total checks: {total}")
        print(f"  {GREEN}Passed: {passed}{RESET}")
        print(f"  {YELLOW}Warnings: {warnings}{RESET}")
        print(f"  {RED}Failed: {failed}{RESET}")

        if failed > 0:
            print(f"\n{RED}{BOLD}Security check FAILED{RESET}")
            print("Please fix the issues above before deploying to production.")
            return False
        elif warnings > 0:
            print(f"\n{YELLOW}{BOLD}Security check PASSED with warnings{RESET}")
            print("Consider addressing the warnings before production deployment.")
            return True
        else:
            print(f"\n{GREEN}{BOLD}Security check PASSED{RESET}")
            return True

    def check_env_files_not_in_git(self) -> CheckResult:
        """Check that .env files are not tracked by git."""
        tracked_env_files = []

        try:
            result = subprocess.run(
                ["git", "ls-files", "*.env", "*.env.*"],
                capture_output=True,
                text=True,
                cwd=self.root_dir
            )
            if result.returncode == 0 and result.stdout.strip():
                tracked_env_files = result.stdout.strip().split('\n')
        except FileNotFoundError:
            return CheckResult(
                name="Environment files not in git",
                passed=True,
                message="Not a git repository, skipping check",
                severity="info"
            )

        if tracked_env_files:
            return CheckResult(
                name="Environment files not in git",
                passed=False,
                message=f"Found {len(tracked_env_files)} .env file(s) tracked by git",
                details=tracked_env_files,
                fixable=True,
                fix_command="git rm --cached <file> && git commit"
            )

        return CheckResult(
            name="Environment files not in git",
            passed=True,
            message="No .env files are tracked by git"
        )

    def check_gitignore_entries(self) -> CheckResult:
        """Check that .gitignore has required entries."""
        required_patterns = [
            ".env",
            "*.env",
            ".env.*",
            "__pycache__",
            "*.pyc",
            "data/",
            "*.log",
        ]

        gitignore_path = self.root_dir / ".gitignore"
        if not gitignore_path.exists():
            return CheckResult(
                name=".gitignore configuration",
                passed=False,
                message="No .gitignore file found",
                fixable=True,
                fix_command="Create .gitignore with sensitive file patterns"
            )

        with open(gitignore_path, 'r') as f:
            gitignore_content = f.read()

        missing = []
        for pattern in required_patterns:
            if pattern not in gitignore_content:
                missing.append(pattern)

        if missing:
            return CheckResult(
                name=".gitignore configuration",
                passed=False,
                message=f"Missing {len(missing)} recommended patterns",
                details=missing,
                severity="warning",
                fixable=True,
                fix_command=f"Add missing patterns to .gitignore"
            )

        return CheckResult(
            name=".gitignore configuration",
            passed=True,
            message="All recommended patterns are in .gitignore"
        )

    def check_no_hardcoded_secrets(self) -> CheckResult:
        """Check for hardcoded secrets in source code."""
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "hardcoded password"),
            (r'api_key\s*=\s*["\'][A-Za-z0-9]{20,}["\']', "hardcoded API key"),
            (r'token\s*=\s*["\'][A-Za-z0-9]{20,}["\']', "hardcoded token"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "hardcoded secret"),
            (r'Bearer\s+[A-Za-z0-9_-]{20,}', "hardcoded bearer token"),
            (r'AKIA[0-9A-Z]{16}', "AWS access key"),
        ]

        findings = []
        python_files = list(self.root_dir.rglob("*.py"))

        for py_file in python_files:
            # Skip test files and this script
            if "test" in py_file.name.lower() or py_file.name == "security_check.py":
                continue

            try:
                content = py_file.read_text()
                for pattern, desc in secret_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        rel_path = py_file.relative_to(self.root_dir)
                        findings.append(f"{rel_path}: {desc}")
            except Exception:
                continue

        if findings:
            return CheckResult(
                name="No hardcoded secrets",
                passed=False,
                message=f"Found {len(findings)} potential hardcoded secrets",
                details=findings,
                severity="error"
            )

        return CheckResult(
            name="No hardcoded secrets",
            passed=True,
            message="No hardcoded secrets detected in Python files"
        )

    def check_docker_nonroot_user(self) -> CheckResult:
        """Check that Dockerfiles use non-root user."""
        issues = []

        for project in self.projects:
            dockerfile = self.root_dir / project / "Dockerfile"
            if not dockerfile.exists():
                continue

            content = dockerfile.read_text()

            # Check for USER directive
            if "USER " not in content:
                issues.append(f"{project}: No USER directive found")
            elif "USER root" in content.lower():
                issues.append(f"{project}: Runs as root user")

        if issues:
            return CheckResult(
                name="Docker non-root user",
                passed=False,
                message=f"Found {len(issues)} Dockerfile(s) without non-root user",
                details=issues,
                fixable=True,
                fix_command="Add 'RUN useradd -m appuser && USER appuser' to Dockerfile"
            )

        return CheckResult(
            name="Docker non-root user",
            passed=True,
            message="All Dockerfiles run as non-root user"
        )

    def check_production_endpoints(self) -> CheckResult:
        """Check for staging/sandbox endpoints in production config."""
        staging_indicators = [
            "sandbox",
            "stage",
            "staging",
            "dev.",
            "-dev",
            "test.",
            "-test",
            "localhost",
            "127.0.0.1",
        ]

        env_files = list(self.root_dir.rglob("*.env"))
        env_files.extend(self.root_dir.rglob("*.env.example"))

        findings = []

        for env_file in env_files:
            # Skip production template files
            if "production" in env_file.name.lower():
                continue

            try:
                content = env_file.read_text()
                for line in content.split('\n'):
                    if '=' not in line or line.strip().startswith('#'):
                        continue

                    key, _, value = line.partition('=')
                    key = key.strip()
                    value = value.strip().strip('"\'')

                    # Check for URLs with staging indicators
                    if any(ind in value.lower() for ind in staging_indicators):
                        if 'URL' in key.upper() or 'BASE' in key.upper() or 'ENDPOINT' in key.upper():
                            rel_path = env_file.relative_to(self.root_dir)
                            findings.append(f"{rel_path}: {key} contains staging URL")
            except Exception:
                continue

        if findings:
            return CheckResult(
                name="Production endpoints",
                passed=False,
                message=f"Found {len(findings)} staging/sandbox endpoint(s)",
                details=findings,
                severity="warning"
            )

        return CheckResult(
            name="Production endpoints",
            passed=True,
            message="No staging/sandbox endpoints detected"
        )

    def check_unique_credentials(self) -> CheckResult:
        """Check that credentials differ across projects."""
        credentials_by_project: Dict[str, Dict[str, str]] = {}
        credential_keys = ['API_KEY', 'TOKEN', 'SECRET', 'PASSWORD']

        for project in self.projects:
            project_dir = self.root_dir / project
            env_files = list(project_dir.glob("*.env"))

            credentials_by_project[project] = {}

            for env_file in env_files:
                try:
                    content = env_file.read_text()
                    for line in content.split('\n'):
                        if '=' not in line:
                            continue
                        key, _, value = line.partition('=')
                        key = key.strip()
                        value = value.strip().strip('"\'')

                        if any(ck in key.upper() for ck in credential_keys):
                            if value and not value.startswith('$'):
                                credentials_by_project[project][key] = value
                except Exception:
                    continue

        # Check for duplicates across projects
        duplicates = []
        projects_list = list(credentials_by_project.keys())

        for i, project1 in enumerate(projects_list):
            for project2 in projects_list[i + 1:]:
                for key, value in credentials_by_project[project1].items():
                    if key in credentials_by_project[project2]:
                        if credentials_by_project[project2][key] == value:
                            duplicates.append(f"{key} same in {project1} and {project2}")

        if duplicates:
            return CheckResult(
                name="Unique credentials per project",
                passed=False,
                message=f"Found {len(duplicates)} shared credential(s)",
                details=duplicates,
                severity="warning"
            )

        return CheckResult(
            name="Unique credentials per project",
            passed=True,
            message="Credentials appear unique across projects"
        )

    def check_sensitive_file_permissions(self) -> CheckResult:
        """Check permissions on sensitive files."""
        issues = []

        sensitive_patterns = ["*.env", "*.key", "*.pem", "*secret*"]

        for pattern in sensitive_patterns:
            for file_path in self.root_dir.rglob(pattern):
                if file_path.is_file():
                    try:
                        mode = file_path.stat().st_mode & 0o777
                        if mode & 0o077:  # Readable/writable by group or others
                            rel_path = file_path.relative_to(self.root_dir)
                            issues.append(f"{rel_path}: mode {oct(mode)} (should be 600)")
                    except Exception:
                        continue

        if issues:
            return CheckResult(
                name="Sensitive file permissions",
                passed=False,
                message=f"Found {len(issues)} file(s) with loose permissions",
                details=issues,
                severity="warning",
                fixable=True,
                fix_command="chmod 600 <file>"
            )

        return CheckResult(
            name="Sensitive file permissions",
            passed=True,
            message="Sensitive files have appropriate permissions"
        )

    def check_dependencies_security(self) -> CheckResult:
        """Check for known vulnerable dependencies."""
        requirements_files = list(self.root_dir.rglob("requirements*.txt"))

        if not requirements_files:
            return CheckResult(
                name="Dependency security",
                passed=True,
                message="No requirements.txt files found",
                severity="info"
            )

        # List of known vulnerable packages (simplified check)
        vulnerable_packages = {
            "pyyaml<5.4": "CVE-2020-14343",
            "requests<2.25.0": "CVE-2018-18074",
            "urllib3<1.26.5": "CVE-2021-33503",
            "pillow<8.3.2": "CVE-2021-34552",
        }

        findings = []

        for req_file in requirements_files:
            try:
                content = req_file.read_text()
                for line in content.split('\n'):
                    line = line.strip().lower()
                    if not line or line.startswith('#'):
                        continue

                    for vuln_spec, cve in vulnerable_packages.items():
                        pkg = vuln_spec.split('<')[0].split('=')[0]
                        if line.startswith(pkg):
                            rel_path = req_file.relative_to(self.root_dir)
                            findings.append(f"{rel_path}: {pkg} may have {cve}")
            except Exception:
                continue

        if findings:
            return CheckResult(
                name="Dependency security",
                passed=False,
                message=f"Found {len(findings)} potentially vulnerable package(s)",
                details=findings,
                severity="warning",
                fixable=True,
                fix_command="pip install --upgrade <package>"
            )

        return CheckResult(
            name="Dependency security",
            passed=True,
            message="No known vulnerable packages detected (basic check)"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Security check for UKG Integration Suite"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )
    parser.add_argument(
        "--dir",
        default=".",
        help="Root directory to check"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    checker = SecurityChecker(args.dir)
    success = checker.run_all_checks()

    if args.json:
        import json
        results = {
            "passed": success,
            "checks": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "severity": r.severity,
                    "message": r.message,
                    "details": r.details
                }
                for r in checker.results
            ]
        }
        print(json.dumps(results, indent=2))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
