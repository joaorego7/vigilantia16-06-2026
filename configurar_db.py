# configurar_db.py
#
# Script interativo para configurar a ligação à base de dados SQL Server do Vigilantia.
# Permite escolher o driver ODBC instalado, definir credenciais, testar a ligação
# e inicializar as tabelas automaticamente.

import os
import sys
import re

try:
    import pyodbc
except ImportError:
    print("ERRO: O pacote 'pyodbc' não está instalado no ambiente virtual.")
    print("Por favor, certifique-se de que ativou o seu ambiente virtual e instalou as dependências:")
    print("  .\\testes_env\\Scripts\\Activate.ps1")
    print("  pip install -r requirements.txt")
    sys.exit(1)


def get_existing_config():
    """Lê as configurações atuais do .env se existir."""
    config = {
        "VIGILANTIA_DB_SERVER": "localhost\\SQLEXPRESS",
        "VIGILANTIA_DB_NAME": "Vigilantia",
        "VIGILANTIA_DB_DRIVER": "ODBC Driver 18 for SQL Server",
        "VIGILANTIA_DB_TRUSTED": "true",
        "VIGILANTIA_DB_USER": "",
        "VIGILANTIA_DB_PASSWORD": "",
        "VIGILANTIA_DB_TRUST_CERT": "true"
    }
    
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    config[key.strip()] = val.strip()
    return config


def save_config(config):
    """Guarda a configuração no ficheiro .env preservando outros campos."""
    existing = {}
    lines = []
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    new_lines = []
    keys_updated = set()
    
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, val = stripped.split("=", 1)
            key = key.strip()
            if key in config:
                new_lines.append(f"{key}={config[key]}\n")
                keys_updated.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    for key, val in config.items():
        if key not in keys_updated:
            new_lines.append(f"{key}={val}\n")
            
    with open(".env", "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def get_input(prompt, default_val):
    """Pede um input ao utilizador com um valor por omissão."""
    display_default = default_val if default_val is not None else ""
    user_input = input(f"{prompt} [{display_default}]: ").strip()
    return user_input if user_input else default_val


def get_bool_input(prompt, default_val):
    """Pede um input booleano (Sim/Não) com um valor por omissão."""
    display_default = "S" if default_val else "N"
    while True:
        user_input = input(f"{prompt} (S/N) [{display_default}]: ").strip().upper()
        if not user_input:
            return default_val
        if user_input in ("S", "SIM", "Y", "YES", "TRUE", "1"):
            return True
        if user_input in ("N", "NÃO", "NO", "FALSE", "0"):
            return False
        print("Resposta inválida. Por favor introduza S ou N.")


def choose_odbc_driver(current_driver):
    """Deteta os drivers ODBC instalados e permite ao utilizador escolher um."""
    drivers = pyodbc.drivers()
    # Filtrar drivers relacionados com SQL Server
    sql_drivers = [d for d in drivers if "sql" in d.lower() or "sqlncli" in d.lower()]
    
    print("\n--- Drivers ODBC de SQL Server Detetados ---")
    if not sql_drivers:
        print("Aviso: Nenhum driver SQL Server foi detetado automaticamente nas fontes ODBC locais.")
        print("Pode introduzir o nome exato do driver manualmente.")
        manual_driver = input(f"Nome do Driver [{current_driver}]: ").strip()
        return manual_driver if manual_driver else current_driver
        
    for idx, driver in enumerate(sql_drivers, 1):
        is_recommended = "18" in driver or "17" in driver
        recommended_tag = " (Recomendado)" if is_recommended else ""
        current_tag = " (Atual)" if driver == current_driver else ""
        print(f"[{idx}] {driver}{recommended_tag}{current_tag}")
        
    print(f"[{len(sql_drivers) + 1}] Introduzir outro driver manualmente")
    
    # Tentar sugerir o melhor driver por omissão
    default_idx = None
    # 1. Se o driver atual está na lista, usá-lo
    if current_driver in sql_drivers:
        default_idx = sql_drivers.index(current_driver) + 1
    # 2. Senão, tentar encontrar um recomendado
    if default_idx is None:
        for idx, driver in enumerate(sql_drivers, 1):
            if "18" in driver or "17" in driver:
                default_idx = idx
                break
    # 3. Senão, usar o primeiro
    if default_idx is None:
        default_idx = 1
        
    while True:
        user_input = input(f"Escolha o driver (1-{len(sql_drivers) + 1}) [{default_idx}]: ").strip()
        if not user_input:
            choice = default_idx
        else:
            try:
                choice = int(user_input)
            except ValueError:
                choice = -1
                
        if 1 <= choice <= len(sql_drivers):
            return sql_drivers[choice - 1]
        elif choice == len(sql_drivers) + 1:
            manual_driver = input("Digite o nome exato do driver ODBC: ").strip()
            if manual_driver:
                return manual_driver
            print("Nome do driver não pode ser vazio.")
        else:
            print("Opção inválida.")


def test_connection_string(driver, server, database, trusted, user, password, trust_cert, use_master=False):
    """Tenta ligar ao SQL Server usando as opções fornecidas."""
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
    ]
    if use_master:
        parts.append("DATABASE=master")
    else:
        parts.append(f"DATABASE={database}")
        
    if trusted:
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={user}")
        parts.append(f"PWD={password}")
        
    if trust_cert:
        parts.append("TrustServerCertificate=yes")
        
    conn_str = ";".join(parts) + ";"
    
    try:
        # Usar timeout curto para o teste não bloquear
        conn = pyodbc.connect(conn_str, timeout=5, autocommit=True)
        return conn, None
    except Exception as e:
        return None, str(e)


