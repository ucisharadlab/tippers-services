import os
import time
from datetime import datetime, timedelta

import paramiko
import psycopg2
import requests
from dotenv import load_dotenv
from sshtunnel import SSHTunnelForwarder

load_dotenv()

SSH_HOST = "sensoria.ics.uci.edu"
SSH_USER = os.environ["SSH_USER"]
SSH_PASSWORD = os.environ["SSH_PASSWORD"]

# --- CONFIG ---
SPACE_ID = int(os.environ.get("SPACE_ID", 295))
START_DATE = "2024-04-01 00:00:00"
END_DATE = "2024-07-31 23:59:00"
INTERVAL_MINUTES = 30

REMOVE_PASSERS = "true"
REMOVE_DUPLICATES = "true"
REMOVE_STATIC = "true"
OCCUPANCY_TYPE = "tumbling"


def _ports_up(client, *ports):
    """Return True if all given ports are listening on the remote host."""
    pattern = "|".join(f":{p}" for p in ports)
    _, stdout, _ = client.exec_command(f"ss -tlnp | grep -E '{pattern}'")
    output = stdout.read().decode()
    return all(f":{p}" in output for p in ports)


def ensure_services(client):
    """Start Locater (9081) and Occupancy (8082) on sensoria-1 if not running."""
    if _ports_up(client, 9081, 8082):
        print("Both services already running.")
        return

    if not _ports_up(client, 9081):
        print("Starting Locater service...")
        client.exec_command(
            "cd ~/Locater-main/Locater-main && nohup mvn clean compile exec:java "
            '-Dexec.mainClass="edu.uci.ics.localization.server" '
            "> /tmp/locater.log 2>&1 &"
        )

    if not _ports_up(client, 8082):
        print("Starting Occupancy service...")
        client.exec_command(
            "cd ~/Occupancy-main/Occupancy-main && nohup mvn clean compile exec:java "
            '"-Dexec.mainClass=occupancy.server" '
            "> /tmp/occupancy.log 2>&1 &"
        )

    print("Waiting for services to come up (this may take ~60s for Maven to compile)...")
    for _ in range(24):  # up to 120s
        time.sleep(5)
        locater_up = _ports_up(client, 9081)
        occupancy_up = _ports_up(client, 8082)
        print(f"  Locater: {'up' if locater_up else 'starting...'} | "
              f"Occupancy: {'up' if occupancy_up else 'starting...'}")
        if locater_up and occupancy_up:
            print("Both services are up.")
            return

    raise RuntimeError(
        "Services did not start within 120s. "
        "Check /tmp/locater.log and /tmp/occupancy.log on sensoria-1."
    )


# --- STEP 1: Start services ---
print(f"Connecting to {SSH_HOST} to start services...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASSWORD)
ensure_services(client)
client.close()

# --- STEP 2: Open tunnel ---
print("Opening SSH tunnel...")
with SSHTunnelForwarder(
    SSH_HOST,
    ssh_username=SSH_USER,
    ssh_password=SSH_PASSWORD,
    remote_bind_addresses=[
        ("127.0.0.1", 8082),              # Occupancy API
        ("sensoria-2.ics.uci.edu", 5432), # Postgres
    ],
) as tunnel:
    api_port, db_port = tunnel.local_bind_ports
    api_url = f"http://127.0.0.1:{api_port}/computePresenceOccupancy"
    print(f"Tunnel open — API on :{api_port}, DB on :{db_port}")

    # --- STEP 3: Fetch from API ---
    current = datetime.strptime(START_DATE, "%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(END_DATE, "%Y-%m-%d %H:%M:%S")
    rows = []

    while current < end:
        next_time = current + timedelta(minutes=INTERVAL_MINUTES)
        params = {
            "spaceID": SPACE_ID,
            "startTime": current.strftime("%Y-%m-%d %H:%M:%S"),
            "endTime": next_time.strftime("%Y-%m-%d %H:%M:%S"),
            "removePassers": REMOVE_PASSERS,
            "removeDuplicates": REMOVE_DUPLICATES,
            "removeStatic": REMOVE_STATIC,
            "occupancy_type": OCCUPANCY_TYPE,
            "interval": INTERVAL_MINUTES,
        }
        try:
            response = requests.get(api_url, params=params, timeout=10)
            occupancy = int(response.text.strip())
            print(f"{current} -> {next_time} = {occupancy}")
            rows.append((SPACE_ID, current, next_time, occupancy))
        except Exception as e:
            print(f"Error at {current}: {e}")
        current = next_time

    # --- STEP 4: Bulk insert ---
    print(f"\nFetched {len(rows)} rows. Inserting into database...")
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=db_port,
        database="datawhisk_capstone",
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO occupancy (spaceid, starttime, endtime, occupancy) VALUES (%s, %s, %s, %s)",
        rows,
    )
    conn.commit()
    print(f"Inserted {len(rows)} rows into occupancy table.")
    cursor.close()
    conn.close()

print("Done!")
