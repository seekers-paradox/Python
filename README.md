# NAP Checker with Google Places API on GCP

This project runs automated NAP (Name, Address, Phone) checks using Google Places API, deployed on **Google Cloud Run** and triggered daily via **Cloud Scheduler**.

---

## 📁 Project Structure

```
nap-checker/
├── Dockerfile
├── nap_audit_fuzzy_v2.py
├── requirements.txt
└── README.md
```

---

## ✅ What It Does
- Reads business data from a CSV file
- Uses Google Places API to search for each business
- Compares NAP data (name, address, phone)
- Uses fuzzy matching to handle minor differences
- Logs results into a `.csv` file or Google Cloud Storage

---

## ⚙️ Setup Instructions

### 1. **Create Google Cloud Project**
- Enable APIs: `Cloud Run`, `Cloud Build`, `Cloud Scheduler`, `Cloud Storage`, `Places API`

### 2. **Prepare Local Files**
- Add your script (`nap_audit_fuzzy_v2.py`)
- Create `requirements.txt`:
  ```
  pandas
  googlemaps
  fuzzywuzzy
  python-Levenshtein
  google-cloud-storage
  ```
- Use the provided `Dockerfile`

### 3. **Build and Deploy to Cloud Run**
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/nap-checker

gcloud run deploy nap-checker \
  --image gcr.io/YOUR_PROJECT_ID/nap-checker \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

> 🔗 Save the service URL.

### 4. **Set Up Cloud Scheduler**
```bash
gcloud scheduler jobs create http nap-check-daily \
  --schedule "0 9 * * *" \
  --uri "https://YOUR_CLOUD_RUN_URL" \
  --http-method GET \
  --time-zone "Asia/Kolkata"
```

---

## 💾 Optional: Write Output to Google Cloud Storage
Inside `nap_audit_fuzzy_v2.py`, replace:
```python
output_df.to_csv('nap_audit_results_fuzzy.csv', index=False)
```
with:
```python
from google.cloud import storage
client = storage.Client()
bucket = client.bucket('your-bucket-name')
blob = bucket.blob('results/nap_audit_results_fuzzy.csv')
blob.upload_from_string(output_df.to_csv(index=False), 'text/csv')
```

---

## 🔐 Secure Your API (Optional)
- Add API key verification or a signed JWT if you don't want it publicly triggered

---

## 🧪 Testing
You can test the service locally using Docker:
```bash
docker build -t nap-checker .
docker run --rm nap-checker
```

---

