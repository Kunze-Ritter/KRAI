# Error Code Pattern Configuration Guide

**Version:** 2.0
**Last Updated:** 2025-10-06

---

## 📋 **OVERVIEW**

Error code patterns are manufacturer-specific regex patterns used to extract error codes from service manuals. Each manufacturer has unique error code formats that must be configured separately to avoid false positives.

**Why manufacturer-specific patterns?**
- ✅ Prevents false positives (part numbers, model numbers)
- ✅ Higher accuracy and confidence
- ✅ Better validation
- ✅ Cleaner extracted data

---

## 📁 **CONFIGURATION FILE**

**Location:** `backend/config/error_code_patterns.json`

**Structure:**
```json
{
  "manufacturer_key": {
    "manufacturer_name": "Display Name",
    "description": "Brief description",
    "format": "Error code format description",
    "patterns": [...regex patterns...],
    "validation_regex": "Validation pattern",
    "categories": {...error categories...}
  },
  "extraction_rules": {...global rules...}
}
```

---

## 🎯 **PATTERN FORMAT**

### **Required Fields:**

```json
{
  "manufacturer_name": "HP",           // Display name
  "description": "HP error codes",     // Brief description
  "format": "XX.XX.XX or XX.XX",       // Human-readable format
  "patterns": [                        // Regex patterns (array)
    "error\\s+code\\s+(\\d{2}\\.\\d{2}\\.\\d{2})",
    "\\b(\\d{2}\\.\\d{2}\\.\\d{2})\\b"
  ],
  "validation_regex": "^\\d{2}\\.\\d{2}(?:\\.\\d{2})?$",  // Validation
  "categories": {                      // Error categories
    "paper_jam": "Paper handling errors",
    "fuser": "Fuser assembly errors"
  }
}
```

---

## 🔤 **REGEX PATTERNS**

### **Pattern Types:**

**1. With Context (Preferred):**
```regex
error\s+code\s+([A-Z]\d{4})
```
- Matches: "error code C1234"
- Higher confidence
- Less false positives

**2. Standalone (Fallback):**
```regex
\b([A-Z]\d{4})\b
```
- Matches: "C1234" anywhere
- Lower confidence
- More false positives

**3. Multiple Formats:**
```regex
\b(\d{2}\.\d{2}(?:\.\d{2})?)\b
```
- Matches: "10.26" OR "10.26.15"
- Flexible matching

---

## 📝 **COMMON FORMATS BY MANUFACTURER**

### **HP:**
```
Format: XX.XX.XX or XX.XX
Examples: 10.26.15, 13.10, 49.38.07
Wildcards: 10.0x.15 (family codes)

Patterns:
  \b(\d{2}\.\d{2}\.\d{2})\b
  \b(\d{2}\.\d{2})\b
  \b(\d{2}\.\dx\.\d{2})\b    // Wildcard support

Validation: ^\d{2}\.\d{2}(?:\.\d{2})?$|^\d{2}\.\d[xX]\.\d{2}$
```

### **Konica Minolta:**
```
Format: C####, J##-##, ##.##, E##-##
Examples: C3425, J01-02, 10.14, E01-02

Patterns:
  \b([CJ]\d{4,5})\b
  \b([CJ]\d{2}-\d{2})\b
  \b(\d{2}\.\d{2})\b
  \b(E\d{2}-\d{2})\b

Validation: ^[CJ]\d{4,5}$|^[CJ]\d{2}-\d{2}$|^\d{2}\.\d{2}$|^E\d{2}-\d{2}$
```

### **Canon:**
```
Format: E### or ####
Examples: E045, E045-0001, #001

Patterns:
  \b(E\d{3,4})\b
  \b(#\d{3})\b

Validation: ^E\d{3,4}$|^#\d{3}$
```

### **Ricoh:**
```
Format: SC###
Examples: SC990, SC123

Patterns:
  \b(SC\d{3,4})\b

Validation: ^SC\d{3,4}$
```

---

## 🛠️ **CREATING NEW PATTERNS**

### **Method 1: Copy from Existing (Rebrands)**

Many manufacturers are rebrands:
- UTAX / TA Triumph-Adler → Kyocera
- Olivetti / Develop → Konica Minolta
- Gestetner / Lanier / Savin / NRG → Ricoh
- Muratec → Brother

