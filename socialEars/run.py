#!/usr/bin/env python3
"""socialEars — Social Listening Agent. Run this to start locally."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv
    load_dotenv()

    print("\n" + "=" * 60)
    print("  socialEars")
    print("  Social Listening Agent for GTM Intelligence")
    print("=" * 60)
    print("\n  Starting server at: http://localhost:8003")
    print("  Press Ctrl+C to stop\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        reload_dirs=["."],
    )
