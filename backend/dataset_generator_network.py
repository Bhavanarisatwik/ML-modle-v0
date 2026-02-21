import pandas as pd
import numpy as np
import os

def clean_and_process_cic_dataset(filepath: str, output_path: str):
    """
    Reads the raw CIC-IDS-2017 Dataset (e.g. Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv)
    Cleans infinite/nan values commonly found in flow generation.
    Strips it down to the essential 9 real-time features plus the Label.
    """
    print(f"Reading dataset: {filepath}")
    
    # Due to space padding in columns, we strip them immediately
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()

    print(f"Original dataset shape: {df.shape}")

    # The required features derived from Zeek mapping
    required_features = {
        'Flow Duration': 'duration',
        'Total Fwd Packets': 'orig_pkts',
        'Total Backward Packets': 'resp_pkts',
        'Total Length of Fwd Packets': 'orig_bytes',
        'Total Length of Bwd Packets': 'resp_bytes',
        'Flow Bytes/s': 'flow_bytes_s',
        'Flow Packets/s': 'flow_pkts_s',
        'Destination Port': 'dst_port',
        'Protocol': 'protocol',  # Usually missing in this specific CSV split, but we can fake/derive it or skip it if needed. Wait, Protocol IS in CIC-IDS, let's check.
        'Label': 'label'
    }

    # Checking if Protocol exists, if not we fall back to just using the available columns
    available_cols = set(df.columns)
    
    features_to_keep = []
    rename_mapping = {}

    for original_col, new_col in required_features.items():
        if original_col in available_cols:
            features_to_keep.append(original_col)
            rename_mapping[original_col] = new_col
        else:
            print(f"Warning: {original_col} not found in CSV. Dropping from mapping.")
            # If Protocol missing (common in some CIC splits), we drop it from requirements
    
    print("Extracting features...")
    df = df[features_to_keep]
    df.rename(columns=rename_mapping, inplace=True)
    
    print("Cleaning Infinity and NaN values...")
    # Clean infinities and NaNs
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)

    print(f"Cleaned dataset shape: {df.shape}")
    print("Label Distribution:")
    print(df['label'].value_counts())

    print(f"Saving to {output_path}...")
    df.to_csv(output_path, index=False)
    print("Done!")

if __name__ == "__main__":
    raw_csv_path = r"c:\Users\satwi\Downloads\ML-modle v0\Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv"
    processed_path = r"c:\Users\satwi\Downloads\ML-modle v0\backend\training_data_network.csv"
    
    if os.path.exists(raw_csv_path):
        clean_and_process_cic_dataset(raw_csv_path, processed_path)
    else:
        print(f"File not found: {raw_csv_path}")

