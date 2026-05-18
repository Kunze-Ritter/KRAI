# Error Code Extraction Testing

**Script:** `test_error_code_extraction.py`
**Purpose:** Test and optimize error code extraction across different manufacturers

---

## 🚀 **QUICK START:**

### **Test Single PDF:**
```powershell
cd backend
python scripts/test_error_code_extraction.py --pdf "path/to/manual.pdf" --manufacturer konica_minolta
```

### **Test All PDFs in Directory:**
```powershell
python scripts/test_error_code_extraction.py --directory "C:/Manuals" --output test_results.txt
```

### **Test Specific Manufacturer:**
```powershell
python scripts/test_error_code_extraction.py --directory "C:/Manuals/HP" --manufacturer hp
```

---

## 📋 **SUPPORTED MANUFACTURERS:**

```
hp              - HP/Hewlett Packard
canon           - Canon
konica_minolta  - Konica Minolta (bizhub)
ricoh           - Ricoh
brother         - Brother
xerox           - Xerox
lexmark         - Lexmark
kyocera         - Kyocera
sharp           - Sharp
epson           - Epson
generic         - Unknown/Generic manufacturer
```

---

## 🧪 **TEST SCENARIOS:**

### **Scenario 1: Konica Minolta TROUBLESHOOTING Section**

**Files:**
- `bizhub_4750i_SM.pdf`
- `AccurioPress_C4070_SM.pdf`

**Expected:**
- Error codes in table format (Contents table)
- "Procedure" sections with numbered steps
- Multiple codes per section (C3722, C3725)
- Component names (CPUB, BASEB, DCPS)

**Test:**
```powershell
python scripts/test_error_code_extraction.py `
  --pdf "C:/Manuals/bizhub_4750i_SM.pdf" `
  --manufacturer konica_minolta `
  --output km_test_results.txt
```

**Check for:**
- ✅ All error codes extracted
- ✅ Solutions include all steps (1., 1), 2), ...)
- ✅ Multi-page procedures captured
- ✅ Component names preserved

---

### **Scenario 2: HP "Recommended Action" Format**

**Files:**
- `HP_M604_SM.pdf`
- `HP_LaserJet_Enterprise_M607_SM.pdf`

**Expected:**
- Error codes like "11.WX.YZ" or "13.XX.YY"
- "Recommended action for customers" sections
- Separate technician procedures
- Clear numbered steps

**Test:**
```powershell
python scripts/test_error_code_extraction.py `
  --pdf "C:/Manuals/HP_M604_SM.pdf" `
  --manufacturer hp `
  --output hp_test_results.txt
```

**Check for:**
- ✅ Customer actions preferred over technician
- ✅ Multiple sections handled
- ✅ Error families (11.*, 13.*) recognized

---

### **Scenario 3: Canon/Ricoh Simple Format**

**Files:**
- `Canon_iR_ADV_C5500_SM.pdf`
- `Ricoh_MP_C3004_SM.pdf`

**Expected:**
- Error codes like "E045-0001" or "SC990"
- "Solution:" keyword
- Free-form text solutions

**Test:**
```powershell
python scripts/test_error_code_extraction.py `
  --directory "C:/Manuals/Canon" `
  --manufacturer canon `
  --output canon_test_results.txt
```

---

## 📊 **INTERPRETING RESULTS:**

### **Report Sections:**

**1. Summary:**
```
Total PDFs tested:        5
Total error codes found:  234
Unique error codes:       187
Codes with solutions:     156 (66.7%)
Average confidence:       0.78
```

**Metrics:**
- `error_codes_found`: Total codes extracted (includes duplicates)
- `unique_codes`: Distinct error codes
- `with_solution`: Codes that have solution_text
- `avg_confidence`: Average extraction confidence (0.0-1.0)

**Target Goals:**
- ✅ Solution rate: >70%
- ✅ Confidence: >0.75
- ✅ Unique rate: >80% (less duplicates)

---

**2. Per-PDF Results:**
```
1. bizhub_4750i_SM
   Manufacturer:    konica_minolta
   Pages:           850
   Codes found:     123 (98 unique)
   With solutions:  89 (72.4%)
   Avg confidence:  0.81

   Top codes:
     [✓] C3722 (p.456, conf: 0.85)
     [✓] C3725 (p.456, conf: 0.85)
     [✗] C2558 (p.234, conf: 0.72)
```

**Look for:**
- ✅ High solution rate (>70%)
- ✅ Confidence >0.75
- ✗ Missing solutions → Check pattern matching
- ✗ Low confidence → Check false positives

---

## 🔧 **TUNING PARAMETERS:**

### **File:** `backend/config/error_code_patterns.json`

**Current Settings:**
```json
{
  "extraction_rules": {
    "min_confidence": 0.75,
    "max_codes_per_page": 15,
    "context_window_chars": 200
  }
}
```

**Tuning Guide:**

| Setting | Current | Too Many False Positives | Missing Real Codes |
|---------|---------|-------------------------|-------------------|
| min_confidence | 0.75 | Increase to 0.80 | Decrease to 0.70 |
| max_codes_per_page | 15 | Decrease to 10 | Increase to 20 |
| context_window_chars | 200 | Increase to 300 | Decrease to 150 |

---

### **File:** `backend/processors/error_code_extractor.py`

**Solution Extraction Settings:**
```python
# Line 329: Text window size
text_after = full_text[code_end_pos:code_end_pos + 5000]

