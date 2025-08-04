#!/usr/bin/env python3
"""
Test script to validate all dependencies for Download Notifier
"""
import sys

def test_imports():
    """Test all required imports"""
    print("Testing Download Notifier dependencies...\n")
    
    # Test basic imports
    try:
        import tkinter as tk
        print("✓ tkinter - GUI framework")
    except ImportError as e:
        print(f"✗ tkinter - {e}")
        return False
    
    try:
        from tkinter import filedialog, messagebox, ttk
        print("✓ tkinter components - File dialogs and message boxes")
    except ImportError as e:
        print(f"✗ tkinter components - {e}")
        return False
    
    try:
        import os, time, threading
        print("✓ os, time, threading - System utilities")
    except ImportError as e:
        print(f"✗ System utilities - {e}")
        return False
    
    # Test watchdog
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        print("✓ watchdog - File system monitoring")
    except ImportError as e:
        print(f"✗ watchdog - {e}")
        return False
    
    # Test pygame
    try:
        import pygame
        pygame.mixer.init()
        print("✓ pygame - Audio playback")
    except ImportError as e:
        print(f"✗ pygame - {e}")
        return False
    except Exception as e:
        print(f"✓ pygame imported (audio init warning: {e})")
    
    # Test requests
    try:
        import requests
        print("✓ requests - HTTP client")
    except ImportError as e:
        print(f"✗ requests - {e}")
        return False
    
    # Test other dependencies
    try:
        import json, re, sqlite3, sys
        from urllib.parse import urlparse
        from pathlib import Path
        print("✓ json, re, sqlite3, urllib, pathlib - Utility modules")
    except ImportError as e:
        print(f"✗ Utility modules - {e}")
        return False
    
    return True

def test_basic_functionality():
    """Test basic functionality"""
    print("\nTesting basic functionality...")
    
    # Test file operations
    try:
        import os
        import tempfile
        
        # Test file creation and detection
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test data")
            tmp_path = tmp.name
        
        if os.path.exists(tmp_path):
            print("✓ File operations working")
            os.unlink(tmp_path)
        else:
            print("✗ File operations failed")
            return False
            
    except Exception as e:
        print(f"✗ File operations error: {e}")
        return False
    
    # Test watchdog basic functionality
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        
        class TestHandler(FileSystemEventHandler):
            def __init__(self):
                self.events = []
            
            def on_created(self, event):
                self.events.append(event)
        
        # Test observer creation (don't actually start it)
        observer = Observer()
        handler = TestHandler()
        print("✓ Watchdog observer creation working")
        
    except Exception as e:
        print(f"✗ Watchdog functionality error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Download Notifier Dependency Test")
    print("=" * 40)
    
    success = True
    
    # Test imports
    if not test_imports():
        success = False
    
    # Test functionality
    if not test_basic_functionality():
        success = False
    
    print("\n" + "=" * 40)
    if success:
        print("✓ ALL TESTS PASSED! Download Notifier should work correctly.")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED! Please install missing dependencies.")
        print("\nTo install missing dependencies, run:")
        print("pip install -r requirements.txt")
        sys.exit(1)
