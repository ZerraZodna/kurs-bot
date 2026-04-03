#!/usr/bin/env python3
"""
Code Review Verification Script

This script verifies the codebase for:
1. Leftover files that shouldn't be present
2. Proper module structure
3. Clean imports without sys.modules warnings
4. Package __init__.py files are properly configured

Usage:
    python3 scripts/verify_codereview.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Set, Tuple

# Add project root to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))


def check_for_leftover_files(project_root: Path) -> List[Tuple[str, str]]:
    """
    Check for leftover files that shouldn't be in the codebase.
    Only checks actual source directory, ignores .venv and __pycache__.
    
    Returns list of tuples: (file_path, reason)
    """
    issues = []
    
    # Skip venv directories entirely
    if '.venv' in str(project_root) or 'venv' in str(project_root):
        return issues
    
    # Check for actual leftover files (not in cache directories)
    for root, dirs, files in os.walk(project_root):
        # Skip cache directories
        if '__pycache__' in dirs or '.pyc' in files:
            continue
        
        # Skip venv
        if '.venv' in root or 'venv' in root:
            continue
        
        # Check for .pyo files (optimized Python bytecode)
        for f in files:
            if f.endswith('.pyo'):
                issues.append((os.path.join(root, f), "Optimized Python bytecode file"))
    
    return issues


def check_module_structure(project_root: Path) -> List[Tuple[str, str]]:
    """
    Check that all Python files have proper __init__.py files in their packages.
    
    Returns list of tuples: (file_path, issue_description)
    """
    issues = []
    
    for root, dirs, files in os.walk(project_root):
        # Skip venv directories
        if '.venv' in root or 'venv' in root:
            continue
        
        for f in files:
            if f.endswith('.py') and f != '__init__.py':
                file_path = Path(root) / f
                
                # Check parent directory for __init__.py
                parent_dir = file_path.parent
                init_file = parent_dir / '__init__.py'
                
                # If this is a subdirectory with Python files but no __init__.py, it's a package issue
                if parent_dir != project_root:
                    # Check if parent has __init__.py or any Python siblings
                    has_init = init_file.exists()
                    has_siblings = any(d.is_file() and d.suffix == '.py' for d in parent_dir.iterdir() if d != f)
                    
                    if not has_init and has_siblings:
                        issues.append((str(file_path), f"Package '{parent_dir.name}' has Python files but missing __init__.py"))
    
    return issues


def check_imports(project_root: Path) -> Tuple[bool, List[str]]:
    """
    Check if modules can be imported without sys.modules warnings.
    
    Returns: (success, list of issues)
    """
    issues = []
    
    test_code = """
import warnings
warnings.filterwarnings('error')

try:
    import swarm
    import swarm.telegram
    print("All imports successful without warnings")
except Exception as e:
    print(f"Import error: {e}")
    sys.exit(1)
