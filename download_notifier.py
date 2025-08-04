import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import pygame # Used for playing alarm sounds
import json
import requests
from urllib.parse import urlparse
import re
import sqlite3 # Added for potential Telegram DB access, though highly experimental
import sys
from pathlib import Path
from datetime import datetime
import webbrowser
import hashlib

# --- Configuration ---
# Default download directory (can be changed by user)
# This is a common path for Windows downloads.
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
# Pygame supports both WAV and MP3.
# Make sure you have an alarm.wav or alarm.mp3 file in the same directory as this script.
ALARM_SOUND_FILE = "alarm.wav" # You can change this to "alarm.mp3" if you prefer

# File size thresholds for notifications (in MB)
MIN_FILE_SIZE_MB = 1  # Only notify for files larger than 1MB
MAX_PROCESSING_TIME = 300  # Maximum time to wait for a file to complete (5 minutes)

# UI Configuration
APP_VERSION = "2.0.0"
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 600
SETTINGS_FILE = "settings.json"

# --- Enhanced Theme Configuration ---
DARK_THEME = {
    "bg": "#2b2b2b",
    "fg": "#ffffff",
    "secondary_bg": "#3c3c3c",
    "accent": "#4CAF50",
    "accent_hover": "#45a049",
    "danger": "#f44336",
    "danger_hover": "#da190b",
    "warning": "#ff9800",
    "info": "#2196F3",
    "success": "#4CAF50",
    "text_bg": "#404040",
    "text_fg": "#ffffff",
    "entry_bg": "#505050",
    "entry_fg": "#ffffff",
    "border": "#555555",
    "hover": "#4a4a4a"
}

LIGHT_THEME = {
    "bg": "#f5f5f5",
    "fg": "#333333",
    "secondary_bg": "#ffffff",
    "accent": "#4CAF50",
    "accent_hover": "#45a049",
    "danger": "#f44336",
    "danger_hover": "#da190b",
    "warning": "#ff9800",
    "info": "#2196F3",
    "success": "#4CAF50",
    "text_bg": "#ffffff",
    "text_fg": "#333333",
    "entry_bg": "#ffffff",
    "entry_fg": "#333333",
    "border": "#cccccc",
    "hover": "#e0e0e0"
}

