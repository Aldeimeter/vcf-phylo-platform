from fastapi import FastAPI
from .routers import datasets, jobs

app = FastAPI()


app.include_router(datasets.router)
app.include_router(jobs.router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
