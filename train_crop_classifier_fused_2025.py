import json
import pickle
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import LabelEncoder

print("Loading datasets...")

# ------------------------------------------------------------------
# Load datasets
# ------------------------------------------------------------------

hls = pd.read_csv("crop_features.csv")
sar = pd.read_csv("sar_scene_features.csv")

# ------------------------------------------------------------------
# Load feature definitions
# ------------------------------------------------------------------

with open("models/feature_columns_hls.json") as f:
    hls_all = json.load(f)

if isinstance(hls_all, dict):
    hls_all = hls_all.get("hls", list(hls_all.values())[0])

with open("models/feature_columns_fused_sar.json") as f:
    fused = json.load(f)

sar_all = fused["sar"]

# ------------------------------------------------------------------
# Keep only 2025
# ------------------------------------------------------------------

hls_cols = [c for c in hls_all if "y2025_" in c]
sar_cols = [c for c in sar_all if "y2025_" in c]

print(f"HLS 2025 features : {len(hls_cols)}")
print(f"SAR 2025 features : {len(sar_cols)}")
print(f"Total features    : {len(hls_cols)+len(sar_cols)}")

assert len(hls_cols) == 160
assert len(sar_cols) == 160

# ------------------------------------------------------------------
# Merge
# ------------------------------------------------------------------

df = hls.merge(sar, on="sp_id")

print("Common parcels:", len(df))

X = df[hls_cols + sar_cols]

y = df["crop"]

# ------------------------------------------------------------------
# Encode labels
# ------------------------------------------------------------------

encoder = LabelEncoder()
y = encoder.fit_transform(y)

# ------------------------------------------------------------------
# Split
# ------------------------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y,
)

# ------------------------------------------------------------------
# Train
# ------------------------------------------------------------------

print("\nTraining HLS 2025 + SAR 2025 model...\n")

model = CatBoostClassifier(
    iterations=1000,
    learning_rate=0.05,
    depth=8,
    loss_function="MultiClass",
    eval_metric="Accuracy",
    random_seed=42,
    od_type="Iter",
    od_wait=50,
    verbose=100,
)

model.fit(
    X_train,
    y_train,
    eval_set=(X_test, y_test),
)

pred = model.predict(X_test)

acc = accuracy_score(y_test, pred)

print("\n===================================")
print(f"Accuracy: {acc*100:.2f}%")
print("===================================\n")

print(classification_report(y_test, pred,
                            target_names=encoder.classes_))

# ------------------------------------------------------------------
# Save
# ------------------------------------------------------------------

model.save_model("models/crop_classifier_fused_2025.cbm")

with open("models/feature_columns_fused_2025.json", "w") as f:
    json.dump({"hls": hls_cols, "sar": sar_cols}, f)

with open("models/label_encoder_fused_2025.pkl", "wb") as f:
    pickle.dump(encoder, f)

print("\nSaved:")
print(" models/crop_classifier_fused_2025.cbm")
print(" models/feature_columns_fused_2025.json")
print(" models/label_encoder_fused_2025.pkl")
