# Download Notifier - Enhanced Version

An intelligent download monitoring application that watches specified directories and notifies you when downloads are complete.

## Features

### Core Functionality
- **Smart Download Detection**: Uses size-aware detection to accurately identify completed downloads
- **Multiple Directory Monitoring**: Monitor multiple folders simultaneously 
- **Recursive Monitoring**: Watches subdirectories for downloads
- **Enhanced Temporary File Detection**: Improved filtering of temporary/incomplete files

### User Interface
- **Modern GUI**: Clean, resizable interface with organized settings
- **Activity Log**: Real-time logging with save/clear functionality
- **Customizable Notifications**: Toggle sound and popup notifications independently
- **File Size Filtering**: Set minimum file size threshold for notifications

### Advanced Features
- **Processing Timeout Protection**: Prevents indefinite processing of problematic files
- **Progress Tracking**: Shows download progress when expected file size is known
- **Companion File Detection**: Attempts to read expected file sizes from metadata files
- **Telegram Download Support**: Experimental support for Telegram downloads

## Installation

### Automatic Installation (Windows)
1. Run `install.bat` to automatically install dependencies

### Manual Installation
1. Ensure Python 3.7+ is installed
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Run the application**:
   ```bash
   python download_notifier.py
   ```

2. **Configure settings**:
   - Set directories to monitor (comma-separated for multiple)
   - Adjust minimum file size threshold
   - Enable/disable sound and popup notifications

3. **Start monitoring**:
   - Click "Start Monitoring"
   - The app will watch for completed downloads in real-time

4. **Manage logs**:
   - View activity in the log panel
   - Save logs to file for record keeping
   - Clear logs as needed

## Configuration

### Default Settings
- **Default Directory**: User's Downloads folder
- **Minimum File Size**: 1 MB
- **Processing Timeout**: 5 minutes
- **Sound/Popup**: Both enabled by default

### Supported File Sources
- Browser downloads (Chrome, Firefox, Edge, etc.)
- Direct downloads
- Telegram Desktop (experimental)
- Any application that saves files to monitored directories

## Supported Temporary File Extensions
The app automatically ignores common temporary file extensions:
- `.tmp`, `.crdownload`, `.part`, `.download`
- `.filepart`, `.downloading`, `.partial`
- `.unconfirmed`, `.opdownload`
- And many more...

## Requirements
- Python 3.7+
- watchdog 3.0.0+
- pygame 2.5.2+
- requests 2.31.0+

## Version History
- **v1.1.0**: Enhanced version with improved detection, settings panel, and logging
- **v1.0.0**: Original version by Sandaru Gunathilake

## License
Open source - feel free to modify and distribute.

## Troubleshooting

### Common Issues
1. **"No module named 'watchdog'"**: Run `pip install -r requirements.txt`
2. **No sound playing**: Ensure `alarm.wav` exists and pygame is properly installed
3. **Files not detected**: Check that directories exist and are accessible

### Performance Tips
- Avoid monitoring very large directories with thousands of files
- Adjust minimum file size to reduce unnecessary processing
- Use specific subdirectories rather than entire drives

## Contributing
This is an enhanced version of the original Download Notifier. Improvements include:
- Better error handling and logging
- Enhanced GUI with more features
- Improved file detection algorithms
- Better cross-platform compatibility
