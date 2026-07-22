import sys
import os

# Add application root directory to python path
sys.path.insert(0, os.path.dirname(__file__))

# Expose application callable for Phusion Passenger / cPanel / LiteSpeed
from app import app as application
