# Consumer Dispute Risk MLOps

Production-grade MLOps project to predict whether a consumer will dispute the eventual resolution of a complaint.

## Project Structure

```text
consumer-dispute-risk-mlops/
│
├── configs/             # Configuration files for training, pipelines, etc.
├── data/
│   ├── raw/             # Raw consumer complaint data
│   ├── processed/       # Preprocessed and cleaned data
│   └── external/        # External reference datasets
│
├── notebooks/           # Jupyter notebooks for EDA and experimentation
│
├── pipelines/           # ZenML or general orchestration pipeline definitions
│
├── steps/               # Individual pipeline steps (loading, preprocessing, training)
│
├── src/                 # Reusable source code module
│   ├── preprocessing/   # Data cleaning and transformations
│   ├── features/        # Feature engineering logic
│   ├── models/          # Model architectures and training scripts
│   ├── evaluation/      # Model validation and evaluation metrics
│   ├── monitoring/      # Data/concept drift and system monitoring
│   └── utils/           # Shared utility functions
│
├── deployment/          # Deployment configurations (FastAPI, Docker, CI/CD)
│
├── tests/               # Unit, integration, and system tests
│
├── docs/                # Project documentation and reports
│
├── app/                 # FastAPI prediction service
│   └── main.py
│
├── Dockerfile           # Containerization configuration
├── docker-compose.yml   # Multi-container local orchestration
├── pyproject.toml       # Python packaging and dependency config
├── requirements.txt     # Python package requirements
└── README.md            # This documentation file
```

## Setup & Execution

### Local Environment
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run the API:
   ```bash
   uvicorn app.main:app --reload
   ```

### Docker
1. Build and run via Docker Compose:
   ```bash
   docker-compose up --build
   ```
