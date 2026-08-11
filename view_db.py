import pyodbc
from dotenv import load_dotenv
import os

# Carregar variáveis do .env
load_dotenv()

server = os.getenv("VIGILANTIA_DB_SERVER", "localhost\\SQLEXPRESS")
database = os.getenv("VIGILANTIA_DB_NAME", "Vigilantia")
driver = os.getenv("VIGILANTIA_DB_DRIVER", "ODBC Driver 18 for SQL Server")

conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};Trusted_Connection=yes;TrustServerCertificate=yes;"

print("A ligar à base de dados...")
try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    print("\n--- WEBSITES ANALISADOS ---")
    cursor.execute("SELECT WebsiteId, Url FROM dbo.Websites")
    for row in cursor.fetchall():
        print(f"ID {row.WebsiteId}: {row.Url}")

    print("\n--- ÚLTIMOS EVENTOS ENCONTRADOS (FINDINGS) ---")
    cursor.execute("""
        SELECT f.FindingId, f.RuleId, f.Description, w.Url
        FROM dbo.Findings f
        JOIN dbo.ScanRuns s ON f.ScanRunId = s.ScanRunId
        JOIN dbo.Websites w ON s.WebsiteId = w.WebsiteId
    """)
    for row in cursor.fetchall():
        print(f"ID {row.FindingId} | Website: {row.Url} | Regra: {row.RuleId} | {row.Description[:60]}...")

    conn.close()
    print("\nListagem concluída!")
except Exception as e:
    print(f"\nErro ao ligar ou consultar a base de dados: {e}")