# --- Enhanced File System Event Handler with Size Checking ---
class SizeAwareDownloadHandler(FileSystemEventHandler):
    """
    Enhanced handler that checks actual file size vs expected size to determine completion.
    Attempts to get expected size from various sources (HTTP HEAD, companion files,
    and a highly experimental/speculative check for Telegram's database).
    """
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.download_queue = []
        self.processing_thread = None
        self.stop_processing_event = threading.Event()
        self.file_creation_times = {} # To track when a file was first detected
        self.file_expected_sizes = {} # Store expected file sizes if found
        self.telegram_db_path = self._find_telegram_db() # Attempt to find Telegram DB

    def _find_telegram_db(self):
        """
        Attempts to locate Telegram's database file (e.g., 'data.db' or similar)
        for potential download info. This is highly experimental and may not work
        reliably across different Telegram versions or OS configurations.
        Telegram's internal database structure is complex and not publicly documented.
        """
        common_telegram_paths = [
            os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Telegram Desktop", "tdata"), # Windows
            os.path.join(os.path.expanduser("~"), ".local", "share", "TelegramDesktop", "tdata"), # Linux
            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Telegram Desktop", "tdata"), # macOS
        ]
        
        for base_path in common_telegram_paths:
            if os.path.exists(base_path):
                # Look for database files in subdirectories, often named like 'data0.db', 'data1.db'
                for root, dirs, files in os.walk(base_path):
                    for file in files:
                        # Prioritize files that look like main data stores
                        if file.endswith('.db') and ('data' in file.lower() or 'downloads' in file.lower()):
                            return os.path.join(root, file)
                # If no specific DB file, return the tdata directory itself for broader search later
                return base_path
        return None

    def _get_expected_file_size_from_url(self, url):
        """
        Attempts to get the expected file size from a URL using an HTTP HEAD request.
        This is useful if the download URL is known.
        """
        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            content_length = response.headers.get('Content-Length')
            if content_length:
                return int(content_length)
        except requests.exceptions.RequestException as e:
            self.app._log_message(f"HTTP HEAD request failed for URL: {e}", "info")
        return None

    def _parse_browser_temp_files(self, file_path):
        """
        Attempts to infer expected size from browser temporary files (e.g., .crdownload).
        This is largely a placeholder as direct parsing of browser temp files for total size
        is complex and browser-specific (e.g., Chrome's .crdownload files don't easily expose total size).
        """
        # For .crdownload, Chrome doesn't typically embed the total size in a parsable way
        # within the .crdownload file itself without deep reverse engineering.
        # The total size is usually known by the browser's internal download manager.
        # This function serves as a hook if such a method were discovered.
        return None

    def _get_telegram_download_info(self, file_path):
        """
        Attempts to extract download information from Telegram's data.
        This is a highly speculative and experimental function. Telegram's internal
        data storage is complex and not officially documented for external parsing.
        It tries to find metadata files or use SQLite if a .db file is found.
        """
        if not self.telegram_db_path or not os.path.exists(self.telegram_db_path):
            return None
            
        filename = os.path.basename(file_path)
        directory = os.path.dirname(file_path)
        
        # Method 1: Look for companion files (e.g., .json, .info) in the same directory
        # Telegram sometimes creates small metadata files alongside downloads.
        for file in os.listdir(directory):
            if file.startswith(filename) and (file.endswith('.json') or file.endswith('.info')):
                metadata_path = os.path.join(directory, file)
                try:
                    with open(metadata_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        # Try to parse as JSON
                        try:
                            data = json.loads(content)
                            size_keys = ['size', 'total_size', 'content_length', 'filesize', 'length']
                            for key in size_keys:
                                if key in data and isinstance(data[key], (int, str)):
                                    return int(data[key])
                        except json.JSONDecodeError:
                            # If not JSON, try regex for size patterns in plain text
                            size_patterns = [
                                r'"size":\s*(\d+)',
                                r'"total_size":\s*(\d+)',
                                r'"content_length":\s*(\d+)',
                                r'size=(\d+)',
                            ]
                            for pattern in size_patterns:
                                match = re.search(pattern, content, re.IGNORECASE)
                                if match:
                                    return int(match.group(1))
                except Exception as e:
                    self.app._log_message(f"Error reading Telegram companion file '{metadata_path}': {e}", "info")
        
        # Method 2: Attempt to query a SQLite database if self.telegram_db_path points to one
        # This is highly speculative as table/column names are unknown.
        if self.telegram_db_path.endswith('.db'):
            try:
                conn = sqlite3.connect(self.telegram_db_path)
                cursor = conn.cursor()
                # This query is a guess and will likely fail without specific knowledge of schema
                cursor.execute(f"SELECT size FROM downloads WHERE filename LIKE '%{filename}%' LIMIT 1")
                result = cursor.fetchone()
                if result and result[0]:
                    self.app._log_message(f"Found size in Telegram DB (speculative): {result[0]}", "info")
                    return int(result[0])
            except sqlite3.Error as e:
                self.app._log_message(f"SQLite error accessing Telegram DB: {e}", "info")
            finally:
                if 'conn' in locals() and conn:
                    conn.close()
        
        return None

    def _detect_expected_file_size(self, file_path):
        """
        Tries multiple methods to detect the expected final file size.
        """
        expected_size = None
        
        # Method 1: Check for companion files with size info (most reliable for non-browser downloads)
        expected_size = self._check_companion_files(file_path)
        if expected_size:
            self.app._log_message(f"Expected size from companion file: {expected_size:,} bytes", "info")
            return expected_size
            
        # Method 2: Try to get info from Telegram (if applicable)
        if self._is_likely_telegram_file(file_path):
            expected_size = self._get_telegram_download_info(file_path)
            if expected_size:
                self.app._log_message(f"Expected size from Telegram data (experimental): {expected_size:,} bytes", "info")
                return expected_size
        
        # Method 3: Parse browser temp files (currently a placeholder as it's complex)
        expected_size = self._parse_browser_temp_files(file_path)
        if expected_size:
            self.app._log_message(f"Expected size from browser temp file (experimental): {expected_size:,} bytes", "info")
            return expected_size
        
        # Method 4: If a URL can be inferred (e.g., from clipboard, browser history - not implemented here),
        # perform an HTTP HEAD request. This is beyond the scope of this current implementation.
        
        return None

    def _check_companion_files(self, file_path):
        """
        Looks for companion files (e.g., .json, .info) that might contain size information.
        """
        directory = os.path.dirname(file_path)
        filename_base, _ = os.path.splitext(os.path.basename(file_path))
        
        # Common patterns for companion files
        companion_patterns = [
            f"{os.path.basename(file_path)}.info",
            f"{os.path.basename(file_path)}.meta",
            f"{os.path.basename(file_path)}.json",
            f"{filename_base}.info",
            f"{filename_base}.meta",
            f"{filename_base}.json",
            f".{os.path.basename(file_path)}.info", # Hidden files
            f".{filename_base}.info",
        ]
        
        for pattern in companion_patterns:
            companion_path = os.path.join(directory, pattern)
            if os.path.exists(companion_path):
                try:
                    with open(companion_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        # Try to parse as JSON first
                        try:
                            data = json.loads(content)
                            # Look for common size-related keys
                            size_keys = ['size', 'total_size', 'content_length', 'filesize', 'length']
                            for key in size_keys:
                                if key in data and isinstance(data[key], (int, str)):
                                    try:
                                        return int(data[key])
                                    except ValueError:
                                        continue # Skip if not a valid integer
                        except json.JSONDecodeError:
                            # If not JSON, try regex patterns on plain text
                            size_patterns = [
                                r'size[:=\s"]*(\d+)',
                                r'length[:=\s"]*(\d+)',
                                r'bytes[:=\s"]*(\d+)',
                                r'total[:=\s"]*(\d+)',
                            ]
                            for pattern in size_patterns:
                                match = re.search(pattern, content, re.IGNORECASE)
                                if match:
                                    try:
                                        return int(match.group(1))
                                    except ValueError:
                                        continue
                except Exception as e:
                    self.app._log_message(f"Error reading companion file '{companion_path}': {e}", "info")
                    continue
                    
        return None

    def _is_file_temporary(self, file_path):
        """
        Enhanced temporary file detection based on common patterns and extensions.
        """
        file_name = os.path.basename(file_path)
        file_name_lower = file_name.lower()
        
        temp_extensions = (
            ".tmp", ".crdownload", ".part", ".download", ".filepart",
            ".idm", ".idm.tmp", ".idm.bak", ".dwnl", ".inprogress",
            ".downloading", ".temp", ".partial", ".resume",
            ".unconfirmed", ".opdownload", ".!ut", ".td", # .td for Telegram temp
            ".crswap", ".swp", ".lock", ".~"
        )
        
        for ext in temp_extensions:
            if file_name_lower.endswith(ext):
                return True
        
        # Common temporary file patterns in filenames
        if (file_name_lower.startswith("downloading_") or 
            file_name_lower.startswith("temp_") or
            file_name_lower.startswith("~") or
            "_downloading" in file_name_lower or
            file_name.startswith(".")):  # Hidden files often used as temp
            return True
            
        # Check file size - very small files might be incomplete
        try:
            file_size = os.path.getsize(file_path)
            if file_size < 1024:  # Less than 1KB, might be a stub
                return True
        except (OSError, FileNotFoundError):
            return True
            
        return False

    def _is_likely_telegram_file(self, file_path):
        """
        Heuristic to check if a file path is likely related to Telegram downloads.
        Telegram often uses numerical or hash-like filenames without extensions initially.
        """
        path_lower = file_path.lower()
        if "telegram desktop" in path_lower or "tdata" in path_lower:
            return True
            
        file_name = os.path.basename(file_path)
        # Telegram files often have long numerical/hex names without extensions
        if (len(file_name) >= 10 and # Long enough to be a hash/ID
            not "." in file_name and # No extension
            file_name.isalnum()): # Contains only alphanumeric characters
            return True
            
        return False

    def _add_to_queue_if_not_temp(self, file_path):
        """
        Adds a file to the processing queue if it's not a temporary file.
        Attempts to detect expected size and updates GUI.
        """
        if not self._is_file_temporary(file_path):
            # Check minimum file size threshold
            try:
                file_size = os.path.getsize(file_path)
                if file_size < MIN_FILE_SIZE_MB * 1024 * 1024:  # Convert MB to bytes
                    self.app._log_message(f"Skipped small file: {os.path.basename(file_path)} ({file_size:,} bytes)", "info")
                    return
            except (OSError, FileNotFoundError):
                return
                
            self.file_creation_times[file_path] = time.time()
            
            # Try to detect expected file size
            expected_size = self._detect_expected_file_size(file_path)
            if expected_size:
                self.file_expected_sizes[file_path] = expected_size
                self.app.update_status(f"Detected file: {os.path.basename(file_path)} (Expected: {expected_size:,} bytes)")
                self.app._log_message(f"File added with expected size: {os.path.basename(file_path)} -> {expected_size:,} bytes", "info")
            else:
                self.app.update_status(f"Detected file: {os.path.basename(file_path)} (Size unknown)")
                self.app._log_message(f"File added without size info: {os.path.basename(file_path)}", "info")
                
            self.download_queue.append(file_path)
            
            if not self.processing_thread or not self.processing_thread.is_alive():
                self.stop_processing_event.clear()
                self.processing_thread = threading.Thread(target=self._process_downloads)
                self.processing_thread.daemon = True # Allow thread to exit with main app
                self.processing_thread.start()
        else:
            self.app.update_status(f"Skipped temporary file: {os.path.basename(file_path)}")
            self.app._log_message(f"Skipped temporary file: {os.path.basename(file_path)}", "info")

    def on_created(self, event):
        """Called when a file or directory is created."""
        if not event.is_directory:
            self._add_to_queue_if_not_temp(event.src_path)

    def on_moved(self, event):
        """
        Called when a file or directory is moved/renamed.
        This is crucial for detecting completed browser downloads.
        """
        if not event.is_directory:
            # When a file is moved/renamed, the destination path is the final, completed file.
            self._add_to_queue_if_not_temp(event.dest_path)

    def _process_downloads(self):
        """
        Processes files in the download queue to determine if they are complete.
        This runs in a separate thread to avoid blocking the GUI.
        Uses size-aware completion detection.
        """
        while self.download_queue and not self.stop_processing_event.is_set():
            file_path = self.download_queue.pop(0) # Get the first file in queue
            
            if not os.path.exists(file_path):
                self.app._log_message(f"File disappeared before processing: {os.path.basename(file_path)}", "info")
                self._cleanup_file_data(file_path)
                continue
                
            # Check if file has been processing too long
            creation_time = self.file_creation_times.get(file_path, time.time())
            if time.time() - creation_time > MAX_PROCESSING_TIME:
                self.app._log_message(f"Processing timeout for: {os.path.basename(file_path)}", "info")
                self._cleanup_file_data(file_path)
                continue
                
            self.app.update_status(f"Checking download status for: {os.path.basename(file_path)}")
            if self._is_download_complete_size_aware(file_path):
                self.app.notify_download_complete(file_path)
                self._cleanup_file_data(file_path)
            else:
                # If not complete, put it back to re-check later
                self.download_queue.append(file_path)
                time.sleep(2) # Wait a bit before re-checking (longer for size-aware)

    def _is_download_complete_size_aware(self, file_path):
        """
        Enhanced completion check using expected file size when available.
        Falls back to stability-based detection if expected size is unknown.
        """
        if not os.path.exists(file_path):
            return False

        try:
            current_size = os.path.getsize(file_path)
            expected_size = self.file_expected_sizes.get(file_path)
            
            # If we know the expected size, use it for precise detection
            if expected_size:
                # Allow a small tolerance for file system quirks or minor differences
                # (e.g., 0.1% tolerance or a few bytes)
                tolerance = max(1024, expected_size * 0.001) # 1KB or 0.1%
                if abs(current_size - expected_size) <= tolerance:
                    # Double-check that file is stable after reaching expected size
                    # This helps ensure it's not still being written to.
                    time.sleep(1)
                    final_size = os.path.getsize(file_path)
                    if abs(final_size - expected_size) <= tolerance:
                        progress_pct = (current_size / expected_size) * 100 if expected_size > 0 else 100
                        self.app._log_message(f"Size match confirmed: {os.path.basename(file_path)} ({progress_pct:.1f}%)", "info")
                        return True
                else:
                    # Show progress if we know expected size
                    progress_pct = (current_size / expected_size) * 100 if expected_size > 0 else 0
                    self.app.update_status(f"Downloading: {os.path.basename(file_path)} ({progress_pct:.1f}% - {current_size:,}/{expected_size:,} bytes)")
                    return False
            
            # Fall back to stability-based detection if no expected size was found
            return self._is_download_complete_stability(file_path)
            
        except Exception as e:
            self.app._log_message(f"Error in size-aware check for {os.path.basename(file_path)}: {e}", "error")
            return False

    def _is_download_complete_stability(self, file_path, check_interval=2, stable_checks=3):
        """
        Fallback stability-based completion detection.
        Checks if file size and modification time remain stable over several intervals.
        """
        creation_time = self.file_creation_times.get(file_path, time.time())
        time_since_creation = time.time() - creation_time
        
        # For very new files, especially Telegram ones, give them a moment to start
        if self._is_likely_telegram_file(file_path) and time_since_creation < 5:
            return False

        last_size = -1
        last_modified = -1
        
        for i in range(stable_checks):
            try:
                current_size = os.path.getsize(file_path)
                current_modified = os.path.getmtime(file_path)
                
                if (current_size == last_size and 
                    current_modified == last_modified and 
                    current_size > 0): # Ensure it's not a zero-byte file that never grew
                    
                    # Add a small buffer time after stability is detected to be extra sure
                    time_since_modified = time.time() - current_modified
                    if time_since_modified > 2: # File hasn't been modified for at least 2 seconds
                        self.app._log_message(f"Stability check passed for: {os.path.basename(file_path)}", "info")
                        return True
                
                last_size = current_size
                last_modified = current_modified
                time.sleep(check_interval)
                
            except FileNotFoundError:
                # If file disappears during checks, it might have been moved/completed
                # Consider it complete if it existed for at least one check (i.e., i > 0)
                self.app._log_message(f"File disappeared during stability check: {os.path.basename(file_path)}", "info")
                return i > 0
            except Exception as e:
                self.app._log_message(f"Error during stability check for {os.path.basename(file_path)}: {e}", "error")
                return False

        self.app._log_message(f"Stability check failed after {stable_checks} attempts for: {os.path.basename(file_path)}", "info")
        return False

    def _cleanup_file_data(self, file_path):
        """Cleans up tracking data for a file after it's processed."""
        self.file_creation_times.pop(file_path, None)
        self.file_expected_sizes.pop(file_path, None)

    def stop_processing(self):
        """Signals the processing thread to stop and cleans up."""
        self.stop_processing_event.set()
        if self.processing_thread and self.processing_thread.is_alive():
            # Give it a moment to finish current task, then join
            self.processing_thread.join(timeout=5)
        self.file_creation_times.clear()
        self.file_expected_sizes.clear()

# --- Main Application Class ---
class DownloadNotifierApp:
    def __init__(self, master):
        self.master = master
        master.title(f"Download Notifier Pro v{APP_VERSION}")
        master.geometry("900x700")
        master.resizable(True, True)
        master.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # Application state
        self.monitor_path = tk.StringVar(value=DEFAULT_DOWNLOAD_DIR)
        self.observers = []
        self.event_handler = None
        self.is_monitoring = False
        self.download_history = []
        self.statistics = {
            "total_downloads": 0,
            "total_size": 0,
            "session_start": time.time()
        }
        
        # Settings
        self.current_theme = "light"
        self.settings = self.load_settings()
        self.notification_sound_enabled = tk.BooleanVar(value=self.settings.get("sound_enabled", True))
        self.notification_popup_enabled = tk.BooleanVar(value=self.settings.get("popup_enabled", True))
        self.min_file_size = tk.DoubleVar(value=self.settings.get("min_file_size", MIN_FILE_SIZE_MB))
        self.auto_clear_log = tk.BooleanVar(value=self.settings.get("auto_clear_log", False))
        self.show_file_details = tk.BooleanVar(value=self.settings.get("show_file_details", True))
        
        # Initialize Pygame mixer
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception as e:
                print(f"Could not initialize Pygame mixer in app: {e}")

        # Setup UI
        self.setup_styles()
        self._create_widgets()
        self.apply_theme()
        self._center_window()
        
        # Bind events
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.master.bind("<Control-s>", lambda e: self.save_settings())
        self.master.bind("<F5>", lambda e: self.refresh_ui())
        
        # Status bar timer
        self.status_timer = None

    def load_settings(self):
        """Load settings from JSON file"""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
        return {}
    
    def save_settings(self):
        """Save current settings to JSON file"""
        try:
            settings = {
                "sound_enabled": self.notification_sound_enabled.get(),
                "popup_enabled": self.notification_popup_enabled.get(),
                "min_file_size": self.min_file_size.get(),
                "auto_clear_log": self.auto_clear_log.get(),
                "show_file_details": self.show_file_details.get(),
                "monitor_paths": self.monitor_path.get(),
                "theme": self.current_theme,
                "window_geometry": self.master.geometry()
            }
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
            self.show_status("Settings saved successfully", "success", 2000)
        except Exception as e:
            self.show_status(f"Error saving settings: {e}", "error", 3000)
    
    def setup_styles(self):
        """Setup ttk styles"""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure styles for different themes
        self.configure_styles()
    
    def configure_styles(self):
        """Configure ttk styles based on current theme"""
        theme = DARK_THEME if self.current_theme == "dark" else LIGHT_THEME
        
        # Configure ttk styles
        self.style.configure('Title.TLabel', 
                           font=('Segoe UI', 16, 'bold'),
                           background=theme["bg"],
                           foreground=theme["fg"])
        
        self.style.configure('Heading.TLabel',
                           font=('Segoe UI', 12, 'bold'),
                           background=theme["bg"],
                           foreground=theme["fg"])
        
        self.style.configure('Custom.TButton',
                           font=('Segoe UI', 10),
                           padding=(10, 5))
        
        self.style.configure('Accent.TButton',
                           font=('Segoe UI', 11, 'bold'),
                           padding=(15, 8))
        
        # Notebook styles
        self.style.configure('Custom.TNotebook',
                           background=theme["bg"],
                           borderwidth=0)
        
        self.style.configure('Custom.TNotebook.Tab',
                           padding=(20, 10),
                           font=('Segoe UI', 10))

    def refresh_ui(self):
        """Refresh the UI components"""
        self.apply_theme()
        self.update_statistics_display()
        self.show_status("UI refreshed", "info", 1500)

    def _create_widgets(self):
        """Create the modern UI layout"""
        # Create main container
        self.main_container = tk.Frame(self.master)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create header
        self.create_header()
        
        # Create main content area with notebook
        self.create_main_content()
        
        # Create status bar
        self.create_status_bar()
    
    def create_header(self):
        """Create the application header"""
        header_frame = tk.Frame(self.main_container, height=80)
        header_frame.pack(fill="x", pady=(0, 15))
        header_frame.pack_propagate(False)
        
        # Left side - App title and version
        title_frame = tk.Frame(header_frame)
        title_frame.pack(side="left", fill="y")
        
        self.app_title = tk.Label(title_frame, text="Download Notifier Pro", 
                                 font=("Segoe UI", 20, "bold"))
        self.app_title.pack(anchor="w")
        
        self.version_label = tk.Label(title_frame, text=f"Version {APP_VERSION}",
                                     font=("Segoe UI", 9))
        self.version_label.pack(anchor="w")
        
        # Right side - Theme toggle and monitoring status
        controls_frame = tk.Frame(header_frame)
        controls_frame.pack(side="right", fill="y")
        
        # Theme toggle button
        self.theme_button = tk.Button(controls_frame, text="🌙 Dark",
                                     command=self.toggle_theme,
                                     font=("Segoe UI", 9),
                                     relief="flat", bd=1, padx=15, pady=5)
        self.theme_button.pack(side="top", anchor="e", pady=(0, 5))
        
        # Monitoring status indicator
        self.status_indicator = tk.Label(controls_frame, text="● Stopped",
                                        font=("Segoe UI", 10, "bold"))
        self.status_indicator.pack(side="top", anchor="e")
    
    def create_main_content(self):
        """Create the main content area with tabs"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_container, style='Custom.TNotebook')
        self.notebook.pack(fill="both", expand=True)
        
        # Tab 1: Monitor Settings
        self.create_monitor_tab()
        
        # Tab 2: Activity Log
        self.create_activity_tab()
        
        # Tab 3: Statistics
        self.create_statistics_tab()
        
        # Tab 4: Settings
        self.create_settings_tab()
    
    def create_monitor_tab(self):
        """Create the main monitoring tab"""
        monitor_frame = tk.Frame(self.notebook)
        self.notebook.add(monitor_frame, text="📁 Monitor")
        
        # Directory selection section
        dir_section = tk.LabelFrame(monitor_frame, text="📂 Directories to Monitor",
                                   font=("Segoe UI", 11, "bold"), padx=15, pady=10)
        dir_section.pack(fill="x", padx=10, pady=10)
        
        # Path entry with modern styling
        path_frame = tk.Frame(dir_section)
        path_frame.pack(fill="x", pady=5)
        
        tk.Label(path_frame, text="Paths (comma-separated):",
                font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 5))
        
        entry_frame = tk.Frame(path_frame)
        entry_frame.pack(fill="x")
        
        self.path_entry = tk.Entry(entry_frame, textvariable=self.monitor_path,
                                  font=("Segoe UI", 10), relief="solid", bd=1)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.browse_button = tk.Button(entry_frame, text="📁 Browse",
                                      command=self.browse_directory,
                                      font=("Segoe UI", 10), relief="raised", bd=1,
                                      padx=15, pady=8)
        self.browse_button.pack(side="right")
        
        # Quick path buttons
        quick_paths_frame = tk.Frame(dir_section)
        quick_paths_frame.pack(fill="x", pady=(10, 0))
        
        tk.Label(quick_paths_frame, text="Quick Add:",
                font=("Segoe UI", 9)).pack(side="left", padx=(0, 10))
        
        quick_paths = [
            ("Downloads", os.path.join(os.path.expanduser("~"), "Downloads")),
            ("Desktop", os.path.join(os.path.expanduser("~"), "Desktop")),
            ("Documents", os.path.join(os.path.expanduser("~"), "Documents"))
        ]
        
        for name, path in quick_paths:
            btn = tk.Button(quick_paths_frame, text=name,
                           command=lambda p=path: self.add_quick_path(p),
                           font=("Segoe UI", 8), relief="flat", bd=1,
                           padx=8, pady=2)
            btn.pack(side="left", padx=(0, 5))
        
        # Control buttons section
        control_section = tk.LabelFrame(monitor_frame, text="🎮 Control Panel",
                                       font=("Segoe UI", 11, "bold"), padx=15, pady=10)
        control_section.pack(fill="x", padx=10, pady=10)
        
        buttons_frame = tk.Frame(control_section)
        buttons_frame.pack(fill="x", pady=10)
        
        # Start/Stop buttons with modern styling
        self.start_button = tk.Button(buttons_frame, text="▶️ Start Monitoring",
                                     command=self.start_monitoring,
                                     font=("Segoe UI", 12, "bold"),
                                     relief="raised", bd=2, padx=20, pady=12)
        self.start_button.pack(side="left", expand=True, fill="x", padx=(0, 5))
        
        self.stop_button = tk.Button(buttons_frame, text="⏹️ Stop Monitoring",
                                    command=self.stop_monitoring,
                                    font=("Segoe UI", 12, "bold"),
                                    relief="raised", bd=2, padx=20, pady=12,
                                    state="disabled")
        self.stop_button.pack(side="left", expand=True, fill="x", padx=(5, 0))
        
        # Additional controls
        extra_controls = tk.Frame(control_section)
        extra_controls.pack(fill="x", pady=(10, 0))
        
        self.stop_alarm_button = tk.Button(extra_controls, text="🔇 Stop Alarm",
                                          command=self.stop_alarm,
                                          font=("Segoe UI", 10),
                                          relief="raised", bd=1, padx=15, pady=6,
                                          state="disabled")
        self.stop_alarm_button.pack(side="left", padx=(0, 10))
        
        self.test_sound_button = tk.Button(extra_controls, text="🔊 Test Sound",
                                          command=self.test_alarm_sound,
                                          font=("Segoe UI", 10),
                                          relief="raised", bd=1, padx=15, pady=6)
        self.test_sound_button.pack(side="left", padx=(0, 10))
        
        # Status display
        status_section = tk.LabelFrame(monitor_frame, text="📊 Current Status",
                                      font=("Segoe UI", 11, "bold"), padx=15, pady=10)
        status_section.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.status_text = tk.Text(status_section, height=6, wrap="word",
                                  font=("Consolas", 9), relief="solid", bd=1,
                                  state="disabled")
        self.status_text.pack(fill="both", expand=True, pady=5)
        
    def create_activity_tab(self):
        """Create the activity log tab"""
        activity_frame = tk.Frame(self.notebook)
        self.notebook.add(activity_frame, text="📜 Activity")
        
        # Log controls
        log_controls = tk.Frame(activity_frame)
        log_controls.pack(fill="x", padx=10, pady=10)
        
        # Filter controls
        filter_frame = tk.LabelFrame(log_controls, text="🔍 Filters", 
                                    font=("Segoe UI", 10, "bold"), padx=10, pady=5)
        filter_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.log_filter = tk.StringVar(value="all")
        filters = [("All", "all"), ("Downloads", "download"), ("Errors", "error"), ("Info", "info")]
        
        for text, value in filters:
            rb = tk.Radiobutton(filter_frame, text=text, variable=self.log_filter,
                               value=value, command=self.filter_log,
                               font=("Segoe UI", 9))
            rb.pack(side="left", padx=5)
        
        # Log action buttons
        actions_frame = tk.Frame(log_controls)
        actions_frame.pack(side="right")
        
        self.clear_log_button = tk.Button(actions_frame, text="🗑️ Clear",
                                         command=self.clear_log,
                                         font=("Segoe UI", 9), relief="raised", bd=1,
                                         padx=10, pady=5)
        self.clear_log_button.pack(side="left", padx=(0, 5))
        
        self.save_log_button = tk.Button(actions_frame, text="💾 Save",
                                        command=self.save_log,
                                        font=("Segoe UI", 9), relief="raised", bd=1,
                                        padx=10, pady=5)
        self.save_log_button.pack(side="left", padx=(0, 5))
        
        self.export_button = tk.Button(actions_frame, text="📤 Export",
                                      command=self.export_log,
                                      font=("Segoe UI", 9), relief="raised", bd=1,
                                      padx=10, pady=5)
        self.export_button.pack(side="left")
        
        # Log display
        log_display_frame = tk.Frame(activity_frame)
        log_display_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Create text widget with scrollbars
        self.log_text = tk.Text(log_display_frame, wrap="word", font=("Consolas", 9),
                               relief="solid", bd=1, state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        
        # Configure text tags for different log levels
        self.log_text.tag_config("download", foreground="#4CAF50", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("error", foreground="#f44336", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("warning", foreground="#ff9800", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("info", foreground="#2196F3")
        self.log_text.tag_config("timestamp", foreground="#666666", font=("Consolas", 8))
        
        # Scrollbars
        v_scrollbar = tk.Scrollbar(log_display_frame, orient="vertical", command=self.log_text.yview)
        v_scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=v_scrollbar.set)
        
        h_scrollbar = tk.Scrollbar(activity_frame, orient="horizontal", command=self.log_text.xview)
        h_scrollbar.pack(side="bottom", fill="x", padx=10)
        self.log_text.config(xscrollcommand=h_scrollbar.set)
    
    def create_statistics_tab(self):
        """Create the statistics tab"""
        stats_frame = tk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="📊 Statistics")
        
        # Statistics display
        stats_container = tk.Frame(stats_frame)
        stats_container.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Session statistics
        session_frame = tk.LabelFrame(stats_container, text="📈 Session Statistics",
                                     font=("Segoe UI", 12, "bold"), padx=15, pady=10)
        session_frame.pack(fill="x", pady=(0, 15))
        
        self.create_stat_row(session_frame, "Session Duration:", "session_duration")
        self.create_stat_row(session_frame, "Downloads Detected:", "total_downloads")
        self.create_stat_row(session_frame, "Total Data Size:", "total_size")
        self.create_stat_row(session_frame, "Average File Size:", "avg_size")
        
        # Recent downloads
        recent_frame = tk.LabelFrame(stats_container, text="📥 Recent Downloads",
                                    font=("Segoe UI", 12, "bold"), padx=15, pady=10)
        recent_frame.pack(fill="both", expand=True)
        
        # Create treeview for recent downloads
        columns = ("Time", "Filename", "Size", "Location")
        self.recent_tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=10)
        
        # Configure columns
        self.recent_tree.heading("Time", text="Time")
        self.recent_tree.heading("Filename", text="Filename")
        self.recent_tree.heading("Size", text="Size")
        self.recent_tree.heading("Location", text="Location")
        
        self.recent_tree.column("Time", width=120, minwidth=100)
        self.recent_tree.column("Filename", width=250, minwidth=200)
        self.recent_tree.column("Size", width=100, minwidth=80)
        self.recent_tree.column("Location", width=300, minwidth=200)
        
        self.recent_tree.pack(fill="both", expand=True, pady=5)
        
        # Treeview scrollbar
        tree_scroll = tk.Scrollbar(recent_frame, orient="vertical", command=self.recent_tree.yview)
        tree_scroll.pack(side="right", fill="y")
        self.recent_tree.config(yscrollcommand=tree_scroll.set)
        
        # Statistics action buttons
        stats_actions = tk.Frame(stats_container)
        stats_actions.pack(fill="x", pady=(10, 0))
        
        tk.Button(stats_actions, text="🔄 Refresh", command=self.update_statistics_display,
                 font=("Segoe UI", 10), relief="raised", bd=1, padx=15, pady=5).pack(side="left")
        
        tk.Button(stats_actions, text="📊 Export Stats", command=self.export_statistics,
                 font=("Segoe UI", 10), relief="raised", bd=1, padx=15, pady=5).pack(side="left", padx=(10, 0))
        
        tk.Button(stats_actions, text="🗑️ Clear History", command=self.clear_statistics,
                 font=("Segoe UI", 10), relief="raised", bd=1, padx=15, pady=5).pack(side="left", padx=(10, 0))
    
    def create_settings_tab(self):
        """Create the settings tab"""
        settings_frame = tk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="⚙️ Settings")
        
        # Create scrollable frame
        canvas = tk.Canvas(settings_frame)
        scrollbar = tk.Scrollbar(settings_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Notification settings
        notif_frame = tk.LabelFrame(scrollable_frame, text="🔔 Notifications",
                                   font=("Segoe UI", 12, "bold"), padx=15, pady=10)
        notif_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        self.sound_checkbox = tk.Checkbutton(notif_frame, text="🔊 Enable sound notifications",
                                            variable=self.notification_sound_enabled,
                                            font=("Segoe UI", 10))
        self.sound_checkbox.pack(anchor="w", pady=2)
        
        self.popup_checkbox = tk.Checkbutton(notif_frame, text="💬 Enable popup notifications",
                                            variable=self.notification_popup_enabled,
                                            font=("Segoe UI", 10))
        self.popup_checkbox.pack(anchor="w", pady=2)
        
        # File filtering settings
        filter_frame = tk.LabelFrame(scrollable_frame, text="🎯 File Filtering",
                                    font=("Segoe UI", 12, "bold"), padx=15, pady=10)
        filter_frame.pack(fill="x", padx=15, pady=10)
        
        size_frame = tk.Frame(filter_frame)
        size_frame.pack(fill="x", pady=5)
        
        tk.Label(size_frame, text="Minimum file size (MB):",
                font=("Segoe UI", 10)).pack(side="left")
        
        self.size_spinbox = tk.Spinbox(size_frame, from_=0.1, to=1000.0, increment=0.5,
                                      textvariable=self.min_file_size, width=10,
                                      font=("Segoe UI", 10))
        self.size_spinbox.pack(side="left", padx=(10, 0))
        
        # Advanced settings
        advanced_frame = tk.LabelFrame(scrollable_frame, text="🔧 Advanced",
                                      font=("Segoe UI", 12, "bold"), padx=15, pady=10)
        advanced_frame.pack(fill="x", padx=15, pady=10)
        
        self.auto_clear_checkbox = tk.Checkbutton(advanced_frame, text="🧹 Auto-clear log (1000+ entries)",
                                                 variable=self.auto_clear_log,
                                                 font=("Segoe UI", 10))
        self.auto_clear_checkbox.pack(anchor="w", pady=2)
        
        self.details_checkbox = tk.Checkbutton(advanced_frame, text="📝 Show detailed file information",
                                              variable=self.show_file_details,
                                              font=("Segoe UI", 10))
        self.details_checkbox.pack(anchor="w", pady=2)
        
        # Application settings
        app_frame = tk.LabelFrame(scrollable_frame, text="🎨 Application",
                                 font=("Segoe UI", 12, "bold"), padx=15, pady=10)
        app_frame.pack(fill="x", padx=15, pady=10)
        
        # Theme selection
        theme_selection = tk.Frame(app_frame)
        theme_selection.pack(fill="x", pady=5)
        
        tk.Label(theme_selection, text="Theme:", font=("Segoe UI", 10)).pack(side="left")
        
        self.theme_var = tk.StringVar(value=self.current_theme)
        for theme in ["light", "dark"]:
            rb = tk.Radiobutton(theme_selection, text=theme.title(), variable=self.theme_var,
                               value=theme, command=self.apply_theme,
                               font=("Segoe UI", 10))
            rb.pack(side="left", padx=(10, 0))
        
        # Action buttons
        actions_frame = tk.Frame(scrollable_frame)
        actions_frame.pack(fill="x", padx=15, pady=15)
        
        tk.Button(actions_frame, text="💾 Save Settings", command=self.save_settings,
                 font=("Segoe UI", 11, "bold"), relief="raised", bd=2,
                 padx=20, pady=8).pack(side="left")
        
        tk.Button(actions_frame, text="🔄 Reset to Defaults", command=self.reset_settings,
                 font=("Segoe UI", 10), relief="raised", bd=1,
                 padx=15, pady=8).pack(side="left", padx=(10, 0))
        
        tk.Button(actions_frame, text="ℹ️ About", command=self.show_about,
                 font=("Segoe UI", 10), relief="raised", bd=1,
                 padx=15, pady=8).pack(side="right")
        
    def create_status_bar(self):
        """Create the status bar"""
        self.status_bar = tk.Frame(self.main_container, height=30, relief="sunken", bd=1)
        self.status_bar.pack(fill="x", side="bottom", pady=(10, 0))
        self.status_bar.pack_propagate(False)
        
        # Status text
        self.status_label = tk.Label(self.status_bar, text="Ready to monitor downloads...",
                                    font=("Segoe UI", 9), anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True, padx=10)
        
        # Progress indicator (hidden by default)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.status_bar, variable=self.progress_var,
                                          mode="determinate", length=150)
        # Don't pack initially
        
        # Connection status
        self.connection_label = tk.Label(self.status_bar, text="●", 
                                        font=("Segoe UI", 12), fg="red")
        self.connection_label.pack(side="right", padx=(0, 10))
    
    def create_stat_row(self, parent, label, key):
        """Create a statistics display row"""
        frame = tk.Frame(parent)
        frame.pack(fill="x", pady=2)
        
        tk.Label(frame, text=label, font=("Segoe UI", 10)).pack(side="left")
        
        value_label = tk.Label(frame, text="--", font=("Segoe UI", 10, "bold"))
        value_label.pack(side="right")
        
        # Store reference for updating
        setattr(self, f"stat_{key}", value_label)
    
    def _center_window(self):
        """Center the window on screen"""
        self.master.update_idletasks()
        width = self.master.winfo_width()
        height = self.master.winfo_height()
        x = (self.master.winfo_screenwidth() // 2) - (width // 2)
        y = (self.master.winfo_screenheight() // 2) - (height // 2)
        self.master.geometry(f'{width}x{height}+{x}+{y}')
    
    def toggle_theme(self):
        """Toggle between light and dark themes"""
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.theme_var.set(self.current_theme)
        self.apply_theme()
    
    def apply_theme(self):
        """Apply the current theme to all widgets"""
        theme = DARK_THEME if self.current_theme == "dark" else LIGHT_THEME
        
        # Update theme button text
        self.theme_button.config(text="☀️ Light" if self.current_theme == "dark" else "🌙 Dark")
        
        # Apply theme to main components
        self.master.config(bg=theme["bg"])
        self.main_container.config(bg=theme["bg"])
        
        # Update styles
        self.configure_styles()
        
        # Apply to all widgets recursively
        self.apply_theme_to_widget(self.master, theme)
    
    def apply_theme_to_widget(self, widget, theme):
        """Recursively apply theme to widget and its children"""
        try:
            widget_class = widget.winfo_class()
            
            if widget_class in ["Frame", "Toplevel"]:
                widget.config(bg=theme["bg"])
            elif widget_class == "Label":
                widget.config(bg=theme["bg"], fg=theme["fg"])
            elif widget_class == "Button":
                self.style_button(widget, theme)
            elif widget_class == "Entry":
                widget.config(bg=theme["entry_bg"], fg=theme["entry_fg"],
                             insertbackground=theme["fg"])
            elif widget_class == "Text":
                widget.config(bg=theme["text_bg"], fg=theme["text_fg"],
                             insertbackground=theme["fg"])
            elif widget_class == "Listbox":
                widget.config(bg=theme["text_bg"], fg=theme["text_fg"])
            elif widget_class == "LabelFrame":
                widget.config(bg=theme["bg"], fg=theme["fg"])
            elif widget_class == "Checkbutton":
                widget.config(bg=theme["bg"], fg=theme["fg"],
                             activebackground=theme["hover"])
            elif widget_class == "Radiobutton":
                widget.config(bg=theme["bg"], fg=theme["fg"],
                             activebackground=theme["hover"])
            elif widget_class == "Spinbox":
                widget.config(bg=theme["entry_bg"], fg=theme["entry_fg"])
            
            # Apply to children
            for child in widget.winfo_children():
                self.apply_theme_to_widget(child, theme)
                
        except tk.TclError:
            pass  # Some widgets don't support certain config options
    
    def style_button(self, button, theme):
        """Apply theme-specific styling to buttons"""
        button_text = button.cget("text")
        
        if "Start" in button_text:
            button.config(bg=theme["accent"], fg="white",
                         activebackground=theme["accent_hover"])
        elif "Stop" in button_text:
            button.config(bg=theme["danger"], fg="white",
                         activebackground=theme["danger_hover"])
        elif button == self.theme_button:
            button.config(bg=theme["secondary_bg"], fg=theme["fg"],
                         activebackground=theme["hover"])
        else:
            button.config(bg=theme["secondary_bg"], fg=theme["fg"],
                         activebackground=theme["hover"])
    
    def show_status(self, message, level="info", duration=0):
        """Show status message with optional auto-clear"""
        colors = {
            "info": "#2196F3",
            "success": "#4CAF50", 
            "warning": "#ff9800",
            "error": "#f44336"
        }
        
        self.status_label.config(text=message, fg=colors.get(level, "#333333"))
        
        if duration > 0:
            if self.status_timer:
                self.master.after_cancel(self.status_timer)
            self.status_timer = self.master.after(duration, 
                lambda: self.status_label.config(text="Ready to monitor downloads...", 
                                                fg="#333333"))
    
    def add_quick_path(self, path):
        """Add a quick path to monitoring directories"""
        current = self.monitor_path.get()
        if current and current.strip():
            if path not in current:
                self.monitor_path.set(f"{current}, {path}")
        else:
            self.monitor_path.set(path)
        
        self.show_status(f"Added: {os.path.basename(path)}", "success", 2000)
    
    def browse_directory(self):
        """Enhanced directory browser"""
        selected_dir = filedialog.askdirectory(
            initialdir=self.monitor_path.get().split(',')[0].strip() if self.monitor_path.get() else os.path.expanduser("~"),
            title="Select Directory to Monitor"
        )
        if selected_dir:
            self.add_quick_path(selected_dir)
    
    def test_alarm_sound(self):
        """Test the alarm sound"""
        if os.path.exists(ALARM_SOUND_FILE):
            threading.Thread(target=self._play_test_sound, daemon=True).start()
        else:
            self.show_status("Alarm sound file not found!", "error", 3000)
    
    def _play_test_sound(self):
        """Play test sound in background thread"""
        try:
            pygame.mixer.music.load(ALARM_SOUND_FILE)
            pygame.mixer.music.play()
            self.show_status("Playing test sound...", "info", 2000)
        except Exception as e:
            self.show_status(f"Sound test failed: {e}", "error", 3000)

    def log_message(self, message, level="info"):
        """Enhanced logging with filtering and formatting"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        # Apply to main log
        self.status_text.config(state="normal")
        self.status_text.insert(tk.END, formatted_message, level)
        self.status_text.see(tk.END)
        self.status_text.config(state="disabled")
        
        # Apply to activity tab log
        self.log_text.config(state="normal")
        
        # Insert timestamp
        self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        
        # Insert message with appropriate tag
        level_icons = {
            "download": "📥 ",
            "error": "❌ ",
            "warning": "⚠️ ",
            "info": "ℹ️ "
        }
        icon = level_icons.get(level, "")
        self.log_text.insert(tk.END, f"{icon}{message}\n", level)
        
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        
        # Auto-clear if enabled and log is too long
        if self.auto_clear_log.get():
            line_count = int(self.log_text.index('end-1c').split('.')[0])
            if line_count > 1000:
                self.clear_log(auto=True)
    
    def filter_log(self):
        """Filter log display based on selection"""
        filter_value = self.log_filter.get()
        # This would require storing log entries separately and rebuilding
        # For now, just show a status message
        self.show_status(f"Showing {filter_value} entries", "info", 2000)
    
    def clear_log(self, auto=False):
        """Clear the activity log"""
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")
        
        self.status_text.config(state="normal")
        self.status_text.delete(1.0, tk.END)
        self.status_text.config(state="disabled")
        
        if not auto:
            self.log_message("Log cleared manually", "info")
        else:
            self.log_message("Log auto-cleared (1000+ entries)", "info")
    
    def save_log(self):
        """Save log to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Activity Log",
                initialname=f"download_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    log_content = self.log_text.get(1.0, tk.END)
                    f.write(f"Download Notifier Pro v{APP_VERSION} - Activity Log\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(log_content)
                
                self.show_status(f"Log saved: {os.path.basename(filename)}", "success", 3000)
        except Exception as e:
            self.show_status(f"Save failed: {e}", "error", 3000)
    
    def export_log(self):
        """Export log in multiple formats"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("CSV files", "*.csv"),
                    ("Text files", "*.txt")
                ],
                title="Export Activity Log",
                initialname=f"download_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            if filename:
                ext = os.path.splitext(filename)[1].lower()
                
                if ext == ".json":
                    self.export_log_json(filename)
                elif ext == ".csv":
                    self.export_log_csv(filename)
                else:
                    self.save_log()  # Fallback to text
                    
        except Exception as e:
            self.show_status(f"Export failed: {e}", "error", 3000)
    
    def export_log_json(self, filename):
        """Export log as JSON"""
        log_data = {
            "metadata": {
                "version": APP_VERSION,
                "exported": datetime.now().isoformat(),
                "session_start": datetime.fromtimestamp(self.statistics["session_start"]).isoformat()
            },
            "statistics": self.statistics,
            "downloads": self.download_history
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        self.show_status(f"Exported JSON: {os.path.basename(filename)}", "success", 3000)
    
    def export_log_csv(self, filename):
        """Export log as CSV"""
        import csv
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Filename", "Size", "Path", "Status"])
            
            for download in self.download_history:
                writer.writerow([
                    download.get("timestamp", ""),
                    download.get("filename", ""),
                    download.get("size", ""),
                    download.get("path", ""),
                    download.get("status", "")
                ])
        
        self.show_status(f"Exported CSV: {os.path.basename(filename)}", "success", 3000)
    
    def update_statistics_display(self):
        """Update the statistics display"""
        # Calculate session duration
        duration = time.time() - self.statistics["session_start"]
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        
        # Update statistics labels
        self.stat_session_duration.config(text=duration_str)
        self.stat_total_downloads.config(text=str(self.statistics["total_downloads"]))
        
        # Format total size
        total_bytes = self.statistics["total_size"]
        if total_bytes >= 1024**3:
            size_str = f"{total_bytes / (1024**3):.2f} GB"
        elif total_bytes >= 1024**2:
            size_str = f"{total_bytes / (1024**2):.2f} MB"
        elif total_bytes >= 1024:
            size_str = f"{total_bytes / 1024:.2f} KB"
        else:
            size_str = f"{total_bytes} bytes"
        
        self.stat_total_size.config(text=size_str)
        
        # Calculate average size
        if self.statistics["total_downloads"] > 0:
            avg_bytes = self.statistics["total_size"] / self.statistics["total_downloads"]
            if avg_bytes >= 1024**2:
                avg_str = f"{avg_bytes / (1024**2):.2f} MB"
            elif avg_bytes >= 1024:
                avg_str = f"{avg_bytes / 1024:.2f} KB"
            else:
                avg_str = f"{avg_bytes:.0f} bytes"
        else:
            avg_str = "N/A"
        
        self.stat_avg_size.config(text=avg_str)
        
        # Update recent downloads tree
        self.update_recent_downloads()
    
    def update_recent_downloads(self):
        """Update the recent downloads tree view"""
        # Clear existing items
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)
        
        # Add recent downloads (last 50)
        recent_downloads = self.download_history[-50:] if len(self.download_history) > 50 else self.download_history
        
        for download in reversed(recent_downloads):  # Most recent first
            self.recent_tree.insert("", "end", values=(
                download.get("timestamp", ""),
                download.get("filename", ""),
                download.get("size_formatted", ""),
                download.get("directory", "")
            ))
    
    def export_statistics(self):
        """Export statistics to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("Text files", "*.txt")],
                title="Export Statistics",
                initialname=f"download_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            
            if filename:
                stats_data = {
                    "export_time": datetime.now().isoformat(),
                    "session_statistics": self.statistics,
                    "download_history": self.download_history,
                    "settings": {
                        "min_file_size": self.min_file_size.get(),
                        "monitored_paths": self.monitor_path.get().split(',')
                    }
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(stats_data, f, indent=2, ensure_ascii=False)
                
                self.show_status(f"Statistics exported: {os.path.basename(filename)}", "success", 3000)
                
        except Exception as e:
            self.show_status(f"Export failed: {e}", "error", 3000)
    
    def clear_statistics(self):
        """Clear statistics and download history"""
        if messagebox.askyesno("Clear Statistics", 
                              "Are you sure you want to clear all statistics and download history?"):
            self.statistics = {
                "total_downloads": 0,
                "total_size": 0,
                "session_start": time.time()
            }
            self.download_history.clear()
            self.update_statistics_display()
            self.show_status("Statistics cleared", "info", 2000)
    
    def reset_settings(self):
        """Reset all settings to defaults"""
        if messagebox.askyesno("Reset Settings", 
                              "Are you sure you want to reset all settings to defaults?"):
            self.notification_sound_enabled.set(True)
            self.notification_popup_enabled.set(True)
            self.min_file_size.set(MIN_FILE_SIZE_MB)
            self.auto_clear_log.set(False)
            self.show_file_details.set(True)
            self.current_theme = "light"
            self.theme_var.set("light")
            self.apply_theme()
            self.show_status("Settings reset to defaults", "success", 2000)

    def _apply_theme(self, theme_colors):
        """Applies the specified theme colors to the widgets."""
        # The root window (self.master) only supports 'bg' for background
        self.master.config(bg=theme_colors["bg"])

        for widget in self.themable_widgets:
            # Skip the root window as it's handled above
            if widget == self.master:
                continue

            if isinstance(widget, tk.Text):
                widget.config(bg=theme_colors["text_bg"], fg=theme_colors["text_fg"])
                # Update tag colors for log text
                widget.tag_config("download", foreground="blue")
                widget.tag_config("error", foreground="red")
                widget.tag_config("info", foreground="grey")
            elif isinstance(widget, tk.Entry):
                widget.config(bg=theme_colors["entry_bg"], fg=theme_colors["entry_fg"], insertbackground=theme_colors["fg"])
            elif isinstance(widget, tk.Button):
                # Specific button colors from theme
                if widget == self.start_button:
                    widget.config(bg=theme_colors["button_bg"], fg=theme_colors["button_fg"])
                elif widget == self.stop_button:
                    widget.config(bg=theme_colors["stop_button_bg"], fg=theme_colors["stop_button_fg"])
                elif widget == self.browse_button:
                    widget.config(bg=theme_colors["browse_button_bg"], fg=theme_colors["browse_button_fg"])
                elif widget == self.stop_alarm_button:
                    widget.config(bg=theme_colors["stop_alarm_button_bg"], fg=theme_colors["stop_alarm_button_fg"])
                elif widget in [self.clear_log_button, self.save_log_button]:
                    widget.config(bg=theme_colors["browse_button_bg"], fg=theme_colors["browse_button_fg"])
            elif isinstance(widget, tk.Label):
                # Apply foreground based on label type
                if widget == self.about_link_label:
                    widget.config(bg=theme_colors["bg"], fg=theme_colors["about_link_fg"])
                    widget.config(font=self.footer_font) # Reset font to default (not underlined)
                else: # General labels (including app_title_label and path_frame labels)
                    widget.config(bg=theme_colors["bg"], fg=theme_colors["fg"])
            elif isinstance(widget, (tk.Frame, tk.LabelFrame)):
                widget.config(bg=theme_colors["bg"])
            elif isinstance(widget, (tk.Checkbutton, tk.Spinbox)):
                widget.config(bg=theme_colors["bg"], fg=theme_colors["fg"])

    def _browse_directory(self):
        """Opens a directory selection dialog."""
        selected_dir = filedialog.askdirectory(initialdir=self.monitor_path.get())
        if selected_dir:
            # If there are already paths, add the new one with comma separation
            current_paths = self.monitor_path.get()
            if current_paths and current_paths.strip():
                self.monitor_path.set(f"{current_paths}, {selected_dir}")
            else:
                self.monitor_path.set(selected_dir)

    def _clear_log(self):
        """Clears the activity log."""
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")
        self._log_message("Log cleared", "info")

    def _save_log(self):
        """Saves the activity log to a file."""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Activity Log"
            )
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    log_content = self.log_text.get(1.0, tk.END)
                    f.write(log_content)
                self._log_message(f"Log saved to: {filename}", "info")
                messagebox.showinfo("Success", f"Log saved successfully to:\n{filename}")
        except Exception as e:
            self._log_message(f"Error saving log: {e}", "error")
            messagebox.showerror("Error", f"Failed to save log:\n{e}")

    def start_monitoring(self):
        """Starts monitoring the selected directory using SizeAwareDownloadHandler."""
        paths_to_monitor_str = self.monitor_path.get()
        # Split by comma and clean up whitespace, filter out empty strings
        paths = [p.strip() for p in paths_to_monitor_str.split(',') if p.strip()]

        if not paths:
            messagebox.showerror("Error", "No directories specified for monitoring.")
            return

        if self.is_monitoring:
            self.update_status("Already monitoring.")
            return

        # Update global MIN_FILE_SIZE_MB from settings
        global MIN_FILE_SIZE_MB
        MIN_FILE_SIZE_MB = self.min_file_size.get()

        # Use the new size-aware handler
        self.event_handler = SizeAwareDownloadHandler(self)
        self.observers = [] # Reset list of observers
        monitoring_successful_paths = []

        for path_to_monitor in paths:
            if not os.path.isdir(path_to_monitor):
                self._log_message(f"Warning: Invalid directory path skipped: {path_to_monitor}", "error")
                continue
            try:
                # Changed recursive to True to monitor subdirectories
                observer = Observer()
                observer.schedule(self.event_handler, path_to_monitor, recursive=True)
                observer.start()
                self.observers.append(observer)
                monitoring_successful_paths.append(path_to_monitor)
            except Exception as e:
                self._log_message(f"Failed to start monitoring for {path_to_monitor}: {e}", "error")

        if monitoring_successful_paths:
            self.is_monitoring = True
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.update_status(f"Size-aware monitoring started for: {', '.join([os.path.basename(p) for p in monitoring_successful_paths])}")
            self._log_message(f"Size-aware monitoring started for: {', '.join(monitoring_successful_paths)}", "info")
        else:
            messagebox.showerror("Error", "No valid directories found to start monitoring.")
            self.update_status("Monitoring failed: No valid directories.")

    def stop_monitoring(self):
        """Stops monitoring the directory."""
        if not self.is_monitoring:
            self.update_status("Not currently monitoring.")
            return

        for observer in self.observers:
            observer.stop()
        for observer in self.observers:
            observer.join() # Wait for all observer threads to terminate
        self.observers = [] # Clear the list of observers

        if self.event_handler:
            self.event_handler.stop_processing() # Stop the download processing thread
            self.event_handler = None

        self.is_monitoring = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.update_status("Monitoring stopped.")
        self._log_message("Monitoring stopped.", "info")

    def stop_alarm(self):
        """Stops the currently playing alarm sound."""
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            self.stop_alarm_button.config(state="disabled")
            self.update_status("Alarm stopped.")
            self._log_message("Alarm manually stopped.", "info")
        else:
            self.update_status("No alarm is currently playing.")

    def update_status(self, message):
        """Updates the status label in the GUI."""
        self.master.after(0, lambda: self.status_label.config(text=message))

    def _log_message(self, message, tag=None):
        """Adds a message to the log text area."""
        self.master.after(0, lambda: self._insert_log_message(message, tag))

    def _insert_log_message(self, message, tag):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n", tag)
        self.log_text.see(tk.END) # Scroll to the end
        self.log_text.config(state="disabled")

    def notify_download_complete(self, file_path):
        """
        Triggers the notification (sound and GUI update) when a download is complete.
        This method is called from the DownloadHandler thread, so it uses master.after()
        to safely update the GUI. Includes file size in notification.
        """
        download_name = os.path.basename(file_path)
        try:
            file_size = os.path.getsize(file_path)
            size_mb = file_size / (1024 * 1024)
            
            if size_mb >= 1: # Use MB for files 1MB or larger
                size_str = f"{size_mb:.2f} MB"
            elif file_size >= 1024: # Use KB for files 1KB or larger
                size_kb = file_size / 1024
                size_str = f"{size_kb:.2f} KB"
            else: # Use bytes for smaller files
                size_str = f"{file_size:,} bytes"
                
            status_msg = f"Download Complete: {download_name} ({size_str})"
            notification_msg = f"File '{download_name}' has finished downloading!\n\nSize: {size_str}"
            
        except Exception as e:
            status_msg = f"Download Complete: {download_name}"
            notification_msg = f"File '{download_name}' has finished downloading! (Size unknown)"
            self._log_message(f"Could not get file size for notification: {e}", "error")
            
        self.master.after(0, lambda: self._show_notification_and_play_sound(download_name, notification_msg))
        self._log_message(status_msg, "download")

    def _play_alarm_sound(self):
        """Plays the alarm sound using pygame.mixer.music."""
        if not self.notification_sound_enabled.get():
            return
            
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init() # Ensure mixer is initialized in this thread if it wasn't already

            pygame.mixer.music.load(ALARM_SOUND_FILE)
            pygame.mixer.music.play()
            self.master.after(0, lambda: self.stop_alarm_button.config(state="normal")) # Enable stop button
            # Wait for sound to finish, then disable stop button
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            self.master.after(0, lambda: self.stop_alarm_button.config(state="disabled")) # Disable stop button
        except pygame.error as e:
            self._log_message(f"Error playing sound with Pygame in thread: {e}. Check if '{ALARM_SOUND_FILE}' exists and is a valid audio file.", "error")
        except Exception as e:
            self._log_message(f"An unexpected error occurred in sound thread: {e}", "error")

    def _show_notification_and_play_sound(self, download_name, notification_msg=None):
        """Helper to show notification and play sound on the main thread."""
        if not notification_msg:
            notification_msg = f"File '{download_name}' has finished downloading!"
            
        self.update_status(f"Download Complete: {download_name}!")

        # Start a new thread to play the alarm sound
        if self.notification_sound_enabled.get():
            sound_thread = threading.Thread(target=self._play_alarm_sound)
            sound_thread.daemon = True # Allow thread to exit with main app
            sound_thread.start()

        # Show the message box on the main thread (this will block until dismissed)
        if self.notification_popup_enabled.get():
            messagebox.showinfo("Download Complete", notification_msg)

    def _show_about(self):
        """Displays an about message box."""
        messagebox.showinfo(
            "About Download Notifier",
            "Version: 1.1.0 (Enhanced)\n"
            "Created by: Sandaru Gunathilake\n"
            "Enhanced by: AI Assistant\n\n"
            "This application monitors specified directories for completed downloads\n"
            "and notifies you with customizable alarms and pop-ups. Features include:\n\n"
            "• Size-aware download detection\n"
            "• Multiple directory monitoring\n"
            "• Configurable file size filtering\n"
            "• Activity logging with save/clear options\n"
            "• Customizable notifications\n"
            "• Enhanced temporary file detection\n"
            "• Processing timeout protection"
        )

    def _on_about_link_enter(self, event):
        """Changes about link appearance on mouse enter (light theme only)."""
        self.about_link_label.config(fg=LIGHT_THEME["about_link_fg"], font=(self.footer_font[0], self.footer_font[1], "underline"))

    def _on_about_link_leave(self, event):
        """Resets about link appearance on mouse leave (light theme only)."""
        self.about_link_label.config(fg=LIGHT_THEME["about_link_fg"], font=self.footer_font)

    def on_closing(self):
        """Handles graceful shutdown when the window is closed."""
        if self.is_monitoring:
            self.stop_monitoring()
        # Ensure any playing music is stopped before quitting mixer
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        # If pygame was initialized, it's good practice to quit all modules
        # However, pygame.mixer.quit() is often sufficient for most use cases
        # and pygame.quit() can sometimes cause issues if other modules were
        # not explicitly initialized. Let's stick to the mixer for now as that's all we use.
        # pygame.quit()
        self.master.destroy()

# --- Main Execution ---
if __name__ == "__main__":
    # Initialize Pygame mixer (must be done before loading any sounds)
    try:
        pygame.init()
        pygame.mixer.init()
    except Exception as e:
        print(f"Could not initialize Pygame mixer: {e}. Ensure necessary audio drivers are installed.")
        # Exit if mixer cannot be initialized, as sound won't work
        # This is a critical failure, so a hard exit is appropriate.
        exit()

    # Create a dummy alarm sound file if it doesn't exist for testing
    if not os.path.exists(ALARM_SOUND_FILE):
        try:
            # Note: Creating a dummy MP3 or WAV from scratch is complex.
            # This will just create an empty file. You MUST replace this
            # with an actual sound file for the alarm to work.
            with open(ALARM_SOUND_FILE, 'wb') as f:
                f.write(b'') # Create an empty file
            print(f"Created an empty dummy file '{ALARM_SOUND_FILE}'. Please replace it with a real .wav or .mp3 sound file.")
        except Exception as e:
            print(f"Could not create dummy alarm file: {e}. Please ensure '{ALARM_SOUND_FILE}' exists and is a .wav or .mp3 file.")

    root = tk.Tk()
    app = DownloadNotifierApp(root)
    root.mainloop()