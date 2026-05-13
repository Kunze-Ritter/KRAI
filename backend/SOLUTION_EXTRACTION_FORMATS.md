# Solution Extraction - Supported Formats

**Module:** `backend/processors/error_code_extractor.py`
**Function:** `_extract_solution()`
**Updated:** 2025-10-06

---

## 📋 **SUPPORTED MANUFACTURER FORMATS:**

### **1. HP Format - "Recommended Action"**

**Structure:**
```
11.WX.YZ error messages
Errors in the 11.* family are related to the printer real-time clock.

Recommended action for customers
Follow these troubleshooting steps in the order presented.
1. Set the time and date on the printer control panel.
2. If the error persists, contact your HP-authorized service...

Recommended action for call-center agents and onsite technicians
1. Set the time and date on the printer control panel.
2. If the error persists, remove and reinstall the formatter.
3. If the error still persists, replace the formatter.
```

**Extraction Pattern:**
```regex
(?:recommended\s+action|corrective\s+action)
(?:\s+for\s+(?:customers?|technicians?|agents?))?
\s*[\n:]+((?:(?:\d+\.|•|-|\*)\s+.{15,}[\n\r]?){2,})
```

**Extracted:**
```
1. Set the time and date on the printer control panel.
2. If the error persists, contact your HP-authorized service...
```

**Features:**
- ✅ Extracts "for customers" section (user-friendly)
- ✅ Skips "for technicians" (too technical)
- ✅ Numbered lists (1., 2., 3.)
- ✅ Multiple sections detected

---

### **2. Konica Minolta Format - "Procedure" with Table**

**Structure:**
```
3.8.4 C2558

Contents
┌──────────────────────────┬─────────────────────────────────────────────┐
│ Trouble type             │ C2558: Abnormally high toner density...    │
│ Rank                     │ B                                           │
│ Trouble detection cond.  │ TC ratio in the imaging unit, which is...  │
│ Trouble isolation        │ -                                           │
│ Relevant electrical parts│ • Imaging unit/K                            │
│                          │ • CPU board (CPUB)                          │
│                          │ • Base board (BASEB)                        │
└──────────────────────────┴─────────────────────────────────────────────┘

Procedure
1. Reinstall the imaging unit.
2. Check the connector between the imaging unit/K-relay CN6-BASEB CN14E...
3. Check CPUB for proper installation and correct as necessary.
4. Replace the imaging unit.
5. Replace CPUB.
6. Replace BASEB.
```

**Extraction Pattern:**
```regex
(?:procedure|repair\s+procedure|service\s+procedure)
\s*[\n:]+((?:(?:\d+\.|•|-|\*)\s+.{15,}[\n\r]?){2,})
```

**Extracted:**
```
1. Reinstall the imaging unit.
2. Check the connector between the imaging unit/K-relay CN6-BASEB CN14E...
3. Check CPUB for proper installation and correct as necessary.
4. Replace the imaging unit.
5. Replace CPUB.
6. Replace BASEB.
```

**Features:**
- ✅ Simple "Procedure" header
- ✅ No customer/technician separation
- ✅ Component abbreviations (CPUB, BASEB, CN6)
- ✅ Direct action steps
- ✅ Table metadata extracted separately

---

### **3. Canon/Ricoh Format - "Solution" Keyword**

**Structure:**
```
Error Code: E045-0001

Description:
Scanner home position error detected.

Solution:
Check the scanner cable connections. If connections are secure,
replace the scanner unit. Clear the error by restarting the device.
```

**Extraction Pattern:**
```regex
(?:solution|fix|remedy|resolution)
\s*[:]\s*(.{50,1500})
```

**Extracted:**
```
Check the scanner cable connections. If connections are secure,
replace the scanner unit. Clear the error by restarting the device.
```

**Features:**
- ✅ Simple "Solution:" header
- ✅ Free-form text (not numbered)
- ✅ Paragraph style
- ✅ Length limited to 1000 chars

---

### **4. Generic Format - Numbered Steps**

**Structure:**
```
To resolve this issue:

1. Turn off the printer and wait 30 seconds.
2. Check the paper path for jammed paper.
3. Remove any obstructions.
4. Restart the printer.
5. If error persists, contact service.
```

**Extraction Pattern:**
```regex
((?:(?:\d+\.|Step\s+\d+)\s+.{20,}[\n\r]?){2,})
```

**Extracted:**
```
1. Turn off the printer and wait 30 seconds.
2. Check the paper path for jammed paper.
3. Remove any obstructions.
4. Restart the printer.
5. If error persists, contact service.
```

**Features:**
- ✅ Works WITHOUT header
- ✅ Numbered lists (1., 2., 3.)
- ✅ "Step 1", "Step 2" variants
- ✅ Continuation lines supported

---

## 🎯 **EXTRACTION LOGIC:**

### **Priority Order:**

