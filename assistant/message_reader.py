import time
import pyautogui
import pyperclip
from pathlib import Path
from tts import edge_speak
from conversation_state import controller, State
from log.logger import get_logger, log_error

logger = get_logger("message_reader")


def count_unread_messages(player=None) -> int:
    """
    Count the number of unread messages by extracting the number from the Unread tab.
    Returns the count of unread messages.
    """
    try:
        import re
        from PIL import Image
        logger.info("Counting unread messages")
        
        # Click on Unread tab first to ensure it's visible
        pyautogui.click(180, 167)  # Position of "Unread" tab
        time.sleep(0.5)
        
        # Take screenshot of the unread tab area
        unread_tab_screenshot = pyautogui.screenshot(region=(130, 150, 120, 30))  # Area around "Unread X" text
        
        # Try OCR to extract the unread count
        try:
            import pytesseract
            # Configure pytesseract to only look for digits
            text = pytesseract.image_to_string(unread_tab_screenshot, config='--psm 8 -c tessedit_char_whitelist=0123456789')
            
            # Extract number from text
            numbers = re.findall(r'\d+', text)
            if numbers:
                count = int(numbers[0])
                logger.info(f"OCR extracted unread count: {count}")
                return count
            else:
                logger.warning("No numbers found in OCR text")
        except ImportError:
            logger.warning("pytesseract not available, using fallback method")
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
        
        # Fallback method: Try to select and copy the unread tab text
        try:
            logger.info("Trying fallback method: copying unread tab text")
            pyperclip.copy("")  # Clear clipboard
            
            # Double-click on the unread tab to potentially select the text
            pyautogui.click(180, 167)
            time.sleep(0.2)
            pyautogui.click(180, 167)
            time.sleep(0.3)
            
            # Try to copy what's selected
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.3)
            
            tab_text = pyperclip.paste()
            logger.info(f"Copied tab text: '{tab_text}'")
            
            # Extract number from the text
            numbers = re.findall(r'\d+', tab_text)
            if numbers:
                count = int(numbers[0])
                logger.info(f"Fallback method extracted count: {count}")
                return count
                
        except Exception as e:
            logger.error(f"Fallback method failed: {e}")
        
        # If we can see the "Unread" tab is active, assume there are unread messages
        logger.info("Could not extract exact count, but unread messages exist")
        return -1  # Return -1 to indicate unknown count but messages exist
        
    except Exception as e:
        logger.error(f"Error counting unread messages: {e}")
        return 0


