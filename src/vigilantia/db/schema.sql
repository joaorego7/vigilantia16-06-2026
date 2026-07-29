-- src/vigilantia/db/schema.sql
--
-- Esquema inicial da base de dados Vigilantia (Semana 1 — infraestrutura).
-- Contém apenas as tabelas de identidade/auditoria necessárias para
-- suportar o registo de eventos na Semana 2 (Websites, ScanRuns).
-- NÃO contém ainda a tabela de eventos/findings — essa é introduzida
-- na Semana 2, já com FK para ScanRuns.
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
