import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .routers import datasets, jobs

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/static/results", StaticFiles(directory=os.environ["STATIC_PATH"]), name="results"
)
app.include_router(datasets.router)
app.include_router(jobs.router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