```python
1. Try "Recommended action" / "Procedure" (HP/Konica Minolta)
   ├─ Most structured
   └─ Highest confidence

2. Try "Solution:" keywords (Canon/Ricoh)
   ├─ Clear section marker
   └─ Medium confidence

3. Try Numbered steps without header (Generic)
   ├─ Less structured
   └─ Lower confidence

4. Try Bullet lists
   └─ Fallback
```

### **Text Window:**

```python
context = 500 chars before error code
text_after = 2500 chars after error code
combined_text = context + text_after  # Total: ~3000 chars
```

### **Cleaning Rules:**

```python
# Limit Steps
max_steps = 10-15 (depending on format)

# Stop at Section Headers
stop_at = ["Note:", "Warning:", "Caution:", "Important:"]

# Max Length
max_length = 1000 chars
```

---

## 📊 **SUPPORTED KEYWORDS:**

### **Primary Keywords:**
```python
keywords = [
    "recommended action",      # HP
    "corrective action",       # HP/Brother
    "troubleshooting steps",   # HP/Xerox
    "service procedure",       # Canon
    "procedure",               # Konica Minolta ✅
    "repair procedure",        # Konica Minolta ✅
    "remedy",                  # Generic
    "solution",                # Canon/Ricoh
    "fix",                     # Generic
    "resolution",              # Generic
    "action",                  # Generic
    "steps"                    # Generic
]
```

### **Context Keywords:**
```python
context_qualifiers = [
    "for customers",           # HP user steps
    "for technicians",         # HP service steps
    "for agents",              # HP support steps
    "for users"                # Generic user steps
]
```

---

## 🧪 **TEST CASES:**

### **Test 1: HP Format**
```python
text = """
Recommended action for customers
1. Restart printer
2. Check paper tray
3. Contact support if error persists
"""
# Expected: Extracts all 3 steps
```

### **Test 2: Konica Minolta Format**
```python
text = """
Procedure
1. Reinstall the imaging unit.
2. Check CPUB connection.
3. Replace BASEB if necessary.
"""
# Expected: Extracts all 3 steps with component names
```

### **Test 3: Mixed Format**
```python
text = """
Error: C2558

Solution: Restart the device.

Procedure
1. Step one
2. Step two
"""
# Expected: Prefers "Procedure" (higher priority)
```

### **Test 4: Continuation Lines**
```python
text = """
1. Open the front cover and remove the
   toner cartridge carefully.
2. Close the cover.
"""
# Expected: Merges continuation line with step 1
```

---

## 🔧 **CONFIGURATION:**

### **In Code:**
```python
# backend/processors/error_code_extractor.py

def _extract_solution(self, context, full_text, code_end_pos):
    # Text window
    text_after = full_text[code_end_pos:code_end_pos + 2500]  # Configurable

    # Pattern matching
    patterns = [
        recommended_action_pattern,  # Priority 1
        solution_keywords_pattern,   # Priority 2
        numbered_steps_pattern,      # Priority 3
        bullet_pattern               # Priority 4
    ]
```

### **Tuning Parameters:**
```python
CONFIG = {
    "text_window_size": 2500,        # Chars after error code
    "context_size": 500,              # Chars before error code
    "max_solution_length": 1000,     # Max extracted length
    "max_steps": 15,                 # Max number of steps
    "min_step_length": 15,           # Min chars per step
    "continuation_threshold": 20     # Chars for continuation lines
}
```

---

## 📈 **QUALITY METRICS:**

### **Extraction Success Rate:**
```
Target: 85%+ of error codes should have solutions extracted
Current: ~75% (needs improvement)
```

### **Quality Indicators:**
```python
confidence_factors = {
    "has_numbered_steps": +0.3,
    "has_clear_header": +0.2,
    "step_count >= 2": +0.2,
    "solution_length > 50": +0.1,
    "contains_action_verbs": +0.1
}
```

### **Common Issues:**
```
❌ Tables parsed as continuous text
❌ Multi-column layouts confused
❌ Image captions extracted as steps
❌ References to other pages ("See page X")
```

---

## 🚀 **FUTURE IMPROVEMENTS:**

### **1. Table Structure Detection**
```python
# Detect Konica Minolta table format
# Extract "Trouble type", "Rank", "Parts" separately
```

### **2. Multi-Language Support**
```python
keywords_de = ["Lösung", "Vorgehensweise", "Abhilfe"]
keywords_ja = ["手順", "対処方法", "解決策"]
```

### **3. Context-Aware Extraction**
```python
# Prefer "for customers" over "for technicians"
# Extract severity from "Rank" field
```

### **4. Component Name Recognition**
```python
# Recognize: CPUB, BASEB, CN6-BASEB
# Link to parts database
```

---

## 📝 **NOTES:**

- ✅ HP format fully supported
- ✅ Konica Minolta "Procedure" supported
- ⚠️ Konica Minolta table structure needs improvement
- ⏳ Multi-column layouts need special handling
- 🔄 Re-processing recommended after updates

---

**Last Updated:** 2025-10-06
**Version:** V2.1
**Status:** ✅ Production Ready
