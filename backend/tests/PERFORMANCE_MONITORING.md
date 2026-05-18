# 📊 Performance Monitoring

**Real-time Performance-Tracking für KRAI Pipeline**

---

## 🚀 Quick Start

### **Option A: Automatisch (Empfohlen)**

```bash
cd backend/tests
run_with_monitoring.bat
```

Das öffnet **2 Fenster**:
1. **Performance Monitor** - Real-time Anzeige
2. **Pipeline** - Wähle Option 9

### **Option B: Manuell**

```bash
# Terminal 1: Performance Monitor
cd backend/tests
python performance_monitor.py

# Terminal 2: Pipeline
cd backend/tests
python krai_master_pipeline.py
# Wähle Option 9
```

---

## 📈 Was wird überwacht?

### **System Metrics**
- ✅ **CPU**: Auslastung (gesamt + per core), Frequenz
- ✅ **RAM**: Verbrauch, Prozent, verfügbar
- ✅ **GPU**: Auslastung, VRAM, Temperatur (wenn verfügbar)
- ✅ **Disk I/O**: Read/Write MB/s
- ✅ **Network**: Sent/Received MB/s

### **Process Metrics**
- ✅ **Process Memory**: Pipeline RAM-Verbrauch
- ✅ **Process CPU**: Pipeline CPU-Nutzung
- ✅ **Threads**: Anzahl aktiver Threads

---

## 📊 Real-time Ausgabe

```
⏱️  00:05:23 | CPU:  45.3% | RAM:  65.2% (10.4GB) | GPU:  78.5% (6234MB) | Disk: R:2.3 W:1.8 MB/s
```

**Was bedeutet das?**
- ⏱️ `00:05:23` - Laufzeit (5 Min 23 Sek)
- 💻 `CPU: 45.3%` - CPU Auslastung
- 🧠 `RAM: 65.2%` - RAM Auslastung (10.4 GB verwendet)
- 🎮 `GPU: 78.5%` - GPU Auslastung (6234 MB VRAM)
- 💾 `Disk: R:2.3 W:1.8` - Disk Read/Write MB/s

---

## 📁 Output Files

### **performance_log.json**
Enthält alle Samples im JSON-Format:
```json
{
  "start_time": "2025-10-02T10:30:00",
  "samples": [
    {
      "timestamp": "2025-10-02T10:30:01",
      "cpu": {"total_percent": 45.3, ...},
      "memory": {"percent": 65.2, "used_gb": 10.4},
      "gpu": {"gpu_percent": 78.5, ...}
    }
  ]
}
```

---

## 🔍 Analyse nach Verarbeitung

```bash
cd backend/tests
python analyze_performance.py
```

**Erwartete Ausgabe:**

```
================================================================================
📊 PERFORMANCE ANALYSIS REPORT
================================================================================

📅 Start Time: 2025-10-02T10:30:00
📊 Total Samples: 1234
⏱️  Duration: 1234.5 seconds (20.6 minutes)

--------------------------------------------------------------------------------
💻 CPU PERFORMANCE
--------------------------------------------------------------------------------
Average:   45.3%
Min:       12.1%
Max:       89.7%

Usage Distribution:
  Low (<30%):      234 samples ( 19.0%)
  Medium (30-70%):  856 samples ( 69.4%)
  High (>70%):      144 samples ( 11.7%)

--------------------------------------------------------------------------------
🧠 MEMORY PERFORMANCE
--------------------------------------------------------------------------------
Average:   65.2% ( 10.4 GB)
Min:       58.3% (  9.3 GB)
Max:       72.1% ( 11.5 GB)

Memory Trend: Stable ✅

--------------------------------------------------------------------------------
🎮 GPU PERFORMANCE
--------------------------------------------------------------------------------
GPU Load:
  Average:   62.3%
  Min:        8.5%
  Max:       95.2%

GPU Memory:
  Average:   75.4% ( 6034 MB)
  Min:       45.2% ( 3616 MB)
  Max:       88.7% ( 7096 MB)

GPU Utilization:
  Idle (<10%):   123 samples ( 10.0%)
  Active (≥10%): 1111 samples ( 90.0%)

--------------------------------------------------------------------------------
💾 DISK I/O PERFORMANCE
--------------------------------------------------------------------------------
Total Read:   1234.5 MB
Total Write:   567.8 MB

Average Read:   1.00 MB/s
Average Write:  0.46 MB/s

Peak Read:   15.23 MB/s
Peak Write:   8.45 MB/s

--------------------------------------------------------------------------------
🏆 PERFORMANCE SCORE
--------------------------------------------------------------------------------

CPU Efficiency:    54.7/100 🟡
Memory Stability:  98.2/100 🟢
GPU Utilization:   62.3/100 🟡

==============================
Overall Score:  71.7/100
==============================
👍 Good performance

================================================================================
```

