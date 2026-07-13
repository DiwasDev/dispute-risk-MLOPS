from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Consumer Dispute Risk Prediction API",
    description="API for predicting the risk of a customer disputing a complaint resolution.",
    version="0.1.0"
)

class ComplaintInput(BaseModel):
    product: str
    sub_product: str | None = None
    issue: str
    sub_issue: str | None = None
    company: str
    state: str | None = None
    submitted_via: str

class DisputePrediction(BaseModel):
    dispute_risk: float
    dispute_predicted: bool

@app.get("/")
def read_root():
    return {"message": "Consumer Dispute Risk API is running."}

@app.post("/predict", response_model=DisputePrediction)
def predict_dispute(complaint: ComplaintInput):
    # Placeholder inference logic
    return DisputePrediction(
        dispute_risk=0.21,
        dispute_predicted=False
    )
