"""
Model Training Script for Cyber Attack Classifier
Trains RandomForest for attack classification and IsolationForest for anomaly detection
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
import joblib
import os


class ModelTrainer:
    def __init__(self):
        self.classifier = None
        self.anomaly_model = None
        self.scaler = None
        self.label_encoder = None
        self.feature_columns = None
    
    def load_data(self, filepath: str = 'training_data.csv') -> tuple:
        """Load training data from CSV"""
        print(f"Loading data from {filepath}...")
        df = pd.read_csv(filepath)
        
        # Separate features and labels
        self.feature_columns = [col for col in df.columns if col != 'label']
        X = df[self.feature_columns]
        y = df['label']
        
        print(f"Features: {self.feature_columns}")
        print(f"Data shape: X={X.shape}, y={y.shape}")
        print(f"Classes: {y.unique()}")
        
        return X, y
    
    def encode_labels(self, y: pd.Series) -> np.ndarray:
        """Encode categorical labels to numeric values"""
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y)
        
        print(f"\nLabel mapping:")
        for i, label in enumerate(self.label_encoder.classes_):
            print(f"  {label}: {i}")
        
        return y_encoded
    
    def train_classifier(self, X: pd.DataFrame, y: np.ndarray):
        """Train RandomForest classifier"""
        print("\nTraining RandomForest Classifier...")
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        self.classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        
        self.classifier.fit(X_train, y_train)
        
        train_accuracy = self.classifier.score(X_train, y_train)
        test_accuracy = self.classifier.score(X_test, y_test)
        
        print(f"  Training accuracy: {train_accuracy:.4f}")
        print(f"  Test accuracy: {test_accuracy:.4f}")
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': self.feature_columns,
            'importance': self.classifier.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print(f"\nFeature Importance:\n{feature_importance}")
        
        return X_train, X_test, y_train, y_test
    
    def train_anomaly_detector(self, X: pd.DataFrame):
        """Train IsolationForest for anomaly detection"""
        print("\nTraining IsolationForest Anomaly Detector...")
        
        # Scale features first
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        self.anomaly_model = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100
        )
        
        self.anomaly_model.fit(X_scaled)
        print("✓ Anomaly detection model trained")
        
        # Get anomaly scores on training data
        anomaly_scores = self.anomaly_model.score_samples(X_scaled)
        n_anomalies = (self.anomaly_model.predict(X_scaled) == -1).sum()
        print(f"  Detected {n_anomalies} anomalies in training data")
    
    def save_models(self, model_dir: str = '.'):
        """Save trained models to disk"""
        print(f"\nSaving models to {model_dir}...")
        
        joblib.dump(self.classifier, os.path.join(model_dir, 'classifier.pkl'))
        joblib.dump(self.anomaly_model, os.path.join(model_dir, 'anomaly_model.pkl'))
        joblib.dump(self.scaler, os.path.join(model_dir, 'scaler.pkl'))
        joblib.dump(self.label_encoder, os.path.join(model_dir, 'label_encoder.pkl'))
        
        # Save feature columns for later use
        joblib.dump(self.feature_columns, os.path.join(model_dir, 'feature_columns.pkl'))
        
        print("✓ classifier.pkl")
        print("✓ anomaly_model.pkl")
        print("✓ scaler.pkl")
        print("✓ label_encoder.pkl")
        print("✓ feature_columns.pkl")


def main():
    """Main training pipeline"""
    trainer = ModelTrainer()
    
    # Load data
    X, y = trainer.load_data('training_data.csv')
    
    # Encode labels
    y_encoded = trainer.encode_labels(y)
    
    # Train classifier
    trainer.train_classifier(X, y_encoded)
    
    # Train anomaly detector
    trainer.train_anomaly_detector(X)
    
    # Save all models
    trainer.save_models('.')
    
    print("\n" + "="*50)
    print("✓ MODEL TRAINING COMPLETE")
    print("="*50)


if __name__ == '__main__':
    main()
