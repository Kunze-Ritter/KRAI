# 🚀 Quick Start: Content Management API

Fast guide to using the new video enrichment and link checking features.

---

## 🎯 **Prerequisites**

1. **Backend running:**
   ```bash
   cd backend
   python main.py
   ```

2. **YouTube API Key** (optional, for YouTube videos):
   ```bash
   # Add to .env file
   YOUTUBE_API_KEY=your_youtube_api_key_here
   ```

---

## 📹 **Video Enrichment**

### **Quick Test (10 videos):**
```bash
curl -X POST http://localhost:8000/content/videos/enrich/sync \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

### **Full Enrichment (all videos):**
```bash
curl -X POST http://localhost:8000/content/videos/enrich \
  -H "Content-Type: application/json" \
  -d '{}'
```

### **Check Results:**
```sql
-- In Supabase SQL Editor
SELECT
    COUNT(*) as total_videos,
    COUNT(video_id) as enriched,
    ROUND(100.0 * COUNT(video_id) / COUNT(*), 1) as percent_done
FROM krai_content.links
WHERE link_type IN ('video', 'youtube', 'vimeo', 'brightcove');
```

---

## 🔗 **Link Checking**

### **Quick Test (10 links):**
```bash
curl -X POST http://localhost:8000/content/links/check/sync \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "check_only": true}'
```

### **Fix Broken Links (50 at a time):**
```bash
curl -X POST http://localhost:8000/content/links/check/sync \
  -H "Content-Type: application/json" \
  -d '{"limit": 50, "check_only": false}'
```

---

## 📊 **Monitor Progress**

### **Swagger UI:**
Visit: http://localhost:8000/docs

### **Check Task Status:**
```bash
# Get task ID from initial response
TASK_ID="video_enrich_1728158400.123"

curl http://localhost:8000/content/tasks/$TASK_ID
```

---

## 🎨 **Python Client Example**

```python
import requests
import time

# Start video enrichment
response = requests.post(
    "http://localhost:8000/content/videos/enrich",
    json={"limit": 100}
)

task_id = response.json()["task_id"]
print(f"Task started: {task_id}")

# Poll for completion
while True:
    status = requests.get(f"http://localhost:8000/content/tasks/{task_id}")
    data = status.json()

    if data["status"] == "completed":
        print(f"✅ Done! Result: {data['result']}")
        break
    elif data["status"] == "failed":
        print(f"❌ Failed: {data['error']}")
        break

    print(f"⏳ Status: {data['status']}")
    time.sleep(5)
```

---

## 🔧 **Troubleshooting**

### **Service Not Available:**
```json
{
  "detail": "Video enrichment service not available"
}
```
**Fix:** Restart backend (`python main.py`)

### **YouTube API Error:**
```
YouTube quota exceeded
```
**Fix:** Wait 24 hours or upgrade quota

### **Import Error:**
```
ModuleNotFoundError: No module named 'enrich_video_metadata'
```
**Fix:** Scripts are in `/scripts` folder, path is auto-configured

---

## 📈 **Performance Tips**

### **Video Enrichment:**
- Use async endpoint for > 20 videos
- Limit YouTube to ~10,000/day (free quota)
- Brightcove/Vimeo have no quota limits

### **Link Checking:**
- Use sync endpoint for < 20 links
- Use async endpoint for > 50 links
- 0.5s delay between checks (automatic)

---

## 🎯 **Next Steps**

1. **Automate with N8N:** See `/n8n/workflows/`
2. **Schedule Daily:** Use cron or N8N schedule trigger
3. **Monitor Metrics:** Track enrichment % over time

---

## 📚 **Full Documentation**

- **API Docs:** `/backend/api/README_CONTENT_MANAGEMENT.md`
- **Scripts Docs:** `/scripts/README_VIDEO_ENRICHMENT.md`
- **Swagger UI:** http://localhost:8000/docs
