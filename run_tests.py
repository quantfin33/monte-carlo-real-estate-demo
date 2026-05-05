#!/usr/bin/env python3
"""
Comprehensive Test Runner for Monte Carlo Model
Automatically runs all tests and generates reports
"""

import os
import sys
import subprocess
import time
import json
import shlex
from pathlib import Path
from datetime import datetime

def run_command(cmd, description):
    """Run a command and return results"""
    print(f"\n🔄 {description}")
    display_cmd = shlex.join(cmd) if isinstance(cmd, (list, tuple)) else cmd
    print(f"Command: {display_cmd}")
    
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd, 
            shell=isinstance(cmd, str),
            capture_output=True, 
            text=True, 
            timeout=300  # 5 minute timeout
        )
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ {description} completed successfully in {duration:.2f}s")
            return True, result.stdout, result.stderr, duration
        else:
            print(f"❌ {description} failed after {duration:.2f}s")
            print(f"Error: {result.stderr}")
            return False, result.stdout, result.stderr, duration
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} timed out after 5 minutes")
        return False, "", "Timeout", 300
    except Exception as e:
        print(f"💥 {description} crashed: {e}")
        return False, "", str(e), 0

def install_test_dependencies():
    """Install testing dependencies"""
    print("📦 Installing testing dependencies...")
    
    # Check if requirements_testing.txt exists
    req_file = Path("requirements_testing.txt")
    if req_file.exists():
        success, stdout, stderr, duration = run_command(
            [sys.executable, "-m", "pip", "install", "-r", "requirements_testing.txt"],
            "Installing test dependencies"
        )
        if not success:
            print("⚠️  Some dependencies may not be installed. Continuing...")
    else:
        print("⚠️  requirements_testing.txt not found. Installing basic pytest...")
        success, stdout, stderr, duration = run_command(
            [sys.executable, "-m", "pip", "install", "pytest", "pytest-cov", "pytest-html"],
            "Installing basic pytest"
        )

def run_unit_tests():
    """Run unit tests"""
    print("\n🧪 Running Unit Tests...")
    
    # Run core model tests
    success, stdout, stderr, duration = run_command(
        [sys.executable, "-m", "pytest", "tests/test_core_model.py", "-v", "--tb=short"],
        "Core model unit tests"
    )
    
    if success:
        print("✅ Core model tests passed")
    else:
        print("❌ Core model tests failed")
        
    return success

def run_integration_tests():
    """Run integration tests"""
    print("\n🔗 Running Integration Tests...")
    
    # Run UI integration tests
    success, stdout, stderr, duration = run_command(
        [sys.executable, "-m", "pytest", "tests/test_ui_integration.py", "-v", "--tb=short"],
        "UI integration tests"
    )
    
    if success:
        print("✅ UI integration tests passed")
    else:
        print("❌ UI integration tests failed")
        
    return success

def run_comprehensive_tests():
    """Run comprehensive test suite with coverage"""
    print("\n📊 Running Comprehensive Test Suite...")
    
    # Create reports directory
    reports_dir = Path("test_reports")
    reports_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Run all tests with coverage and HTML report
    success, stdout, stderr, duration = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-v",
            "--cov=monte_carlo_model",
            f"--cov-report=html:test_reports/coverage_{timestamp}",
            "--cov-report=term-missing",
            f"--html=test_reports/report_{timestamp}.html",
            "--self-contained-html",
        ],
        "Comprehensive test suite with coverage"
    )
    
    if success:
        print("✅ Comprehensive tests completed")
        print(f"📁 Coverage report: test_reports/coverage_{timestamp}/index.html")
        print(f"📁 HTML report: test_reports/report_{timestamp}.html")
    else:
        print("❌ Comprehensive tests failed")
        
    return success

def run_performance_tests():
    """Run performance tests"""
    print("\n⚡ Running Performance Tests...")
    
    success, stdout, stderr, duration = run_command(
        [sys.executable, "-m", "pytest", "tests/", "-m", "performance", "-v"],
        "Performance tests"
    )
    
    if success:
        print("✅ Performance tests passed")
    else:
        print("❌ Performance tests failed")
        
    return success

def run_smoke_tests():
    """Run quick smoke tests"""
    print("\n💨 Running Smoke Tests...")
    
    # Quick basic functionality test
    smoke_code = (
        "import monte_carlo_model; "
        "print('✅ monte_carlo_model imports successfully'); "
        "result = monte_carlo_model.run_model(monte_carlo_model.default_params()); "
        "print(f\"✅ Basic model run: IRR={result.get('IRR', 0):.4f}\")"
    )
    success, stdout, stderr, duration = run_command(
        [sys.executable, "-c", smoke_code],
        "Basic smoke test"
    )
    
    if success:
        print("✅ Smoke tests passed")
    else:
        print("❌ Smoke tests failed")
        
    return success

