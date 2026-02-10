from fastapi import FastAPI
from .routers import datasets

app = FastAPI()


app.include_router(datasets.router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
