"""Database manager for alloy/material queries. Uses env vars for credentials."""
import psycopg2
from typing import Any
import decimal
import logging

logger = logging.getLogger(__name__)


def clean_sql(sql: str) -> str:
    sql = sql.replace("\\n", " ")
    sql = sql.replace("\n", " ")
    sql = sql.replace("\'", "'")
    return sql


def convert_type(input_val: Any) -> str:
    if type(input_val) == decimal.Decimal:
        input_val = float(input_val)
    return str(input_val)


def convert_records(records) -> str:
    if isinstance(records, dict):
        return str(records)
    if records and len(records) == 1 and len(records[0]) == 1:
        records = records[0][0]
    return convert_type(records)


class DBManager:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        user: str = "",
        password: str = "",
        database: str = "postgres"
    ) -> None:
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port

    def connect(self) -> None:
        self.connection = None
        self.cursor = None
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            self.cursor = self.connection.cursor()
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL: {e}")
            raise

    def close(self) -> None:
        if self.connection:
            self.connection.close()
        if self.cursor:
            self.cursor.close()

    def execute_sql(self, sql: str = None) -> list:
        records = []
        if self.cursor and sql:
            sql = clean_sql(sql)
            try:
                self.cursor.execute(sql)
                records = self.cursor.fetchall()
            except Exception as e:
                records = {"error": str(e)}
        return convert_records(records)
