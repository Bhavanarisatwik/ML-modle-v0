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
        """Generate a single row of synthetic cybersecurity data with realistic behavior"""
        # Determine behavior profile
        profile = np.random.choice(['Normal', 'BruteForce', 'Injection', 'DataExfil', 'Recon'], p=[0.6, 0.15, 0.05, 0.1, 0.1])
        
        if profile == 'Normal':
            failed_logins = np.random.randint(0, 5)
            request_rate = np.random.randint(1, 50)
            commands_count = np.random.randint(0, 5)
            sql_payload = 0
            honeytoken_access = 0
            session_time = np.random.randint(60, 600)
            label = 'Normal'
        elif profile == 'BruteForce':
            failed_logins = np.random.randint(50, 150)
            request_rate = np.random.randint(100, 300)
            commands_count = np.random.randint(0, 2)
            sql_payload = 0
            honeytoken_access = 0
            session_time = np.random.randint(10, 120)
            label = 'BruteForce'
        elif profile == 'Injection':
            failed_logins = np.random.randint(0, 10)
            request_rate = np.random.randint(20, 100)
            commands_count = np.random.randint(10, 20)
            sql_payload = 1
            honeytoken_access = np.random.choice([0, 1], p=[0.7, 0.3])
            session_time = np.random.randint(30, 300)
            label = 'Injection'
        elif profile == 'DataExfil':
            failed_logins = np.random.randint(0, 3)
            request_rate = np.random.randint(5, 40)
            commands_count = np.random.randint(1, 10)
            sql_payload = 0
            honeytoken_access = 1
            session_time = np.random.randint(120, 600)
            label = 'DataExfil'
        else: # Recon
            failed_logins = np.random.randint(0, 15)
            request_rate = np.random.randint(400, 600)
            commands_count = np.random.randint(1, 5)
            sql_payload = 0
            honeytoken_access = 0
            session_time = np.random.randint(10, 60)
            label = 'Recon'
            
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
    
    def generate_dataset(self, num_rows: int = 10000) -> pd.DataFrame:
        """Generate complete dataset with specified number of rows"""
        print(f"Generating {num_rows} rows of realistic cybersecurity attack data...")
        
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