def run_specific_tests(test_pattern):
    """Run specific tests matching a pattern"""
    print(f"\n🎯 Running Specific Tests: {test_pattern}")
    
    success, stdout, stderr, duration = run_command(
        [sys.executable, "-m", "pytest", "tests/", "-k", test_pattern, "-v"],
        f"Specific tests: {test_pattern}"
    )
    
    if success:
        print(f"✅ Specific tests '{test_pattern}' passed")
    else:
        print(f"❌ Specific tests '{test_pattern}' failed")
        
    return success

def generate_test_summary():
    """Generate a summary of test results"""
    print("\n📋 Generating Test Summary...")
    
    summary = {
        "timestamp": datetime.now().isoformat(),
        "tests_run": [],
        "overall_status": "unknown"
    }
    
    # Check test results
    test_files = [
        "tests/test_core_model.py",
        "tests/test_ui_integration.py"
    ]
    
    all_passed = True
    for test_file in test_files:
        if Path(test_file).exists():
            success, stdout, stderr, duration = run_command(
                [sys.executable, "-m", "pytest", test_file, "--collect-only", "-q"],
                f"Collecting tests from {test_file}"
            )
            
            if success:
                # Count tests
                test_count = stdout.count("collected")
                summary["tests_run"].append({
                    "file": test_file,
                    "status": "available",
                    "test_count": test_count
                })
            else:
                summary["tests_run"].append({
                    "file": test_file,
                    "status": "error",
                    "test_count": 0
                })
                all_passed = False
        else:
            summary["tests_run"].append({
                "file": test_file,
                "status": "missing",
                "test_count": 0
            })
            all_passed = False
    
    summary["overall_status"] = "passed" if all_passed else "failed"
    
    # Save summary
    summary_file = Path("test_reports/test_summary.json")
    summary_file.parent.mkdir(exist_ok=True)
    
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"📁 Test summary saved to: {summary_file}")
    return summary

def main():
    """Main test runner"""
    print("🚀 MONTE CARLO MODEL COMPREHENSIVE TEST RUNNER")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "install":
            install_test_dependencies()
            return
        elif command == "smoke":
            run_smoke_tests()
            return
        elif command == "unit":
            run_unit_tests()
            return
        elif command == "integration":
            run_integration_tests()
            return
        elif command == "performance":
            run_performance_tests()
            return
        elif command == "quick":
            # Quick test run
            print("\n⚡ Quick Test Run...")
            run_smoke_tests()
            run_unit_tests()
            return
        elif command == "specific" and len(sys.argv) > 2:
            test_pattern = sys.argv[2]
            run_specific_tests(test_pattern)
            return
        elif command == "help":
            print_help()
            return
        else:
            print(f"❌ Unknown command: {command}")
            print_help()
            return
    
    # Full test run
    print("\n🎯 Running Full Test Suite...")
    
    # Install dependencies
    install_test_dependencies()
    
    # Run tests
    smoke_success = run_smoke_tests()
    unit_success = run_unit_tests()
    integration_success = run_integration_tests()
    performance_success = run_performance_tests()
    
    # Run comprehensive suite
    comprehensive_success = run_comprehensive_tests()
    
    # Generate summary
    summary = generate_test_summary()
    
    # Final results
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS")
    print("=" * 60)
    
    results = [
        ("Smoke Tests", smoke_success),
        ("Unit Tests", unit_success),
        ("Integration Tests", integration_success),
        ("Performance Tests", performance_success),
        ("Comprehensive Suite", comprehensive_success)
    ]
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name:20s}: {status}")
        if not success:
            all_passed = False
    
    print("-" * 60)
    overall_status = "🎉 ALL TESTS PASSED!" if all_passed else "💥 SOME TESTS FAILED"
    print(f"Overall Status: {overall_status}")
    
    if all_passed:
        print("\n🚀 Your Monte Carlo model is ready to ship!")
        print("✅ All functionality verified")
        print("✅ UI integration working")
        print("✅ Performance acceptable")
        print("✅ No critical issues found")
    else:
        print("\n⚠️  Please fix failing tests before shipping")
        print("🔍 Check test reports for details")
    
    print(f"\n📁 Test reports available in: test_reports/")
    print(f"📋 Test summary: test_reports/test_summary.json")

def print_help():
    """Print help information"""
    print("""
🚀 MONTE CARLO MODEL TEST RUNNER

Usage: python run_tests.py [command]

Commands:
  (no args)    Run full test suite
  install      Install test dependencies
  smoke        Run quick smoke tests only
  unit         Run unit tests only
  integration  Run integration tests only
  performance  Run performance tests only
  quick        Run smoke + unit tests
  specific     Run tests matching a pattern
  help         Show this help

Examples:
  python run_tests.py                    # Full test suite
  python run_tests.py smoke              # Quick smoke test
  python run_tests.py specific reserve   # Test reserve functionality
  python run_tests.py quick              # Fast test run

Test Reports:
  - Coverage reports: test_reports/coverage_*/
  - HTML reports: test_reports/report_*.html
  - Summary: test_reports/test_summary.json
""")

if __name__ == "__main__":
    main()
