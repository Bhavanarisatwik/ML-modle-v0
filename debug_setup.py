import sys, os
sys.path.insert(0, r'C:\DecoyVerse')
os.chdir(r'C:\DecoyVerse')
from agent_setup import HoneytokenSetup

config = {'initial_decoys': 3, 'initial_honeytokens': 5}
setup = HoneytokenSetup()
result = setup.setup_all(config)
print(f'Setup result: {result}')
print(f'Decoys: {len(setup.decoys)}')
print(f'Honeytokens: {len(setup.honeytokens)}')
deployed = setup.get_deployed_decoys()
print(f'Deployed count: {len(deployed)}')
for d in deployed[:5]:
    print(f'  file_path={d.get("file_path")}  file_name={d.get("file_name")}')
paths = [d.get('file_path', d.get('path', '')) for d in deployed if d.get('file_path') or d.get('path')]
print(f'Extracted paths: {len(paths)}')
for p in paths[:5]:
    exists = os.path.exists(p) if p else False
    print(f'  {p} (exists={exists})')
