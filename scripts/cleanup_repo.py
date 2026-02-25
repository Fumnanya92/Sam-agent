"""
REPOSITORY CLEANUP AND ORGANIZATION SCRIPT
==========================================

This script organizes the Sam-Agent repository into a clean structure:
- Moves documentation to docs/
- Moves debug files to debug/
- Moves utility scripts to scripts/
- Removes old/deprecated files
- Creates a clean project structure
"""

import os
import shutil
from pathlib import Path

# Get the repository root (parent of this script)
REPO_ROOT = Path(__file__).parent.parent

def create_directories():
    """Create necessary directories"""
    dirs = [
        'docs',
        'scripts/debug',
        'scripts/utilities',
        'debug/json',
        'debug/html',
        'debug/old_tests',
    ]
    
    for dir_path in dirs:
        full_path = REPO_ROOT / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {dir_path}")

def move_documentation():
    """Move all documentation files to docs/"""
    doc_files = [
        'IMPLEMENTATION_GUIDE.md',
        'OCR_SETUP.md',
        'PROJECT_STRUCTURE.md',
        'README_RESEARCH.md',
        'SAM_MASTER_ARCHITECTURE_PLAN.md',
        'SETUP_LAPTOP.md',
        'SOLUTION_SUMMARY.md',
        'VISUAL_COMPARISON.md',
        'WHATSAPP_AI_COMPLETE.md',
        'WHATSAPP_DOM_RESEARCH.md',
    ]
    
    moved = 0
    for filename in doc_files:
        src = REPO_ROOT / filename
        if src.exists():
            dst = REPO_ROOT / 'docs' / filename
            try:
                shutil.move(str(src), str(dst))
                print(f"  📄 Moved: {filename} → docs/")
                moved += 1
            except Exception as e:
                print(f"  ❌ Error moving {filename}: {e}")
    
    print(f"✅ Moved {moved} documentation files")

def move_debug_files():
    """Move debug files to debug/ folder"""
    # JSON debug files
    json_files = [
        'DIAGNOSTIC_RESULT.json',
        'DOM_STRUCTURE.json',
        'FINAL_TEST.json',
        'MESSAGE_EXTRACTION.json',
        'MESSAGE_HTML.json',
        'TESTIDS_IN_CHAT.json',
    ]
    
    for filename in json_files:
        src = REPO_ROOT / filename
        if src.exists():
            dst = REPO_ROOT / 'debug' / 'json' / filename
            try:
                shutil.move(str(src), str(dst))
                print(f"  🔍 Moved: {filename} → debug/json/")
            except Exception as e:
                print(f"  ❌ Error: {e}")
    
    # HTML debug files
    html_files = [
        'speech_client.html',
        'speech_client_compact.html',
    ]
    
    for filename in html_files:
        src = REPO_ROOT / filename
        if src.exists():
            dst = REPO_ROOT / 'debug' / 'html' / filename
            try:
                shutil.move(str(src), str(dst))
                print(f"  🌐 Moved: {filename} → debug/html/")
            except Exception as e:
                print(f"  ❌ Error: {e}")
    
    # Text debug files
    txt_files = [
        'debug_dir.txt',
        'diag_output.txt',
        'header_test.txt',
        'test_output.txt',
    ]
    
    for filename in txt_files:
        src = REPO_ROOT / filename
        if src.exists():
            dst = REPO_ROOT / 'debug' / filename
            try:
                shutil.move(str(src), str(dst))
                print(f"  📝 Moved: {filename} → debug/")
            except Exception as e:
                print(f"  ❌ Error: {e}")
    
    print("✅ Organized debug files")

def move_old_test_files():
    """Move old test files from root to tests/ or debug/"""
    old_test_files = [
        'check_dom_structure.py',
        'debug_direction.py',
        'extract_message.py',
        'final_test.py',
        'find_testids.py',
        'get_html.py',
        'quick_diag.py',
        'run_diag.py',
        't1.py',
        'test_wa_connection.py',
        'test_wa_simple.py',
        'test_whatsapp_selectors.py',
        'whatsapp_dom_diagnostic.js',
        'whatsapp_selectors_updated.py',
    ]
    
    for filename in old_test_files:
        src = REPO_ROOT / filename
        if src.exists():
            dst = REPO_ROOT / 'debug' / 'old_tests' / filename
            try:
                shutil.move(str(src), str(dst))
                print(f"  🧪 Moved: {filename} → debug/old_tests/")
            except Exception as e:
                print(f"  ❌ Error: {e}")
    
    print("✅ Moved old test files")

def move_scripts():
    """Move utility scripts to scripts/"""
    script_files = [
        'start_chrome_debug.bat',
    ]
    
    for filename in script_files:
        src = REPO_ROOT / filename
        if src.exists():
            dst = REPO_ROOT / 'scripts' / filename
            try:
                shutil.move(str(src), str(dst))
                print(f"  ⚙️ Moved: {filename} → scripts/")
            except Exception as e:
                print(f"  ❌ Error: {e}")
    
    print("✅ Moved utility scripts")

