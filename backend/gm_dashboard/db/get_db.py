from __future__ import annotations

import os

import psycopg2
import psycopg2.extras


def get_connection():
    url = os.environ.get("DATABASE_URL", "postgresql://kaihou_gm:kaihou_gm_dev@localhost:54329/kaihou_gm")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    return conn
