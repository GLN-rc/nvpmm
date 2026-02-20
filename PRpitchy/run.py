#!/usr/bin/env python3
"""
PR Pitchy - Development Server
Run this script to start the webapp locally.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv
    load_dotenv()

    print("\n" + "="*60)
    print("  PR Pitchy")
    print("  AI-Powered PR Pitch Generator")
    print("="*60)
    print("\n  Starting server at: http://localhost:8001")
    print("  Press Ctrl+C to stop\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        reload_dirs=["."]
    )
