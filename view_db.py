import sys
import os
from dotenv import load_dotenv
import pyodbc

# Adicionar pasta 'src' ao PATH para carregar as configurações do projeto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from vigilantia.db.config import DatabaseConfig

# Carregar variáveis do .env
load_dotenv()

try:
    cfg = DatabaseConfig.from_env()
    conn_str = cfg.to_connection_string()
except Exception as e:
    print(f"Erro ao carregar configurações do .env: {e}")
    sys.exit(1)

print("A ligar à base de dados...")
try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Query unificada com LEFT JOIN para listar todos os sites e os seus respetivos findings
    query = """
        SELECT 
            w.Url,
            s.StartedAt,
            s.Status AS ScanStatus,
            f.RuleId,
            f.Description
        FROM dbo.Websites w
        INNER JOIN dbo.ScanRuns s ON w.WebsiteId = s.WebsiteId
        LEFT JOIN dbo.Findings f ON s.ScanRunId = f.ScanRunId
        ORDER BY s.StartedAt DESC, w.Url, f.RuleId;
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()

    print("\n=========================================================================================================")
    print("                              RELATÓRIO UNIFICADO DE WEBSITES E NÃO-CONFORMIDADES")
    print("=========================================================================================================")
    print(f"{'Website (URL)':<35} | {'Data/Hora do Scan':<19} | {'Estado':<10} | {'Regra':<6} | {'Descrição da Regra'}")
    print("-" * 105)

    if not rows:
        print("Nenhum registo de scan ou websites encontrado na base de dados.")
    else:
        for row in rows:
            # Truncar URL para caber na coluna
            url = row.Url
            if len(url) > 32:
                url = url[:32] + "..."
            
            # Formatar a data
            date_str = str(row.StartedAt)[:19] if row.StartedAt else "N/A"
            
            # Estado do scan
            scan_status = row.ScanStatus or "N/A"
            
            # Regra e descrição
            rule = row.RuleId if row.RuleId else "Conforme"
            desc = row.Description if row.Description else "Nenhuma não-conformidade detetada neste scan."
            if len(desc) > 35:
                desc = desc[:32] + "..."
            
            print(f"{url:<35} | {date_str:<19} | {scan_status:<10} | {rule:<6} | {desc}")
            
    conn.close()
    print("=========================================================================================================")
    print("Listagem concluída!")
except Exception as e:
    print(f"\nErro ao ligar ou consultar a base de dados: {e}")
