# Sprint 2 ML Pipeline: Complete ML Workflow

## Overview

The Sprint 2 ML Pipeline is a comprehensive, end-to-end workflow that orchestrates the complete machine learning pipeline for predictive maintenance:

1. **Radix Data Import** — Fetch service tickets from Radix RxPlusService API
2. **Feature Extraction** — Transform raw ticket data into ML-ready features
3. **Label Building** — Classify tickets as Common (top-N) or Long-Tail problems
4. **Model Training** — Train XGBoost classifier with 5-fold stratified cross-validation
5. **Model Evaluation** — Compute cross-validation metrics and feature importance
6. **Batch Predictions** — Generate predictions for all tickets and store to database

## Quick Start

### Prerequisites

- PostgreSQL 15+ running with krai_pm schema
- Radix RxPlusService API access (requires Bearer token)
- Python 3.10+
- Dependencies installed: `pip install -r backend/requirements.txt`

### Running the Pipeline

#### Option 1: With Pre-Generated Bearer Token

```bash
python backend/scripts/sprint2_ml_pipeline.py \
    --radix-token "your-bearer-token" \
    --limit 1000
```

#### Option 2: Generate Token from Credentials

```bash
python backend/scripts/sprint2_ml_pipeline.py \
    --radix-username HAT \
    --radix-password-b64 "base64-encoded-password" \
    --radix-code 1FB \
    --radix-license APP-RX+SM_1FB \
    --limit 1000
```

### Skipping Stages

```bash
# Skip import, use existing tickets
python backend/scripts/sprint2_ml_pipeline.py \
    --radix-token "token" \
    --skip-import

# Skip training, use pre-trained model
python backend/scripts/sprint2_ml_pipeline.py \
    --radix-token "token" \
    --skip-training
```

## Architecture

### Directory Structure

```
backend/pm/
├── models/
│   ├── ticket.py                      # Pydantic models (ServiceTicketFeatures, PredictionResult)
│   ├── radix_models.py                # Radix API models
│   ├── long_tail_classifier.py        # XGBoost classifier
│   ├── error_pattern_analyzer.py      # Error analysis utilities
│   └── checkpoints/                   # Saved model files
├── features/
│   └── feature_engineer.py            # Feature extraction engine
├── evaluation/
│   └── model_evaluator.py             # CV, metrics, ablation testing
├── services/
│   ├── radix_data_client.py           # Low-level HTTP client for Radix API
│   ├── radix_importer.py              # Radix → KRAI data mapping
│   └── prediction_service.py          # Batch prediction service
└── SPRINT2_ML_PIPELINE.md             # This file
```

### Core Components

#### 1. FeatureEngineer (`backend/pm/features/feature_engineer.py`)

Extracts ML-ready features from service tickets:

- **repair_time_minutes**: Repair duration from work times
- **problem_frequency**: How often this problem appears in dataset
- **part_replacement_count**: Number of replaced parts
- **error_code_count**: Number of associated error codes
- **manufacturer_encoded**: Integer encoding of manufacturer
- **error_code_top10**: One-Hot encoding of top 10 error codes
- **device_age_months**, **page_count**, **service_history_count**: Placeholders for future Docuware data

```python
engineer = FeatureEngineer(db)
features_list = await engineer.extract_features_batch(limit=1000)
top_problems = await engineer.get_top_problems(top_n=20)
```

#### 2. LongTailClassifier (`backend/pm/models/long_tail_classifier.py`)

XGBoost binary classifier: **Common (top-N) vs Long-Tail**

- Handles class imbalance via `scale_pos_weight`
- 5-fold stratified cross-validation
- Feature importance tracking
- Model persistence (joblib serialization)

```python
classifier = LongTailClassifier(threshold=20)
metrics = await classifier.fit(features_list, labels)
predictions = classifier.predict_batch(features_list)
classifier.save()
```

#### 3. ModelEvaluator (`backend/pm/evaluation/model_evaluator.py`)

Comprehensive model evaluation:

- **Metrics**: Accuracy, Precision, Recall, F1, AUC-ROC
- **Cross-Validation**: StratifiedKFold with per-fold metrics
- **Ablation Testing**: Feature importance via ablation

```python
evaluator = ModelEvaluator()
cv_results = evaluator.cross_validate(classifier, features, labels, cv=5)
ablation = evaluator.ablation_test(classifier, features, labels)
```

#### 4. PredictionService (`backend/pm/services/prediction_service.py`)

Idempotent batch predictions:

- Extracts features for all tickets
- Generates predictions using trained model
- Stores results to `krai_pm.predictions` table
- Skips already-predicted tickets

```python
service = PredictionService(db, engineer, classifier)
result = await service.run_batch(limit=None)
# Returns: {'predicted': N, 'skipped': M, 'errors': K}
```

#### 5. RadixImporter (`backend/pm/services/radix_importer.py`)

Imports service tickets from Radix:

- Maps Radix activities → krai_pm.service_tickets
- Fetches spare parts and work times per activity
- Deduplicates by ticket ID
- Logs detailed import statistics

```python
importer = RadixImporter(db, radix_client)
result = await importer.import_activities(limit=1000, skip_duplicates=True)
# Returns: {'imported': N, 'skipped': M, 'errors': K}
```

## Database Schema

### krai_pm.service_tickets

