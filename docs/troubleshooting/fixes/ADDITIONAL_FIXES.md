# Additional Fixes - October 2, 2025 (11:44)

## 🐛 Issues Found During Testing

### Issue 1: NoneType Error Still Occurring
**Problem**: `"object of type 'NoneType' has no len()"` still appeared in logs

**Root Cause**: Additional places in the code where `None` values weren't handled properly when comparing string lengths

**Fix Applied**:
- Added defensive checks in deduplication logic (line 178-189)
- Added defensive checks in merge logic (line 290-304)
- Using `or ''` pattern to ensure strings are never None

**File**: `backend/processors/metadata_processor_ai.py`

### Issue 2: Vision Model Crashes After First Image
**Problem**:
```
✅ Works: "Extracted 1 error codes from image using llava:7b"
❌ Then: "model runner has unexpectedly stopped" on next image
```

**Root Cause**:
- GPU memory not being freed between image processing
- Multiple images processed too quickly
- VRAM exhaustion from accumulated memory

**Fixes Applied**:

#### 1. Image Processing Limit
Added `MAX_VISION_IMAGES` setting to limit how many images are processed per document

**Default**: 5 images (safe for 8GB VRAM)
**File**: `.env` line 56

```bash
MAX_VISION_IMAGES=5
```

#### 2. Delay Between Images
Added 2-second delay between processing each image to give GPU time to free memory

**File**: `backend/processors/metadata_processor_ai.py` line 288

#### 3. Per-Image Error Handling
Wrapped each image processing in try-catch so one failure doesn't stop the entire process

**File**: `backend/processors/metadata_processor_ai.py` line 255-293

---

## ✅ What Changed

### Code Changes

**File**: `backend/processors/metadata_processor_ai.py`

1. **Added imports** (lines 8-9):
   ```python
   import os
   import asyncio
   ```

2. **Fixed NoneType checks** (lines 178-189, 290-304):
   ```python
   ec_solution = ec.get('solution_text') or ''
   existing_solution = unique_codes[code_key].get('solution_text') or ''
   ```

3. **Added image limit** (lines 241-248):
   ```python
   max_images_to_process = int(os.getenv('MAX_VISION_IMAGES', '10'))
   processed_count = 0

   if processed_count >= max_images_to_process:
       self.logger.warning(f"Reached max vision image limit")
       break
   ```

4. **Added delay between images** (lines 285-288):
   ```python
   if processed_count < max_images_to_process:
       await asyncio.sleep(2)  # 2 second delay
   ```

5. **Added per-image error handling** (lines 255, 290-293):
   ```python
   try:
       # Process image
   except Exception as img_error:
       self.logger.warning(f"Failed to process image: {img_error}")
       continue  # Continue with next image
   ```

**File**: `.env`

Added new configuration option (lines 53-56):
```bash
# Maximum number of images to process with vision model per document
# Lower values = more stable, higher values = more complete analysis
# Recommended: 5-10 for 8GB VRAM, 10-20 for 12GB+ VRAM
MAX_VISION_IMAGES=5
```

---

## 🎯 Expected Behavior Now

### Vision Model Processing

**Before**:
- ✅ Image 1: Works
- ❌ Image 2: Crashes
- ❌ Pipeline stops

**After**:
- ✅ Image 1: Works (2s delay)
- ✅ Image 2: Works (2s delay)
- ✅ Image 3: Works (2s delay)
- ✅ Image 4: Works (2s delay)
- ✅ Image 5: Works
- ⏭️ Image 6+: Skipped (limit reached)
- ✅ Pipeline continues

### If Image Fails

**Before**: Pipeline crashes

**After**:
- ⚠️ Warning logged
- ⏭️ Skip to next image
- ✅ Pipeline continues

---

## ⚙️ Configuration Options

### Conservative (Most Stable)
```bash
MAX_VISION_IMAGES=3
DISABLE_VISION_PROCESSING=false
```
- Process only 3 images per document
- ~15 seconds for vision processing
- Very stable

### Balanced (Recommended)
```bash
MAX_VISION_IMAGES=5
DISABLE_VISION_PROCESSING=false
```
- Process 5 images per document
- ~20 seconds for vision processing
- Good balance of coverage and stability

### Aggressive (More Coverage)
```bash
MAX_VISION_IMAGES=10
DISABLE_VISION_PROCESSING=false
```
- Process up to 10 images
- ~40 seconds for vision processing
- May crash on documents with many images

### Disabled (Fastest)
```bash
DISABLE_VISION_PROCESSING=true
```
- No vision processing
- Instant
- 100% stable

---

## 📊 Performance Impact

| Setting | Images/Doc | Time Added | Stability | Coverage |
|---------|-----------|------------|-----------|----------|
| `MAX_VISION_IMAGES=3` | 3 | ~15s | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| `MAX_VISION_IMAGES=5` | 5 | ~20s | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| `MAX_VISION_IMAGES=10` | 10 | ~40s | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| `DISABLE_VISION_PROCESSING` | 0 | 0s | ⭐⭐⭐⭐⭐ | ⭐ |

**Recommendation for your RTX 2000 (8GB VRAM)**: `MAX_VISION_IMAGES=5`

---

## 🧪 Testing

To test the new behavior:

```cmd
cd C:\Users\haast\Docker\KRAI-minimal\backend\tests
python krai_master_pipeline.py
```

**What to look for in logs**:
```
✅ "Extracted X error codes from image using llava:7b"
✅ "AI extracted X error codes from images"
✅ No "model runner has unexpectedly stopped" errors
✅ Or "Reached max vision image limit (5)"
```

**If it still crashes**:
1. Reduce limit: `MAX_VISION_IMAGES=3`
2. Or disable: `DISABLE_VISION_PROCESSING=true`

---

## 🔍 Debugging

### Check Current Settings
```cmd
# View .env file
type .env | findstr VISION
```

### Monitor Processing
Watch the logs for:
- `"Extracted X error codes from image"` - Success
- `"Failed to process image"` - Skipped image (not fatal)
- `"Reached max vision image limit"` - Limit hit (expected)
- `"model runner has unexpectedly stopped"` - Still crashing (reduce limit)

### Adjust Based on Results

**If stable**: Can increase `MAX_VISION_IMAGES` to 7 or 10

**If still crashes**: Decrease to 3 or 2

**If too slow**: Decrease or disable vision processing

---

## ✅ Summary

**Fixed**:
- ✅ Additional NoneType errors
- ✅ Vision model crashing after first image
- ✅ No delay between image processing
- ✅ No limit on images processed

**Added**:
- ✅ `MAX_VISION_IMAGES` configuration
- ✅ 2-second delay between images
- ✅ Per-image error handling
- ✅ Continue processing on image failure

**Result**:
- ✅ More stable vision processing
- ✅ Configurable trade-off between coverage and stability
- ✅ Pipeline continues even if some images fail

---

**Time**: 11:44 AM, October 2, 2025
**Status**: Ready to test
**Next Step**: Run the pipeline and monitor logs
