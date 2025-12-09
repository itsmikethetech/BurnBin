import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import subprocess
import os
import sys
import time
import uuid
import json
from datetime import datetime
from flask import Flask, send_file, request, jsonify, Response
from werkzeug.utils import secure_filename

class FileShareApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BurnBin - Share Files Online")
        self.root.geometry("1000x700")
        self.root.minsize(900, 600)
        self.root.resizable(True, True)
        
        # Dark theme with orange highlights
        self.colors = {
            'bg_main': '#1a1a1a',
            'bg_header': '#2d2d2d',
            'bg_card': '#252525',
            'bg_button_primary': '#ff6b35',
            'bg_button_primary_hover': '#ff8555',
            'bg_button_success': '#ff6b35',
            'bg_button_success_hover': '#ff8555',
            'bg_button_danger': '#ff4444',
            'bg_button_danger_hover': '#ff6666',
            'text_primary': '#ffffff',
            'text_secondary': '#b0b0b0',
            'text_light': '#808080',
            'border': '#404040',
            'accent': '#ff6b35',
            'success': '#ff6b35',
            'warning': '#ffaa00',
            'error': '#ff4444'
        }
        
        # Initialize Flask app
        self.flask_app = Flask(__name__)
        self.setup_flask_routes()
        
        # Storage for shared files
        self.shared_files = {}  # {file_id: {path, name, size, upload_time, downloads}}
        self.download_sessions = {}  # {session_id: {file_id, start_time, progress, status}}
        self.uploaded_files = {}  # {file_id: {path, name, size, upload_time, uploader_ip}}
        
        # Create uploads directory
        # When running as PyInstaller executable, use directory next to exe
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_path = os.path.dirname(sys.executable)
        else:
            # Running as script
            base_path = os.getcwd()
        self.uploads_dir = os.path.join(base_path, "uploads")
        os.makedirs(self.uploads_dir, exist_ok=True)
        
        # Persistence file path
        self.shared_files_file = os.path.join(base_path, "shared_files.json")
        
        # Server state
        self.server_thread = None
        self.cloudflare_process = None
        self.server_running = False
        self.public_url = None
        self.local_port = 5000
        
        # Load persisted shared files
        self.load_shared_files()
        
        # Set root background
        self.root.configure(bg=self.colors['bg_main'])
        
        # Setup UI
        self.setup_ui()
        
        # Populate treeview with loaded shared files
        self.populate_files_treeview()
        
        # Start local server
        self.start_local_server()
    
    def setup_ui(self):
        
        # Modern header with gradient effect
        header_frame = tk.Frame(self.root, bg=self.colors['bg_header'], height=120)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        # Header content container
        header_content = tk.Frame(header_frame, bg=self.colors['bg_header'])
        header_content.pack(fill=tk.BOTH, expand=True, padx=30, pady=18)
        
        # Title with icon emoji
        title_container = tk.Frame(header_content, bg=self.colors['bg_header'])
        title_container.pack(anchor=tk.W)
        
        title_label = tk.Label(
            title_container,
            text="🔥 BurnBin",
            font=("Segoe UI", 28, "bold"),
            bg=self.colors['bg_header'],
            fg="#ff6b35"
        )
        title_label.pack(side=tk.LEFT)
        
        subtitle_label = tk.Label(
            header_content,
            text="Share files instantly with secure public links • PyroSoft Productions",
            font=("Segoe UI", 10),
            bg=self.colors['bg_header'],
            fg="#b0b0b0"
        )
        subtitle_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Website link
        website_label = tk.Label(
            header_content,
            text="https://pyrosoft.pro/",
            font=("Segoe UI", 9),
            bg=self.colors['bg_header'],
            fg="#ff6b35",
            cursor="hand2"
        )
        website_label.pack(anchor=tk.W, pady=(2, 0))
        website_label.bind("<Button-1>", lambda e: self.open_website())
        
        # Main container with tabs
        main_container = tk.Frame(self.root, bg=self.colors['bg_main'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Create notebook (tabs)
        style = ttk.Style()
        style.theme_use("clam")
        
        # Configure tab style for dark theme
        style.configure("TNotebook", background=self.colors['bg_main'], borderwidth=0)
        style.configure("TNotebook.Tab", 
                       padding=[20, 10],
                       font=("Segoe UI", 11, "bold"),
                       background='#2d2d2d',
                       foreground=self.colors['text_secondary'])
        # Configure selected tab with larger padding
        style.configure("TNotebook.Tab",
                       padding=[20, 10])
        style.map("TNotebook.Tab",
                 background=[("selected", self.colors['bg_card'])],
                 foreground=[("selected", self.colors['accent'])],
                 padding=[("selected", [24, 12]), ("!selected", [18, 8])])
        
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Tab 1: Share (Add files + Status)
        self.share_tab = tk.Frame(self.notebook, bg=self.colors['bg_main'], padx=25, pady=25)
        self.notebook.add(self.share_tab, text="🔥 Share")
        self.setup_share_tab()
        
        # Tab 2: Files (Shared files list)
        self.files_tab = tk.Frame(self.notebook, bg=self.colors['bg_main'], padx=25, pady=25)
        self.notebook.add(self.files_tab, text="🔥 Files")
        self.setup_files_tab()
        
        # Tab 3: Uploads (Files uploaded by users)
        self.uploads_tab = tk.Frame(self.notebook, bg=self.colors['bg_main'], padx=25, pady=25)
        self.notebook.add(self.uploads_tab, text="🔥 Uploads")
        self.setup_uploads_tab()
        
        # Tab 4: Activity (Download activity log)
        self.activity_tab = tk.Frame(self.notebook, bg=self.colors['bg_main'], padx=25, pady=25)
        self.notebook.add(self.activity_tab, text="🔥 Activity")
        self.setup_activity_tab()
        
        # Start update loop
        self.update_status()
    
    def setup_share_tab(self):
        """Setup the Share tab with file upload and status"""
        # Add file section - Modern card design
        add_file_card = tk.Frame(
            self.share_tab,
            bg=self.colors['bg_card'],
            relief=tk.FLAT,
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        add_file_card.pack(fill=tk.X, pady=(0, 20))
        
        # Card header
        card_header = tk.Frame(add_file_card, bg=self.colors['bg_card'])
        card_header.pack(fill=tk.X, padx=20, pady=(20, 15))
        
        card_title = tk.Label(
            card_header,
            text="🔥 Add File to Share",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors['bg_card'],
            fg=self.colors['text_primary']
        )
        card_title.pack(anchor=tk.W)
        
        # File selection area
        file_selection_frame = tk.Frame(add_file_card, bg=self.colors['bg_card'])
        file_selection_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # File path input with modern styling
        input_container = tk.Frame(file_selection_frame, bg=self.colors['bg_card'])
        input_container.pack(fill=tk.X, pady=(0, 12))
        
        self.file_path_var = tk.StringVar()
        file_entry = tk.Entry(
            input_container,
            textvariable=self.file_path_var,
            font=("Segoe UI", 11),
            state="readonly",
            relief=tk.FLAT,
            highlightbackground=self.colors['border'],
            highlightthickness=1,
            highlightcolor=self.colors['accent'],
            bg='#1a1a1a',
            fg=self.colors['text_primary'],
            insertbackground=self.colors['text_primary']
        )
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12), ipady=10)
        
        # Modern browse button
        browse_btn = tk.Button(
            input_container,
            text="🔥 Browse",
            command=self.browse_file,
            bg=self.colors['bg_button_primary'],
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=24,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors['bg_button_primary_hover'],
            activeforeground="white",
            borderwidth=0
        )
        browse_btn.pack(side=tk.RIGHT)
        
        # Share button - prominent CTA
        share_btn = tk.Button(
            file_selection_frame,
            text="🔥 Share File",
            command=self.share_file,
            bg=self.colors['bg_button_success'],
            fg="white",
            font=("Segoe UI", 12, "bold"),
            padx=40,
            pady=12,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors['bg_button_success_hover'],
            activeforeground="white",
            borderwidth=0
        )
        share_btn.pack(fill=tk.X)
        
        # Status section - Modern card with status indicators
        status_card = tk.Frame(
            self.share_tab,
            bg=self.colors['bg_card'],
            relief=tk.FLAT,
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        status_card.pack(fill=tk.X)
        
        status_header = tk.Frame(status_card, bg=self.colors['bg_card'])
        status_header.pack(fill=tk.X, padx=20, pady=(20, 15))
        
        status_title = tk.Label(
            status_header,
            text="🔥 Connection Status",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors['bg_card'],
            fg=self.colors['text_primary']
        )
        status_title.pack(anchor=tk.W)
        
        status_content = tk.Frame(status_card, bg=self.colors['bg_card'])
        status_content.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        self.status_label = tk.Label(
            status_content,
            text="⏳ Starting server...",
            font=("Segoe UI", 11),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_card'],
            anchor=tk.W
        )
        self.status_label.pack(fill=tk.X, pady=(0, 8))
        
        self.url_label = tk.Label(
            status_content,
            text="",
            font=("Segoe UI", 10),
            fg=self.colors['accent'],
            bg=self.colors['bg_card'],
            cursor="hand2",
            anchor=tk.W
        )
        self.url_label.bind("<Button-1>", lambda e: self.open_url())
        self.url_label.bind("<Enter>", lambda e: self.url_label.config(fg=self.colors['bg_button_primary_hover']))
        self.url_label.bind("<Leave>", lambda e: self.url_label.config(fg=self.colors['accent']))
        
        # Install cloudflared button (initially hidden)
        self.install_cloudflared_btn = tk.Button(
            status_content,
            text="🔥 Install Cloudflared",
            command=self.install_cloudflared,
            bg=self.colors['bg_button_primary'],
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=8,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors['bg_button_primary_hover'],
            activeforeground="white",
            borderwidth=0
        )
        # Don't pack initially - will be shown when needed
        
    
    def setup_files_tab(self):
        """Setup the Files tab with shared files list"""
        # Shared files section - Modern card
        files_card = tk.Frame(
            self.files_tab,
            bg=self.colors['bg_card'],
            relief=tk.FLAT,
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        files_card.pack(fill=tk.BOTH, expand=True)
        
        files_header = tk.Frame(files_card, bg=self.colors['bg_card'])
        files_header.pack(fill=tk.X, padx=20, pady=(20, 15))
        
        files_title = tk.Label(
            files_header,
            text="🔥 Shared Files",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors['bg_card'],
            fg=self.colors['text_primary']
        )
        files_title.pack(side=tk.LEFT)
        
        # Treeview container
        tree_container = tk.Frame(files_card, bg=self.colors['bg_card'])
        tree_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))
        
        # Configure modern treeview style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                       background=self.colors['bg_card'],
                       foreground=self.colors['text_primary'],
                       fieldbackground=self.colors['bg_card'],
                       borderwidth=0,
                       font=("Segoe UI", 10))
        style.configure("Treeview.Heading",
                       background='#2d2d2d',
                       foreground=self.colors['text_primary'],
                       font=("Segoe UI", 10, "bold"),
                       relief=tk.FLAT)
        style.map("Treeview",
                 background=[('selected', self.colors['accent'])],
                 foreground=[('selected', 'white')])
        
        # Treeview for files
        columns = ("File Name", "Size", "Status", "Downloads", "Link")
        self.files_tree = ttk.Treeview(tree_container, columns=columns, show="tree headings", height=15)
        self.files_tree.heading("#0", text="")
        self.files_tree.column("#0", width=20)
        
        for col in columns:
            self.files_tree.heading(col, text=col)
            if col == "File Name":
                self.files_tree.column(col, width=300)
            elif col == "Size":
                self.files_tree.column(col, width=120)
            elif col == "Status":
                self.files_tree.column(col, width=140)
            elif col == "Downloads":
                self.files_tree.column(col, width=100)
            else:
                self.files_tree.column(col, width=280)
        
        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=scrollbar.set)
        
        self.files_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click to copy link
        self.files_tree.bind("<Double-1>", self.copy_file_link)
        
        # Button container
        button_container = tk.Frame(files_card, bg=self.colors['bg_card'])
        button_container.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # Modern remove button
        remove_btn = tk.Button(
            button_container,
            text="🔥 Remove Selected",
            command=self.remove_file,
            bg=self.colors['bg_button_danger'],
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=24,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors['bg_button_danger_hover'],
            activeforeground="white",
            borderwidth=0
        )
        remove_btn.pack(side=tk.RIGHT)
    
    def setup_uploads_tab(self):
        """Setup the Uploads tab with files uploaded by users"""
        # Uploaded files section - Modern card
        uploads_card = tk.Frame(
            self.uploads_tab,
            bg=self.colors['bg_card'],
            relief=tk.FLAT,
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        uploads_card.pack(fill=tk.BOTH, expand=True)
        
        uploads_header = tk.Frame(uploads_card, bg=self.colors['bg_card'])
        uploads_header.pack(fill=tk.X, padx=20, pady=(20, 15))
        
        uploads_title = tk.Label(
            uploads_header,
            text="🔥 Uploaded Files",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors['bg_card'],
            fg=self.colors['text_primary']
        )
        uploads_title.pack(side=tk.LEFT)
        
        # Treeview container
        tree_container = tk.Frame(uploads_card, bg=self.colors['bg_card'])
        tree_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))
        
        # Configure modern treeview style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Uploads.Treeview",
                       background=self.colors['bg_card'],
                       foreground=self.colors['text_primary'],
                       fieldbackground=self.colors['bg_card'],
                       borderwidth=0,
                       font=("Segoe UI", 10))
        style.configure("Uploads.Treeview.Heading",
                       background='#2d2d2d',
                       foreground=self.colors['text_primary'],
                       font=("Segoe UI", 10, "bold"),
                       relief=tk.FLAT)
        style.map("Uploads.Treeview",
                 background=[('selected', self.colors['accent'])],
                 foreground=[('selected', 'white')])
        
        # Treeview for uploaded files
        columns = ("File Name", "Size", "Upload Time", "From IP")
        self.uploads_tree = ttk.Treeview(tree_container, columns=columns, show="tree headings", height=15, style="Uploads.Treeview")
        self.uploads_tree.heading("#0", text="")
        self.uploads_tree.column("#0", width=20)
        
        for col in columns:
            self.uploads_tree.heading(col, text=col)
            if col == "File Name":
                self.uploads_tree.column(col, width=300)
            elif col == "Size":
                self.uploads_tree.column(col, width=120)
            elif col == "Upload Time":
                self.uploads_tree.column(col, width=180)
            else:
                self.uploads_tree.column(col, width=150)
        
        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.uploads_tree.yview)
        self.uploads_tree.configure(yscrollcommand=scrollbar.set)
        
        self.uploads_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click to download
        self.uploads_tree.bind("<Double-1>", self.download_uploaded_file)
        
        # Button container
        button_container = tk.Frame(uploads_card, bg=self.colors['bg_card'])
        button_container.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # Download button
        download_btn = tk.Button(
            button_container,
            text="🔥 Download Selected",
            command=self.download_selected_upload,
            bg=self.colors['bg_button_success'],
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=24,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors['bg_button_success_hover'],
            activeforeground="white",
            borderwidth=0
        )
        download_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Share button
        share_upload_btn = tk.Button(
            button_container,
            text="🔥 Share Selected",
            command=self.share_uploaded_file,
            bg=self.colors['bg_button_primary'],
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=24,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors['bg_button_primary_hover'],
            activeforeground="white",
            borderwidth=0
        )
        share_upload_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Remove button
        remove_upload_btn = tk.Button(
            button_container,
            text="🔥 Remove Selected",
            command=self.remove_uploaded_file,
            bg=self.colors['bg_button_danger'],
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=24,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors['bg_button_danger_hover'],
            activeforeground="white",
            borderwidth=0
        )
        remove_upload_btn.pack(side=tk.RIGHT)
    
    def setup_activity_tab(self):
        """Setup the Activity tab with download activity log"""
        # Download activity section - Modern card
        activity_card = tk.Frame(
            self.activity_tab,
            bg=self.colors['bg_card'],
            relief=tk.FLAT,
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        activity_card.pack(fill=tk.BOTH, expand=True)
        
        activity_header = tk.Frame(activity_card, bg=self.colors['bg_card'])
        activity_header.pack(fill=tk.X, padx=20, pady=(20, 15))
        
        activity_title = tk.Label(
            activity_header,
            text="🔥 Download Activity",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors['bg_card'],
            fg=self.colors['text_primary']
        )
        activity_title.pack(anchor=tk.W)
        
        activity_content = tk.Frame(activity_card, bg=self.colors['bg_card'])
        activity_content.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Modern text widget with styling
        self.activity_text = tk.Text(
            activity_content,
            font=("Consolas", 9),
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg='#1a1a1a',
            fg=self.colors['text_primary'],
            relief=tk.FLAT,
            highlightbackground=self.colors['border'],
            highlightthickness=1,
            padx=12,
            pady=12
        )
        self.activity_text.pack(fill=tk.BOTH, expand=True)
    
    def get_client_ip(self, request):
        """Get the real client IP address, handling proxies and Cloudflare Tunnel"""
        # Check X-Forwarded-For header (most common for proxies)
        if request.headers.get('X-Forwarded-For'):
            # X-Forwarded-For can contain multiple IPs, take the first one
            ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
            if ip:
                return ip
        
        # Check X-Real-IP header
        if request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        
        # Check CF-Connecting-IP (Cloudflare specific)
        if request.headers.get('CF-Connecting-IP'):
            return request.headers.get('CF-Connecting-IP')
        
        # Fall back to remote_addr
        return request.remote_addr
    
    def setup_flask_routes(self):
        # Define HTML template once
        html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>BurnBin - File Sharing</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    * { margin: 0; padding: 0; box-sizing: border-box; }
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                        background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
                        min-height: 100vh;
                        padding: 20px;
                    }
                    .container {
                        max-width: 800px;
                        margin: 0 auto;
                        background: #252525;
                        border-radius: 15px;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.5);
                        padding: 40px;
                        border: 1px solid #404040;
                    }
                    h1 {
                        color: #ff6b35;
                        margin-bottom: 10px;
                        font-size: 2.5em;
                    }
                    .subtitle {
                        color: #b0b0b0;
                        margin-bottom: 30px;
                        font-size: 1.1em;
                    }
                    .file-list {
                        list-style: none;
                    }
                    .file-item {
                        background: #2d2d2d;
                        border-radius: 10px;
                        padding: 20px;
                        margin-bottom: 15px;
                        border-left: 4px solid #ff6b35;
                        transition: transform 0.2s, box-shadow 0.2s;
                    }
                    .file-item:hover {
                        transform: translateY(-2px);
                        box-shadow: 0 5px 15px rgba(255, 107, 53, 0.3);
                    }
                    .file-name {
                        font-size: 1.3em;
                        font-weight: bold;
                        color: #ffffff;
                        margin-bottom: 8px;
                    }
                    .file-info {
                        color: #b0b0b0;
                        font-size: 0.9em;
                        margin-bottom: 15px;
                    }
                    .download-btn {
                        background: linear-gradient(135deg, #ff6b35 0%, #ff8555 100%);
                        color: white;
                        border: none;
                        padding: 12px 30px;
                        border-radius: 25px;
                        font-size: 1em;
                        font-weight: bold;
                        cursor: pointer;
                        text-decoration: none;
                        display: inline-block;
                        transition: transform 0.2s, box-shadow 0.2s;
                    }
                    .download-btn:hover {
                        transform: scale(1.05);
                        box-shadow: 0 5px 20px rgba(255, 107, 53, 0.5);
                    }
                    .progress-container {
                        margin-top: 15px;
                        display: none;
                    }
                    .progress-bar {
                        width: 100%;
                        height: 25px;
                        background: #1a1a1a;
                        border-radius: 12px;
                        overflow: hidden;
                        margin-bottom: 5px;
                    }
                    .progress-fill {
                        height: 100%;
                        background: linear-gradient(90deg, #ff6b35 0%, #ff8555 100%);
                        width: 0%;
                        transition: width 0.3s;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-size: 0.85em;
                        font-weight: bold;
                    }
                    .progress-text {
                        text-align: center;
                        color: #b0b0b0;
                        font-size: 0.9em;
                    }
                    .empty-state {
                        text-align: center;
                        padding: 60px 20px;
                        color: #808080;
                    }
                    .empty-state-icon {
                        font-size: 4em;
                        margin-bottom: 20px;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🔥 BurnBin</h1>
                    <p class="subtitle">Download files or upload files to the host • PyroSoft Productions</p>
                    
                    <!-- Download Section -->
                    <h2 style="color: #ff6b35; margin-bottom: 15px; font-size: 1.3em;">🔥 Download Files</h2>
                    <ul class="file-list" id="fileList">
                        <!-- Files will be inserted here -->
                    </ul>
                    
                    <!-- Upload Section -->
                    <div style="background: #2d2d2d; border-radius: 10px; padding: 20px; margin-top: 30px; border-left: 4px solid #ff6b35;">
                        <h2 style="color: #ff6b35; margin-bottom: 15px; font-size: 1.3em;">🔥 Upload File to Host</h2>
                        <form id="uploadForm" enctype="multipart/form-data">
                            <input type="file" id="fileInput" name="file" required 
                                   style="width: 100%; padding: 10px; background: #1a1a1a; border: 1px solid #404040; border-radius: 5px; color: #ffffff; margin-bottom: 15px;">
                            <button type="submit" 
                                    style="background: linear-gradient(135deg, #ff6b35 0%, #ff8555 100%); color: white; border: none; padding: 12px 30px; border-radius: 25px; font-size: 1em; font-weight: bold; cursor: pointer; width: 100%;">
                                🔥 Upload File
                            </button>
                        </form>
                        <div id="uploadStatus" style="margin-top: 15px; color: #b0b0b0; display: none;"></div>
                        <div class="progress-container" id="uploadProgress" style="display: none;">
                            <div class="progress-bar">
                                <div class="progress-fill" id="uploadProgressFill">0%</div>
                            </div>
                            <div class="progress-text" id="uploadProgressText">Preparing upload...</div>
                        </div>
                    </div>
                </div>
                <script>
                    function updateFileList() {
                        fetch('/api/files')
                            .then(r => r.json())
                            .then(data => {
                                const list = document.getElementById('fileList');
                                if (data.files.length === 0) {
                                    list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><p>No files available for download</p></div>';
                                    return;
                                }
                                list.innerHTML = data.files.map(file => `
                                    <li class="file-item">
                                        <div class="file-name">${file.name}</div>
                                        <div class="file-info">Size: ${file.size} | Added: ${file.upload_time}</div>
                                        <button class="download-btn" id="download-btn-${file.id}" onclick="trackDownload('${file.id}', event);">
                                            Download File
                                        </button>
                                        <div class="progress-container" id="progress-${file.id}">
                                            <div class="progress-bar">
                                                <div class="progress-fill" id="progress-fill-${file.id}">0%</div>
                                            </div>
                                            <div class="progress-text" id="progress-text-${file.id}">Preparing download...</div>
                                        </div>
                                    </li>
                                `).join('');
                            });
                    }
                    
                    // Track active downloads and intervals to prevent duplicates
                    const activeDownloads = {};
                    
                    function trackDownload(fileId, event) {
                        // Prevent default if event exists
                        if (event) {
                            event.preventDefault();
                            event.stopPropagation();
                        }
                        
                        // Prevent multiple simultaneous downloads
                        if (activeDownloads[fileId]) {
                            return;
                        }
                        
                        const progressContainer = document.getElementById('progress-' + fileId);
                        const progressFill = document.getElementById('progress-fill-' + fileId);
                        const progressText = document.getElementById('progress-text-' + fileId);
                        const downloadBtn = document.getElementById('download-btn-' + fileId);
                        
                        if (progressContainer) {
                            progressContainer.style.display = 'block';
                        }
                        
                        // Disable button to prevent multiple clicks
                        if (downloadBtn) {
                            downloadBtn.disabled = true;
                            downloadBtn.style.opacity = '0.6';
                            downloadBtn.style.cursor = 'not-allowed';
                        }
                        
                        // Mark as active
                        activeDownloads[fileId] = true;
                        
                        // Track download click
                        fetch('/api/track-download', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({file_id: fileId})
                        });
                        
                        // Create session first, then start download
                        fetch('/api/start-download/' + fileId)
                            .then(r => r.json())
                            .then(data => {
                                if (data.error) {
                                    delete activeDownloads[fileId];
                                    if (downloadBtn) {
                                        downloadBtn.disabled = false;
                                        downloadBtn.style.opacity = '1';
                                        downloadBtn.style.cursor = 'pointer';
                                    }
                                    if (progressText) {
                                        progressText.textContent = 'Error: ' + data.error;
                                        progressText.style.color = '#ff4444';
                                    }
                                    return;
                                }
                                
                                const sessionId = data.session_id;
                                const fileSize = data.file_size;
                                
                                // Start native browser download (fast!)
                                const a = document.createElement('a');
                                a.href = data.download_url;
                                a.style.display = 'none';
                                a.download = '';
                                document.body.appendChild(a);
                                a.click();
                                document.body.removeChild(a);
                                
                                // Poll for real progress
                                const progressInterval = setInterval(() => {
                                    fetch('/api/download-progress/' + sessionId)
                                        .then(r => r.json())
                                        .then(progressData => {
                                            if (progressData.error) {
                                                clearInterval(progressInterval);
                                                delete activeDownloads[fileId];
                                                if (downloadBtn) {
                                                    downloadBtn.disabled = false;
                                                    downloadBtn.style.opacity = '1';
                                                    downloadBtn.style.cursor = 'pointer';
                                                }
                                                return;
                                            }
                                            
                                            const progress = Math.min(progressData.progress || 0, 100);
                                            const bytesSent = progressData.bytes_sent || 0;
                                            const totalSize = progressData.file_size || fileSize;
                                            
                                            if (progressFill) {
                                                progressFill.style.width = progress + '%';
                                                progressFill.textContent = Math.round(progress) + '%';
                                            }
                                            
                                            if (progressText) {
                                                const mbSent = (bytesSent / (1024 * 1024)).toFixed(2);
                                                const mbTotal = (totalSize / (1024 * 1024)).toFixed(2);
                                                progressText.textContent = `Downloading... ${mbSent} MB / ${mbTotal} MB (${Math.round(progress)}%)`;
                                            }
                                            
                                            if (progressData.status === 'completed' || progress >= 100) {
                                                clearInterval(progressInterval);
                                                delete activeDownloads[fileId];
                                                if (downloadBtn) {
                                                    downloadBtn.disabled = false;
                                                    downloadBtn.style.opacity = '1';
                                                    downloadBtn.style.cursor = 'pointer';
                                                }
                                                if (progressFill) {
                                                    progressFill.style.width = '100%';
                                                    progressFill.textContent = '100%';
                                                }
                                                if (progressText) {
                                                    const mbTotal = (totalSize / (1024 * 1024)).toFixed(2);
                                                    progressText.textContent = `Download complete! ${mbTotal} MB`;
                                                }
                                            }
                                        })
                                        .catch(err => {
                                            console.error('Progress fetch error:', err);
                                            clearInterval(progressInterval);
                                            delete activeDownloads[fileId];
                                            if (downloadBtn) {
                                                downloadBtn.disabled = false;
                                                downloadBtn.style.opacity = '1';
                                                downloadBtn.style.cursor = 'pointer';
                                            }
                                        });
                                }, 300); // Poll every 300ms
                            })
                            .catch(err => {
                                console.error('Error starting download:', err);
                                delete activeDownloads[fileId];
                                if (downloadBtn) {
                                    downloadBtn.disabled = false;
                                    downloadBtn.style.opacity = '1';
                                    downloadBtn.style.cursor = 'pointer';
                                }
                                if (progressText) {
                                    progressText.textContent = 'Error starting download';
                                    progressText.style.color = '#ff4444';
                                }
                            });
                    }
                    
                    // Upload form handler with real progress tracking
                    document.getElementById('uploadForm').addEventListener('submit', function(e) {
                        e.preventDefault();
                        const fileInput = document.getElementById('fileInput');
                        const statusDiv = document.getElementById('uploadStatus');
                        const progressContainer = document.getElementById('uploadProgress');
                        const progressFill = document.getElementById('uploadProgressFill');
                        const progressText = document.getElementById('uploadProgressText');
                        
                        if (!fileInput.files[0]) {
                            statusDiv.textContent = 'Please select a file';
                            statusDiv.style.display = 'block';
                            statusDiv.style.color = '#ff4444';
                            return;
                        }
                        
                        const file = fileInput.files[0];
                        const fileSize = file.size;
                        const formData = new FormData();
                        formData.append('file', file);
                        
                        // Show progress bar
                        progressContainer.style.display = 'block';
                        statusDiv.style.display = 'none';
                        
                        // Use XMLHttpRequest for upload progress tracking
                        const xhr = new XMLHttpRequest();
                        
                        // Track upload progress
                        xhr.upload.addEventListener('progress', function(e) {
                            if (e.lengthComputable) {
                                const percentComplete = (e.loaded / e.total) * 100;
                                const mbLoaded = (e.loaded / (1024 * 1024)).toFixed(2);
                                const mbTotal = (e.total / (1024 * 1024)).toFixed(2);
                                
                                if (progressFill) {
                                    progressFill.style.width = percentComplete + '%';
                                    progressFill.textContent = Math.round(percentComplete) + '%';
                                }
                                
                                if (progressText) {
                                    progressText.textContent = `Uploading... ${mbLoaded} MB / ${mbTotal} MB (${Math.round(percentComplete)}%)`;
                                }
                            }
                        });
                        
                        // Handle completion
                        xhr.addEventListener('load', function() {
                            if (xhr.status === 200) {
                                try {
                                    const data = JSON.parse(xhr.responseText);
                                    if (data.status === 'success') {
                                        if (progressFill) {
                                            progressFill.style.width = '100%';
                                            progressFill.textContent = '100%';
                                        }
                                        if (progressText) {
                                            const mbTotal = (fileSize / (1024 * 1024)).toFixed(2);
                                            progressText.textContent = `Upload complete! ${mbTotal} MB`;
                                        }
                                        
                                        statusDiv.textContent = '✅ File uploaded successfully!';
                                        statusDiv.style.color = '#ff6b35';
                                        statusDiv.style.display = 'block';
                                        fileInput.value = '';
                                        
                                        // Hide progress after 3 seconds
                                        setTimeout(() => {
                                            progressContainer.style.display = 'none';
                                            statusDiv.style.display = 'none';
                                        }, 3000);
                                        
                                        // Refresh file list
                                        updateFileList();
                                    } else {
                                        throw new Error(data.error || 'Upload failed');
                                    }
                                } catch (err) {
                                    statusDiv.textContent = '❌ Error: ' + err.message;
                                    statusDiv.style.color = '#ff4444';
                                    statusDiv.style.display = 'block';
                                    progressContainer.style.display = 'none';
                                }
                            } else {
                                try {
                                    const data = JSON.parse(xhr.responseText);
                                    statusDiv.textContent = '❌ Error: ' + (data.error || 'Upload failed');
                                } catch {
                                    statusDiv.textContent = '❌ Error: Upload failed (HTTP ' + xhr.status + ')';
                                }
                                statusDiv.style.color = '#ff4444';
                                statusDiv.style.display = 'block';
                                progressContainer.style.display = 'none';
                            }
                        });
                        
                        // Handle errors
                        xhr.addEventListener('error', function() {
                            statusDiv.textContent = '❌ Error: Network error during upload';
                            statusDiv.style.color = '#ff4444';
                            statusDiv.style.display = 'block';
                            progressContainer.style.display = 'none';
                        });
                        
                        // Start upload
                        xhr.open('POST', '/api/upload');
                        xhr.send(formData);
                    });
                    
                    updateFileList();
                    setInterval(updateFileList, 2000);
                </script>
            </body>
            </html>
            """
        
        @self.flask_app.route('/')
        def index():
            return html_template
        
        # Add catch-all route to handle any path issues (redirect unknown paths to root)
        @self.flask_app.route('/<path:path>')
        def catch_all(path):
            # If it's not a known API route, redirect to root
            if not path.startswith(('api/', 'download/', 'download-upload/')):
                return html_template
            return "Not found", 404
        
        @self.flask_app.route('/download/<file_id>')
        def download_file(file_id):
            if file_id not in self.shared_files:
                return "File not found", 404
            
            file_info = self.shared_files[file_id]
            file_path = file_info['path']
            
            if not os.path.exists(file_path):
                return "File not found", 404
            
            # Get session ID from query parameter or create new one
            session_id = request.args.get('session')
            file_size = os.path.getsize(file_path)
            
            if session_id and session_id in self.download_sessions:
                # Use existing session
                self.download_sessions[session_id]['status'] = 'downloading'
                self.download_sessions[session_id]['start_time'] = datetime.now()
            else:
                # Create new session if not provided
                session_id = str(uuid.uuid4())
                self.download_sessions[session_id] = {
                    'file_id': file_id,
                    'start_time': datetime.now(),
                    'progress': 0,
                    'status': 'downloading',
                    'file_size': file_size,
                    'bytes_sent': 0
                }
            
            # Increment download count
            self.shared_files[file_id]['downloads'] += 1
            self.save_shared_files()  # Persist download count
            
            # Log activity
            self.log_activity(f"Download started: {file_info['name']} (Session: {session_id[:8]})")
            
            # Create a generator to track progress with larger chunks for better performance
            def generate():
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(131072)  # 128KB chunks for better performance
                        if not chunk:
                            break
                        self.download_sessions[session_id]['bytes_sent'] += len(chunk)
                        progress = (self.download_sessions[session_id]['bytes_sent'] / file_size) * 100
                        self.download_sessions[session_id]['progress'] = progress
                        yield chunk
                
                # Mark as completed
                self.download_sessions[session_id]['status'] = 'completed'
                self.download_sessions[session_id]['end_time'] = datetime.now()
                duration = (self.download_sessions[session_id]['end_time'] - 
                           self.download_sessions[session_id]['start_time']).total_seconds()
                self.log_activity(
                    f"Download completed: {file_info['name']} "
                    f"({self.format_size(file_size)} in {duration:.1f}s)"
                )
            
            return Response(
                generate(),
                mimetype='application/octet-stream',
                headers={
                    'Content-Disposition': f'attachment; filename="{file_info["name"]}"',
                    'Content-Length': str(file_size),
                    'X-Session-Id': session_id,  # Include session ID for progress tracking
                    'Cache-Control': 'no-cache'  # Prevent caching for accurate progress
                }
            )
        
        @self.flask_app.route('/api/files')
        def api_files():
            files = []
            for file_id, file_info in self.shared_files.items():
                files.append({
                    'id': file_id,
                    'name': file_info['name'],
                    'size': file_info['size'],
                    'upload_time': file_info['upload_time']
                })
            return jsonify({'files': files})
        
        @self.flask_app.route('/api/track-download', methods=['POST'])
        def track_download():
            data = request.json
            file_id = data.get('file_id')
            if file_id in self.shared_files:
                self.log_activity(f"Download clicked: {self.shared_files[file_id]['name']}")
            return jsonify({'status': 'ok'})
        
        @self.flask_app.route('/api/start-download/<file_id>')
        def start_download(file_id):
            """Create a download session and return session ID"""
            if file_id not in self.shared_files:
                return jsonify({'error': 'File not found'}), 404
            
            file_info = self.shared_files[file_id]
            file_path = file_info['path']
            
            if not os.path.exists(file_path):
                return jsonify({'error': 'File not found'}), 404
            
            # Create session
            session_id = str(uuid.uuid4())
            file_size = os.path.getsize(file_path)
            self.download_sessions[session_id] = {
                'file_id': file_id,
                'start_time': datetime.now(),
                'progress': 0,
                'status': 'pending',
                'file_size': file_size,
                'bytes_sent': 0
            }
            
            return jsonify({
                'session_id': session_id,
                'file_size': file_size,
                'download_url': f'/download/{file_id}?session={session_id}'
            })
        
        @self.flask_app.route('/api/download-progress/<session_id>')
        def get_download_progress(session_id):
            if session_id in self.download_sessions:
                session = self.download_sessions[session_id]
                return jsonify({
                    'progress': session['progress'],
                    'status': session['status'],
                    'bytes_sent': session.get('bytes_sent', 0),
                    'file_size': session.get('file_size', 0)
                })
            return jsonify({'error': 'Session not found'}), 404
        
        @self.flask_app.route('/api/upload', methods=['POST'])
        def upload_file():
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            filename = secure_filename(file.filename)
            file_path = os.path.join(self.uploads_dir, f"{file_id}_{filename}")
            
            # Save file
            file.save(file_path)
            file_size = os.path.getsize(file_path)
            
            # Get real client IP
            client_ip = self.get_client_ip(request)
            
            # Store file info
            self.uploaded_files[file_id] = {
                'path': file_path,
                'name': filename,
                'size': self.format_size(file_size),
                'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'uploader_ip': client_ip
            }
            
            # Log activity
            self.log_activity(f"File uploaded: {filename} (from {client_ip})")
            
            return jsonify({
                'status': 'success',
                'file_id': file_id,
                'message': 'File uploaded successfully'
            })
        
        @self.flask_app.route('/api/uploaded-files')
        def api_uploaded_files():
            files = []
            for file_id, file_info in self.uploaded_files.items():
                files.append({
                    'id': file_id,
                    'name': file_info['name'],
                    'size': file_info['size'],
                    'upload_time': file_info['upload_time'],
                    'uploader_ip': file_info.get('uploader_ip', 'Unknown')
                })
            return jsonify({'files': files})
        
        @self.flask_app.route('/download-upload/<file_id>')
        def download_uploaded_file(file_id):
            if file_id not in self.uploaded_files:
                return "File not found", 404
            
            file_info = self.uploaded_files[file_id]
            file_path = file_info['path']
            
            if not os.path.exists(file_path):
                return "File not found", 404
            
            self.log_activity(f"Uploaded file downloaded: {file_info['name']}")
            
            return send_file(
                file_path,
                as_attachment=True,
                download_name=file_info['name']
            )
    
    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select a file to share",
            filetypes=[("All Files", "*.*")]
        )
        if file_path:
            self.file_path_var.set(file_path)
    
    def share_file(self):
        file_path = self.file_path_var.get()
        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("Error", "Please select a valid file.")
            return
        
        if not self.server_running:
            messagebox.showerror("Error", "Server is not running. Please wait...")
            return
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        file_name = os.path.basename(file_path)
        file_size = self.format_size(os.path.getsize(file_path))
        
        self.shared_files[file_id] = {
            'path': file_path,
            'name': file_name,
            'size': file_size,
            'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'downloads': 0
        }
        
        # Add to treeview
        self.files_tree.insert(
            "",
            tk.END,
            iid=file_id,
            values=(
                file_name,
                file_size,
                "🔥 Active",
                "🔥 0",
                f"{self.public_url}/download/{file_id}" if self.public_url else "⏳ Generating..."
            )
        )
        
        self.file_path_var.set("")
        self.log_activity(f"File shared: {file_name}")
        self.save_shared_files()  # Persist changes
        
        if self.public_url:
            messagebox.showinfo(
                "File Shared!",
                f"File '{file_name}' is now available at:\n{self.public_url}/download/{file_id}\n\nDouble-click the file in the list to copy the link."
            )
    
    def remove_file(self):
        selection = self.files_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a file to remove.")
            return
        
        file_id = selection[0]
        if file_id in self.shared_files:
            file_name = self.shared_files[file_id]['name']
            del self.shared_files[file_id]
            self.files_tree.delete(file_id)
            self.log_activity(f"File removed: {file_name}")
            self.save_shared_files()  # Persist changes
    
    def copy_file_link(self, event):
        selection = self.files_tree.selection()
        if selection:
            file_id = selection[0]
            if file_id in self.shared_files and self.public_url:
                link = f"{self.public_url}/download/{file_id}"
                self.root.clipboard_clear()
                self.root.clipboard_append(link)
                messagebox.showinfo("Link Copied", f"Download link copied to clipboard:\n{link}")
    
    def is_valid_url(self, url):
        """Validate that URL is properly formatted"""
        if not url:
            return False
        url = url.strip()
        # Check if it's a valid HTTPS URL with proper domain
        if url.startswith('https://') and ('.trycloudflare.com' in url or '.cloudflared.net' in url):
            # Basic validation - check it doesn't have spaces or invalid chars
            if ' ' not in url and len(url) > 20:
                return True
        return False
    
    def open_url(self):
        """Open the URL in the default browser"""
        if not self.server_running:
            messagebox.showwarning("Server Not Ready", "Server is not running yet. Please wait...")
            return
        
        url_to_open = None
        if self.public_url and self.is_valid_url(self.public_url):
            # Use public URL as-is (cloudflared handles routing)
            url_to_open = self.public_url.strip()
        elif self.server_running:
            url_to_open = f"http://127.0.0.1:{self.local_port}"
        
        if url_to_open:
            import webbrowser
            # Ensure URL ends with / for root route
            if not url_to_open.endswith('/'):
                url_to_open += '/'
            try:
                webbrowser.open(url_to_open)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open browser:\n{str(e)}")
        else:
            messagebox.showwarning("URL Not Available", "Public URL is not available yet. Please wait for the tunnel to establish.")
    
    def open_website(self):
        import webbrowser
        webbrowser.open("https://pyrosoft.pro/")
    
    def download_uploaded_file(self, event=None):
        """Download the selected uploaded file"""
        selection = self.uploads_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a file to download.")
            return
        
        file_id = selection[0]
        if file_id in self.uploaded_files:
            file_info = self.uploaded_files[file_id]
            file_path = file_info['path']
            
            if not os.path.exists(file_path):
                messagebox.showerror("Error", "File not found on disk.")
                return
            
            # Open file dialog to save
            save_path = filedialog.asksaveasfilename(
                title="Save uploaded file",
                initialfile=file_info['name'],
                defaultextension=""
            )
            
            if save_path:
                import shutil
                shutil.copy2(file_path, save_path)
                self.log_activity(f"Downloaded uploaded file: {file_info['name']}")
                messagebox.showinfo("Success", f"File saved to:\n{save_path}")
    
    def download_selected_upload(self):
        """Download selected uploaded file (button handler)"""
        self.download_uploaded_file()
    
    def share_uploaded_file(self):
        """Share an uploaded file (make it available for download)"""
        selection = self.uploads_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a file to share.")
            return
        
        upload_file_id = selection[0]
        if upload_file_id not in self.uploaded_files:
            messagebox.showerror("Error", "File not found.")
            return
        
        if not self.server_running:
            messagebox.showerror("Error", "Server is not running. Please wait...")
            return
        
        file_info = self.uploaded_files[upload_file_id]
        file_path = file_info['path']
        file_name = file_info['name']
        
        if not os.path.exists(file_path):
            messagebox.showerror("Error", "File not found on disk.")
            return
        
        # Generate new unique file ID for sharing
        share_file_id = str(uuid.uuid4())
        file_size = self.format_size(os.path.getsize(file_path))
        
        # Add to shared files
        self.shared_files[share_file_id] = {
            'path': file_path,
            'name': file_name,
            'size': file_size,
            'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'downloads': 0
        }
        
        # Add to treeview
        self.files_tree.insert(
            "",
            tk.END,
            iid=share_file_id,
            values=(
                file_name,
                file_size,
                "🔥 Active",
                "🔥 0",
                f"{self.public_url}/download/{share_file_id}" if self.public_url else "⏳ Generating..."
            )
        )
        
        self.log_activity(f"Uploaded file shared: {file_name}")
        self.save_shared_files()  # Persist changes
        
        # Switch to Files tab to show the newly shared file
        self.notebook.select(1)  # Switch to Files tab (index 1)
        
        if self.public_url:
            messagebox.showinfo(
                "File Shared!",
                f"File '{file_name}' is now available for download at:\n{self.public_url}/download/{share_file_id}\n\nDouble-click the file in the Files tab to copy the link."
            )
        else:
            messagebox.showinfo(
                "File Shared!",
                f"File '{file_name}' is now available for download.\n\nNote: Public URL will be available once Cloudflare Tunnel is active."
            )
    
    def remove_uploaded_file(self):
        """Remove the selected uploaded file"""
        selection = self.uploads_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a file to remove.")
            return
        
        file_id = selection[0]
        if file_id in self.uploaded_files:
            file_info = self.uploaded_files[file_id]
            file_path = file_info['path']
            
            # Delete file from disk
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete file: {str(e)}")
                    return
            
            file_name = file_info['name']
            del self.uploaded_files[file_id]
            self.uploads_tree.delete(file_id)
            self.log_activity(f"Uploaded file removed: {file_name}")
    
    def start_local_server(self):
        def run_server():
            self.flask_app.run(host='127.0.0.1', port=self.local_port, debug=False, use_reloader=False)
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Wait a moment for server to start
        time.sleep(1)
        self.server_running = True
        self.start_cloudflare_tunnel()
    
    def check_cloudflared_installed(self):
        """Check if cloudflared is installed and available"""
        try:
            result = subprocess.run(
                ['cloudflared', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def start_cloudflare_tunnel(self):
        def run_tunnel():
            # Check if cloudflared is available
            if not self.check_cloudflared_installed():
                self.log_activity("Cloudflared not found. App running in local mode only.")
                self.log_activity("Click 'Install Cloudflared' button to enable public URLs.")
                return
            
            try:
                # Start tunnel with a small delay to avoid rapid reconnections
                self.log_activity("Starting Cloudflare Tunnel...")
                time.sleep(0.5)  # Small delay to avoid rapid tunnel creation
                process = subprocess.Popen(
                    ['cloudflared', 'tunnel', '--url', f'http://127.0.0.1:{self.local_port}'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                self.cloudflare_process = process
                
                # Read output to get public URL
                import re
                url_found = False
                timeout = time.time() + 30  # 30 second timeout
                error_messages = []
                
                for line in process.stdout:
                    if time.time() > timeout:
                        self.log_activity("Timeout waiting for tunnel URL")
                        break
                    
                    # Log tunnel output for debugging
                    line_stripped = line.strip()
                    if line_stripped:
                        # Check for error messages indicating rate limits or issues
                        line_lower = line_stripped.lower()
                        if any(keyword in line_lower for keyword in ['error', 'failed', 'limit', 'rate', 'quota', 'too many']):
                            error_messages.append(line_stripped)
                            self.log_activity(f"⚠️ Tunnel warning: {line_stripped}")
                        
                        # Only log non-error lines if verbose (to reduce spam)
                        elif 'https://' in line_stripped or 'tunnel' in line_lower:
                            self.log_activity(f"Tunnel: {line_stripped}")
                    
                    # Look for cloudflare tunnel URLs (trycloudflare.com or cloudflared.net domain)
                    # Updated patterns to match various cloudflared output formats
                    url_patterns = [
                        r'https://[a-zA-Z0-9-]+\.trycloudflare\.com',
                        r'https://[a-zA-Z0-9-]+\.cloudflared\.net',
                        r'https://[a-zA-Z0-9-]+\.(?:trycloudflare|cloudflared)\.(?:com|net)',
                    ]
                    
                    for pattern in url_patterns:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            url = match.group(0).strip()
                            # Validate URL format
                            if url.startswith('https://') and ('.trycloudflare.com' in url or '.cloudflared.net' in url):
                                self.public_url = url
                                self.log_activity(f"✅ Tunnel active! Public URL: {self.public_url}")
                                url_found = True
                                break
                    
                    if url_found:
                        break
                    
                    if process.poll() is not None:
                        self.log_activity("❌ Cloudflared process ended unexpectedly")
                        break
                
                if not url_found:
                    if error_messages:
                        error_msg = "\n".join(error_messages[-3:])  # Show last 3 errors
                        self.log_activity(f"❌ Tunnel failed. Possible Cloudflare rate limit or error:")
                        self.log_activity(f"   {error_msg}")
                        self.log_activity("💡 Tip: Wait a few minutes and try again, or restart the app.")
                    else:
                        self.log_activity("⚠️ Warning: Could not extract tunnel URL from cloudflared output")
                        self.log_activity("💡 Tip: Cloudflare may be rate-limiting. Wait 5-10 minutes and restart.")
                
            except Exception as e:
                self.log_activity(f"Tunnel error: {str(e)}")
        
        tunnel_thread = threading.Thread(target=run_tunnel, daemon=True)
        tunnel_thread.start()
    
    def install_cloudflared(self):
        """Install cloudflared using the installer script"""
        installer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "install_cloudflared.bat")
        
        if not os.path.exists(installer_path):
            # If installer doesn't exist, create it on the fly
            messagebox.showinfo(
                "Install Cloudflared",
                "Please install cloudflared manually:\n\n"
                "1. Download from: https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe\n"
                "2. Rename to cloudflared.exe\n"
                "3. Place in C:\\Windows\\System32 or add to PATH\n\n"
                "Or use winget:\n"
                "winget install --id Cloudflare.cloudflared"
            )
            return
        
        # Run installer with elevated privileges
        try:
            import ctypes
            if ctypes.windll.shell32.IsUserAnAdmin():
                # Already admin, run directly
                subprocess.Popen([installer_path], shell=True)
            else:
                # Request admin privileges
                ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    installer_path,
                    None,
                    None,
                    1
                )
            
            messagebox.showinfo(
                "Installing Cloudflared",
                "The installer is running. Please:\n\n"
                "1. Follow the installation prompts\n"
                "2. Restart BurnBin after installation completes\n\n"
                "The app will work locally until cloudflared is installed."
            )
        except Exception as e:
            messagebox.showerror(
                "Installation Error",
                f"Failed to start installer:\n{str(e)}\n\n"
                "Please run install_cloudflared.bat manually as administrator."
            )
    
    def update_status(self):
        cloudflared_installed = self.check_cloudflared_installed()
        
        if self.server_running:
            if self.public_url and self.is_valid_url(self.public_url):
                self.status_label.config(
                    text="🔥 Server running | 🔥 Tunnel active",
                    fg=self.colors['success']
                )
                self.url_label.config(
                    text=f"🔥 {self.public_url} (Click to open)",
                    fg=self.colors['accent']
                )
                self.url_label.pack(fill=tk.X)
                self.install_cloudflared_btn.pack_forget()
            elif self.public_url:
                # Invalid URL - reset it
                self.public_url = None
                self.status_label.config(
                    text="🔥 Server running | ⏳ Starting tunnel...",
                    fg=self.colors['warning']
                )
                self.url_label.config(text="")
                self.url_label.pack(fill=tk.X)
                self.install_cloudflared_btn.pack_forget()
            else:
                if cloudflared_installed:
                    self.status_label.config(
                        text="🔥 Server running | ⏳ Starting tunnel...",
                        fg=self.colors['warning']
                    )
                    self.url_label.config(text="")
                    self.url_label.pack(fill=tk.X)
                    self.install_cloudflared_btn.pack_forget()
                else:
                    # Cloudflared not installed - show local URL and install button
                    self.status_label.config(
                        text="🔥 Server running | ⚠️ Local mode only",
                        fg=self.colors['warning']
                    )
                    local_url = f"http://127.0.0.1:{self.local_port}"
                    self.url_label.config(
                        text=f"🔥 Local URL: {local_url} (Click to open)",
                        fg=self.colors['text_secondary']
                    )
                    self.url_label.pack(fill=tk.X, pady=(0, 8))
                    # Show install button
                    if not self.install_cloudflared_btn.winfo_ismapped():
                        self.install_cloudflared_btn.pack(fill=tk.X)
        else:
            self.status_label.config(
                text="⏳ Starting server...",
                fg=self.colors['text_light']
            )
            self.url_label.config(text="")
            self.url_label.pack(fill=tk.X)
            self.install_cloudflared_btn.pack_forget()
        
        # Update file list status
        for file_id in self.shared_files:
            if file_id in self.files_tree.get_children():
                file_info = self.shared_files[file_id]
                values = list(self.files_tree.item(file_id, 'values'))
                if len(values) >= 4:
                    values[2] = "🔥 Active"
                    values[3] = f"🔥 {file_info['downloads']}"
                    if self.public_url:
                        values[4] = f"{self.public_url}/download/{file_id}"
                    self.files_tree.item(file_id, values=values)
        
        # Update uploaded files list
        current_upload_ids = set(self.uploads_tree.get_children())
        new_upload_ids = set(self.uploaded_files.keys())
        
        # Remove files that no longer exist
        for file_id in current_upload_ids - new_upload_ids:
            self.uploads_tree.delete(file_id)
        
        # Add new uploaded files
        for file_id in new_upload_ids - current_upload_ids:
            file_info = self.uploaded_files[file_id]
            self.uploads_tree.insert(
                "",
                tk.END,
                iid=file_id,
                values=(
                    file_info['name'],
                    file_info['size'],
                    file_info['upload_time'],
                    file_info.get('uploader_ip', 'Unknown')
                )
            )
        
        self.root.after(1000, self.update_status)
    
    def log_activity(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        # Only log if UI is initialized
        if hasattr(self, 'activity_text') and self.activity_text:
            try:
                self.activity_text.config(state=tk.NORMAL)
                self.activity_text.insert(tk.END, log_message)
                self.activity_text.see(tk.END)
                self.activity_text.config(state=tk.DISABLED)
            except (tk.TclError, AttributeError):
                # UI widget might not be ready yet
                pass
    
    def format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def save_shared_files(self):
        """Save shared files to JSON file for persistence"""
        try:
            data = {}
            for file_id, file_info in self.shared_files.items():
                # Only save if file still exists
                if os.path.exists(file_info['path']):
                    data[file_id] = {
                        'path': file_info['path'],
                        'name': file_info['name'],
                        'size': file_info['size'],
                        'upload_time': file_info['upload_time'],
                        'downloads': file_info.get('downloads', 0)
                    }
            
            with open(self.shared_files_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.log_activity(f"Error saving shared files: {str(e)}")
    
    def load_shared_files(self):
        """Load shared files from JSON file on startup"""
        if not os.path.exists(self.shared_files_file):
            return
        
        try:
            with open(self.shared_files_file, 'r') as f:
                data = json.load(f)
            
            loaded_count = 0
            for file_id, file_info in data.items():
                file_path = file_info['path']
                
                # Check if file still exists
                if os.path.exists(file_path):
                    # Recalculate size in case file changed
                    file_size = self.format_size(os.path.getsize(file_path))
                    
                    self.shared_files[file_id] = {
                        'path': file_path,
                        'name': file_info['name'],
                        'size': file_size,
                        'upload_time': file_info.get('upload_time', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                        'downloads': file_info.get('downloads', 0)
                    }
                    loaded_count += 1
                else:
                    # File no longer exists, skip it
                    continue
            
            if loaded_count > 0:
                self.log_activity(f"Loaded {loaded_count} shared file(s) from previous session")
        except Exception as e:
            self.log_activity(f"Error loading shared files: {str(e)}")
    
    def populate_files_treeview(self):
        """Populate the files treeview with loaded shared files"""
        for file_id, file_info in self.shared_files.items():
            # Check if already in treeview
            if file_id not in self.files_tree.get_children():
                self.files_tree.insert(
                    "",
                    tk.END,
                    iid=file_id,
                    values=(
                        file_info['name'],
                        file_info['size'],
                        "🔥 Active",
                        f"🔥 {file_info.get('downloads', 0)}",
                        f"{self.public_url}/download/{file_id}" if self.public_url else "⏳ Generating..."
                    )
                )
    
    def on_closing(self):
        # Save shared files before closing
        self.save_shared_files()
        if self.cloudflare_process:
            self.cloudflare_process.terminate()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = FileShareApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()

