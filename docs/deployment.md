# Deployment — Streamlit Cloud

Steps to get this live on Streamlit Community Cloud (free tier, no credit card).

---

## 1. Push to GitHub

Make sure the repo is public and the code is committed:

```bash
git add .
git commit -m "ready for deployment"
git push origin main
```

The `.streamlit/config.toml` file needs to be in the repo — it controls the dark theme and port settings.

---

## 2. Connect to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with your GitHub account
3. Click **New app**
4. Select repo: `funstation-demand-forecaster`
5. Branch: `main`
6. Main file path: `app/streamlit_app.py`
7. Click **Deploy**

---

## 3. Wait for build (~2-3 minutes)

Streamlit Cloud installs from `requirements.txt` automatically. The first run will also execute the data pipeline to build the processed CSVs — this takes around 30 seconds and is cached after that.

If the scraping steps fail (gov.uk occasionally rate-limits bots), the app falls back to hardcoded 2025/2026 term date data automatically so it won't break.

---

## 4. Update the README with the live URL

Once deployed, grab the URL from Streamlit Cloud (format: `https://[username]-funstation-demand-forecaster-app-streamlit-app-[hash].streamlit.app`) and update the placeholder in README.md.

---

## Troubleshooting

**App crashes on startup**: Check the Streamlit Cloud logs for import errors. Most likely a package version conflict — try pinning `numpy` to `1.26.4` if there are `pandas` compatibility errors.

**Data not loading**: The `data/processed/` directory needs to be writable. On Streamlit Cloud this should work fine. If it doesn't, the app rebuilds from source on every cold start (slow but functional).

**Term date scraper errors**: gov.uk and mygov.scot occasionally restructure their pages. If scraping fails, the fallback hardcoded data activates — check the app logs and file an issue if the fallback is visibly wrong (e.g. wrong Easter dates).

---

## Alternative: run locally with Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:
```bash
docker build -t funstation-forecaster .
docker run -p 8501:8501 funstation-forecaster
```
