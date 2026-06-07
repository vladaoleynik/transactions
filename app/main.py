from fastapi import FastAPI

app = FastAPI(title="Transactions")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