"""
    
    try:
        result = subprocess.run(
            [sys.executable, '-c', test_code],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            issues.append(f"Import test failed:\n{result.stdout}\n{result.stderr}")
            return False, issues
        
        return True, issues
        
    except subprocess.TimeoutExpired:
        issues.append("Import test timed out")
        return False, issues


def check_telegram_init_structure(project_root: Path) -> List[Tuple[str, str]]:
    """
    Check the telegram/__init__.py for proper import structure.
    
    Issues to check:
    1. No circular imports
    2. All imported modules are properly defined
    3. No leftover imports from non-existent modules
    """
    issues = []
    
    telegram_init = project_root / 'swarm' / 'telegram' / '__init__.py'
    if not telegram_init.exists():
        return issues
    
    content = telegram_init.read_text()
    
    # Check for imports from non-existent modules
    for line in content.split('\n'):
        if 'from .' in line or 'import .' in line:
            # Extract the module name being imported
            for module in ['integration', 'telegram_swarm_polling', 'workflow_coordinator']:
                if f'.{module}' in line:
                    module_path = project_root / 'swarm' / 'telegram' / f'{module}.py'
                    if not module_path.exists():
                        issues.append((str(telegram_init), f"Import from non-existent module: .{module}"))
    
    return issues


def run_verification(project_root: Path) -> Dict[str, any]:
    """
    Run all verification checks and return results.
    """
    results = {
        'success': True,
        'checks': {},
        'issues': []
    }
    
    print("=" * 60)
    print("CODE REVIEW VERIFICATION")
    print("=" * 60)
    
    # Check for leftover files
    print("\n1. Checking for leftover files...")
    leftover_files = check_for_leftover_files(project_root)
    if leftover_files:
        results['success'] = False
        results['checks']['leftover_files'] = {
            'status': 'failed',
            'count': len(leftover_files),
            'files': leftover_files
        }
        for file_path, reason in leftover_files:
            results['issues'].append(f"LEFTOVER: {file_path} - {reason}")
            print(f"   ✗ {file_path}")
    else:
        results['checks']['leftover_files'] = {'status': 'passed'}
        print("   ✓ No leftover files found")
    
    # Check module structure
    print("\n2. Checking module structure...")
    structure_issues = check_module_structure(project_root)
    if structure_issues:
        results['success'] = False
        results['checks']['module_structure'] = {
            'status': 'failed',
            'count': len(structure_issues),
            'issues': structure_issues
        }
        for file_path, issue in structure_issues:
            results['issues'].append(f"STRUCTURE: {file_path} - {issue}")
            print(f"   ✗ {file_path}: {issue}")
    else:
        results['checks']['module_structure'] = {'status': 'passed'}
        print("   ✓ Module structure is correct")
    
    # Check imports
    print("\n3. Checking imports for sys.modules warnings...")
    import_success, import_issues = check_imports(project_root)
    if not import_success:
        results['success'] = False
        results['checks']['imports'] = {
            'status': 'failed',
            'issues': import_issues
        }
        for issue in import_issues:
            results['issues'].append(f"IMPORT: {issue}")
            print(f"   ✗ {issue}")
    else:
        results['checks']['imports'] = {'status': 'passed'}
        print("   ✓ All imports successful without sys.modules warnings")
    
    # Check telegram init structure
    print("\n4. Checking telegram/__init__.py structure...")
    telegram_issues = check_telegram_init_structure(project_root)
    if telegram_issues:
        results['success'] = False
        results['checks']['telegram_init'] = {
            'status': 'failed',
            'count': len(telegram_issues),
            'issues': telegram_issues
        }
        for file_path, issue in telegram_issues:
            results['issues'].append(f"TELEGRAM_INIT: {file_path} - {issue}")
            print(f"   ✗ {file_path}: {issue}")
    else:
        results['checks']['telegram_init'] = {'status': 'passed'}
        print("   ✓ telegram/__init__.py structure is correct")
    
    # Summary
    print("\n" + "=" * 60)
    if results['success']:
        print("VERIFICATION PASSED - Codebase is clean")
    else:
        print("VERIFICATION FAILED - Issues found:")
        for issue in results['issues']:
            print(f"   - {issue}")
    print("=" * 60)
    
    return results


def clean_caches(project_root: Path):
    """
    Clean Python cache files and directories.
    """
    print("\nCleaning Python caches...")
    
    for root, dirs, files in os.walk(project_root):
        # Remove __pycache__ directories
        if '__pycache__' in dirs:
            cache_dir = Path(root) / '__pycache__'
            try:
                shutil.rmtree(cache_dir)
                print(f"   Removed: {cache_dir}")
            except Exception as e:
                print(f"   Error removing {cache_dir}: {e}")
        
        # Remove .pyc files
        for f in files:
            if f.endswith('.pyc'):
                pyc_path = Path(root) / f
                try:
                    pyc_path.unlink()
                    print(f"   Removed: {pyc_path}")
                except Exception as e:
                    print(f"   Error removing {pyc_path}: {e}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Code Review Verification Script')
    parser.add_argument('--clean', action='store_true', help='Clean caches before verification')
    args = parser.parse_args()
    
    project_root = Path(__file__).resolve().parent.parent
    
    if args.clean:
        clean_caches(project_root)
    
    run_verification(project_root)
    sys.exit(0 if run_verification(project_root)['success'] else 1)
