#!/usr/bin/env python3
"""
Test Runner for Email Monitor FastAPI Service

Provides different test execution modes and utilities for development.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status"""
    print(f"\n🔄 {description}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        print("Make sure all dependencies are installed: pip install -r requirements_dev.txt")
        return False


def run_unit_tests():
    """Run unit tests only"""
    cmd = [
        "python", "-m", "pytest", 
        "tests/",
        "-m", "unit",
        "-v", 
        "--tb=short"
    ]
    return run_command(cmd, "Running unit tests")


def run_integration_tests():
    """Run integration tests only"""
    cmd = [
        "python", "-m", "pytest", 
        "tests/",
        "-m", "integration", 
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, "Running integration tests")


def run_all_tests():
    """Run all tests with coverage"""
    cmd = [
        "python", "-m", "pytest",
        "tests/",
        "-v",
        "--cov=app",
        "--cov=attachment_worker", 
        "--cov=worker_runner",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "--tb=short"
    ]
    return run_command(cmd, "Running all tests with coverage")


def run_fast_tests():
    """Run fast tests only (exclude slow tests)"""
    cmd = [
        "python", "-m", "pytest",
        "tests/",
        "-m", "not slow",
        "-v",
        "--tb=line"
    ]
    return run_command(cmd, "Running fast tests")


def run_redis_tests():
    """Run Redis-specific tests"""
    cmd = [
        "python", "-m", "pytest",
        "tests/",
        "-m", "redis",
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, "Running Redis tests")


def run_worker_tests():
    """Run worker-specific tests"""
    cmd = [
        "python", "-m", "pytest",
        "tests/",
        "-m", "worker",
        "-v", 
        "--tb=short"
    ]
    return run_command(cmd, "Running worker tests")


def run_api_tests():
    """Run API endpoint tests"""
    cmd = [
        "python", "-m", "pytest",
        "tests/",
        "-m", "api",
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, "Running API tests")


def lint_code():
    """Run code linting"""
    success = True
    
    # Flake8 linting
    cmd = ["flake8", "app/", "attachment_worker.py", "worker_runner.py", "tests/"]
    success &= run_command(cmd, "Running flake8 linting")
    
    # Black formatting check
    cmd = ["black", "--check", "--diff", "app/", "attachment_worker.py", "worker_runner.py", "tests/"]
    success &= run_command(cmd, "Checking code formatting with black")
    
    # Import sorting check  
    cmd = ["isort", "--check-only", "--diff", "app/", "attachment_worker.py", "worker_runner.py", "tests/"]
    success &= run_command(cmd, "Checking import sorting with isort")
    
    return success


def format_code():
    """Format code automatically"""
    success = True
    
    # Black formatting
    cmd = ["black", "app/", "attachment_worker.py", "worker_runner.py", "tests/"]
    success &= run_command(cmd, "Formatting code with black")
    
    # Sort imports
    cmd = ["isort", "app/", "attachment_worker.py", "worker_runner.py", "tests/"]
    success &= run_command(cmd, "Sorting imports with isort")
    
    return success


def type_check():
    """Run type checking"""
    cmd = [
        "mypy", 
        "app/",
        "attachment_worker.py", 
        "worker_runner.py",
        "--ignore-missing-imports",
        "--strict-optional"
    ]
    return run_command(cmd, "Running type checking with mypy")


def run_security_check():
    """Run security checks"""
    # Check for common security issues
    cmd = ["bandit", "-r", "app/", "attachment_worker.py", "worker_runner.py"]
    return run_command(cmd, "Running security checks with bandit")


def setup_test_environment():
    """Set up test environment"""
    print("🔧 Setting up test environment...")
    
    # Create test directories
    test_dirs = ["tests", "htmlcov", "processing_results", "test_temp"]
    for directory in test_dirs:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")
    
    # Set test environment variables
    test_env = {
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379", 
        "REDIS_DB": "1",  # Use different DB for testing
        "EMAIL_QUEUE_NAME": "test_email_attachments",
        "MAX_QUEUE_SIZE": "100",
        "WORKER_TEMP_DIR": "test_temp",
        "PIPELINE_APP_NAME": "TEST_APP",
        "PIPELINE_USER_ID": "test_user"
    }
    
    for key, value in test_env.items():
        os.environ[key] = value
        print(f"✅ Set {key}={value}")
    
    print("✅ Test environment setup complete")


def cleanup_test_environment():
    """Clean up test artifacts"""
    print("🧹 Cleaning up test environment...")
    
    # Remove test directories
    import shutil
    cleanup_dirs = ["htmlcov", "processing_results", "test_temp", ".pytest_cache", "__pycache__"]
    
    for directory in cleanup_dirs:
        dir_path = Path(directory)
        if dir_path.exists():
            if dir_path.is_dir():
                shutil.rmtree(dir_path)
            else:
                dir_path.unlink()
            print(f"✅ Removed: {directory}")
    
    # Remove coverage files
    coverage_files = [".coverage", "coverage.xml"]
    for file_path in coverage_files:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            print(f"✅ Removed: {file_path}")
    
    print("✅ Cleanup complete")


def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(
        description="Test runner for Email Monitor FastAPI Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py --all                 # Run all tests with coverage
  python run_tests.py --unit               # Run unit tests only  
  python run_tests.py --integration        # Run integration tests only
  python run_tests.py --fast               # Run fast tests only
  python run_tests.py --lint               # Run linting only
  python run_tests.py --format             # Format code
  python run_tests.py --setup              # Setup test environment
  python run_tests.py --cleanup            # Cleanup test artifacts
        """
    )
    
    parser.add_argument("--all", action="store_true", help="Run all tests with coverage")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--fast", action="store_true", help="Run fast tests only")
    parser.add_argument("--redis", action="store_true", help="Run Redis tests only")
    parser.add_argument("--worker", action="store_true", help="Run worker tests only")
    parser.add_argument("--api", action="store_true", help="Run API tests only")
    parser.add_argument("--lint", action="store_true", help="Run code linting")
    parser.add_argument("--format", action="store_true", help="Format code automatically")
    parser.add_argument("--type-check", action="store_true", help="Run type checking")
    parser.add_argument("--security", action="store_true", help="Run security checks")
    parser.add_argument("--setup", action="store_true", help="Setup test environment")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup test artifacts")
    parser.add_argument("--ci", action="store_true", help="Run full CI pipeline")
    
    args = parser.parse_args()
    
    # Setup test environment by default
    setup_test_environment()
    
    success = True
    
    if args.setup:
        return
    elif args.cleanup:
        cleanup_test_environment()
        return
    elif args.format:
        success = format_code()
    elif args.lint:
        success = lint_code()
    elif args.type_check:
        success = type_check()
    elif args.security:
        success = run_security_check()
    elif args.unit:
        success = run_unit_tests()
    elif args.integration:
        success = run_integration_tests()
    elif args.fast:
        success = run_fast_tests()
    elif args.redis:
        success = run_redis_tests()
    elif args.worker:
        success = run_worker_tests()
    elif args.api:
        success = run_api_tests()
    elif args.ci:
        # Full CI pipeline
        print("🚀 Running full CI pipeline...")
        success &= lint_code()
        success &= type_check() 
        success &= run_all_tests()
    elif args.all:
        success = run_all_tests()
    else:
        # Default: run fast tests
        success = run_fast_tests()
    
    # Print summary
    print("\n" + "=" * 60)
    if success:
        print("🎉 All operations completed successfully!")
        sys.exit(0)
    else:
        print("💥 Some operations failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()