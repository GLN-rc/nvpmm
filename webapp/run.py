#!/usr/bin/env python3
"""
Website Competitor Scanner - Development Server
Run this script to start the webapp locally.
"""

import os
import sys

# Add the webapp directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Change to webapp directory for static file serving
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    print("\n" + "="*60)
    print("  Website Competitor Scanner")
    print("  SEO | GEO | LLM Optimization Analysis")
    print("="*60)
    print("\n  Starting server at: http://localhost:8000")
    print("  Press Ctrl+C to stop\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."]
    )
