"""trustFall — start the server."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8005, reload=True)
