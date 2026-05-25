-- ============================================================
--  Sistema de Gestão de Doações Inteligente
--  UNIG EAD — Projeto Integrador 4º Período — 2025
--  Prof. Denise Moraes
--  ODS 1: Erradicação da Pobreza
-- ============================================================

-- Extensão para UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ----------------------------------------------------------
-- 1. USUÁRIO (base para herança lógica)
-- ----------------------------------------------------------
CREATE TABLE usuario (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome        VARCHAR(120)  NOT NULL,
    email       VARCHAR(180)  NOT NULL UNIQUE,
    senha_hash  VARCHAR(256)  NOT NULL,
    role        VARCHAR(20)   NOT NULL CHECK (role IN ('doador','beneficiario','organizacao','admin')),
    ativo       BOOLEAN       NOT NULL DEFAULT TRUE,
    criado_em   TIMESTAMP     NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMP   NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------
-- 2. DOADOR
-- ----------------------------------------------------------
CREATE TABLE doador (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id  UUID NOT NULL UNIQUE REFERENCES usuario(id) ON DELETE CASCADE,
    cpf         VARCHAR(14)  NOT NULL UNIQUE,
    telefone    VARCHAR(20),
    lat         NUMERIC(9,6),
    lng         NUMERIC(9,6)
);

-- ----------------------------------------------------------
-- 3. BENEFICIÁRIO
-- ----------------------------------------------------------
CREATE TABLE beneficiario (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id  UUID NOT NULL UNIQUE REFERENCES usuario(id) ON DELETE CASCADE,
    cpf         VARCHAR(14)  NOT NULL UNIQUE,
    num_membros INTEGER      NOT NULL DEFAULT 1 CHECK (num_membros >= 1),
    lat         NUMERIC(9,6),
    lng         NUMERIC(9,6)
);

-- ----------------------------------------------------------
-- 4. ORGANIZAÇÃO
-- ----------------------------------------------------------
CREATE TABLE organizacao (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id  UUID NOT NULL UNIQUE REFERENCES usuario(id) ON DELETE CASCADE,
    cnpj        VARCHAR(18)   NOT NULL UNIQUE,
    endereco    VARCHAR(256),
    lat         NUMERIC(9,6),
    lng         NUMERIC(9,6)
);

-- ----------------------------------------------------------
-- 5. ITEM DOADO
-- ----------------------------------------------------------
CREATE TYPE status_item AS ENUM ('disponivel', 'reservado', 'entregue', 'cancelado');

CREATE TABLE item_doado (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doador_id   UUID NOT NULL REFERENCES doador(id) ON DELETE CASCADE,
    categoria   VARCHAR(60)   NOT NULL,
    descricao   TEXT,
    status      status_item   NOT NULL DEFAULT 'disponivel',
    criado_em   TIMESTAMP     NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMP   NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------
-- 6. SOLICITAÇÃO
-- ----------------------------------------------------------
CREATE TYPE status_sol AS ENUM ('aberta', 'em_atendimento', 'atendida', 'cancelada');

CREATE TABLE solicitacao (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    beneficiario_id UUID NOT NULL REFERENCES beneficiario(id) ON DELETE CASCADE,
    categoria       VARCHAR(60)   NOT NULL,
    descricao       TEXT,
    status          status_sol    NOT NULL DEFAULT 'aberta',
    criado_em       TIMESTAMP     NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMP     NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------
-- 7. DOAÇÃO (matching item ↔ solicitação)
-- ----------------------------------------------------------
CREATE TYPE status_doacao AS ENUM ('pendente', 'confirmada', 'entregue', 'cancelada');

CREATE TABLE doacao (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    item_id         UUID NOT NULL UNIQUE REFERENCES item_doado(id),
    solicitacao_id  UUID NOT NULL UNIQUE REFERENCES solicitacao(id),
    organizacao_id  UUID REFERENCES organizacao(id),
    status          status_doacao NOT NULL DEFAULT 'pendente',
    data_entrega    DATE,
    criado_em       TIMESTAMP     NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMP     NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------
-- 8. FEEDBACK
-- ----------------------------------------------------------
CREATE TABLE feedback (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doacao_id   UUID NOT NULL REFERENCES doacao(id) ON DELETE CASCADE,
    usuario_id  UUID NOT NULL REFERENCES usuario(id),
    nota        SMALLINT     NOT NULL CHECK (nota BETWEEN 1 AND 5),
    comentario  TEXT,
    criado_em   TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------
-- ÍNDICES (performance)
-- ----------------------------------------------------------
CREATE INDEX idx_item_doador    ON item_doado(doador_id);
CREATE INDEX idx_item_status    ON item_doado(status);
CREATE INDEX idx_item_categoria ON item_doado(categoria);
CREATE INDEX idx_sol_benef      ON solicitacao(beneficiario_id);
CREATE INDEX idx_sol_status     ON solicitacao(status);
CREATE INDEX idx_sol_categoria  ON solicitacao(categoria);
CREATE INDEX idx_doacao_status  ON doacao(status);
CREATE INDEX idx_feedback_doa   ON feedback(doacao_id);

-- ----------------------------------------------------------
-- VIEW: relatório de impacto
-- ----------------------------------------------------------
CREATE OR REPLACE VIEW vw_relatorio_impacto AS
SELECT
    COUNT(DISTINCT d.id)              AS total_doacoes,
    COUNT(DISTINCT i.doador_id)       AS total_doadores_ativos,
    COUNT(DISTINCT s.beneficiario_id) AS total_beneficiarios_atendidos,
    COUNT(CASE WHEN d.status = 'entregue' THEN 1 END) AS doacoes_entregues,
    COUNT(CASE WHEN d.status = 'pendente' THEN 1 END) AS doacoes_pendentes,
    AVG(f.nota)::NUMERIC(3,2)         AS media_satisfacao
FROM doacao d
LEFT JOIN item_doado  i ON i.id = d.item_id
LEFT JOIN solicitacao s ON s.id = d.solicitacao_id
LEFT JOIN feedback    f ON f.doacao_id = d.id;

-- ----------------------------------------------------------
-- DADOS DE EXEMPLO (seed)
-- ----------------------------------------------------------
INSERT INTO usuario (nome, email, senha_hash, role) VALUES
  ('Admin Sistema',     'admin@doacoes.app',    'hashed_pw_1', 'admin'),
  ('João Silva',        'joao@email.com',        'hashed_pw_2', 'doador'),
  ('Maria Souza',       'maria@email.com',       'hashed_pw_3', 'beneficiario'),
  ('ONG Esperança',     'ong@esperanca.org',     'hashed_pw_4', 'organizacao');

