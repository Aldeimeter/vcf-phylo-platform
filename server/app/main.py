import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .routers import datasets, jobs

app = FastAPI()

app.mount(
    "/static/results", StaticFiles(directory=os.environ["STATIC_PATH"]), name="results"
)
app.include_router(datasets.router)
app.include_router(jobs.router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
