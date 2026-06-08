from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from spin3.router import router as spin3_router

app = FastAPI(title="SP3 Multi-Project API")

# Enable CORS for the Vue frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "FastAPI Multi-Project Backend is running!"}

# Include routers from sub-projects
app.include_router(spin3_router, prefix="/spin3", tags=["spin3"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
