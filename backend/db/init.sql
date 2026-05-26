-- Inicialização do Esquema de Dados para a Plataforma de Leilões
-- Alinhado com as boas práticas de LSS 2026 (Segurança e Normalização)

-- Garantir isolamento de transações em caso de concorrência extrema
BEGIN;

-- 1. Remoção de Tabelas Existentes para idempotência de execução (útil em testes)
DROP TABLE IF EXISTS bids CASCADE;
DROP TABLE IF EXISTS auctions CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- 2. Tabela de Utilizadores
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 3. Tabela de Leilões
CREATE TABLE auctions (
    id SERIAL PRIMARY KEY,
    creator_id INTEGER NOT NULL,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    starting_price NUMERIC(10, 2) NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Restrições de Integridade Relacional e Lógica de Negócio (Slides de DB I)
    CONSTRAINT fk_auction_creator FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT check_starting_price CHECK (starting_price > 0)
);

-- 4. Tabela de Licitações (Bids)
CREATE TABLE bids (
    id SERIAL PRIMARY KEY,
    auction_id INTEGER NOT NULL,
    bidder_id INTEGER NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Restrições de Integridade Relacional e Lógica de Negócio
    CONSTRAINT fk_bid_auction FOREIGN KEY (auction_id) REFERENCES auctions(id) ON DELETE CASCADE,
    CONSTRAINT fk_bid_bidder FOREIGN KEY (bidder_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT check_bid_amount CHECK (amount > 0)
);

-- 5. Otimização de Performance (Lab 1: Impacto da Indexação)
-- Criar índices B-Tree nas chaves estrangeiras mais pesquisadas e filtros ordenados
CREATE INDEX idx_auctions_is_active_end_time ON auctions(is_active, end_time);
CREATE INDEX idx_bids_auction_amount ON bids(auction_id, amount DESC);

COMMIT;