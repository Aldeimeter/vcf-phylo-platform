import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .routers import datasets, jobs, logs, export
from .database import database
from .logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI server starting up")
    await database.connect()
    logger.info("Connected to MongoDB")
    yield
    await database.disconnect()
    logger.info("FastAPI server shutting down")


app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{os.environ.get('FRONTEND_PORT', '8080')}",
        f"http://127.0.0.1:{os.environ.get('FRONTEND_PORT', '8080')}",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/static/results", StaticFiles(directory=os.environ["STATIC_PATH"]), name="results"
)
app.include_router(datasets.router)
app.include_router(jobs.router)
app.include_router(logs.router)
app.include_router(export.router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
