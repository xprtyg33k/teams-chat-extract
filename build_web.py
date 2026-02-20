#!/usr/bin/env python3
"""Script to inject API_URL into index.html for Docker builds"""
import os
import sys

api_url = os.environ.get("API_URL", "http://localhost:8000")

# Read index.html
with open("web/index.html", "r") as f:
    content = f.read()

# Inject API_URL as a global variable before app.js loads
injection = f'<script>window.API_BASE = "{api_url}";</script>'
content = content.replace("</head>", f"{injection}\n</head>")

# Write back
with open("web/index.html", "w") as f:
    f.write(content)

print(f"Injected API_URL: {api_url}")
