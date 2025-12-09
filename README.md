# 🔥 BurnBin - Easy File Sharing

A simple, user-friendly Python application that allows you to share files online with public links using Cloudflare Tunnel. 

Note: This project uses a dual-license model. Feel free to check out the code here, or [donate ($1+) to download a built binary from Itch.io](https://mikethetech.itch.io/burnbin). :)

## Features

- 🎯 **Easy to Use**: Simple GUI designed for novice users
- 🌐 **Public Links**: Automatically creates public URLs via Cloudflare Tunnel
- 📊 **Progress Tracking**: See when files are accessed and downloaded
- 📁 **Multiple Files**: Share as many files as you want, each with a unique URL
- 🔒 **Secure**: Uses Cloudflare's secure tunnel infrastructure
- 💻 **Cross-Platform**: Works on Windows, macOS, and Linux

## Prerequisites

1. **Python 3.7 or higher** - [Download Python](https://www.python.org/downloads/)

2. **Cloudflare Tunnel (cloudflared)** - Required for creating public links
   - **Windows**: Download from [Cloudflare Releases](https://github.com/cloudflare/cloudflared/releases) and add to PATH, or use:
     ```powershell
     winget install --id Cloudflare.cloudflared
     ```
   - **macOS**: 
     ```bash
     brew install cloudflared
     ```
   - **Linux**: 
     ```bash
     # Debian/Ubuntu
     wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
     sudo dpkg -i cloudflared-linux-amd64.deb
     
     # Or using package manager
     sudo apt-get install cloudflared
     ```

## Installation

### Option 1: Run from Source

1. **Clone or download this repository**

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify cloudflared is installed**:
   ```bash
   cloudflared --version
   ```

4. **Run the application**:
   ```bash
   python main.py
   ```
   Or double-click `run.bat` on Windows

### Option 2: Build Standalone Executable

1. **Install build dependencies**:
   ```bash
   pip install pyinstaller
   ```

2. **Build the executable**:
   ```bash
   build_exe.bat
   ```
   Or manually:
   ```bash
   pyinstaller BurnBin.spec
   ```

3. **Find your executable**:
   - Location: `dist\BurnBin.exe`
   - The executable includes all Python dependencies
   - **Note**: Users still need `cloudflared` installed on their system

## Usage

1. **Run the application**:
   - **From source**: `python main.py` or double-click `run.bat`
   - **From executable**: Double-click `BurnBin.exe`

2. **Share a file**:
   - Click "Browse..." to select a file
   - Click "Share File" to make it available online
   - Wait for the Cloudflare Tunnel to establish (usually takes 5-10 seconds)
   - Your public URL will appear in the status section

3. **Get the download link**:
   - Double-click any file in the "Shared Files" list to copy its download link
   - Or copy the public URL and append `/download/<file-id>`

4. **Monitor activity**:
   - Watch the "Download Activity" section to see when files are accessed
   - See download counts for each shared file

5. **Upload files** (users can upload back to you):
   - Users visit your public URL
   - They can upload files using the upload form
   - View uploaded files in the "Uploads" tab

6. **Remove files**:
   - Select a file in the list and click "Remove Selected File"

## How It Works

1. **Local Server**: The app runs a local HTTP server on port 5000
2. **Cloudflare Tunnel**: Creates a secure tunnel from Cloudflare's servers to your local server
3. **Public Access**: Anyone with the link can download your files
4. **Progress Tracking**: The app tracks when files are accessed and downloaded

## Troubleshooting

### "cloudflared not found" Error

- Make sure cloudflared is installed and accessible from your command line
- Verify installation: `cloudflared --version`
- Add cloudflared to your system PATH if needed

### Tunnel Not Starting

- Check your internet connection
- Ensure port 5000 is not already in use
- Try restarting the application

### Files Not Downloading

- Verify the file still exists at the original location
- Check that the tunnel is active (green status indicator)
- Ensure the public URL is accessible

## Security Notes

- Files are served directly from your computer while the app is running
- Remove files from sharing when you no longer want them accessible
- Close the application to stop serving files
- Cloudflare Tunnel provides secure HTTPS connections

## Licensing

This project uses a dual-license model:

### Source Code License (Open Source)
The source code in this repository is licensed under the **MIT License**
and is jointly owned by **PyroSoft Productions and Playcast.io**.

You are free to view, modify, fork, and build the software from source under
the terms of the MIT License.

### Compiled Binary License (Commercial)
Official builds, installers, and distributed binaries are licensed
separately under the **PyroSoft Productions Commercial License**.

See `COMMERCIAL_LICENSE.txt` for full terms.

## Support

For issues or questions:
1. Check that cloudflared is properly installed
2. Verify Python dependencies are installed
3. Ensure your firewall allows the application to run

