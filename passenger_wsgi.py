# -*- coding: utf-8 -*-
import sys
import os

# Add the application directory to Python path
app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

# Set the working directory
os.chdir(app_dir)

# Force UTF-8 encoding for stdout/stderr
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Try to import and run the app
try:
    from app import app as application
except Exception as e:
    # Log the error with proper encoding
    with open(os.path.join(app_dir, 'passenger_error.log'), 'w', encoding='utf-8') as f:
        import traceback
        f.write(f"Error importing app: {e}\n")
        traceback.print_exc(file=f)
    raise