**Command:**
```bash
python scripts/create_manufacturer_patterns.py \
  --name UTAX \
  --based-on kyocera
```

---

### **Method 2: Interactive Wizard**

**Command:**
```bash
python scripts/create_manufacturer_patterns.py \
  --name "New Manufacturer" \
  --interactive
```

**Steps:**
1. Enter error code format (e.g., "C####")
2. Provide 3-5 example codes
3. Script generates patterns automatically
4. Test against examples
5. Save to config

---

### **Method 3: Manual Configuration**

**1. Collect Examples:**
```
Find 5-10 error codes from manual:
  C1234, C5678, E01-02, etc.
```

**2. Identify Pattern:**
```
C#### = [A-Z]\d{4}
E##-## = [A-Z]\d{2}-\d{2}
##.## = \d{2}\.\d{2}
```

**3. Create Regex:**
```regex
// With context (preferred)
error\s+code\s+([A-Z]\d{4})

// Standalone (fallback)
\b([A-Z]\d{4})\b
```

**4. Create Validation:**
```regex
^[A-Z]\d{4}$
```

**5. Add to Config:**
```json
"new_manufacturer": {
  "manufacturer_name": "New Manufacturer",
  "description": "Error code patterns",
  "format": "C####",
  "patterns": [
    "error\\s+code\\s+([A-Z]\\d{4})",
    "\\b([A-Z]\\d{4})\\b"
  ],
  "validation_regex": "^[A-Z]\\d{4}$",
  "categories": {
    "system": "System errors"
  }
}
```

---

## 🧪 **TESTING PATTERNS**

### **Test Script:**
```bash
python scripts/test_error_code_extraction.py \
  --pdf "path/to/manual.pdf" \
  --manufacturer new_manufacturer \
  --output test_results.txt
```

### **What to Check:**
```
✅ Extraction Rate: >70% of visible codes found
✅ False Positives: <10% (no part numbers, model numbers)
✅ Confidence: >0.75 average
✅ Solutions: >70% have solution text
```

### **Common Issues:**

**Issue 1: Too Many False Positives**
```
Problem: Part numbers matched (W9210, JC44-00249A)
Fix: Make patterns more specific, add context requirements
```

**Issue 2: Missing Codes**
```
Problem: Codes not extracted
Fix: Add more pattern variations, check validation regex
```

**Issue 3: Low Confidence**
```
Problem: Confidence <0.70
Fix: Add context keywords, improve description extraction
```

---

## 📊 **VALIDATION REGEX**

**Purpose:** Final validation of extracted codes

**Examples:**

**Exact Match:**
```regex
^C\d{4}$              // Exactly C followed by 4 digits
```

**Multiple Formats:**
```regex
^C\d{4}$|^E\d{2}-\d{2}$   // C#### OR E##-##
```

**Optional Parts:**
```regex
^\d{2}\.\d{2}(?:\.\d{2})?$   // XX.XX or XX.XX.XX
```

**Wildcards:**
```regex
^\d{2}\.\d[xX]\.\d{2}$        // XX.Xx.XX (10.0x.15)
```

---

## 🎨 **CATEGORIES**

**Purpose:** Classify errors by type

**Common Categories:**
```json
{
  "paper_jam": "Paper handling and jam errors",
  "fuser": "Fuser assembly and temperature errors",
  "scanner": "Scanner and imaging errors",
  "toner": "Toner cartridge errors",
  "drum": "Drum unit errors",
  "laser": "Laser unit errors",
  "motor": "Motor and mechanical errors",
  "system": "System and controller errors",
  "memory": "Memory and storage errors",
  "communication": "Communication errors"
}
```

---

## ⚙️ **EXTRACTION RULES**

**Global settings for all manufacturers:**

```json
"extraction_rules": {
  "min_confidence": 0.75,           // Minimum confidence to accept
  "max_codes_per_page": 15,         // Max codes per page (prevent spam)
  "context_window_chars": 200,      // Context size for validation

  "require_context_keywords": [     // Must have at least one
    "error", "code", "fault", "trouble", "troubleshooting"
  ],

  "exclude_if_near": [               // Reject if these nearby
    "page", "figure", "table", "section"
  ]
}
```

---

## 🚨 **ERROR HANDLING**

### **Missing Manufacturer Pattern:**

When processing a PDF without configured patterns:

