import os
import sys
from pathlib import Path

def setup_path(service_name=None):
    root_path = Path(__file__).parent.parent.parent.absolute()
    if str(root_path) not in sys.path:
        sys.path.append(str(root_path))
    
    if service_name:
        s_path = root_path / "services" / service_name
        if s_path.is_dir() and str(s_path) not in sys.path:
            sys.path.append(str(s_path))


