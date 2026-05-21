"""Vercel serverless entry point"""
import sys
import os

# Add project root to Python path so 'from main import app' works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
