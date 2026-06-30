from fastapi import FastAPI
from app.core.database import create_tables
from app.api.routes import router

app = FastAPI(
    title = "AI_Powered Transaction Processing Pipeline",
    description = "Upload messy CSVs, get clean data + AI insights",
    version = "1.0.0"
)

@app.on_event("startup")
def startup():
    create_tables()
    print("Database tables ready.")

app.include_router(router)

@app.get("/")
def root():
    return {"message": "AI Powered Transaction Processing Pipeline is running", "docs": "/docs"}