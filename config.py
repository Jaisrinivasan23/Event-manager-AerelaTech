import os

class Config:
    """Configuration class for Flask application"""
    
    # Secret key for session management
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database configuration
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'events.db')
    
    # Disable FSAModifications tracking (saves resources)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
