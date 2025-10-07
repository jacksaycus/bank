from fastapi import FastAPI
app = FastAPI(
    title="NextGen Bank - FastAPI",
    description="Fully features banking API build with FastAPI",
)

@app.get("/")
def home():
    return {"message": "Welcome to the Next Gen Bank API"}