# api/index.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import json
import os

app = FastAPI()

# 1. Enable CORS for POST requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

# 2. Define the expected request body schema
class LatencyRequest(BaseModel):
    regions: list[str]
    threshold_ms: float = 180

# Load data once when the function initializes
# The path is relative to the Vercel project root, but accessed via the function's directory
try:
    # '..' navigates from 'api/' back to the project root
    file_path = os.path.join(os.path.dirname(__file__), '..', 'q-vercel-latency.json')
    with open(file_path, 'r') as f:
        LATENCY_DATA = json.load(f)
    DF_FULL = pd.DataFrame(LATENCY_DATA)
except FileNotFoundError:
    DF_FULL = pd.DataFrame() 

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
    # P95: 95th percentile, using 'higher' interpolation for Vercel's test case consistency
    p95_latency = df_region['latency_ms'].quantile(0.95, interpolation='higher')
    avg_uptime = df_region['uptime_pct'].mean()
    breaches = (df_region['latency_ms'] >= threshold).sum()

    return {
        "avg_latency": round(avg_latency, 2),
        "p95_latency": round(p95_latency, 2),
        "avg_uptime": round(avg_uptime, 3),
        "breaches": int(breaches)
    }

# 3. Define the POST endpoint
@app.post("/", response_model=dict)
async def get_latency_metrics(request_data: LatencyRequest):
    regions = request_data.regions
    threshold = request_data.threshold_ms
    
    # Filter for requested regions
    df_filtered = DF_FULL[DF_FULL['region'].isin(regions)]
    
    # Calculate and return results for each region
    results = {}
    for region in regions:
        df_region = df_filtered[df_filtered['region'] == region]
        results[region] = calculate_region_metrics(df_region, threshold)
        
    return results