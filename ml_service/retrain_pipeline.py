"""
Decoyvers ML Retraining Pipeline
One-command script to retrain ML model on real production logs

Usage:
    python retrain_pipeline.py

This will:
1. Export logs from MongoDB
2. Auto-label data using rules
3. Train new classifier and anomaly detector
4. Save updated models
"""

import sys
import os
from datetime import datetime


def run_command(script_name, description):
    """Run a Python script and handle errors"""
    print(f"\n{'='*60}")
    print(f"STEP: {description}")
    print(f"{'='*60}")
    
    exit_code = os.system(f'python {script_name}')
    
    if exit_code != 0:
        print(f"\n✗ FAILED: {description}")
        print(f"  Command: python {script_name}")
        print(f"  Exit code: {exit_code}")
        sys.exit(1)
    
    print(f"\n✓ COMPLETED: {description}")


def main():
    """Main pipeline execution"""
    start_time = datetime.now()
    
    print("=" * 60)
    print("DECOYVERS ML RETRAINING PIPELINE")
    print("=" * 60)
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Export real logs from MongoDB
    run_command(
        "export_real_logs.py",
        "Export real logs from MongoDB and convert to features"
    )
    
    # Step 2: Train models on real data
    run_command(
        "train_model.py",
        "Train Random Forest and Isolation Forest models"
    )
    
    # Done
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "=" * 60)
    print("✓ RETRAINING PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Duration: {duration:.1f} seconds")
    print(f"\nUpdated models:")
    print(f"  - classifier.pkl")
    print(f"  - anomaly_model.pkl")
    print(f"  - scaler.pkl")
    print(f"  - label_encoder.pkl")
    print(f"  - feature_columns.pkl")
    print(f"\nNext steps:")
    print(f"  1. Test models locally: python ml_api.py")
    print(f"  2. Deploy to Render: git push")
    print(f"  3. Verify production: curl https://ml-modle-v0-2.onrender.com/predict")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Pipeline failed with error: {e}")
        sys.exit(1)
