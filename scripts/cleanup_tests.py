"""
TESTS DIRECTORY CLEANUP
=======================

Organizes the tests directory by:
- Moving old diagnostic/exploration tests to archive
- Keeping current integration and system tests
"""

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TESTS_DIR = REPO_ROOT / 'tests'

# Tests to keep (current/active tests)
KEEP_TESTS = {
    'test_message_content.py',
    'test_sam_whatsapp_complete.py',
    'test_sam_status.py',
    'test_draft_system.py',
    'README.md',
}

# Tests to archive (old diagnostic/exploration tests)
ARCHIVE_TESTS = {
    'explore_badges.py',
    'find_unread_indicators.py',
    'quick_dom_test.py',
    'quick_test.py',
    'test_button_diagnostic.py',
    'test_complete_draft_fixed.py',
    'test_dom_probe.py',
    'test_enhanced_dom_probe.py',
    'test_header_selector.py',
    'test_input_box_selector.py',
    'test_manual_send.py',
    'test_simple_dom.py',
    'test_unread_with_click.py',
    'test_send_to_sugar.py',
    'run_daily_plan.py',
}

def create_archive_dir():
    """Create tests/archive directory"""
    archive_dir = TESTS_DIR / 'archive'
    archive_dir.mkdir(exist_ok=True)
    print(f"✅ Created: tests/archive/")
    return archive_dir

def move_old_tests():
    """Move old diagnostic tests to archive"""
    archive_dir = create_archive_dir()
    
    moved_count = 0
    for test_file in ARCHIVE_TESTS:
        src = TESTS_DIR / test_file
        if src.exists():
            dst = archive_dir / test_file
            try:
                shutil.move(str(src), str(dst))
                print(f"  🧪 Archived: {test_file}")
                moved_count += 1
            except Exception as e:
                print(f"  ❌ Error moving {test_file}: {e}")
    
    print(f"\n✅ Archived {moved_count} old test files")

def create_tests_readme():
    """Create README for tests directory"""
    readme_content = """# Sam Agent Tests

This directory contains all test files for Sam Agent.

## Active Tests

### Integration Tests
- **test_sam_whatsapp_complete.py** - Full WhatsApp workflow test (Chrome -> QR -> messages -> draft -> confirm)
- **test_message_content.py** - Verifies message content extraction from WhatsApp
- **test_draft_system.py** - Tests reply drafting and clipboard workflow

### Status & Monitoring
- **test_sam_status.py** - Quick status check of all Sam components

## Archived Tests
Old diagnostic and exploration tests are in the `archive/` subdirectory.
These were used during development for debugging and are kept for reference.

## Running Tests

```bash
# Run all tests
cd c:\\Users\\DELL.COM\\Desktop\\Darey\\Sam-Agent
python -m pytest tests/

# Run specific test
python tests/test_sam_status.py
```

## Test Requirements
- Chrome with remote debugging (port 9222)
- WhatsApp Web logged in
- All dependencies from REQUIREMENTS.txt installed
"""
    
    readme_path = TESTS_DIR / 'README.md'
    readme_path.write_text(readme_content, encoding='utf-8')
    print(f"✅ Created tests/README.md")

def create_archive_readme():
    """Create README for archive directory"""
    readme_content = """# Archived Tests

This directory contains old diagnostic and exploration tests from the development phase.

These tests were used to:
- Explore WhatsApp DOM structure
- Test various selector strategies
- Debug message extraction
- Experiment with different automation approaches

They are kept for reference but are no longer actively maintained.

## Files
- **explore_badges.py** - Badge/unread indicator exploration
- **find_unread_indicators.py** - Unread message indicator detection
- **quick_dom_test.py** - Quick DOM structure tests
- **test_button_diagnostic.py** - Button selector diagnostics
- **test_dom_probe.py** - DOM structure probing
- **test_enhanced_dom_probe.py** - Enhanced DOM probing
- **test_header_selector.py** - Header selector testing
- **test_input_box_selector.py** - Input box selector testing
- **test_manual_send.py** - Manual send testing
- **test_simple_dom.py** - Simple DOM tests
- **test_unread_with_click.py** - Unread chat clicking
- **test_send_to_sugar.py** - Specific contact testing
"""
    
    archive_path = TESTS_DIR / 'archive' / 'README.md'
    archive_path.write_text(readme_content, encoding='utf-8')
    print(f"✅ Created tests/archive/README.md")

def print_summary():
    """Print cleanup summary"""
    print("\n" + "="*80)
    print("TESTS DIRECTORY ORGANIZED!")
    print("="*80)
    print("\n📁 TESTS STRUCTURE:")
    print("""
tests/
├── test_draft_system.py            # 🟢 Draft & clipboard workflow tests
├── test_message_content.py         # 🟢 Message content extraction tests
├── test_sam_status.py              # 🟢 Component status checks
├── test_sam_whatsapp_complete.py   # 🟢 Full integration test
├── archive/                         # 📦 Old diagnostic tests
│   ├── explore_badges.py
│   ├── find_unread_indicators.py
│   ├── quick_dom_test.py
│   ├── test_button_diagnostic.py
│   ├── test_dom_probe.py
│   ├── test_enhanced_dom_probe.py
│   ├── test_header_selector.py
│   ├── test_input_box_selector.py
│   ├── test_manual_send.py
│   ├── test_simple_dom.py
│   ├── test_unread_with_click.py
│   ├── test_send_to_sugar.py
│   └── README.md
└── README.md
""")
    print("\n✅ Active tests kept in tests/")
    print("✅ Old diagnostic tests archived in tests/archive/")
    print("✅ README files created")
    print("\n🎯 Tests directory is now organized!")

def main():
    print("="*80)
    print("TESTS DIRECTORY CLEANUP")
    print("="*80)
    print()
    
    print("📦 Step 1: Archiving old tests...")
    move_old_tests()
    print()
    
    print("📚 Step 2: Creating README files...")
    create_tests_readme()
    create_archive_readme()
    print()
    
    print_summary()

if __name__ == "__main__":
    main()
