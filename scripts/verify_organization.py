"""
Repository Organization Verification
=====================================

Verifies that the repository cleanup was successful and all files are in the correct locations.
"""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).parent.parent

def check_directory_structure():
    """Verify all expected directories exist"""
    print("=" * 80)
    print("VERIFYING DIRECTORY STRUCTURE")
    print("=" * 80)
    print()
    
    expected_dirs = [
        'actions',
        'assistant',
        'automation',
        'backup',
        'config',
        'core',
        'debug',
        'debug/json',
        'debug/html',
        'debug/old_tests',
        'docs',
        'log',
        'memory',
        'scripts',
        'scripts/debug',
        'scripts/utilities',
        'static',
        'tests',
        'tests/archive',
    ]
    
    all_good = True
    for dir_path in expected_dirs:
        full_path = REPO_ROOT / dir_path
        if full_path.exists():
            print(f"✅ {dir_path}")
        else:
            print(f"❌ MISSING: {dir_path}")
            all_good = False
    
    print()
    return all_good

def check_core_files():
    """Verify core application files are in root"""
    print("=" * 80)
    print("VERIFYING CORE FILES IN ROOT")
    print("=" * 80)
    print()
    
    core_files = [
        'main.py',
        'ui.py',
        'llm.py',
        'tts.py',
        'conversation_state.py',
        'shared_state.py',
        'websocket_server.py',
        'speech_to_text_websocket.py',
        'README.md',
        'REQUIREMENTS.txt',
        '.gitignore',
    ]
    
    all_good = True
    for file_name in core_files:
        file_path = REPO_ROOT / file_name
        if file_path.exists():
            print(f"✅ {file_name}")
        else:
            print(f"❌ MISSING: {file_name}")
            all_good = False
    
    print()
    return all_good

def check_no_loose_files():
    """Check that debug/doc files are NOT in root"""
    print("=" * 80)
    print("VERIFYING NO LOOSE DEBUG/DOC FILES IN ROOT")
    print("=" * 80)
    print()
    
    # Files that should NOT be in root
    should_not_exist = [
        'check_dom_structure.py',
        'debug_direction.py',
        'extract_message.py',
        'DIAGNOSTIC_RESULT.json',
        'DOM_STRUCTURE.json',
        'IMPLEMENTATION_GUIDE.md',
        'speech_client.html',
        'test_wa_connection.py',
        'WHATSAPP_AI_COMPLETE.md',
    ]
    
    all_good = True
    for file_name in should_not_exist:
        file_path = REPO_ROOT / file_name
        if not file_path.exists():
            print(f"✅ Correctly moved: {file_name}")
        else:
            print(f"❌ STILL IN ROOT: {file_name}")
            all_good = False
    
    print()
    return all_good

def check_documentation():
    """Verify documentation files are in docs/"""
    print("=" * 80)
    print("VERIFYING DOCUMENTATION IN docs/")
    print("=" * 80)
    print()
    
    expected_docs = [
        'docs/README.md',
        'docs/WHATSAPP_AI_COMPLETE.md',
        'docs/SAM_MASTER_ARCHITECTURE_PLAN.md',
        'docs/IMPLEMENTATION_GUIDE.md',
        'docs/CLEANUP_SUMMARY.md',
        'docs/BEFORE_AFTER_COMPARISON.md',
    ]
    
    all_good = True
    for doc_path in expected_docs:
        full_path = REPO_ROOT / doc_path
        if full_path.exists():
            print(f"✅ {doc_path}")
        else:
            print(f"❌ MISSING: {doc_path}")
            all_good = False
    
    print()
    return all_good

def check_tests():
    """Verify test organization"""
    print("=" * 80)
    print("VERIFYING TEST ORGANIZATION")
    print("=" * 80)
    print()
    
    # Active tests should be in tests/
    active_tests = [
        'tests/test_draft_system.py',
        'tests/test_message_content.py',
        'tests/test_sam_status.py',
        'tests/test_sam_whatsapp_complete.py',
        'tests/README.md',
    ]
    
    # Old tests should be in tests/archive/
    archived_tests = [
        'tests/archive/explore_badges.py',
        'tests/archive/test_dom_probe.py',
        'tests/archive/README.md',
    ]
    
    all_good = True
    
    print("Active Tests:")
    for test_path in active_tests:
        full_path = REPO_ROOT / test_path
        if full_path.exists():
            print(f"  ✅ {test_path}")
        else:
            print(f"  ❌ MISSING: {test_path}")
            all_good = False
    
    print("\nArchived Tests:")
    for test_path in archived_tests:
        full_path = REPO_ROOT / test_path
        if full_path.exists():
            print(f"  ✅ {test_path}")
        else:
            print(f"  ❌ MISSING: {test_path}")
            all_good = False
    
    print()
    return all_good

def check_scripts():
    """Verify scripts are organized"""
    print("=" * 80)
    print("VERIFYING SCRIPTS ORGANIZATION")
    print("=" * 80)
    print()
    
    expected_scripts = [
        'scripts/start_chrome_debug.bat',
        'scripts/cleanup_repo.py',
        'scripts/cleanup_tests.py',
        'scripts/README.md',
    ]
    
    all_good = True
    for script_path in expected_scripts:
        full_path = REPO_ROOT / script_path
        if full_path.exists():
            print(f"✅ {script_path}")
        else:
            print(f"❌ MISSING: {script_path}")
            all_good = False
    
    print()
    return all_good

def check_debug_files():
    """Verify debug files are organized"""
    print("=" * 80)
    print("VERIFYING DEBUG FILES ORGANIZATION")
    print("=" * 80)
    print()
    
    # Check for at least some expected debug files
    expected_debug = [
        'debug/README.md',
        'debug/json/DOM_STRUCTURE.json',
        'debug/old_tests/check_dom_structure.py',
    ]
    
    all_good = True
    for debug_path in expected_debug:
        full_path = REPO_ROOT / debug_path
        if full_path.exists():
            print(f"✅ {debug_path}")
        else:
            print(f"⚠️  Optional: {debug_path} (may not exist if no debug files were present)")
    
    print()
    return True  # Always pass since debug files are optional

def print_summary(results):
    """Print overall verification summary"""
    print("=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print()
    
    all_passed = all(results.values())
    
    for check_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {check_name}")
    
    print()
    if all_passed:
        print("🎉 ALL VERIFICATIONS PASSED!")
        print("✅ Repository is properly organized")
        return 0
    else:
        print("❌ SOME VERIFICATIONS FAILED")
        print("⚠️  Please check the output above for details")
        return 1

def main():
    """Run all verification checks"""
    print("\n")
    print("*" * 80)
    print(" REPOSITORY ORGANIZATION VERIFICATION ".center(80, "*"))
    print("*" * 80)
    print("\n")
    
    results = {
        'Directory Structure': check_directory_structure(),
        'Core Files': check_core_files(),
        'No Loose Files': check_no_loose_files(),
        'Documentation': check_documentation(),
        'Tests': check_tests(),
        'Scripts': check_scripts(),
        'Debug Files': check_debug_files(),
    }
    
    exit_code = print_summary(results)
    
    print("\n" + "=" * 80)
    print(f"Repository root: {REPO_ROOT}")
    print("=" * 80)
    print()
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