def execute_sql_file(conn, file_path):
    """Executa um ficheiro SQL dividindo-o por blocos 'GO'."""
    if not os.path.exists(file_path):
        print(f"Ficheiro de schema não encontrado em: {file_path}")
        return False
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # SQL Server GO é um comando especial de batch. Temos de dividir as instruções por GO
    # nas linhas em que aparece sozinho.
    # Regex para apanhar "GO" como uma linha independente, ignorando espaços ou comentários
    batches = re.split(r'^\s*GO\s*(?:--.*)?$', content, flags=re.MULTILINE | re.IGNORECASE)
    
    cursor = conn.cursor()
    success = True
    executed_count = 0
    
    print("\nA inicializar as tabelas da base de dados...")
    for idx, batch in enumerate(batches, 1):
        batch = batch.strip()
        if not batch:
            continue
            
        # Ignorar comandos USE já que estamos ligados à BD alvo, ou deixá-los correr
        # se funcionarem.
        try:
            cursor.execute(batch)
            executed_count += 1
        except Exception as e:
            # Em alguns casos, comandos de CREATE DATABASE/USE não funcionam ou já foram tratados.
            # Mostramos o erro mas tentamos continuar se for apenas um aviso ou DB já existente.
            print(f"Aviso no bloco SQL #{idx}: {e}")
            # Se for um erro crítico de criação de tabela, podemos querer saber
            if "CREATE TABLE" in batch.upper():
                success = False
                
    print(f"Executados {executed_count} blocos SQL com sucesso.")
    return success


