"""Start the app: python run.py  ->  http://127.0.0.1:8000"""
import uvicorn

from config.settings import HOST, PORT

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=False)
