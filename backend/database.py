import os
import logging
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import ThreadedConnectionPool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://lss_user:lss_secure_password@db:5432/auction_db"
)

try:
    connection_pool = ThreadedConnectionPool(1, 20, dsn=DATABASE_URL)
    logger.info("Pool de ligações ao PostgreSQL inicializado com sucesso.")
except Exception as e:
    logger.critical(f"Falha ao ligar à Base de Dados: {e}")
    connection_pool = None

@contextmanager
def get_db_cursor():
    """
    Context Manager que fornece um cursor de base de dados seguro.
    Garante que os recursos são libertados e que as propriedades ACID
    são respeitadas (auto-commit ou auto-rollback em caso de falha).
    """
    if connection_pool is None:
        raise RuntimeError("O pool de conexões à base de dados não está inicializado.")
    
    conn = connection_pool.getconn()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Exceção capturada na transação. Executado ROLLBACK automático. Erro: {e}")
        raise e
    finally:
        cursor.close()
        connection_pool.putconn(conn)