def main():
    print("=====================================================================")
    print("      CONFIGURAÇÃO DA BASE DE DADOS DO VIGILANTIA")
    print("=====================================================================")
    print("Este script permite configurar a ligação ao Microsoft SQL Server")
    print("sem alterar diretamente os ficheiros de código da plataforma.")
    
    current_cfg = get_existing_config()
    
    # 1. Escolha do Driver ODBC
    driver = choose_odbc_driver(current_cfg["VIGILANTIA_DB_DRIVER"])
    
    # 2. Nome do Servidor
    server = get_input("Nome/Instância do Servidor SQL Server", current_cfg["VIGILANTIA_DB_SERVER"])
    
    # 3. Nome da Base de Dados
    database = get_input("Nome da Base de Dados", current_cfg["VIGILANTIA_DB_NAME"])
    
    # 4. Modo de Autenticação
    is_trusted_default = current_cfg["VIGILANTIA_DB_TRUSTED"].lower() in ("true", "1", "yes")
    trusted = get_bool_input("Usar Autenticação do Windows (Trusted Connection)?", is_trusted_default)
    
    user = ""
    password = ""
    if not trusted:
        user = get_input("Utilizador da Base de Dados", current_cfg["VIGILANTIA_DB_USER"])
        password = get_input("Palavra-passe da Base de Dados", current_cfg["VIGILANTIA_DB_PASSWORD"])
        
    # 5. Confiança no Certificado do Servidor
    trust_cert_default = current_cfg["VIGILANTIA_DB_TRUST_CERT"].lower() in ("true", "1", "yes")
    trust_cert = get_bool_input("Confiar no Certificado do Servidor (Trust Server Certificate)?", trust_cert_default)
    
    print("\n--- Testar Ligação ---")
    print("A tentar estabelecer ligação ao servidor...")
    
    # Primeiro testamos a ligação ao servidor em geral (liga-se a master para verificar se o servidor responde)
    conn, err = test_connection_string(driver, server, database, trusted, user, password, trust_cert, use_master=False)
    
    db_needs_creation = False
    
    if err:
        # Se falhou, vamos ver se o erro é porque a BD não existe
        if "does not exist" in err.lower() or "cannot open database" in err.lower() or "login failed" in err.lower():
            # Tentar ligar a master para ver se o servidor em si está acessível
            conn_master, master_err = test_connection_string(driver, server, database, trusted, user, password, trust_cert, use_master=True)
            if conn_master:
                print(f"[OK] Servidor responde, mas a base de dados '{database}' não foi encontrada.")
                db_needs_creation = True
                conn_master.close()
            else:
                print(f"\n[ERRO] Falha ao ligar ao Servidor SQL Server: {err}")
                print("\nSugestões de Resolução:")
                print("1. Confirme se o serviço do SQL Server (ex: SQLEXPRESS) está em execução.")
                print("2. Verifique se o nome do servidor/instância está correto.")
                print("3. Se o SQL Server estiver numa máquina remota, garanta que as ligações TCP/IP estão ativas.")
                print("4. Experimente alterar a opção de Confiar no Certificado do Servidor.")
                
                if not get_bool_input("\nDeseja guardar estas definições mesmo com erro?", False):
                    print("Operação cancelada. Configurações não guardadas.")
                    return
        else:
            print(f"\n[ERRO] Falha ao ligar: {err}")
            if not get_bool_input("\nDeseja guardar estas definições mesmo com erro?", False):
                print("Operação cancelada. Configurações não guardadas.")
                return
    else:
        print("[SUCESSO] Ligação bem-sucedida à base de dados!")
        
    # Criar Base de Dados se necessário
    if db_needs_creation:
        create_db = get_bool_input(f"Deseja criar a base de dados '{database}' automaticamente?", True)
        if create_db:
            conn_master, _ = test_connection_string(driver, server, database, trusted, user, password, trust_cert, use_master=True)
            if conn_master:
                try:
                    cursor = conn_master.cursor()
                    cursor.execute(f"CREATE DATABASE [{database}]")
                    print(f"[OK] Base de dados '{database}' criada com sucesso!")
                    conn_master.close()
                    # Ligar agora à nova BD
                    conn, err = test_connection_string(driver, server, database, trusted, user, password, trust_cert, use_master=False)
                except Exception as e:
                    print(f"[ERRO] Não foi possível criar a base de dados: {e}")
                    db_needs_creation = False
            else:
                print("[ERRO] Falha ao ligar a 'master' para criar a base de dados.")
                
    # Inicializar as tabelas usando o schema.sql
    if conn and not err:
        # Verificar se as tabelas já existem (ver se a tabela Websites existe)
        schema_exists = False
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'Websites'")
            if cursor.fetchone():
                schema_exists = True
        except:
            pass
            
        if schema_exists:
            init_schema = get_bool_input("As tabelas do Vigilantia já parecem existir. Deseja re-executar/inicializar o schema.sql?", False)
        else:
            init_schema = get_bool_input("A base de dados está vazia. Deseja criar as tabelas do Vigilantia (schema.sql)?", True)
            
        if init_schema:
            schema_path = os.path.join("src", "vigilantia", "db", "schema.sql")
            execute_sql_file(conn, schema_path)
            
        conn.close()
        
    # Escrever no ficheiro .env
    new_cfg = {
        "VIGILANTIA_DB_SERVER": server,
        "VIGILANTIA_DB_NAME": database,
        "VIGILANTIA_DB_DRIVER": driver,
        "VIGILANTIA_DB_TRUSTED": "true" if trusted else "false",
        "VIGILANTIA_DB_USER": user,
        "VIGILANTIA_DB_PASSWORD": password,
        "VIGILANTIA_DB_TRUST_CERT": "true" if trust_cert else "false"
    }
    
    save_config(new_cfg)
    print("\n[OK] Configurações guardadas com sucesso no ficheiro '.env'!")
    print("Agora pode executar a plataforma ou testar as tabelas executando:")
    print("  python run_vigilantia_mvp.py")
    print("  python view_db.py")


if __name__ == "__main__":
    main()
