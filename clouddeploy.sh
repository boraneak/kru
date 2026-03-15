#!/bin/bash
# Nova Live Tutor — Google Cloud Run Deployment
# Usage: ./clouddeploy.sh

set -e

PROJECT_ID="nova-tutor-2026"
REGION="asia-southeast1"
SERVICE_NAME="nova-live-tutor"
IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Deploying Nova to Google Cloud Run..."

# Build and push Docker image
gcloud builds submit --tag $IMAGE

# Deploy to Cloud Run with WebSocket session affinity
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --session-affinity \
  --set-env-vars GEMINI_API_KEY=$GEMINI_API_KEY \
  --set-env-vars MODEL_NAME=$MODEL_NAME \
  --port 8080 \
  --timeout 3600

echo "✅ Nova deployed!"
echo "🌐 URL:"
gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --format="value(status.url)"
