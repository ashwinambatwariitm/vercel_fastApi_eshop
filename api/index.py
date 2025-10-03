# api/index.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import json
import os

# -----------------
# 1. INITIAL SETUP
# -----------------

app = FastAPI()

# Enable CORS for POST requests from any origin (as required by the prompt)
# This prevents "Failed to fetch" errors when calling the API from a different domain (like a dashboard).
origins = ["*"] 

# api/index.py (CORSMiddleware section)

app.add_middleware(
    CORSMiddleware,
    # Use "*" to allow all origins as required
    allow_origins=["*"], 
    
    # REMOVE 'allow_credentials=True' when using allow_origins=["*"]
    # allow_credentials=True, 
    
    # Ensure OPTIONS is allowed for preflight checks
    allow_methods=["POST", "OPTIONS"], 
    allow_headers=["*"],
    expose_headers=["*"],
)

# -----------------
# 2. DATA LOADING & SCHEMA
# -----------------

# Define the expected request body schema for Pydantic validation
class LatencyRequest(BaseModel):
    regions: list[str]
    threshold_ms: float = 180

# Load data once when the function initializes (cold start)
try:
    # Path is relative to the Vercel project root, accessed via the function's directory
    file_path = os.path.join(os.path.dirname(__file__), '..', 'q-vercel-latency.json')
    with open(file_path, 'r') as f:
        LATENCY_DATA = json.load(f)
    DF_FULL = pd.DataFrame(LATENCY_DATA)
except FileNotFoundError:
    DF_FULL = pd.DataFrame() 

# -----------------
# 3. METRIC CALCULATION LOGIC
# -----------------

def calculate_region_metrics(df_region: pd.DataFrame, threshold: float) -> dict:
    """Calculates avg, p95, uptime mean, and breaches for a region's DataFrame."""
    if df_region.empty:
        return {
            "avg_latency": 0.0,
            "p95_latency": 0.0,
            "avg_uptime": 0.0,
            "breaches": 0
        }

    # Calculate metrics
    avg_latency = df_region['latency_ms'].mean()
    # P95: 95th percentile, using 'higher' interpolation for consistency
    p95_latency = df_region['latency_ms'].quantile(0.95, interpolation='higher')
    avg_uptime = df_region['uptime_pct'].mean()
    # Breaches: Count of records where latency is >= threshold
    breaches = (df_region['latency_ms'] >= threshold).sum()

    return {
        "avg_latency": round(avg_latency, 2),
        "p95_latency": round(p95_latency, 2),
        "avg_uptime": round(avg_uptime, 3),
        "breaches": int(breaches)
    }

# -----------------
# 4. API ENDPOINT
# -----------------

# Define the required POST endpoint
@app.post("/", response_model=dict)
async def get_latency_metrics(request_data: LatencyRequest):
    """
    Accepts regions and a threshold, and returns per-region metrics
    (avg_latency, p95_latency, avg_uptime, breaches).
    """
    regions = request_data.regions
    threshold = request_data.threshold_ms
    
    # Filter the DataFrame for the requested regions
    df_filtered = DF_FULL[DF_FULL['region'].isin(regions)]
    
    # Calculate and store results for each region
    results = {}
    for region in regions:
        df_region = df_filtered[df_filtered['region'] == region]
        results[region] = calculate_region_metrics(df_region, threshold)
    
    # CHANGE: Wrap the results under a top-level key named "regions"
    return {"regions": results} 

# Optional: Add a simple GET route for health checking in a browser (or use /health)
@app.get("/")
def root():
    return {"message": "POST request required with JSON body to retrieve metrics."}