```sql
CREATE TABLE krai_pm.service_tickets (
    id VARCHAR(255) PRIMARY KEY,
    problem_short VARCHAR(500),
    problem_long TEXT,
    error_codes TEXT[],           -- Array of error codes
    replaced_parts TEXT[],        -- Array of part names
    repair_time_minutes FLOAT,
    manufacturer_id VARCHAR(100),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    metadata JSONB                -- Radix metadata
);
```

### krai_pm.predictions

```sql
CREATE TABLE krai_pm.predictions (
    id SERIAL PRIMARY KEY,
    prediction_type VARCHAR(100),  -- 'long_tail'
    model_name VARCHAR(255),
    model_version VARCHAR(50),
    confidence FLOAT,              -- 0-1
    risk_score FLOAT,              -- 0-1
    metadata JSONB,                -- {'ticket_id', 'is_common', 'confidence'}
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Pipeline Execution Flow

```
START
  ↓
[STEP 1] Import Radix Tickets
  ├─ GET /api/activity (filter by limit)
  ├─ Parse and validate RadixActivity objects
  ├─ Fetch spare parts + work times per activity
  ├─ Map to krai_pm.service_tickets
  └─ Skip duplicates (by ticket ID)
  ↓
[STEP 2] Extract Features
  ├─ SELECT all tickets from krai_pm.service_tickets
  ├─ Calculate problem_frequency (COUNT GROUP BY)
  ├─ Encode manufacturer → integer
  ├─ One-Hot encode top 10 error codes
  └─ Return ServiceTicketFeatures list
  ↓
[STEP 3] Build Labels
  ├─ SELECT top 20 problems by frequency
  ├─ Label = 1 if problem in top 20 (Common)
  ├─ Label = 0 if problem not in top 20 (Long-Tail)
  └─ Return binary labels
  ↓
[STEP 4] Train Model
  ├─ Create XGBClassifier with scale_pos_weight for imbalance
  ├─ Train on features + labels
  ├─ Compute training metrics (Accuracy, Precision, Recall, F1, AUC)
  └─ Log results
  ↓
[STEP 5] Evaluate (5-fold CV)
  ├─ StratifiedKFold(n_splits=5)
  ├─ Train on 4 folds, evaluate on 1 fold (5 times)
  ├─ Log per-fold metrics
  ├─ Compute feature importance
  └─ Return CV metrics + top 5 features
  ↓
[STEP 6] Batch Predictions
  ├─ SELECT all tickets not in krai_pm.predictions
  ├─ Extract features for each ticket
  ├─ Generate predictions (is_common, confidence)
  ├─ INSERT into krai_pm.predictions
  └─ Log counts (predicted, skipped, errors)
  ↓
DONE ✓
```

## Configuration

### Radix API Configuration

Set environment variables or pass as CLI arguments:

```bash
RADIX_API_URL=https://radix.kunze-ritter.de/IM.RxPlusService.Api
RADIX_USERNAME=HAT
RADIX_PASSWORD_BASE64=<base64-encoded-password>
RADIX_CLIENT_CODE=1FB
RADIX_LICENSE_ID=APP-RX+SM_1FB
RADIX_API_LANGUAGE=DE
RADIX_BEARER_TOKEN=<pre-generated-token>
```

### Model Configuration

Edit `backend/pm/models/long_tail_classifier.py`:

- `TOP_N_COMMON`: Number of top problems to classify as 'common' (default: 20)
- `MODEL_PATH`: Path to save/load trained models
- XGBoost hyperparameters: `max_depth`, `learning_rate`, `n_estimators`

## Monitoring & Debugging

### Log Output

The pipeline logs detailed progress at each stage:

```
2026-05-19 14:25:30 [INFO] Starting Radix activity import...
2026-05-19 14:25:35 [INFO] Fetched 1000 activities from Radix
2026-05-19 14:25:45 [INFO] Import complete: 950 imported, 50 skipped, 0 errors
2026-05-19 14:25:50 [INFO] Extracted features for 950 tickets
2026-05-19 14:26:00 [INFO] Training complete: accuracy=0.92, F1=0.88
2026-05-19 14:26:15 [INFO] CV Results: accuracy=0.89±0.03
2026-05-19 14:26:30 [INFO] Predictions complete: 950 predicted, 0 skipped, 0 errors
```

### Common Issues

**Issue**: "Radix login failed: 401"
- **Solution**: Verify Bearer token is valid, check username/password encoding

**Issue**: "Model not trained. Call fit() first."
- **Solution**: Don't use `--skip-training` on first run, or train model first

**Issue**: "No tickets found for feature extraction"
- **Solution**: Ensure Radix import succeeded, check database connection

## Future Enhancements (Phase 2)

1. **Integration with Docuware** — Pull device_age_months, page_count, service_history
2. **Error Code Hierarchy** — Use error_pattern_analyzer for better classification
3. **Real-time Predictions** — API endpoint for predicting on new tickets
4. **Model Versioning** — Track model performance over time
5. **Feature Drift Detection** — Alert when feature distributions change

## References

- Radix RxPlusService API: `https://radix.kunze-ritter.de/IM.RxPlusService.Api/swagger`
- XGBoost Documentation: `https://xgboost.readthedocs.io/`
- Scikit-learn CV: `https://scikit-learn.org/stable/modules/cross_validation.html`
