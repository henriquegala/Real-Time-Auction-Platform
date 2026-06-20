import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
import bcrypt
import jwt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "lss_secure_fallback_secret_key_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def hash_password(password: str) -> str:
    """
    Gera um hash Bcrypt seguro com salt aleatório a partir de uma password.
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12) 
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifica se uma password em texto claro corresponde ao hash guardado.
    """
    try:
        password_bytes = password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        logger.error(f"Erro ao verificar a password: {e}")
        return False

def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Gera um Token de Acesso JWT assinado pelo servidor contendo os dados do utilizador.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict]:
    """
    Descodifica e valida a assinatura e data de expiração do Token JWT.
    Retorna o dicionário de claims se for válido, ou None se tiver expirado/inválido.
    """
    try:
        decoded_payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded_payload
    except jwt.ExpiredSignatureError:
        logger = logging.getLogger(__name__) if '__name__' in locals() else None
        if logger: logger.warning("Token expirado.")
        return None
    except jwt.InvalidTokenError:
        return None
