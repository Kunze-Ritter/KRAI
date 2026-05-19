# ADR-003: Long-Tail Classification Strategy

**Status:** Proposed

**Context:**
Sprint 1 delivered 180 test service tickets spanning 3 manufacturers (HP, Konica Minolta, Ricoh) with unequal problem frequency distribution. The PM initiative needs to classify tickets into "Common" (high-frequency, predictable) and "Long-Tail" (rare, unpredictable) categories to enable targeted maintenance strategies.

The distribution follows an 80/20 pattern: ~20% of problem types account for ~80% of tickets, while the remaining 80% of problem types appear rarely. This imbalance is typical for technical support and necessitates a specialized classification approach.

**Decision:**
Use a **binary XGBoost classifier** trained with a 80/20 threshold on problem frequency to classify service tickets as Common (1) or Long-Tail (0).

**Rationale:**

1. **Interpretability**: Binary classification directly answers the business question ("Is this problem common or rare?") without unnecessary complexity.

2. **Robustness to imbalance**: XGBoost with `scale_pos_weight` parameter naturally handles class imbalance by weighting the minority class (Long-Tail). No oversampling or undersampling required.

3. **Feature relevance**: Leverages available PM schema features:
   - Problem frequency (normalized across dataset)
   - Repair time (correlates with problem difficulty)
   - Error codes (manufacturer-specific patterns)
   - Part replacements (hardware-level diagnosis)
   - Manufacturer (distribution patterns differ per brand)

4. **Avoids regression pitfalls**: Regression models would predict continuous repair time, introducing noise. Binary classification is more reliable for imbalanced data.

5. **Scalability**: Can be retrained incrementally as Docuware/Radix data arrives without changing architecture.

6. **5-fold Stratified CV**: Ensures balanced label representation in each fold, preventing class imbalance artifacts.

**Threshold Definition:**
- **Common**: Problem appears in top 20 problem_short values by frequency
- **Long-Tail**: All other problems
- **Top 20** determined by querying `COUNT(problem_short)` from krai_pm.service_tickets, ordered descending

**Alternative Considered:**
- Multi-class classifier per manufacturer (rejected: adds complexity, 180 tickets insufficient for stratified splits per brand)
- Regression on repair time (rejected: noisy, doesn't answer "common vs rare" question)

**Consequences:**

**Positive:**
- Simple, interpretable decision boundary
- Fits 180-ticket dataset without overfitting
- Extensible to hierarchical classification (common → subcategory) in Sprint 3
- Aligns with OODA loop: Observe (classification) → Orient (pattern analysis) → Decide (maintenance strategy)

**Negative:**
- Cannot predict specific repair time; separate model needed if required later
- Dependent on problem_short consistency in data (requires validation during FeatureEngineer)
- 80/20 threshold is heuristic; may need tuning with real-world feedback

**Implementation:**
- Feature extraction: `backend/pm/features/feature_engineer.py`
- Model: `backend/pm/models/long_tail_classifier.py` (XGBoost binary classifier)
- Evaluation: `backend/pm/evaluation/model_evaluator.py` (Accuracy, Precision, Recall, F1, AUC-ROC)
- Persistence: `prediction_service.py` stores results in `krai_pm.predictions`

**Follow-up:**
- ADR-004 (deferred): Multi-manufacturer hierarchical classification when Docuware volume permits
- ADR-005 (deferred): Active learning strategy for Long-Tail refinement
