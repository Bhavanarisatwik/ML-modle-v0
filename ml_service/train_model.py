"""
Train ML Model on Real Decoyvers Logs
Uses actual honeypot and agent event data for training
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import os
from feature_extractor import FeatureExtractor

# Input/Output files
DATASET_FILE = "real_logs_dataset.csv"
MODEL_DIR = "."

# Model output files
CLASSIFIER_FILE = os.path.join(MODEL_DIR, "classifier.pkl")
ANOMALY_FILE = os.path.join(MODEL_DIR, "anomaly_model.pkl")
SCALER_FILE = os.path.join(MODEL_DIR, "scaler.pkl")
LABEL_ENCODER_FILE = os.path.join(MODEL_DIR, "label_encoder.pkl")
FEATURE_COLUMNS_FILE = os.path.join(MODEL_DIR, "feature_columns.pkl")


def load_dataset():
    """Load real logs dataset"""
    if not os.path.exists(DATASET_FILE):
        print(f"✗ Dataset not found: {DATASET_FILE}")
        print(f"  Run: python export_real_logs.py")
        exit(1)
    
    df = pd.read_csv(DATASET_FILE)
    print(f"✓ Loaded dataset: {len(df)} samples")
    return df


def prepare_data(df):
    """Prepare features and labels"""
    # Extract features (in correct order)
    X = df[FeatureExtractor.FEATURE_ORDER].values
    
    # Extract labels
    y = df['label'].values
    
    print(f"\n📊 Dataset Statistics:")
    print(f"  Features: {X.shape[1]}")
    print(f"  Samples: {X.shape[0]}")
    print(f"  Labels: {np.unique(y)}")
    print(f"\n  Label distribution:")
    for label in np.unique(y):
        count = np.sum(y == label)
        percentage = (count / len(y)) * 100
        print(f"    {label}: {count} ({percentage:.1f}%)")
    
    return X, y


def train_classifier(X, y):
    """Train Random Forest Classifier"""
    print(f"\n🌲 Training Random Forest Classifier...")
    
    # Encode labels
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
    )
    
    # Train classifier
    classifier = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    
    classifier.fit(X_train, y_train)
    
    # Evaluate
    y_pred = classifier.predict(X_test)
    accuracy = np.mean(y_pred == y_test)
    
    print(f"  ✓ Training complete")
    print(f"  Accuracy: {accuracy:.2%}")
    
    # Show classification report
    print(f"\n  Classification Report:")
    print(classification_report(
        y_test, y_pred,
        target_names=label_encoder.classes_,
        zero_division=0
    ))
    
    # Feature importance
    print(f"\n  Feature Importance:")
    for feature, importance in zip(FeatureExtractor.FEATURE_ORDER, classifier.feature_importances_):
        print(f"    {feature}: {importance:.3f}")
    
    return classifier, label_encoder


def train_anomaly_detector(X):
    """Train Isolation Forest for anomaly detection"""
    print(f"\n🌲 Training Isolation Forest (Anomaly Detector)...")
    
    # Scale features for anomaly detection
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Train anomaly detector
    anomaly_model = IsolationForest(
        contamination=0.1,  # Expect 10% anomalies
        random_state=42,
        n_jobs=-1
    )
    
    anomaly_model.fit(X_scaled)
    
    # Get anomaly predictions
    anomalies = anomaly_model.predict(X_scaled)
    anomaly_count = np.sum(anomalies == -1)
    
    print(f"  ✓ Training complete")
    print(f"  Detected anomalies: {anomaly_count}/{len(X)} ({100*anomaly_count/len(X):.1f}%)")
    
    return anomaly_model, scaler


def save_models(classifier, anomaly_model, scaler, label_encoder):
    """Save all trained models"""
    print(f"\n💾 Saving models...")
    
    joblib.dump(classifier, CLASSIFIER_FILE)
    print(f"  ✓ Saved: {CLASSIFIER_FILE}")
    
    joblib.dump(anomaly_model, ANOMALY_FILE)
    print(f"  ✓ Saved: {ANOMALY_FILE}")
    
    joblib.dump(scaler, SCALER_FILE)
    print(f"  ✓ Saved: {SCALER_FILE}")
    
    joblib.dump(label_encoder, LABEL_ENCODER_FILE)
    print(f"  ✓ Saved: {LABEL_ENCODER_FILE}")
    
    joblib.dump(FeatureExtractor.FEATURE_ORDER, FEATURE_COLUMNS_FILE)
    print(f"  ✓ Saved: {FEATURE_COLUMNS_FILE}")


def main():
    """Main training pipeline"""
    print("=" * 60)
    print("DECOYVERS ML MODEL TRAINING")
    print("=" * 60)
    
    # Load dataset
    df = load_dataset()
    
    # Prepare data
    X, y = prepare_data(df)
    
    # Train classifier
    classifier, label_encoder = train_classifier(X, y)
    
    # Train anomaly detector
    anomaly_model, scaler = train_anomaly_detector(X)
    
    # Save models
    save_models(classifier, anomaly_model, scaler, label_encoder)
    
    print(f"\n{'=' * 60}")
    print(f"✓ Training complete! Models ready for deployment.")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
