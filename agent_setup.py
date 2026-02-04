"""
Smart Honeytoken Deployment Module
Deploys randomized, realistic decoys across the system to trap attackers
"""

import os
import json
import random
import string
import platform
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple


class SmartHoneytokenDeployer:
    """
    Intelligent honeytoken deployment system
    - Randomized file names and content
    - Strategic placement in sensitive directories
    - OS-aware deployment paths
    - Realistic fake credentials
    """
    
    # Realistic file name patterns attackers look for
    FILE_NAME_PATTERNS = {
        'credentials': [
            'credentials', 'creds', 'secrets', 'passwords', 'auth',
            'login', 'access', 'keys', 'tokens', 'config'
        ],
        'cloud': [
            'aws', 'azure', 'gcp', 'cloud', 's3', 'ec2', 'lambda',
            'terraform', 'ansible', 'docker', 'k8s', 'kubernetes'
        ],
        'database': [
            'db', 'database', 'mysql', 'postgres', 'mongo', 'redis',
            'sql', 'backup', 'dump', 'export'
        ],
        'api': [
            'api', 'token', 'jwt', 'oauth', 'bearer', 'webhook',
            'stripe', 'twilio', 'sendgrid', 'slack'
        ],
        'ssh': [
            'id_rsa', 'id_ed25519', 'id_dsa', 'authorized_keys',
            'known_hosts', 'ssh_config'
        ],
        'env': [
            'env', 'environment', 'local', 'development', 'production',
            'staging', 'secrets'
        ]
    }
    
    # File extensions that look realistic
    EXTENSIONS = ['.txt', '.env', '.json', '.yaml', '.yml', '.conf', '.cfg', '.key', '.pem', '']
    
    # Prefixes/suffixes that make files look real
    MODIFIERS = ['', '_backup', '_old', '_new', '_prod', '_dev', '_staging', '_2024', '_2025', '_copy', '.bak']
    
    def __init__(self, base_dir: str = None):
        """Initialize the smart deployer"""
        self.os_type = platform.system().lower()
        self.base_dir = base_dir or self._get_default_base_dir()
        self.honeytokens: List[Dict] = []
        self.deployed_paths: List[str] = []
        
    def _get_default_base_dir(self) -> str:
        """Get OS-appropriate base directory"""
        home = Path.home()
        if self.os_type == 'windows':
            return str(home / 'AppData' / 'Local' / '.cache')
        elif self.os_type == 'darwin':  # macOS
            return str(home / '.local' / 'share')
        else:  # Linux
            return str(home / '.cache' / '.data')
    
    def _get_target_directories(self) -> List[Tuple[str, int]]:
        """
        Get strategic directories to plant honeytokens
        Returns: List of (path, priority) tuples
        Priority: Higher = more attractive to attackers
        """
        home = Path.home()
        targets = []
        
        if self.os_type == 'windows':
            targets = [
                # High-value Windows locations
                (str(home / 'Documents'), 8),
                (str(home / 'Desktop'), 7),
                (str(home / 'Downloads'), 6),
                (str(home / '.aws'), 10),
                (str(home / '.ssh'), 10),
                (str(home / 'AppData' / 'Local'), 5),
                (str(home / 'AppData' / 'Roaming'), 5),
                (str(home / '.docker'), 9),
                (str(home / '.kube'), 9),
                (str(home / '.azure'), 9),
                (str(home / 'source' / 'repos'), 7),
                (str(home / 'projects'), 7),
                ('C:\\inetpub', 8),
                ('C:\\xampp', 7),
                ('C:\\wamp', 7),
            ]
        elif self.os_type == 'darwin':  # macOS
            targets = [
                (str(home / 'Documents'), 8),
                (str(home / 'Desktop'), 7),
                (str(home / 'Downloads'), 6),
                (str(home / '.aws'), 10),
                (str(home / '.ssh'), 10),
                (str(home / '.docker'), 9),
                (str(home / '.kube'), 9),
                (str(home / 'Library' / 'Application Support'), 5),
                (str(home / 'Developer'), 7),
                (str(home / 'projects'), 7),
                ('/etc', 6),
                ('/var/www', 8),
            ]
        else:  # Linux
            targets = [
                (str(home / 'Documents'), 8),
                (str(home / 'Desktop'), 7),
                (str(home / '.aws'), 10),
                (str(home / '.ssh'), 10),
                (str(home / '.docker'), 9),
                (str(home / '.kube'), 9),
                (str(home / '.config'), 7),
                (str(home / '.local' / 'share'), 5),
                (str(home / 'projects'), 7),
                ('/var/www', 8),
                ('/opt', 6),
                ('/tmp', 3),
                (str(home / '.gnupg'), 9),
            ]
        
        # Filter to only existing directories (or create high-value ones)
        valid_targets = []
        for path, priority in targets:
            if os.path.exists(path) and os.access(path, os.W_OK):
                valid_targets.append((path, priority))
            elif priority >= 9:  # Create high-priority dirs
                try:
                    os.makedirs(path, exist_ok=True)
                    valid_targets.append((path, priority))
                except:
                    pass
        
        return valid_targets
    
    def _generate_random_filename(self, category: str = None) -> str:
        """Generate a realistic random filename"""
        if category is None:
            category = random.choice(list(self.FILE_NAME_PATTERNS.keys()))
        
        base_names = self.FILE_NAME_PATTERNS.get(category, self.FILE_NAME_PATTERNS['credentials'])
        base = random.choice(base_names)
        
        modifier = random.choice(self.MODIFIERS)
        extension = random.choice(self.EXTENSIONS)
        
        # Sometimes add a random suffix
        if random.random() < 0.3:
            suffix = ''.join(random.choices(string.digits, k=random.randint(1, 4)))
            base = f"{base}_{suffix}"
        
        # Sometimes add underscore or dash variations
        if random.random() < 0.4:
            base = base.replace('_', '-') if '_' in base else base.replace('-', '_')
        
        return f"{base}{modifier}{extension}"
    
    def _generate_aws_credentials(self) -> str:
        """Generate realistic fake AWS credentials"""
        access_key = 'AKIA' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        secret_key = ''.join(random.choices(string.ascii_letters + string.digits + '+/', k=40))
        
        profiles = ['default', 'production', 'staging', 'dev', 'backup']
        selected_profiles = random.sample(profiles, k=random.randint(1, 3))
        
        content = ""
        for profile in selected_profiles:
            region = random.choice(['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1'])
            content += f"""[{profile}]
aws_access_key_id = {access_key}
aws_secret_access_key = {secret_key}
region = {region}
output = json

"""
        return content.strip()
    
    def _generate_db_credentials(self) -> str:
        """Generate realistic fake database credentials"""
        db_types = [
            ('MYSQL', 3306, 'mysql'),
            ('POSTGRES', 5432, 'postgresql'),
            ('MONGODB', 27017, 'mongodb'),
            ('REDIS', 6379, 'redis'),
        ]
        
        selected = random.sample(db_types, k=random.randint(2, 4))
        
        # Generate random but realistic-looking values
        def random_password():
            chars = string.ascii_letters + string.digits + '!@#$%^&*'
            return ''.join(random.choices(chars, k=random.randint(16, 24)))
        
        def random_host():
            prefixes = ['db', 'database', 'prod-db', 'rds', 'cluster']
            domains = ['internal', 'local', 'company.com', 'aws.internal']
            return f"{random.choice(prefixes)}-{random.randint(1,5)}.{random.choice(domains)}"
        
        content = "# Database Credentials - DO NOT SHARE\n"
        content += f"# Generated: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        
        for db_name, port, scheme in selected:
            content += f"# {db_name}\n"
            content += f"{db_name}_HOST={random_host()}\n"
            content += f"{db_name}_PORT={port}\n"
            content += f"{db_name}_USER={random.choice(['admin', 'root', 'dbadmin', 'app_user'])}\n"
            content += f"{db_name}_PASSWORD={random_password()}\n"
            content += f"{db_name}_DATABASE={random.choice(['production', 'main', 'app', 'data'])}_db\n"
            content += f"{db_name}_URI={scheme}://${{" + f"{db_name}_USER}}:${{{db_name}_PASSWORD}}@${{{db_name}_HOST}}:${{{db_name}_PORT}}/${{{db_name}_DATABASE}}\n\n"
        
        return content.strip()
    
    def _generate_api_keys(self) -> str:
        """Generate realistic fake API keys"""
        services = [
            ('STRIPE', 'sk_live_', 48),
            ('STRIPE_PUBLISHABLE', 'pk_live_', 48),
            ('SENDGRID', 'SG.', 64),
            ('TWILIO_SID', 'AC', 32),
            ('TWILIO_TOKEN', '', 32),
            ('SLACK_TOKEN', 'xoxb-', 50),
            ('GITHUB_TOKEN', 'ghp_', 36),
            ('OPENAI_KEY', 'sk-', 48),
            ('JWT_SECRET', '', 64),
            ('ENCRYPTION_KEY', '', 32),
        ]
        
        selected = random.sample(services, k=random.randint(3, 6))
        
        content = "# API Keys and Tokens\n"
        content += f"# Environment: {random.choice(['production', 'staging', 'live'])}\n\n"
        
        for name, prefix, length in selected:
            key = prefix + ''.join(random.choices(string.ascii_letters + string.digits, k=length))
            content += f"{name}={key}\n"
        
        return content.strip()
    
    def _generate_ssh_key(self) -> str:
        """Generate a fake SSH private key"""
        # This is a fake key structure - not a real key
        fake_key_body = '\n'.join([
            ''.join(random.choices(string.ascii_letters + string.digits + '+/', k=64))
            for _ in range(25)
        ])
        
        return f"""-----BEGIN OPENSSH PRIVATE KEY-----
{fake_key_body}
-----END OPENSSH PRIVATE KEY-----
"""
    
    def _generate_json_config(self) -> str:
        """Generate fake JSON configuration"""
        config = {
            "database": {
                "host": f"db-{random.randint(1,9)}.internal.company.com",
                "port": random.choice([3306, 5432, 27017]),
                "username": random.choice(["admin", "app_user", "service"]),
                "password": ''.join(random.choices(string.ascii_letters + string.digits, k=20)),
            },
            "api": {
                "key": ''.join(random.choices(string.ascii_letters + string.digits, k=32)),
                "secret": ''.join(random.choices(string.ascii_letters + string.digits, k=48)),
                "endpoint": f"https://api.{random.choice(['prod', 'live', 'main'])}.company.com"
            },
            "aws": {
                "access_key": 'AKIA' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=16)),
                "secret_key": ''.join(random.choices(string.ascii_letters + string.digits, k=40)),
                "region": random.choice(["us-east-1", "eu-west-1", "ap-southeast-1"])
            },
            "encryption": {
                "key": ''.join(random.choices(string.ascii_letters + string.digits, k=32)),
                "algorithm": "AES-256-GCM"
            }
        }
        return json.dumps(config, indent=2)
    
    def _generate_kubeconfig(self) -> str:
        """Generate fake Kubernetes config"""
        cluster_name = f"prod-cluster-{random.randint(1, 5)}"
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
        
        return f"""apiVersion: v1
kind: Config
clusters:
- cluster:
    certificate-authority-data: {hashlib.sha256(str(random.random()).encode()).hexdigest()}
    server: https://kubernetes.{random.choice(['prod', 'live'])}.company.com:6443
  name: {cluster_name}
contexts:
- context:
    cluster: {cluster_name}
    user: admin
  name: {cluster_name}-admin
current-context: {cluster_name}-admin
users:
- name: admin
  user:
    token: {token}
"""
    
    def _get_content_generator(self, category: str):
        """Get appropriate content generator for category"""
        generators = {
            'credentials': self._generate_db_credentials,
            'cloud': self._generate_aws_credentials,
            'database': self._generate_db_credentials,
            'api': self._generate_api_keys,
            'ssh': self._generate_ssh_key,
            'env': self._generate_api_keys,
        }
        return generators.get(category, self._generate_json_config)
    
    def deploy_honeytoken(self, directory: str, category: str = None) -> Dict:
        """Deploy a single honeytoken to a directory"""
        if category is None:
            category = random.choice(list(self.FILE_NAME_PATTERNS.keys()))
        
        filename = self._generate_random_filename(category)
        filepath = os.path.join(directory, filename)
        
        # Skip if file already exists or path already used
        if os.path.exists(filepath) or filepath in self.deployed_paths:
            # Try with different name
            filename = self._generate_random_filename(category)
            filepath = os.path.join(directory, filename)
        
        # Generate content
        generator = self._get_content_generator(category)
        content = generator()
        
        try:
            # Create subdirectory if needed (for hidden folders like .aws)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Make file hidden on Windows
            if self.os_type == 'windows' and filename.startswith('.'):
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(filepath, 2)
            
            honeytoken = {
                'type': category,
                'file_name': filename,
                'path': filepath,
                'size': len(content),
                'created': datetime.now().isoformat(),
                'category': category
            }
            
            self.honeytokens.append(honeytoken)
            self.deployed_paths.append(filepath)
            
            print(f"  ✓ Deployed: {filepath}")
            return honeytoken
            
        except Exception as e:
            print(f"  ✗ Failed to deploy to {filepath}: {e}")
            return None
    
    def setup_all(self, deployment_config: dict = None) -> bool:
        """
        Deploy honeytokens based on configuration
        
        Args:
            deployment_config: {
                'initial_decoys': int,
                'initial_honeytokens': int,
                'deploy_path': str (optional custom path)
            }
        """
        print("\n" + "="*60)
        print("🍯 SMART HONEYTOKEN DEPLOYMENT")
        print("="*60)
        print(f"   OS: {self.os_type}")
        
        # Parse config
        initial_decoys = 3
        initial_honeytokens = 5
        
        if deployment_config:
            initial_decoys = deployment_config.get('initial_decoys', 3)
            initial_honeytokens = deployment_config.get('initial_honeytokens', 5)
        
        total_to_deploy = initial_decoys + initial_honeytokens
        print(f"   Deploying: {total_to_deploy} honeytokens ({initial_decoys} decoys + {initial_honeytokens} tokens)")
        
        # Get target directories
        targets = self._get_target_directories()
        if not targets:
            print("   ✗ No writable target directories found!")
            # Fallback to base_dir
            os.makedirs(self.base_dir, exist_ok=True)
            targets = [(self.base_dir, 5)]
        
        print(f"   Found {len(targets)} target locations")
        
        # Sort by priority and select deployment locations
        targets.sort(key=lambda x: x[1], reverse=True)
        
        # Categories to deploy (weighted by importance)
        categories = ['cloud', 'cloud', 'database', 'api', 'ssh', 'credentials', 'env']
        
        print("\n   Deploying honeytokens...")
        deployed_count = 0
        
        for i in range(total_to_deploy):
            # Select directory (weighted by priority)
            if targets:
                # Bias toward high-priority directories
                weights = [t[1] for t in targets]
                directory = random.choices(targets, weights=weights, k=1)[0][0]
            else:
                directory = self.base_dir
            
            # Select category
            category = random.choice(categories)
            
            result = self.deploy_honeytoken(directory, category)
            if result:
                deployed_count += 1
        
        # Save manifest
        self.save_manifest()
        
        print(f"\n   ✓ Successfully deployed {deployed_count}/{total_to_deploy} honeytokens")
        print(f"   📁 Spread across {len(set(os.path.dirname(h['path']) for h in self.honeytokens))} directories")
        print(f"   🍯 Ready to trap attackers!")
        
        return deployed_count > 0
    
    def save_manifest(self):
        """Save deployment manifest for tracking"""
        manifest_dir = self.base_dir
        os.makedirs(manifest_dir, exist_ok=True)
        
        manifest_file = os.path.join(manifest_dir, ".honeytoken_manifest.json")
        
        manifest = {
            "deployed_at": datetime.now().isoformat(),
            "os": self.os_type,
            "count": len(self.honeytokens),
            "honeytokens": self.honeytokens
        }
        
        try:
            with open(manifest_file, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Hide manifest on Windows
            if self.os_type == 'windows':
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(manifest_file, 2)
                
        except Exception as e:
            print(f"   Warning: Could not save manifest: {e}")
    
    def get_deployed_decoys(self) -> List[Dict]:
        """Return list of deployed decoys for backend registration"""
        return [{
            "file_name": h["file_name"],
            "file_path": h["path"],
            "type": h["type"],
            "status": "active",
            "auto_deployed": True
        } for h in self.honeytokens]
    
    def list_honeytokens(self):
        """Display deployed honeytokens"""
        print("\n🍯 DEPLOYED HONEYTOKENS:")
        
        # Group by directory
        by_dir = {}
        for token in self.honeytokens:
            dir_path = os.path.dirname(token['path'])
            if dir_path not in by_dir:
                by_dir[dir_path] = []
            by_dir[dir_path].append(token)
        
        for dir_path, tokens in by_dir.items():
            print(f"\n  📁 {dir_path}")
            for token in tokens:
                print(f"     • {token['file_name']} ({token['type']}) - {token['size']} bytes")


# Backwards compatibility alias
HoneytokenSetup = SmartHoneytokenDeployer


def main():
    """Test deployment"""
    deployer = SmartHoneytokenDeployer()
    
    config = {
        'initial_decoys': 3,
        'initial_honeytokens': 5
    }
    
    if deployer.setup_all(config):
        deployer.list_honeytokens()
        print("\n" + "="*60)
        print("✓ SMART HONEYTOKEN DEPLOYMENT COMPLETE")
        print("="*60)


if __name__ == '__main__':
    main()
