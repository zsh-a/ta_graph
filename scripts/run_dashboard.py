import uvicorn
from src.dashboard import app
from src.database.session import init_db
import os

if __name__ == "__main__":
    # Ensure database tables exist
    print("🛠 Initializing Database...")
    init_db()
    
    print("🚀 Starting Standalone Dashboard Server...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
