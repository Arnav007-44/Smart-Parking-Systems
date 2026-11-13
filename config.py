"""Database settings.

Change DB_PASSWORD below to your own MySQL password,
or set environment variables with the same names.
"""
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")   # <-- put your MySQL password here
DB_NAME = os.environ.get("DB_NAME", "smart_parking")
