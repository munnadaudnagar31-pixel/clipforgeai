import os
import glob

def prepend_sys_path():
    base_dir = r'C:\myexp\clipforge\backend\app'
    snippet = '''import os
import sys
# Inject workspace paths to fix IDE red lines and Render imports
_app_dir = os.path.dirname(os.path.abspath(__file__))
while os.path.basename(_app_dir) != 'app' and _app_dir != os.path.dirname(_app_dir):
    _app_dir = os.path.dirname(_app_dir)
_backend_dir = os.path.dirname(_app_dir)
_root_dir = os.path.dirname(_backend_dir)
if _backend_dir not in sys.path: sys.path.insert(0, _backend_dir)
if _root_dir not in sys.path: sys.path.insert(0, _root_dir)
'''
    files = glob.glob(base_dir + '/**/*.py', recursive=True)
    for f in files:
        if '__init__' in f: continue
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
        
        if '# Inject workspace paths' not in content:
            # Handle files that might have #!/usr/bin/env python or similar
            if content.startswith('\"\"\"'):
                # find the end of the docstring
                end_idx = content.find('\"\"\"', 3)
                if end_idx != -1:
                    new_content = content[:end_idx+3] + '\n' + snippet + content[end_idx+3:]
                else:
                    new_content = snippet + '\n' + content
            else:
                new_content = snippet + '\n' + content
            
            with open(f, 'w', encoding='utf-8') as file:
                file.write(new_content)
                print(f'Updated {f}')

prepend_sys_path()
