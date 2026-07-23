import sys
import os

# Set working directory & Python path to application directory
app_dir = os.path.dirname(__file__)
sys.path.insert(0, app_dir)
os.chdir(app_dir)

# Expose application callable for Phusion Passenger / cPanel / LiteSpeed
from app import app as application
