# Download Notifier Pro v2.0.0

A powerful, intelligent download monitoring application with a modern interface that watches specified directories and provides smart notifications when downloads complete.

## 🌟 Key Features

### 🎯 Smart Download Detection
- **Size-aware detection** with expected file size comparison
- **Enhanced temporary file filtering** with 20+ temporary file patterns
- **Processing timeout protection** prevents infinite processing
- **Recursive directory monitoring** watches subdirectories automatically
- **Browser download support** for Chrome, Firefox, Edge, and more

### 🎨 Modern User Interface
- **Tabbed interface** with organized sections (Monitor, Activity, Statistics, Settings)
- **Dark/Light theme support** with instant switching
- **Responsive design** with resizable windows
- **Real-time status indicators** and progress feedback
- **Quick path buttons** for common directories
- **Custom notification dialogs** with themed styling

### 📊 Advanced Analytics
- **Session statistics** tracking downloads, sizes, and duration
- **Download history** with searchable recent downloads table
- **Export capabilities** (JSON, CSV, TXT formats)
- **Real-time activity logging** with filtering options
- **Automatic log management** with configurable auto-clear

### 🔔 Customizable Notifications
- **Toggle sound/popup** notifications independently
- **Test sound functionality** to verify audio setup
- **Custom notification dialogs** with file details
- **File size filtering** to reduce noise from small files
- **Enhanced sound alerts** with stop functionality

### ⚙️ Advanced Settings
- **Persistent settings** saved to JSON configuration
- **Multiple directory monitoring** with comma separation
- **Configurable file size thresholds** (0.1MB to 1000MB)
- **Detailed file information** toggle
- **Auto-clear log** when exceeding 1000 entries

## 🚀 Installation

### Quick Start (Windows)
1. **Automatic Setup**: Run `install.bat` for one-click installation
2. **Manual Setup**: Follow the steps below

### Manual Installation
1. **Requirements**: Python 3.7+ required
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run Application**:
   ```bash
   python download_notifier.py
   ```

### Dependencies
- `watchdog>=3.0.0` - File system monitoring
- `pygame>=2.5.2` - Audio playback
- `requests>=2.31.0` - HTTP utilities

## 📖 Usage Guide

### Getting Started
1. **Launch** the application
2. **Set directories** to monitor (use Browse or Quick Add buttons)
3. **Configure settings** in the Settings tab
4. **Start monitoring** and wait for download notifications

### Interface Overview

#### 📁 Monitor Tab
- **Directory Selection**: Add multiple paths separated by commas
- **Quick Add Buttons**: Instantly add Downloads, Desktop, Documents
- **Control Panel**: Start/stop monitoring with visual feedback
- **Real-time Status**: Live updates on monitoring activity

#### 📜 Activity Tab  
- **Live Activity Log**: Real-time download detection events
- **Log Filtering**: Filter by All, Downloads, Errors, Info
- **Export Options**: Save logs in multiple formats
- **Enhanced Formatting**: Color-coded entries with timestamps

#### 📊 Statistics Tab
- **Session Metrics**: Duration, total downloads, data transferred
- **Recent Downloads**: Sortable table of latest activity
- **Export Statistics**: Detailed analytics export
- **Visual Indicators**: Charts and progress displays

#### ⚙️ Settings Tab
- **Notification Controls**: Toggle sound and popup alerts
- **File Filtering**: Set minimum file size thresholds
- **Advanced Options**: Auto-clear logs, detailed info display
- **Theme Selection**: Switch between light and dark modes

### Keyboard Shortcuts
- `Ctrl+S` - Save settings
- `F5` - Refresh UI
- `Escape` - Close dialogs

## 🔧 Advanced Configuration

### Settings File
Settings are automatically saved to `settings.json`:
```json
{
  "sound_enabled": true,
  "popup_enabled": true,
  "min_file_size": 1.0,
  "auto_clear_log": false,
  "show_file_details": true,
  "monitor_paths": "C:\\Users\\User\\Downloads",
  "theme": "light",
  "window_geometry": "900x700+100+100"
}
```