---

## 🎯 Performance-Ziele

### **Optimal**
- 🟢 CPU: 40-70% (gut ausgelastet, nicht überlastet)
- 🟢 RAM: <80% (genug Headroom)
- 🟢 GPU: 60-90% (gute Auslastung)
- 🟢 Memory Trend: Stable (kein Memory Leak)

### **Warnung**
- 🟡 CPU: >80% (könnte bottleneck sein)
- 🟡 RAM: >85% (könnte swappen)
- 🟡 GPU: <30% (schlecht ausgenutzt)

### **Problem**
- 🔴 CPU: >95% (definitiv bottleneck)
- 🔴 RAM: >95% (kritisch!)
- 🔴 Memory Trend: Increasing (Memory Leak!)

---

## 🔧 Optionen

### **performance_monitor.py**

```bash
python performance_monitor.py --interval 1 --output performance_log.json

Optionen:
  --interval FLOAT    Sampling-Intervall in Sekunden (default: 1.0)
  --output STRING     Output-Datei (default: performance_log.json)
```

**Beispiele:**
```bash
# Alle 0.5 Sekunden samplen (höhere Auflösung)
python performance_monitor.py --interval 0.5

# Custom output file
python performance_monitor.py --output test_run_001.json

# Schnelles Sampling mit custom file
python performance_monitor.py --interval 0.5 --output fast_test.json
```

---

## 📊 Performance-Tipps

### **CPU zu hoch (>80%)**
- ✅ Reduziere `max_concurrent` in Pipeline
- ✅ Prüfe ob andere Programme laufen
- ✅ Check CPU-intensive Stages (Text, Image)

### **RAM zu hoch (>85%)**
- ✅ Reduziere Batch-Size
- ✅ Schließe andere Programme
- ✅ Check für Memory Leaks (steigt RAM kontinuierlich?)

### **GPU schlecht genutzt (<30%)**
- ✅ Prüfe Ollama-Status
- ✅ Check GPU-Prozesse (Task Manager → GPU)
- ✅ Eventuell mehr AI-Stages aktivieren

### **Disk I/O hoch**
- ✅ Nutze SSD statt HDD
- ✅ Dokumente auf schnelleres Laufwerk
- ✅ Check Antivirus (scannt Dateien?)

---

## 🐛 Troubleshooting

### **"GPUtil not available"**
```bash
pip install gputil
```

### **Monitor startet nicht**
```bash
# Prüfe Dependencies
pip install psutil gputil
```

### **Keine GPU erkannt**
- Normal wenn keine dedizierte GPU
- Monitor läuft trotzdem (ohne GPU-Metrics)

### **Performance-Log wird nicht erstellt**
- Prüfe Schreibrechte im Verzeichnis
- Monitor muss mindestens 1 Sekunde laufen

---

## 📈 Vergleich mehrerer Runs

```bash
# Run 1
python performance_monitor.py --output run1.json
# ... Pipeline ausführen ...

# Run 2 (nach Optimierung)
python performance_monitor.py --output run2.json
# ... Pipeline ausführen ...

# Vergleichen
python analyze_performance.py run1.json > report1.txt
python analyze_performance.py run2.json > report2.txt

# Dann manuell vergleichen oder diff:
diff report1.txt report2.txt
```

---

## 📅 Best Practices

1. ✅ **Baseline erstellen**: Ersten Run monitoren für Vergleich
2. ✅ **Clean System**: Andere Programme schließen für aussagekräftige Werte
3. ✅ **Mehrere Runs**: 3-5 Runs für Durchschnittswerte
4. ✅ **Logs aufbewahren**: Für Langzeit-Vergleiche
5. ✅ **Peak-Zeiten beachten**: CPU/RAM können durch andere Prozesse beeinflusst sein

---

## 🎉 Erwartete Performance (34 Dokumente)

**Hardware:** RTX 2060 8GB, 16GB RAM, SSD

```
Duration:    15-25 Minuten
CPU Average: 45-65%
RAM Average: 60-75%
GPU Average: 60-80%
Disk I/O:    1-3 MB/s

Documents/Minute: ~1.5-2.2
Overall Score: 70-85/100
```

---

**Created:** Oktober 2025
**Status:** ✅ Ready to Use
