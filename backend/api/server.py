"""
Uvicorn entry point for the Voice AI backend.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.routes:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
