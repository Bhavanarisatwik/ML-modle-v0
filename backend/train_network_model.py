import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
import joblib
import os

class NetworkModelTrainer:
    def __init__(self):
        self.classifier = None
        self.scaler = None
        self.label_encoder = None
        self.feature_columns = None
    
    def load_data(self, filepath: str = 'backend/training_data_network.csv') -> tuple:
        """Load the preprocessed network flow data"""
        print(f"Loading data from {filepath}...")
        df = pd.read_csv(filepath)
        
        # Clean col names again just in case
        df.columns = df.columns.str.strip()
        
        # Separate features and labels
        self.feature_columns = [col for col in df.columns if col != 'label']
        X = df[self.feature_columns]
        y = df['label']
        
        print(f"Features mapped ({len(self.feature_columns)}): {self.feature_columns}")
        print(f"Data shape: X={X.shape}, y={y.shape}")
        print(f"Classes found: {y.unique()}")
        
        return X, y
    
    def prepare_data(self, X: pd.DataFrame, y: pd.Series):
        """Encode labels and scale features"""
        print("\nEncoding Labels...")
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y)
        
        print(f"Label mapping:")
        for i, label in enumerate(self.label_encoder.classes_):
            print(f"  {label}: {i}")
            
        print("\nScaling Features...")
        self.scaler = StandardScaler()
        # Fit scaler on full data (or train subset, simplified for script)
        X_scaled = self.scaler.fit_transform(X)
        
        return X_scaled, y_encoded
    
    def train_classifier(self, X_scaled: np.ndarray, y_encoded: np.ndarray):
        """Train RandomForest classifier on flow data"""
        print("\nTraining Network RandomForest Classifier...")
        
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
        )
        
        # Optimized for speed and avoiding overfit on CIC-IDS
        self.classifier = RandomForestClassifier(
            n_estimators=50,
            max_depth=12,
            min_samples_split=10,
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
    
    def save_models(self, model_dir: str = 'backend'):
        """Save trained network models to disk"""
        os.makedirs(model_dir, exist_ok=True)
        print(f"\nSaving models to {model_dir}...")
        
        joblib.dump(self.classifier, os.path.join(model_dir, 'network_classifier.pkl'))
        joblib.dump(self.scaler, os.path.join(model_dir, 'network_scaler.pkl'))
        joblib.dump(self.label_encoder, os.path.join(model_dir, 'network_label_encoder.pkl'))
        joblib.dump(self.feature_columns, os.path.join(model_dir, 'network_feature_columns.pkl'))
        
        print("✓ network_classifier.pkl")
        print("✓ network_scaler.pkl")
        print("✓ network_label_encoder.pkl")
        print("✓ network_feature_columns.pkl")


def main():
    trainer = NetworkModelTrainer()
    
    # Run pipeline
    data_path = os.path.join(os.path.dirname(__file__), 'training_data_network.csv')
    X, y = trainer.load_data(data_path)
    X_scaled, y_encoded = trainer.prepare_data(X, y)
    trainer.train_classifier(X_scaled, y_encoded)
    trainer.save_models(os.path.dirname(__file__))
    
    print("\n" + "="*50)
    print("✓ NETWORK MODEL TRAINING COMPLETE")
    print("="*50)

if __name__ == '__main__':
    main()
