-- src/vigilantia/db/schema.sql
--
-- Esquema da base de dados Vigilantia.
-- Semana 1 (infraestrutura): Websites, ScanRuns.
-- Semana 2 (registo de eventos): Findings, ligada a ScanRuns via FK.
--
-- Idempotente: pode ser corrido várias vezes sem erro (usa IF NOT EXISTS).

IF DB_ID(N'Vigilantia') IS NULL
BEGIN
    CREATE DATABASE Vigilantia;
END
GO

USE Vigilantia;
GO

-- =========================================================
-- Websites: um registo por URL alvo analisado.
-- =========================================================
IF OBJECT_ID(N'dbo.Websites', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Websites (
        WebsiteId     INT IDENTITY(1,1) NOT NULL,
        Url           NVARCHAR(2083)    NOT NULL,
        Domain        NVARCHAR(255)     NOT NULL,
        CreatedAt     DATETIME2(0)      NOT NULL
            CONSTRAINT DF_Websites_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_Websites PRIMARY KEY CLUSTERED (WebsiteId),
        -- Um mesmo URL não deve gerar duas identidades de site distintas.
        CONSTRAINT UQ_Websites_Url UNIQUE (Url)
    );

    -- Preparação para correlação por domínio na Semana 4
    -- (ex.: "o mesmo tracker presente em vários websites").
    CREATE NONCLUSTERED INDEX IX_Websites_Domain ON dbo.Websites (Domain);
END
GO

-- =========================================================
-- ScanRuns: uma execução de scan a um Website. Regista só
-- metadados da execução — nenhum resultado/finding ainda.
-- =========================================================
IF OBJECT_ID(N'dbo.ScanRuns', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ScanRuns (
        ScanRunId     INT IDENTITY(1,1) NOT NULL,
        WebsiteId     INT               NOT NULL,
        -- Liga ao report_id de 8 caracteres já gerado em reporter.py,
        -- para conseguir cruzar um registo na BD com o ficheiro HTML.
        ReportRef     CHAR(8)           NULL,
        StartedAt     DATETIME2(0)      NOT NULL
            CONSTRAINT DF_ScanRuns_StartedAt DEFAULT SYSUTCDATETIME(),
        FinishedAt    DATETIME2(0)      NULL,
        Status        NVARCHAR(20)      NOT NULL
            CONSTRAINT DF_ScanRuns_Status DEFAULT N'Running',
        ErrorMessage  NVARCHAR(MAX)     NULL,
        CONSTRAINT PK_ScanRuns PRIMARY KEY CLUSTERED (ScanRunId),
        CONSTRAINT FK_ScanRuns_Websites FOREIGN KEY (WebsiteId)
            REFERENCES dbo.Websites (WebsiteId),
        CONSTRAINT CK_ScanRuns_Status CHECK (
            Status IN (N'Running', N'Completed', N'Failed')
        )
    );

    -- Consultas típicas: "histórico de scans deste website, mais recente primeiro".
    CREATE NONCLUSTERED INDEX IX_ScanRuns_WebsiteId_StartedAt
        ON dbo.ScanRuns (WebsiteId, StartedAt DESC);
END
GO

-- =========================================================
-- Findings: um registo por não-conformidade encontrada num
-- ScanRun (Semana 2 — registo de eventos).
--
-- Campos mínimos pedidos: Website (acessível via JOIN a
-- ScanRuns.WebsiteId — não duplicado aqui), Data/Hora (CreatedAt),
-- Categoria (Category), Tipo (RuleId), Descrição (Description),
-- Evidência (EvidenceJson) e Estado (Status).
--
-- Deliberadamente NÃO incluído nesta fase (Semana 2):
--   - Severidade/classificação automática -> Semana 3.
--   - Deduplicação (UNIQUE por Website+Evento, LastSeen) -> Semana 3.
--     Por isso NÃO há aqui nenhuma constraint UNIQUE nem coluna
--     LastSeen: cada scan gera sempre novas linhas, mesmo repetidas.
-- Category fica NULLABLE e por preencher propositadamente: a lógica
-- de classificação automática (Privacy/Cookies/Tracking/...) só é
-- introduzida na Semana 3, mas a coluna já existe para essa migração
-- não exigir alterar o schema outra vez.
-- =========================================================
IF OBJECT_ID(N'dbo.Findings', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Findings (
        FindingId      INT IDENTITY(1,1) NOT NULL,
        ScanRunId      INT               NOT NULL,
        RuleId         NVARCHAR(10)      NOT NULL,   -- Tipo (ex.: "R09")
        Category       NVARCHAR(50)      NULL,        -- Categoria (por preencher na Semana 3)
        Description    NVARCHAR(MAX)     NOT NULL,
        Recommendation NVARCHAR(MAX)     NOT NULL,
        EvidenceJson    NVARCHAR(MAX)     NOT NULL,    -- Finding.evidence serializado em JSON
        Status         NVARCHAR(20)      NOT NULL
            CONSTRAINT DF_Findings_Status DEFAULT N'Open',  -- Estado
        CreatedAt      DATETIME2(0)      NOT NULL         -- Data/Hora
            CONSTRAINT DF_Findings_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_Findings PRIMARY KEY CLUSTERED (FindingId),
        CONSTRAINT FK_Findings_ScanRuns FOREIGN KEY (ScanRunId)
            REFERENCES dbo.ScanRuns (ScanRunId)
    );

    -- Consulta típica: "todos os findings de um scan específico".
    CREATE NONCLUSTERED INDEX IX_Findings_ScanRunId ON dbo.Findings (ScanRunId);

    -- Preparação para a Semana 3 (agregações por regra, ex.: "quantos
    -- sites têm R01 em aberto"). Sem custo relevante já com poucas linhas.
    CREATE NONCLUSTERED INDEX IX_Findings_RuleId ON dbo.Findings (RuleId);
END
GO