```
╔═══════════════════════════════════════════════════════════╗
║  ❌ ERROR: Manufacturer Pattern Not Found                 ║
╠═══════════════════════════════════════════════════════════╣
║  Manufacturer: UTAX                                       ║
║  Stage: Error Code Extraction                             ║
║                                                           ║
║  🔧 SOLUTIONS:                                            ║
║  1. Copy from existing (if rebrand)                       ║
║  2. Create interactively                                  ║
║  3. Manual configuration                                  ║
║                                                           ║
║  📚 See: backend/docs/ERROR_CODE_PATTERNS.md              ║
╚═══════════════════════════════════════════════════════════╝
```

**Processing stops** - User must add patterns before continuing.

---

## 📚 **EXAMPLES**

### **Example 1: Simple Format**
```json
"brother": {
  "manufacturer_name": "Brother",
  "format": "## or E##",
  "patterns": [
    "error\\s+code\\s+(E\\d{2})",
    "\\b(E\\d{2})\\b",
    "\\b(\\d{2})\\b(?=\\s*(error|code))"
  ],
  "validation_regex": "^E\\d{2}$|^\\d{2}$"
}
```

### **Example 2: Multiple Formats**
```json
"konica_minolta": {
  "manufacturer_name": "Konica Minolta",
  "format": "C####, J##-##, ##.##, E##-##",
  "patterns": [
    "\\b([CJ]\\d{4,5})\\b",
    "\\b([CJ]\\d{2}-\\d{2})\\b",
    "\\b(\\d{2}\\.\\d{2})\\b",
    "\\b(E\\d{2}-\\d{2})\\b"
  ],
  "validation_regex": "^[CJ]\\d{4,5}$|^[CJ]\\d{2}-\\d{2}$|^\\d{2}\\.\\d{2}$|^E\\d{2}-\\d{2}$"
}
```

### **Example 3: Wildcard Support**
```json
"hp": {
  "manufacturer_name": "HP",
  "format": "XX.XX.XX or XX.XX or XX.Xx.XX (x=wildcard)",
  "patterns": [
    "\\b(\\d{2}\\.\\dx\\.\\d{2})\\b",     // 10.0x.15
    "\\b(\\d{2}\\.\\dX\\.\\d{2})\\b",     // 10.0X.15
    "\\b(\\d{2}\\.\\d{2}\\.\\d{2})\\b",   // 10.26.15
    "\\b(\\d{2}\\.\\d{2})\\b"             // 10.26
  ],
  "validation_regex": "^\\d{2}\\.\\d[xX]\\.\\d{2}$|^\\d{2}\\.\\d{2}(?:\\.\\d{2})?$"
}
```

---

## 🔍 **DEBUGGING**

### **Pattern Not Matching:**

**1. Test Regex:**
```python
import re
pattern = r'\b(C\d{4})\b'
text = "Error code C1234 occurred"
match = re.search(pattern, text)
print(match.group(1) if match else "No match")
```

**2. Check Validation:**
```python
validation = r'^C\d{4}$'
code = "C1234"
valid = bool(re.match(validation, code))
print(f"Valid: {valid}")
```

**3. Test Context:**
```python
# Check if context keywords present
context = "Error code C1234: Fuser malfunction"
keywords = ["error", "code", "fault"]
has_keyword = any(kw in context.lower() for kw in keywords)
print(f"Has keyword: {has_keyword}")
```

---

## 📖 **BEST PRACTICES**

1. **Start Specific, Then Broaden**
   - Begin with context patterns (`error\s+code\s+...`)
   - Add standalone patterns as fallback

2. **Test Thoroughly**
   - Test with real PDFs
   - Check for false positives
   - Verify solution extraction

3. **Use Validation**
   - Always include validation_regex
   - Be strict to avoid false positives

4. **Document Format**
   - Clear format description
   - Include examples in description

5. **Categorize Errors**
   - Add meaningful categories
   - Helps with error classification

---

## 🆘 **SUPPORT**

**Questions?**
- See: `backend/scripts/ERROR_CODE_TESTING.md`
- Run: `python scripts/create_manufacturer_patterns.py --help`
- Check: Existing patterns in `error_code_patterns.json`

**Issues?**
- Test extraction with debug logging
- Check pattern matching manually
- Verify validation regex

---

**Last Updated:** 2025-10-06
**Version:** 2.0