def read_latest_whatsapp_message(player=None) -> bool:
    """
    Opens WhatsApp Desktop and reads the most recent message.
    Triggered mode only.
    """

    try:
        pyautogui.PAUSE = 0.2

        # Clear clipboard first to avoid reading old data
        pyperclip.copy("")
        logger.info("Cleared clipboard")

        # Open WhatsApp
        app_name = "WhatsApp"
        logger.info(f"Opening app: {app_name}")
        if player:
            player.write_log(f"Opening app: {app_name}")

        pyautogui.press("win")
        time.sleep(0.5)
        pyautogui.write("WhatsApp", interval=0.05)
        pyautogui.press("enter")
        time.sleep(3.0)  # Give more time for WhatsApp to fully load
        logger.info("WhatsApp should be open now")

        # Try to focus WhatsApp window by clicking on it first
        # This is more reliable than keyboard shortcuts
        try:
            # Look for WhatsApp window and click on it
            try:
                import pygetwindow as gw
                whatsapp_windows = gw.getWindowsWithTitle("WhatsApp")
                if whatsapp_windows:
                    whatsapp_windows[0].activate()
                    logger.info("Focused WhatsApp window")
                    time.sleep(1.0)
                else:
                    logger.warning("No WhatsApp window found")
            except ImportError:
                logger.info("pygetwindow not available, using fallback method")
            except Exception as e:
                logger.warning(f"Could not focus WhatsApp window: {e}")
        except Exception as e:
            logger.warning(f"Window focusing failed: {e}, continuing anyway")

        # Check for unread messages count first
        unread_count = count_unread_messages(player)
        
        # Report unread message count
        if unread_count > 0:
            count_msg = f"Sir, you have {unread_count} unread messages. Let me read the latest one."
            logger.info(f"Found {unread_count} unread messages")
            if player:
                player.write_log(count_msg)
            controller.set_state(State.SPEAKING)
            edge_speak(count_msg, player, blocking=True)
            controller.set_state(State.IDLE)
        elif unread_count == -1:
            count_msg = "Sir, you have unread messages. Let me read the latest one."
            logger.info("Found unread messages (count unknown)")
            if player:
                player.write_log(count_msg)
            controller.set_state(State.SPEAKING)
            edge_speak(count_msg, player, blocking=True)
            controller.set_state(State.IDLE)
        else:
            count_msg = "Sir, you have no unread messages."
            logger.info("No unread messages found")
            if player:
                player.write_log(count_msg)
            controller.set_state(State.SPEAKING)
            edge_speak(count_msg, player, blocking=True)
            controller.set_state(State.IDLE)
            return True  # Exit early if no unread messages

        # Click on "Unread" tab to filter to unread messages only
        logger.info("Clicking on Unread tab to filter messages")
        try:
            # Click on "Unread 40" tab (updated coordinates based on UI)
            pyautogui.click(175, 166)  # Position of "Unread" tab
            time.sleep(1.5)
            logger.info("Clicked Unread tab")
        except Exception as e:
            logger.warning(f"Could not click Unread tab: {e}")
        
        # Press Escape first to ensure we're not in search mode
        pyautogui.press("escape")
        time.sleep(0.3)
        
        # Click on the first unread chat in the list (Bedemi Friend in this case)
        logger.info("Clicking on first unread chat")
        pyautogui.click(150, 230)  # Position of first chat in unread list
        time.sleep(2.0)  # Give more time for chat to fully load
        logger.info("Opened first unread chat")

        # Now focus on the actual message area and go to the bottom
        logger.info("Focusing on message area")
        pyautogui.click(800, 400)  # Click in the middle of message area
        time.sleep(0.5)
        
        # Go to the very bottom of the conversation
        pyautogui.hotkey("ctrl", "end")
        time.sleep(0.5)
        logger.info("Moved to bottom of conversation")

        # Now try multiple methods to select and copy message content
        success = False
        chat_text = ""

        # Method 1: Try right-click context menu to copy (most reliable for WhatsApp)
        try:
            logger.info("Method 1: Trying right-click context menu method")
            pyperclip.copy("")  # Clear clipboard
            
            # Click on a message in the recent area
            msg_x, msg_y = 800, 550
            pyautogui.click(msg_x, msg_y)
            time.sleep(0.3)
            
            # Right-click to open context menu
            pyautogui.rightClick(msg_x, msg_y)
            time.sleep(0.5)
            
            # Press Down arrow a few times to find "Copy" option
            # In WhatsApp, "Copy" is usually 2-3 items down in the context menu
            pyautogui.press("down")
            time.sleep(0.1)
            pyautogui.press("down")
            time.sleep(0.1)
            pyautogui.press("enter")
            time.sleep(0.5)
            
            test_text = pyperclip.paste()
            if test_text and test_text.strip() and len(test_text.strip()) > 3:
                chat_text = test_text
                success = True
                logger.info(f"Method 1 SUCCESS (right-click): Got text: '{chat_text[:100]}...'")
            else:
                logger.warning(f"Method 1 failed: Got '{test_text}'")
                # Try pressing ESC to close any menu
                pyautogui.press("escape")
                time.sleep(0.2)
        except Exception as e:
            logger.error(f"Method 1 error: {e}")
            pyautogui.press("escape")  # Close any open menu

        # Method 2: Try selecting text with mouse and using keyboard shortcut
        if not success:
            try:
                logger.info("Method 2: Trying precise mouse drag on message bubble")
                pyperclip.copy("")
                time.sleep(0.2)
                
                # Click at the start of a message line
                start_x, start_y = 580, 600  #  Start of message text
                end_x, end_y = 1020, 630     # End of message text
                
                # Perform drag selection
                pyautogui.moveTo(start_x, start_y)
                time.sleep(0.2)
                pyautogui.mouseDown()
                pyautogui.moveTo(end_x, end_y, duration=0.5)
                pyautogui.mouseUp()
                time.sleep(0.3)
                
                #Try Ctrl+C
                pyautogui.hotkey("ctrl", "c")
                time.sleep(0.5)
                
                test_text = pyperclip.paste()
                if test_text and test_text.strip():
                    chat_text = test_text
                    success = True
                    logger.info(f"Method 2 SUCCESS: Got text: '{chat_text[:100]}...'")
                else:
                    logger.warning("Method 2 failed: Empty clipboard")
            except Exception as e:
                logger.error(f"Method 2 error: {e}")

        # Method 3: Try selecting the recent message area with mouse drag
        if not success:
            try:
                logger.info("Method 3: Trying mouse drag selection in recent area")
                pyperclip.copy("")
                time.sleep(0.2)
                
                # Drag from top of recent messages to bottom
                start_x, start_y = 580, 500  # Start of recent message area
                end_x, end_y = 1000, 650     # End of recent message area
                
                pyautogui.moveTo(start_x, start_y)
                pyautogui.dragTo(end_x, end_y, duration=0.8)  # Slower drag
                time.sleep(0.3)
                
                pyautogui.hotkey("ctrl", "c")
                time.sleep(0.5)
                
                test_text = pyperclip.paste()
                if test_text and test_text.strip():
                    chat_text = test_text
                    success = True
                    logger.info(f"Method 3 SUCCESS: Got text: '{chat_text[:100]}...'")
                else:
                    logger.warning("Method 3 failed: Empty clipboard")
            except Exception as e:
                logger.error(f"Method 3 error: {e}")

        # Method 4: Last resort - select all and filter for recent content  
        if not success:
            try:
                logger.info("Method 4: Last resort - select all and filter")
                pyperclip.copy("")
                time.sleep(0.2)
                
                # Click to focus, then select all
                pyautogui.click(800, 400)
                time.sleep(0.3)
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.5)
                pyautogui.hotkey("ctrl", "c")
                time.sleep(0.7)
                
                test_text = pyperclip.paste()
                if test_text and test_text.strip():
                    chat_text = test_text
                    success = True
                    logger.info(f"Method 4 SUCCESS: Got text: '{chat_text[:100]}...'")
                else:
                    logger.warning("Method 4 failed: Empty clipboard")
            except Exception as e:
                logger.error(f"Method 4 error: {e}")

        logger.info(f"Final clipboard content length: {len(chat_text)} characters")
        if chat_text:
            logger.info(f"Raw clipboard content: '{chat_text[:300]}...'")
        else:
            logger.warning("All clipboard copy methods failed - using OCR fallback")
            
            # OCR FALLBACK METHOD - Read text directly from screen
            try:
                logger.info("Attempting OCR to read message from screen")
                from PIL import Image
                import pytesseract
                
                # Take screenshot of the message area (right side of WhatsApp)
                # Based on typical WhatsApp layout: messages are on the right
                message_area = pyautogui.screenshot(region=(520, 200, 820, 500))  # (x, y, width, height)
                
                # Save screenshot for debugging
                screenshot_path = str(Path(__file__).parent.parent / "log" / "whatsapp_screenshot.png")
                message_area.save(screenshot_path)
                logger.info(f"Saved screenshot to {screenshot_path}")
                
                # Perform OCR
                ocr_text = pytesseract.image_to_string(message_area)
                logger.info(f"OCR extracted text ({len(ocr_text)} chars): '{ocr_text[:200]}...'")
                
                if ocr_text and ocr_text.strip():
                    chat_text = ocr_text
                    success = True
                    logger.info("OCR method successful!")
                else:
                    logger.error("OCR returned empty text")
                    
            except ImportError as e:
                logger.error(f"OCR libraries not available: {e}")
                logger.error("Please install: pip install pytesseract pillow")
                logger.error("And install Tesseract OCR: https://github.com/tesseract-ocr/tesseract")
            except Exception as e:
                logger.error(f"OCR method failed: {e}")
        
        if player:
            player.write_log(f"Raw clipboard ({len(chat_text)} chars): {chat_text[:100]}...")

        if not chat_text.strip():
            msg = "Sir, I could not read any recent messages from this chat."
            logger.warning("Clipboard was empty after all copy attempts")
        else:
            lines = chat_text.strip().split("\n")
            logger.info(f"Parsing {len(lines)} lines from clipboard")
            
            # Filter out empty lines, timestamps, and system messages
            meaningful_lines = []
            for i, line in enumerate(lines):
                line = line.strip()
                logger.debug(f"Line {i}: '{line}'")
                if line and not any([
                    line.startswith("WhatsApp"),
                    line.startswith("Today"),
                    line.startswith("Yesterday"), 
                    line.startswith("Sunday"),
                    line.startswith("Monday"),
                    line.startswith("Tuesday"),
                    line.startswith("Wednesday"),
                    line.startswith("Thursday"),
                    line.startswith("Friday"),
                    line.startswith("Saturday"),
                    "AM" in line and len(line) < 20,  # Likely timestamp
                    "PM" in line and len(line) < 20,  # Likely timestamp
                    line.startswith("1/") and "/" in line and len(line) < 15,  # Date format
                    line.startswith("2/") and "/" in line and len(line) < 15,  # Date format
                    line == "Unread messages",
                    line.startswith("Search or start"),
                    line in ["All", "Unread", "Favorites"],
                ]):
                    meaningful_lines.append(line)
                    logger.debug(f"  -> Kept meaningful line: '{line}'")
                else:
                    logger.debug(f"  -> Filtered out: '{line}'")
            
            logger.info(f"Found {len(meaningful_lines)} meaningful lines")
            
            if meaningful_lines:
                # Get the last meaningful message (most recent)
                last_message = meaningful_lines[-1]
                logger.info(f"Last meaningful line: '{last_message}'")
                
                # Sometimes the very last line might be incomplete, check the last 2-3 lines
                # for the most substantial message
                candidate_messages = meaningful_lines[-3:] if len(meaningful_lines) >= 3 else meaningful_lines
                
                # Find the longest/most substantial message in the last few
                best_message = max(candidate_messages, key=len) if candidate_messages else last_message
                
                logger.info(f"Selected message to report: '{best_message[:100]}...'")
                last_message = best_message
                
                # Handle different message types with confirmation language
                if "📷 Photo" in last_message:
                    msg = "Sir, the most recent unread message is a photo."
                elif "🎵 Audio" in last_message or "Voice message" in last_message:
                    msg = "Sir, the most recent unread message is a voice note."
                elif "📹 Video" in last_message:
                    msg = "Sir, the most recent unread message is a video."
                elif "📄 Document" in last_message:
                    msg = "Sir, the most recent unread message is a document."
                elif last_message.startswith("Sticker"):
                    msg = "Sir, the most recent unread message is a sticker."
                elif len(last_message) < 30 and last_message.endswith(":"):
                    # This might be just a sender name, look for the previous line
                    logger.info("Last line looks like sender name, checking previous lines")
                    if len(meaningful_lines) > 1:
                        for i in range(len(meaningful_lines) - 2, -1, -1):
                            prev_line = meaningful_lines[i]
                            if not prev_line.endswith(":") and len(prev_line) > 3:
                                sender = last_message.replace(":", "")
                                msg = f"Sir, the most recent unread message is from {sender}, saying: {prev_line}"
                                break
                        else:
                            msg = f"Sir, the most recent unread message is from {last_message.replace(':', '')}"
                    else:
                        msg = f"Sir, the most recent unread message is from {last_message.replace(':', '')}"
                else:
                    # Check if this is a group message (has sender name)
                    if ":" in last_message and not last_message.startswith("http"):
                        parts = last_message.split(":", 1)
                        if len(parts) == 2 and len(parts[0]) < 50:  # Reasonable sender name length
                            sender = parts[0].strip()
                            message = parts[1].strip()
                            if message:
                                msg = f"Sir, the most recent unread message is from {sender}, saying: {message}"
                            else:
                                msg = f"Sir, the most recent unread message is from {sender}, but I couldn't read the content."
                        else:
                            msg = f"Sir, the most recent unread message says: {last_message}"
                    else:
                        msg = f"Sir, the most recent unread message says: {last_message}"
                
                logger.info(f"Final message to speak: '{msg}'")
            else:
                msg = "Sir, I opened the chat but couldn't find any readable message content."
                logger.warning("No meaningful content found in clipboard after filtering")

        if player:
            player.write_log(msg)

        controller.set_state(State.SPEAKING)
        edge_speak(msg, player, blocking=True)
        controller.set_state(State.IDLE)

        return True

    except Exception as e:
        msg = "Sir, I encountered an error while trying to read your WhatsApp messages."
        if player:
            player.write_log(f"{msg} ({e})")

        # Log the error to components log
        try:
            log_error(logger, "read_latest_whatsapp_message", e)
        except Exception:
            logger.error(f"Error logging failure: {e}")

        controller.set_state(State.SPEAKING)
        edge_speak(msg, player, blocking=True)
        controller.set_state(State.IDLE)

        return False
