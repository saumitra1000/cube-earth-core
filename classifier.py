"""
classifier.py — Crop classification using CatBoost model
Loads crop_classifier_v2.cbm and predicts crop type from feature vector
"""
import json
import pickle
import numpy as np
from catboost import CatBoostClassifier

MODEL_PATH   = 'models/crop_classifier_v2.cbm'
ENCODER_PATH = 'models/label_encoder_v2.pkl'
FEATURES_PATH = 'models/feature_columns_v2.json'

# Load once at import
_clf = None
_le  = None
_feat_cols = None

def load_model():
    global _clf, _le, _feat_cols
    if _clf is None:
        _clf = CatBoostClassifier()
        _clf.load_model(MODEL_PATH)
        with open(ENCODER_PATH, 'rb') as f:
            _le = pickle.load(f)
        with open(FEATURES_PATH) as f:
            _feat_cols = json.load(f)
        print(f"Model loaded ✅  {len(_feat_cols)} features  {len(_le.classes_)} classes")
    return _clf, _le, _feat_cols

def predict(feature_dict: dict) -> dict:
    """
    Predict crop type from feature dictionary.
    feature_dict: {col_name: value}
    Returns: {crop, confidence, confidence_category, top3}
    """
    clf, le, feat_cols = load_model()

    # Build feature vector in exact column order
    X = np.array([[feature_dict.get(c, 0.4) for c in feat_cols]])

    probs = clf.predict_proba(X)[0]
    top3_idx = np.argsort(probs)[::-1][:3]
    pred_idx = top3_idx[0]

    confidence = round(float(probs[pred_idx]) * 100, 1)

    if confidence >= 70:   cat = 'High'
    elif confidence >= 45: cat = 'Medium'
    else:                  cat = 'Low'

    return {
        'crop':                  le.classes_[pred_idx],
        'confidence':            confidence,
        'confidence_category':   cat,
        'top3': [
            {'crop': le.classes_[i],
             'probability': round(float(probs[i]) * 100, 1)}
            for i in top3_idx
        ],
        'all_classes': {
            le.classes_[i]: round(float(p) * 100, 1)
            for i, p in enumerate(probs)
        }
    }

if __name__ == '__main__':
    clf, le, feat_cols = load_model()
    print(f"Classes: {list(le.classes_)}")

    # Test with dummy features
    dummy = {col: 0.4 for col in feat_cols}
    result = predict(dummy)
    print(f"\nDummy prediction:")
    print(f"  Crop:       {result['crop']}")
    print(f"  Confidence: {result['confidence']}% ({result['confidence_category']})")
    print(f"  Top 3:")
    for t in result['top3']:
        print(f"    {t['crop']:<20} {t['probability']}%")
