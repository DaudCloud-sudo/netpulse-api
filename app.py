import subprocess
import logging
import json
import time
import socket
import requests
import re
from flask import Flask, request, jsonify
from psycopg2 import pool, OperationalError

# 1. ENTERPRISE LOGGING
logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}')
logger = logging.getLogger("NetPulse")

app = Flask(__name__)

# 2. VITALI'S TIMEOUT RULE (PostgreSQL Options)
# We add `options="-c statement_timeout=3000"`. 
# If the database hangs for more than 3 seconds, Postgres will violently kill the query 
# to save our Python API from freezing.
try:
    db_pool = pool.SimpleConnectionPool(
        1, 5,
        host="127.0.0.1",
        port="5432",
        database="sredb",
        user="sre_user",
        password="secure_password_123",
        options="-c statement_timeout=3000"
    )
    logger.info("Database pool initialized with 3000ms hard timeout.")
except OperationalError as e:
    logger.critical(f"FATAL: Database pool failed. {e}")
    db_pool = None

# 3. SRE SECURITY: INPUT VALIDATION
def is_valid_input(domain):
    # This Regex strictly enforces standard Domain names and IPv4 formats.
    # It instantly blocks command injection attempts like "google.com; rm -rf /"
    pattern = re.compile(r"^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$|^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}$")
    return bool(pattern.match(domain))

# 4. OSI MODEL TELEMETRY ENGINE
def execute_telemetry(domain):
    metrics = {"icmp_ms": None, "tcp_ms": None, "http_status": None, "error": None}

    # LAYER 3: ICMP Ping (Will fail on AWS/Netflix, which is fine)
    try:
        ping_res = subprocess.run(['ping', '-c', '1', '-W', '1', domain], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if ping_res.returncode == 0:
            time_str = ping_res.stdout.split('time=')[-1].split(' ')[0]
            metrics["icmp_ms"] = round(float(time_str), 2)
    except Exception:
        pass 

    # LAYER 4: TCP Handshake (Bypasses ICMP Firewalls)
    try:
        tcp_start = time.time()
        # Attempt to establish a raw TCP connection on Port 443 (HTTPS) with a 2-second timeout
        sock = socket.create_connection((domain, 443), timeout=2)
        metrics["tcp_ms"] = round((time.time() - tcp_start) * 1000, 2)
        sock.close()
    except socket.error as e:
        metrics["error"] = f"TCP Blocked: {str(e)}"
        return metrics # If Layer 4 fails, Layer 7 is impossible. Abort here.

    # LAYER 7: HTTP Response
    try:
        # Ask the web server for its actual status
        http_res = requests.get(f"https://{domain}", timeout=2)
        metrics["http_status"] = http_res.status_code
    except requests.RequestException as e:
        metrics["error"] = f"HTTP Error: {str(e)}"

    return metrics

@app.route('/api/telemetry', methods=['POST'])
def run_telemetry():
    data = request.get_json()
    if not data or 'domain' not in data:
        return jsonify({"error": "Missing 'domain'"}), 400
    
    domain = data['domain']
    
    if not is_valid_input(domain):
        logger.warning(f"SECURITY ALERT: Blocked invalid network input: {domain}")
        return jsonify({"error": "Invalid Domain or IP structure."}), 403

    logger.info(f"Executing OSI Telemetry for: {domain}")
    net_metrics = execute_telemetry(domain)
    
    overall_status = "Online" if net_metrics["tcp_ms"] else "Offline"
    error_msg = net_metrics["error"][:250] if net_metrics["error"] else None

    db_latency = None
    db_sync = "Offline"

    # 5. DATABASE HEALTH MEASUREMENT
    if db_pool:
        try:
            # We measure how long it takes to borrow a connection and talk to Postgres
            db_start = time.time()
            conn = db_pool.getconn()
            cursor = conn.cursor()
            
            cursor.execute("SELECT 1;") # A tiny query just to measure DB speed
            db_latency = round((time.time() - db_start) * 1000, 2)
            
            # Now we write the massive payload
            cursor.execute(
                """INSERT INTO network_metrics 
                (target_domain, latency_ms, status, tcp_latency_ms, http_status, error_context, db_latency_ms) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (domain, net_metrics["icmp_ms"], overall_status, net_metrics["tcp_ms"], net_metrics["http_status"], error_msg, db_latency)
            )
            conn.commit()
            cursor.close()
            db_pool.putconn(conn)
            db_sync = "Success"
            
        except Exception as e:
            logger.error(f"Database write failed: {str(e)}")
            db_sync = "Failed"

    return jsonify({
        "domain": domain,
        "status": overall_status,
        "metrics": {
            "layer_3_ping_ms": net_metrics["icmp_ms"],
            "layer_4_tcp_ms": net_metrics["tcp_ms"],
            "layer_7_http_code": net_metrics["http_status"]
        },
        "database": {
            "sync": db_sync,
            "latency_ms": db_latency
        },
        "error": error_msg
    }), 200

if __name__ == '__main__':
    app.run()