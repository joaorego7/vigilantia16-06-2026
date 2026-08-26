-- =========================================================================
-- CONSULTA PERSONALIZADA DO VIGILANTIA
-- =========================================================================
-- Este script junta as tabelas Websites, ScanRuns e Findings para exibir
-- um relatório unificado de todos os scans efetuados e os respetivos findings.
-- Junta ainda a tabela Companies (LEFT JOIN), preenchida quando o scan foi
-- iniciado a partir dos dados de uma empresa: sites analisados por URL
-- aparecem na mesma, com as colunas da empresa a NULL.
--
-- Como utilizar no SQL Server Management Studio (SSMS):
-- 1. Abra o SSMS e ligue-se ao seu servidor (ex: PC1\SQLEXPRESS).
-- 2. Abra este ficheiro no SSMS (File -> Open -> File) ou copie e cole o código.
-- 3. Certifique-se de que a base de dados ativa é a que configurou no assistente 
--    (por exemplo, 'clientes_websites' ou 'vigilatia_teste').
--    Se necessário, substitua o nome da BD no comando "USE" abaixo.
-- 4. Pressione F5 ou clique em "Execute" para executar a consulta.
-- =========================================================================

-- Substitua 'clientes_websites' pelo nome da sua base de dados atual se for diferente
USE clientes_websites;
GO

SELECT 
    w.Url AS [Website URL],
    ISNULL(c.LegalName, c.Name) AS [Empresa],
    c.Nif AS [NIF],
    c.Address AS [Morada],
    CASE c.RegistryVerified
        WHEN 1 THEN 'Confirmado'
        WHEN 0 THEN 'Não confirmado'
        ELSE NULL
    END AS [Registo Público],
    s.StartedAt AS [Data/Hora do Scan],
    s.Status AS [Estado do Scan],
    ISNULL(f.RuleId, 'Conforme') AS [ID da Regra],
    ISNULL(f.Description, 'Nenhuma não-conformidade detetada neste scan.') AS [Descrição da Não-Conformidade],
    ISNULL(f.Recommendation, 'Sem recomendações necessárias.') AS [Recomendação],
    ISNULL(f.Status, '-') AS [Estado do Finding]
FROM dbo.Websites w
INNER JOIN dbo.ScanRuns s ON w.WebsiteId = s.WebsiteId
LEFT JOIN dbo.Companies c ON w.WebsiteId = c.WebsiteId
LEFT JOIN dbo.Findings f ON s.ScanRunId = f.ScanRunId
ORDER BY s.StartedAt DESC, w.Url, f.RuleId;
GO
