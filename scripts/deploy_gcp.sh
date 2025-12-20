#!/bin/bash
set -e

# Configuration
REGION="us-central1"
SERVICE_NAME="community-notes-analytics"
SA_NAME="cn-analytics-runner"
PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME="${PROJECT_ID}-cn-data"
ARTIFACT_PATH="artifacts/community_notes_full.duckdb" # STRICT: Full artifact only
ARTIFACT_GCS="gs://${BUCKET_NAME}/${ARTIFACT_PATH}"
MOUNT_PATH="/mnt/gcs_data"
# GCS path relative to mount point
ENV_DB_PATH="${MOUNT_PATH}/${ARTIFACT_PATH}"

echo "🚀 Starting Deployment for Project: ${PROJECT_ID}"

# 1. Setup Infra (Idempotent)
echo "🔧 Configuring Infrastructure..."

# Check if we accidentally have a sample
if [ ! -f "${ARTIFACT_PATH}" ]; then
    echo "❌ CRITICAL ERROR: Full artifact '${ARTIFACT_PATH}' not found!"
    echo "   Did you run: 'python scripts/build_db.py' (without --sample)?"
    echo "   We NEVER deploy sample data to production."
    exit 1
fi

# Create Service Account if not exists
if ! gcloud iam service-accounts describe ${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com > /dev/null 2>&1; then
    echo "   creating service account: ${SA_NAME}"
    gcloud iam service-accounts create ${SA_NAME} \
        --display-name="CN Analytics Runner"
else
    echo "   service account ${SA_NAME} exists."
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Create Bucket if not exists
if ! gcloud storage buckets describe gs://${BUCKET_NAME} > /dev/null 2>&1; then
    echo "   creating bucket: ${BUCKET_NAME}"
    gcloud storage buckets create gs://${BUCKET_NAME} --location=${REGION}
else
    echo "   bucket ${BUCKET_NAME} exists."
fi

# Grant Permissions
echo "   granting objectViewer to ${SA_EMAIL} on ${BUCKET_NAME}"
gcloud storage buckets add-iam-policy-binding gs://${BUCKET_NAME} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.objectViewer" > /dev/null

# 2. Artifact Upload
echo "📦 Uploading DuckDB artifact to GCS..."
echo "   Source: ${ARTIFACT_PATH}"
echo "   Target: ${ARTIFACT_GCS}"

gcloud storage cp "${ARTIFACT_PATH}" "${ARTIFACT_GCS}"

# 3. Preflight Check (Strict Idempotency)
echo "🔍 Running Preflight Checks in ${REGION}..."

# Check 1: Cloud Run Job Conflict
if gcloud run jobs describe ${SERVICE_NAME} --region ${REGION} > /dev/null 2>&1; then
    echo "❌ Conflict: Cloud Run Job '${SERVICE_NAME}' exists in ${REGION}. Rename required."
    exit 1
fi

# Check 2: Cloud Run Service Existence
if gcloud run services describe ${SERVICE_NAME} --region ${REGION} > /dev/null 2>&1; then
    echo "ℹ️  Found existing service '${SERVICE_NAME}' in ${REGION}. Updating..."
else
    echo "ℹ️  Service '${SERVICE_NAME}' not found in ${REGION}. Creating new..."
fi

# 4. Deploy
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --source . \
    --platform managed \
    --region ${REGION} \
    --service-account ${SA_EMAIL} \
    --execution-environment gen2 \
    --add-volume name=cn_data,type=cloud-storage,bucket=${BUCKET_NAME},readonly=true \
    --add-volume-mount volume=cn_data,mount-path=${MOUNT_PATH} \
    --set-env-vars CN_DUCKDB_PATH=${ENV_DB_PATH} \
    --concurrency 1 \
    --memory 4Gi \
    --no-cpu-throttling \
    --cpu-boost \
    --allow-unauthenticated

# 5. Set service-level minimum instances (keeps warm across revisions)
echo "⚡ Setting service-level min instances to 1..."
gcloud run services update ${SERVICE_NAME} \
    --region ${REGION} \
    --min 1

echo "✅ Success! Deployment complete."
echo "   Performance optimizations applied: --no-cpu-throttling, --cpu-boost, --min 1"