### Supported File Sources
- **Browser Downloads**: Chrome (.crdownload), Firefox (.part), Edge
- **Download Managers**: IDM, uTorrent, BitTorrent
- **Cloud Services**: Dropbox, OneDrive, Google Drive sync
- **Telegram Desktop**: Experimental support for Telegram downloads
- **Direct Downloads**: Any application saving to monitored folders

### Temporary File Patterns
The app intelligently ignores these temporary extensions:
```
.tmp, .crdownload, .part, .download, .filepart, .downloading, 
.temp, .partial, .resume, .unconfirmed, .opdownload, .!ut,
.td, .crswap, .swp, .lock, .~
```

## 📈 Performance & Optimization

### System Requirements
- **RAM**: 50-100MB typical usage
- **CPU**: Minimal impact, event-driven monitoring
- **Storage**: <10MB application + logs
- **Network**: Only for HTTP HEAD requests (optional)

### Performance Tips
- Monitor specific subdirectories rather than entire drives
- Adjust file size threshold to reduce processing overhead
- Enable auto-clear logs for long-running sessions
- Use SSD storage for faster file detection

## 🎨 Themes & Customization

### Built-in Themes
- **Light Theme**: Clean, professional appearance
- **Dark Theme**: Reduced eye strain for extended use
- **Auto Theme Detection**: Respects system preferences

### Custom Styling
Themes are defined in the source code and can be customized:
```python
CUSTOM_THEME = {
    "bg": "#your_background_color",
    "fg": "#your_text_color", 
    "accent": "#your_accent_color",
    # ... more options
}
```

## 🔍 Troubleshooting

### Common Issues

**"No module named 'watchdog'"**
```bash
pip install watchdog pygame requests
```

**Sound not playing**
- Ensure `alarm.wav` exists (auto-generated if missing)
- Check system audio settings
- Test with "Test Sound" button

**Files not detected**
- Verify directory paths exist and are accessible
- Check file size meets minimum threshold
- Ensure files aren't matched by temporary patterns

**High CPU usage**
- Reduce monitored directory scope
- Increase minimum file size threshold
- Check for recursive symlinks

### Debug Mode
Run with verbose output:
```bash
python download_notifier.py --debug
```

### Log Analysis
Check `settings.json` and exported logs for detailed diagnostics.

## 🚀 What's New in v2.0.0

### Major Enhancements
- **Complete UI Redesign**: Modern tabbed interface with dark/light themes
- **Advanced Statistics**: Comprehensive download analytics and history
- **Enhanced Notifications**: Custom dialogs with detailed information
- **Persistent Settings**: Auto-save configuration and window state
- **Export Capabilities**: Multiple format support (JSON, CSV, TXT)
- **Performance Improvements**: Optimized file detection algorithms
- **Better Error Handling**: Graceful failure recovery and user feedback

### Technical Improvements
- **Thread Safety**: Improved multi-threading for UI responsiveness
- **Memory Management**: Better resource cleanup and optimization
- **Code Architecture**: Modular design with enhanced maintainability
- **Testing Framework**: Comprehensive dependency validation

## 🤝 Contributing

This project welcomes contributions! Areas for improvement:
- Additional theme support
- Plugin architecture for custom handlers
- Advanced filtering rules
- Integration with cloud services
- Mobile companion app
- System tray integration

## 📄 License

Open source software - free to use, modify, and distribute.

## 👥 Credits

- **Original Creator**: Sandaru Gunathilake
- **Enhanced Version**: AI Assistant collaboration
- **Community**: Thanks to all users providing feedback

## 🔗 Links

- **GitHub Repository**: [Download-Notifier-App](https://github.com/RensithUdara/Download-Notifer-App)
- **Issue Tracker**: Report bugs and request features
- **Discussions**: Share tips and configurations

---

**Download Notifier Pro** - Making download monitoring intelligent and beautiful! 🚀