# Line 346: Max steps
for line in lines[:20]:

# Line 393: Max numbered steps
for line in lines[:15]:
```

**Tuning:**
- **text_after**: 5000 → 7500 (for very long procedures)
- **max steps**: 20 → 25 (for complex multi-step procedures)

---

## 🎯 **TESTING WORKFLOW:**

### **Step 1: Baseline Test**
```powershell
# Test current settings
python scripts/test_error_code_extraction.py `
  --directory "C:/Manuals/KonicaMinolta" `
  --manufacturer konica_minolta `
  --output baseline_test.txt
```

**Review:**
- Note solution rate
- Note confidence scores
- Identify problems

---

### **Step 2: Adjust Settings**

**Example: Increase solution extraction:**
```python
# In error_code_extractor.py Line 329
text_after = full_text[code_end_pos:code_end_pos + 7500]  # Was: 5000
```

---

### **Step 3: Re-Test**
```powershell
python scripts/test_error_code_extraction.py `
  --directory "C:/Manuals/KonicaMinolta" `
  --manufacturer konica_minolta `
  --output improved_test.txt
```

---

### **Step 4: Compare Results**
```powershell
# Compare reports
fc baseline_test.txt improved_test.txt

# Or view side-by-side
code --diff baseline_test.txt improved_test.txt
```

---

## 📁 **SAMPLE TEST STRUCTURE:**

```
C:/Manuals/
├── HP/
│   ├── HP_M604_SM.pdf
│   ├── HP_M607_SM.pdf
│   └── HP_LaserJet_Enterprise_M612_SM.pdf
│
├── KonicaMinolta/
│   ├── bizhub_4750i_SM.pdf
│   ├── bizhub_4050i_SM.pdf
│   ├── AccurioPress_C4070_SM.pdf
│   └── AccurioPress_C4080_SM.pdf
│
├── Canon/
│   ├── Canon_iR_ADV_C5500_SM.pdf
│   └── Canon_imageRUNNER_ADVANCE_DX_C5800_SM.pdf
│
└── Ricoh/
    ├── Ricoh_MP_C3004_SM.pdf
    └── Ricoh_MP_C6004_SM.pdf
```

**Test All:**
```powershell
# Test each manufacturer
foreach ($mfr in @("HP", "KonicaMinolta", "Canon", "Ricoh")) {
    python scripts/test_error_code_extraction.py `
      --directory "C:/Manuals/$mfr" `
      --output "test_results_$mfr.txt"
}
```

---

## 🐛 **COMMON ISSUES & FIXES:**

### **Issue 1: No Solutions Extracted**

**Symptoms:**
```
With solutions:  0 (0.0%)
```

**Causes:**
- "Procedure" keyword not found
- Text window too small
- Steps format not recognized

**Debug:**
```python
# Add logging in error_code_extractor.py Line 340
logger.debug(f"Looking for procedure in: {combined_text[:500]}")
```

**Fixes:**
- Check if "Procedure" exists in PDF
- Increase text_after window
- Add new pattern keyword

---

### **Issue 2: Too Many False Positives**

**Symptoms:**
```
Codes found:     456 (123 unique)  # Too many duplicates
Avg confidence:  0.62               # Low confidence
```

**Causes:**
- Patterns too broad
- Page numbers matched as codes
- Context validation insufficient

**Fixes:**
```json
// In error_code_patterns.json
{
  "extraction_rules": {
    "min_confidence": 0.80,      // Increase from 0.75
    "max_codes_per_page": 10     // Decrease from 15
  }
}
```

---

### **Issue 3: Multi-Code Sections Not Handled**

**Symptoms:**
```
C3722, C3725 → Only C3722 extracted
```

**Current:** Each code extracted separately
**Workaround:** Both codes will get extracted if on same page
**Fix Needed:** Detect "C3722, C3725" pattern and create 2 entries

---

## 📈 **QUALITY METRICS:**

### **Target Quality:**

| Metric | Target | Good | Needs Work |
|--------|--------|------|------------|
| Solution Rate | >70% | >80% | <60% |
| Confidence | >0.75 | >0.80 | <0.70 |
| False Positives | <10% | <5% | >15% |
| Unique Ratio | >80% | >90% | <70% |

### **Manufacturer-Specific Targets:**

**Konica Minolta:**
- Solution rate: >75% (structured procedures)
- Confidence: >0.80 (clear table format)

**HP:**
- Solution rate: >70% (multiple sections)
- Confidence: >0.75 (varied formats)

**Canon/Ricoh:**
- Solution rate: >60% (simpler format)
- Confidence: >0.75

---

## 🔄 **CONTINUOUS IMPROVEMENT:**

### **After Each Test:**

1. **Review** low-confidence codes
2. **Check** missing solutions
3. **Identify** false positives
4. **Adjust** patterns/settings
5. **Re-test** with same PDFs
6. **Compare** results
7. **Document** improvements

---

## 📝 **NOTES:**

- ✅ Konica Minolta: TROUBLESHOOTING section is key
- ✅ HP: Multiple "Recommended action" sections
- ✅ Multi-page procedures: Need 5000+ char window
- ✅ Sub-steps (1), 2)): Now supported
- ⏳ Table parsing: Needs improvement
- ⏳ Multi-code detection: Not yet implemented

---

**Last Updated:** 2025-10-06
**Version:** V2.1
