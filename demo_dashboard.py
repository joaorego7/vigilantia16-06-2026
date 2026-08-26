"""
Script para demonstrar como ficam os dados no dashboard.
Cria uma BD SQLite fictícia com a tabela de notificações e insere dados de exemplo.
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = "demo_dashboard.db"

# 1. Criar a tabela que simula o que a SP [service].[create_notification] gravaria
conn = sqlite3.connect(DB_PATH)
conn.execute("""
    CREATE TABLE IF NOT EXISTS Notifications (
        NotificationAutoId INTEGER PRIMARY KEY AUTOINCREMENT,
        ClientId            INT NOT NULL,
        DeviceId            INT NOT NULL,
        RemoteAddress       TEXT NOT NULL,
        DeviceName          TEXT,
        Category            TEXT NOT NULL,
        NotificationId      TEXT NOT NULL,
        Level               INT NOT NULL,
        LogTimestamp         DATETIME,
        Description         TEXT NOT NULL,
        Type                TEXT NOT NULL DEFAULT 'generic_audit',
        CreatedAt           DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

# 2. Dados fictícios — como se o Vigilantia tivesse analisado 2 sites
dados = [
    # Site 1: pcm.pt — 3 problemas encontrados
    {
        "ClientId": 1840264,
        "DeviceId": 0,
        "RemoteAddress": "https://pcm.pt/",
        "DeviceName": "pcm.pt",
        "Category": "missing_cookie_consent",
        "NotificationId": "missing_cookie_consent",
        "Level": 3,
        "LogTimestamp": None,
        "Description": "https://pcm.pt — Não foi detetado um banner de consentimento de cookies.",
        "Type": "website_audit",
    },
    {
        "ClientId": 1840264,
        "DeviceId": 0,
        "RemoteAddress": "https://pcm.pt/",
        "DeviceName": "pcm.pt",
        "Category": "policy_missing_dpo_contact",
        "NotificationId": "policy_missing_dpo_contact",
        "Level": 1,
        "LogTimestamp": None,
        "Description": "https://pcm.pt — A política de privacidade não identifica o DPO.",
        "Type": "website_audit",
    },
    {
        "ClientId": 1840264,
        "DeviceId": 0,
        "RemoteAddress": "https://pcm.pt/",
        "DeviceName": "pcm.pt",
        "Category": "forms_without_purpose_notice",
        "NotificationId": "forms_without_purpose_notice",
        "Level": 2,
        "LogTimestamp": None,
        "Description": "https://pcm.pt — Formulário recolhe dados pessoais sem aviso de finalidade.",
        "Type": "website_audit",
    },
    # Site 2: tretas.eu — 2 problemas
    {
        "ClientId": 9900123,
        "DeviceId": 0,
        "RemoteAddress": "https://tretas.eu/",
        "DeviceName": "tretas.eu",
        "Category": "missing_privacy_policy",
        "NotificationId": "missing_privacy_policy",
        "Level": 3,
        "LogTimestamp": None,
        "Description": "https://tretas.eu — Nenhuma política de privacidade encontrada.",
        "Type": "website_audit",
    },
    {
        "ClientId": 9900123,
        "DeviceId": 0,
        "RemoteAddress": "https://tretas.eu/",
        "DeviceName": "tretas.eu",
        "Category": "tracking_cookies_before_consent",
        "NotificationId": "tracking_cookies_before_consent",
        "Level": 3,
        "LogTimestamp": None,
        "Description": "https://tretas.eu — Cookies de tracking instalados antes do consentimento.",
        "Type": "website_audit",
    },
]

# 3. Inserir
for d in dados:
    conn.execute(
        """INSERT INTO Notifications 
           (ClientId, DeviceId, RemoteAddress, DeviceName, Category, 
            NotificationId, Level, LogTimestamp, Description, Type)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (d["ClientId"], d["DeviceId"], d["RemoteAddress"], d["DeviceName"],
         d["Category"], d["NotificationId"], d["Level"], d["LogTimestamp"],
         d["Description"], d["Type"]),
    )
conn.commit()

# 4. Mostrar os resultados
print("=" * 90)
print("DEMO — Tabela Notifications (como ficaria no dashboard)")
print("=" * 90)

cursor = conn.execute("""
    SELECT NotificationAutoId, ClientId, DeviceName, Category, Level, Description, Type, CreatedAt 
    FROM Notifications 
    ORDER BY ClientId, NotificationAutoId
""")

nivel_label = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}

for row in cursor:
    auto_id, client_id, device, category, level, desc, tipo, created = row
    print(f"\n  ID: {auto_id}")
    print(f"  ClientId:       {client_id}")
    print(f"  DeviceName:     {device}")
    print(f"  Category:       {category}")
    print(f"  NotificationId: {category}")
    print(f"  Level:          {level} ({nivel_label.get(level, '?')})")
    print(f"  Description:    {desc}")
    print(f"  Type:           {tipo}")
    print(f"  CreatedAt:      {created}")
    print(f"  {'-' * 70}")

# Resumo
print(f"\nTotal de notificações: {conn.execute('SELECT COUNT(*) FROM Notifications').fetchone()[0]}")
print(f"Clientes distintos:   {conn.execute('SELECT COUNT(DISTINCT ClientId) FROM Notifications').fetchone()[0]}")
print(f"Sites distintos:      {conn.execute('SELECT COUNT(DISTINCT DeviceName) FROM Notifications').fetchone()[0]}")

conn.close()
print(f"\nBD fictícia guardada em: {DB_PATH}")
