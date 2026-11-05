"""Підключення до трьох баз лабораторної."""

import psycopg2
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient

PG_DB = "university_lab2"
PG = dict(host="localhost", port=5432, user="sasha")
MONGO_URI = "mongodb://127.0.0.1:27017"
MONGO_DB = "university_lab2"


def pg(dbname=PG_DB, dict_rows=False):
    return psycopg2.connect(dbname=dbname, cursor_factory=RealDictCursor if dict_rows else None, **PG)


def mongo():
    return MongoClient(MONGO_URI)[MONGO_DB]
