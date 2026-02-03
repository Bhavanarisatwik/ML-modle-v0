"""
Honeytoken Setup Module
Creates fake credentials and files to bait attackers
"""

import os
import json
from pathlib import Path
from datetime import datetime


class HoneytokenSetup:
    """Create deceptive honeytokens"""
    
    def __init__(self, base_dir: str = "system_cache"):
        """Initialize honeytoken setup"""
        self.base_dir = base_dir
        self.honeytokens = []
    
    def create_hidden_folder(self) -> bool:
        """Create hidden honeytokens folder"""
        try:
            # Create directory
            os.makedirs(self.base_dir, exist_ok=True)
            
            # Make it hidden on Windows
            if os.name == 'nt':
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(self.base_dir, 2)  # 2 = hidden
            
            print(f"✓ Created hidden folder: {self.base_dir}")
            return True
        except Exception as e:
            print(f"✗ Error creating folder: {e}")
            return False
    
    def create_aws_credentials(self) -> str:
        """Create fake AWS credentials file"""
        filename = os.path.join(self.base_dir, "aws_keys.txt")
        
        content = """AWS Access Key ID: AKIAIOSFODNN7EXAMPLE
AWS Secret Access Key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
Region: us-east-1
Account ID: 123456789012

[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
region = us-east-1
output = json

[production]
aws_access_key_id = AKIAJ7XAMPLE12345678
aws_secret_access_key = RxU1tnFEMI/K7MDENG/bPxRfiCYEXAMPLE9876
region = eu-west-1

[staging]
aws_access_key_id = AKIA5EXAMPLE87654321
aws_secret_access_key = aWalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE1234
region = ap-south-1
"""
        
        try:
            with open(filename, 'w') as f:
                f.write(content)
            self.honeytokens.append({
                'type': 'aws_credentials',
                'path': filename,
                'size': len(content),
                'created': datetime.now().isoformat()
            })
            print(f"✓ Created AWS credentials: {filename}")
            return filename
        except Exception as e:
            print(f"✗ Error creating AWS credentials: {e}")
            return None
    
    def create_database_credentials(self) -> str:
        """Create fake database credentials file"""
        filename = os.path.join(self.base_dir, "db_creds.env")
        
        content = """# Database Credentials
DB_HOST=prod-db.company.internal
DB_PORT=5432
DB_USER=admin
DB_PASSWORD=Tr0pic@lM0nkey#2024!
DB_NAME=production_db
DB_SSL=true

# MySQL
MYSQL_HOST=mysql-prod.company.local
MYSQL_USER=root
MYSQL_PASSWORD=C0mplex!Pass123#ABC
MYSQL_DATABASE=main_db

# MongoDB
MONGO_URI=mongodb+srv://admin:SuperSecret@2024@cluster0.mongodb.net/production?retryWrites=true
MONGO_USER=admin
MONGO_PASSWORD=M0ng0DB@Secure123!

# Redis
REDIS_HOST=redis.company.internal
REDIS_PORT=6379
REDIS_PASSWORD=<REDACTED>

# API Keys
API_KEY_STRIPE=<REDACTED>
API_KEY_TWILIO=<REDACTED>
API_KEY_SENDGRID=<REDACTED>
"""
        
        try:
            with open(filename, 'w') as f:
                f.write(content)
            self.honeytokens.append({
                'type': 'database_credentials',
                'path': filename,
                'size': len(content),
                'created': datetime.now().isoformat()
            })
            print(f"✓ Created DB credentials: {filename}")
            return filename
        except Exception as e:
            print(f"✗ Error creating DB credentials: {e}")
            return None
    
    def create_employee_data(self) -> str:
        """Create fake employee salary file"""
        filename = os.path.join(self.base_dir, "employee_salary.xlsx")
        
        # Create CSV format (readable as Excel alternative)
        content = """Employee ID,Name,Department,Base Salary,Bonus,Total Compensation
E001,John Smith,Engineering,150000,30000,180000
E002,Sarah Johnson,Engineering,160000,35000,195000
E003,Michael Brown,Product,140000,28000,168000
E004,Emily Davis,Sales,120000,45000,165000
E005,Robert Wilson,Finance,130000,25000,155000
E006,Jessica Taylor,HR,100000,15000,115000
E007,David Martinez,Engineering,155000,32000,187000
E008,Lisa Anderson,Marketing,110000,20000,130000
E009,James Thomas,Operations,95000,10000,105000
E010,Patricia Garcia,Executive,250000,100000,350000
E011,Christopher Lee,Engineering,145000,29000,174000
E012,Jennifer White,Legal,135000,27000,162000
"""
        
        try:
            with open(filename, 'w') as f:
                f.write(content)
            self.honeytokens.append({
                'type': 'employee_data',
                'path': filename,
                'size': len(content),
                'created': datetime.now().isoformat()
            })
            print(f"✓ Created employee data: {filename}")
            return filename
        except Exception as e:
            print(f"✗ Error creating employee data: {e}")
            return None
    
    def create_backup_file(self) -> str:
        """Create fake server backup file"""
        filename = os.path.join(self.base_dir, "server_backup.sql")
        
        content = """-- Production Database Backup
-- Created: 2026-02-03
-- Size: 2.4 GB (compressed)

-- Database: production_db
CREATE DATABASE IF NOT EXISTS production_db;
USE production_db;

-- Table: users
CREATE TABLE users (
  id INT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(255) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users VALUES
(1, 'admin', 'admin@company.com', '$2y$10$abcd1234efgh5678ijkl9012mnopqrstu', '2024-01-01'),
(2, 'superuser', 'su@company.com', '$2y$10$wxyz9876abcd4321efgh1234ijklmnop', '2024-01-05'),
(3, 'testuser', 'test@company.com', '$2y$10$1234abcd5678efgh9012ijkl3456mnop', '2024-01-10');

-- Table: sensitive_data
CREATE TABLE sensitive_data (
  id INT PRIMARY KEY AUTO_INCREMENT,
  data_type VARCHAR(100),
  encrypted_content LONGBLOB,
  access_level VARCHAR(20),
  created_at TIMESTAMP
);

INSERT INTO sensitive_data VALUES
(1, 'financial_records', UNHEX('E8F9A2B3C4D5E6F7A8B9C0D1E2F3A4B5'), 'secret', '2026-01-20'),
(2, 'client_list', UNHEX('1A2B3C4D5E6F7A8B9C0D1E2F3A4B5C6D'), 'confidential', '2026-01-25');

-- Server Configuration
-- Host: prod-db.company.internal
-- Port: 3306
-- Backup Status: COMPLETED
-- Backup Size: 2.4 GB
-- Compression: gzip
"""
        
        try:
            with open(filename, 'w') as f:
                f.write(content)
            self.honeytokens.append({
                'type': 'database_backup',
                'path': filename,
                'size': len(content),
                'created': datetime.now().isoformat()
            })
            print(f"✓ Created backup file: {filename}")
            return filename
        except Exception as e:
            print(f"✗ Error creating backup file: {e}")
            return None
    
    def create_api_keys_file(self) -> str:
        """Create fake API keys file"""
        filename = os.path.join(self.base_dir, "api_keys.json")
        
        data = {
            "production": {
                "stripe": "<REDACTED>",
                "twilio": "<REDACTED>",
                "sendgrid": "<REDACTED>",
                "github": "<REDACTED>",
                "aws": "<REDACTED>"
            },
            "staging": {
                "stripe": "<REDACTED>",
                "twilio": "<REDACTED>",
                "sendgrid": "<REDACTED>"
            },
            "development": {
                "stripe": "sk_test_123456789",
                "twilio": "ACzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
            }
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            self.honeytokens.append({
                'type': 'api_keys',
                'path': filename,
                'size': len(json.dumps(data)),
                'created': datetime.now().isoformat()
            })
            print(f"✓ Created API keys file: {filename}")
            return filename
        except Exception as e:
            print(f"✗ Error creating API keys: {e}")
            return None
    
    def setup_all(self) -> bool:
        """Create all honeytokens"""
        print("\n" + "="*60)
        print("🍯 CREATING HONEYTOKENS")
        print("="*60)
        
        # Create folder
        if not self.create_hidden_folder():
            return False
        
        print("\nCreating fake files (bait)...")
        self.create_aws_credentials()
        self.create_database_credentials()
        self.create_employee_data()
        self.create_backup_file()
        self.create_api_keys_file()
        
        # Save honeytoken manifest
        self.save_manifest()
        
        print(f"\n✓ Created {len(self.honeytokens)} honeytokens")
        print(f"📁 Location: {os.path.abspath(self.base_dir)}")
        print(f"🍯 Ready to trap attackers!")
        
        return True
    
    def save_manifest(self):
        """Save honeytoken manifest for tracking"""
        manifest_file = os.path.join(self.base_dir, ".manifest.json")
        try:
            with open(manifest_file, 'w') as f:
                json.dump(self.honeytokens, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save manifest: {e}")
    
    def list_honeytokens(self):
        """List all created honeytokens"""
        print("\n🍯 HONEYTOKENS CREATED:")
        for i, token in enumerate(self.honeytokens, 1):
            print(f"\n  {i}. {token['type'].upper()}")
            print(f"     Path: {token['path']}")
            print(f"     Size: {token['size']} bytes")
            print(f"     Created: {token['created']}")


def main():
    """Main setup function"""
    setup = HoneytokenSetup()
    if setup.setup_all():
        setup.list_honeytokens()
        print("\n" + "="*60)
        print("✓ HONEYTOKEN SETUP COMPLETE")
        print("="*60)


if __name__ == '__main__':
    main()
