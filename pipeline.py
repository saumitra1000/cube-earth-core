"""
pipeline.py — Full crop intelligence pipeline
Connects: bbox → S1+S2 extraction → features → crop prediction
"""
from features import extract_features
from classifier import predict, load_model

def run(lat: float, lng: float, years: list = None) -> dict:
    """
    Full pipeline: lat/lng → crop prediction
    """
    if years is None:
        years = [2022, 2023, 2024, 2025]

    print(f"\n{'='*50}")
    print(f"Cube Earth Crop Intelligence Pipeline")
    print(f"Location: {lat}, {lng}")
    print(f"Years: {years}")
    print(f"{'='*50}\n")

    # Load model to get feature columns
    _, _, feat_cols = load_model()

    # Extract features
    print("Extracting satellite features...")
    features = extract_features(lat, lng, years=years, feat_cols=feat_cols)
    print(f"Features extracted: {len(features)}")

    # Count non-default values
    non_default = sum(1 for v in features.values() if v != 0.4)
    print(f"Non-default values: {non_default}/{len(features)}")

    # Predict
    print("\nRunning crop classifier...")
    result = predict(features)

    print(f"\n{'='*50}")
    print(f"RESULT")
    print(f"{'='*50}")
    print(f"Crop:       {result['crop']}")
    print(f"Confidence: {result['confidence']}% ({result['confidence_category']})")
    print(f"\nTop 3:")
    for t in result['top3']:
        print(f"  {t['crop']:<20} {t['probability']}%")
    print(f"{'='*50}\n")

    return {
        'lat': lat,
        'lng': lng,
        'years': years,
        **result
    }

if __name__ == '__main__':
    # Test on known Carlow Spring Barley parcel
    result = run(52.84, -6.93, years=[2022, 2023, 2024, 2025])
