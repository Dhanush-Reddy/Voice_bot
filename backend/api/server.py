"""
Uvicorn entry point for the Voice AI backend.
Version: 1.1.1
"""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(
        "api.routes:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
