# Sam Agent Tests

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
cd c:\Users\DELL.COM\Desktop\Darey\Sam-Agent
python -m pytest tests/

# Run specific test
python tests/test_sam_status.py
```

## Test Requirements
- Chrome with remote debugging (port 9222)
- WhatsApp Web logged in
- All dependencies from REQUIREMENTS.txt installed
