"""
Dataset Generator for ML-based Cyber Attack Behavior Classifier
Generates synthetic cybersecurity attack behavior data with labeled attack types
"""

import pandas as pd
import numpy as np
from typing import List
import os

class DatasetGenerator:
    def __init__(self, seed: int = 42):
        """Initialize dataset generator with optional seed for reproducibility"""
        np.random.seed(seed)
        self.data = []
    
    def generate_row(self) -> dict:
        """Generate a single row of synthetic cybersecurity data"""
        failed_logins = np.random.randint(0, 151)
        request_rate = np.random.randint(1, 601)
        commands_count = np.random.randint(0, 21)
        sql_payload = np.random.choice([0, 1], p=[0.85, 0.15])
        honeytoken_access = np.random.choice([0, 1], p=[0.9, 0.1])
        session_time = np.random.randint(10, 601)
        
        # Assign label based on rules
        label = self._assign_label(
            sql_payload, 
            failed_logins, 
            honeytoken_access, 
            request_rate
        )
        
        return {
            'failed_logins': failed_logins,
            'request_rate': request_rate,
            'commands_count': commands_count,
            'sql_payload': sql_payload,
            'honeytoken_access': honeytoken_access,
            'session_time': session_time,
            'label': label
        }
    
    def _assign_label(self, sql_payload: int, failed_logins: int, 
                      honeytoken_access: int, request_rate: int) -> str:
        """Assign attack type label based on feature rules"""
        if sql_payload == 1:
            return 'Injection'
        elif failed_logins > 80:
            return 'BruteForce'
        elif honeytoken_access == 1:
            return 'DataExfil'
        elif request_rate > 400:
            return 'Recon'
        else:
            return 'Normal'
    
    def generate_dataset(self, num_rows: int = 1000) -> pd.DataFrame:
        """Generate complete dataset with specified number of rows"""
        print(f"Generating {num_rows} rows of cybersecurity attack data...")
        
        data = [self.generate_row() for _ in range(num_rows)]
        df = pd.DataFrame(data)
        
        print(f"\nDataset shape: {df.shape}")
        print(f"\nLabel distribution:\n{df['label'].value_counts()}")
        print(f"\nDataset preview:\n{df.head(10)}")
        
        return df
    
    def save_dataset(self, df: pd.DataFrame, filepath: str = 'training_data.csv'):
        """Save dataset to CSV file"""
        df.to_csv(filepath, index=False)
        print(f"\n✓ Dataset saved to {filepath}")


def main():
    """Main function to generate and save dataset"""
    generator = DatasetGenerator(seed=42)
    df = generator.generate_dataset(num_rows=1000)
    generator.save_dataset(df, 'training_data.csv')


if __name__ == '__main__':
    main()