def update_gitignore():
    """Update .gitignore with new structure"""
    gitignore_additions = """
# Debug files
debug/
*.log

# Python cache
__pycache__/
*.pyc
*.pyo

# Environment
.env
.venv/
venv/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.temp
"""
    
    gitignore_path = REPO_ROOT / '.gitignore'
    
    # Read existing gitignore
    existing_content = ""
    if gitignore_path.exists():
        with open(gitignore_path, 'r') as f:
            existing_content = f.read()
    
    # Only add if not already present
    if 'debug/' not in existing_content:
        with open(gitignore_path, 'a') as f:
            f.write(gitignore_additions)
        print("✅ Updated .gitignore")
    else:
        print("✅ .gitignore already up to date")

def create_readme_files():
    """Create README files for each major directory"""
    
    # docs/README.md
    docs_readme = REPO_ROOT / 'docs' / 'README.md'
    docs_readme.write_text("""# Sam Agent Documentation

This directory contains all project documentation:

- **IMPLEMENTATION_GUIDE.md** - Implementation details and guides
- **SAM_MASTER_ARCHITECTURE_PLAN.md** - Master architecture plan
- **WHATSAPP_AI_COMPLETE.md** - WhatsApp AI integration documentation
- **WHATSAPP_DOM_RESEARCH.md** - WhatsApp DOM research notes
- **PROJECT_STRUCTURE.md** - Project structure overview
- **SETUP_LAPTOP.md** - Laptop setup instructions
- **README_RESEARCH.md** - Research notes

## Other Documentation
- OCR_SETUP.md - OCR setup guide
- SOLUTION_SUMMARY.md - Solution summaries
- VISUAL_COMPARISON.md - Visual comparison notes
""")
    print("✅ Created docs/README.md")
    
    # scripts/README.md
    scripts_readme = REPO_ROOT / 'scripts' / 'README.md'
    scripts_readme.write_text("""# Sam Agent Scripts

This directory contains utility scripts and tools:

## Utilities
- **start_chrome_debug.bat** - Launch Chrome with remote debugging

## Debug Scripts
- Located in `debug/` subdirectory

## Usage
Run scripts from the project root directory.
""")
    print("✅ Created scripts/README.md")
    
    # debug/README.md
    debug_readme = REPO_ROOT / 'debug' / 'README.md'
    debug_readme.write_text("""# Debug Files

This directory contains debug output and development files:

- **json/** - JSON debug output files
- **html/** - HTML test files
- **old_tests/** - Deprecated test files (kept for reference)

These files are for development purposes only and are gitignored.
""")
    print("✅ Created debug/README.md")

def print_summary():
    """Print organization summary"""
    print("\n" + "="*80)
    print("REPOSITORY ORGANIZATION COMPLETE!")
    print("="*80)
    print("\n📁 NEW DIRECTORY STRUCTURE:")
    print("""
Sam-Agent/
├── actions/              # Action modules (send_message, etc.)
├── assistant/            # Assistant modules (message_reader, etc.)
├── automation/           # WhatsApp automation (chrome_debug, whatsapp_dom, etc.)
├── backup/               # Backup files
├── config/               # Configuration files
├── core/                 # Core modules (prompt.txt, etc.)
├── debug/                # 🆕 Debug files and old tests
│   ├── json/            # JSON debug output
│   ├── html/            # HTML test files
│   └── old_tests/       # Deprecated test files
├── docs/                 # 🆕 All documentation
├── log/                  # Log files
├── memory/               # Memory management
├── scripts/              # 🆕 Utility scripts
│   ├── debug/           # Debug scripts
│   └── utilities/       # Utility scripts
├── static/               # Static files
├── tests/                # All test files
├── main.py               # Main entry point
├── ui.py                 # UI module
├── tts.py                # Text-to-speech
├── llm.py                # LLM integration
├── conversation_state.py # Conversation state
├── shared_state.py       # Shared state
├── websocket_server.py   # WebSocket server
├── speech_to_text_websocket.py # Speech-to-text
├── README                # Main README
├── REQUIREMENTS.txt      # Python dependencies
└── .gitignore            # Git ignore rules
""")
    print("\n✅ All files organized!")
    print("✅ Documentation moved to docs/")
    print("✅ Debug files moved to debug/")
    print("✅ Scripts moved to scripts/")
    print("✅ Old tests archived in debug/old_tests/")
    print("\n🎯 Repository is now clean and organized!")

def main():
    """Main cleanup function"""
    print("="*80)
    print("SAM AGENT REPOSITORY CLEANUP")
    print("="*80)
    print()
    
    print("📁 Step 1: Creating directory structure...")
    create_directories()
    print()
    
    print("📄 Step 2: Moving documentation...")
    move_documentation()
    print()
    
    print("🔍 Step 3: Organizing debug files...")
    move_debug_files()
    print()
    
    print("🧪 Step 4: Moving old test files...")
    move_old_test_files()
    print()
    
    print("⚙️ Step 5: Moving utility scripts...")
    move_scripts()
    print()
    
    print("📝 Step 6: Updating .gitignore...")
    update_gitignore()
    print()
    
    print("📚 Step 7: Creating README files...")
    create_readme_files()
    print()
    
    print_summary()

if __name__ == "__main__":
    main()