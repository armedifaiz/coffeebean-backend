import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'coffeebean_secret'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///coffeebean.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'coffeebean_jwt_secret'

    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']
