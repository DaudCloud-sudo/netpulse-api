from flask import Flask, jsonify
import psycopg2
from psycopg2 import OperationalError

app = Flask(__name__)

# The Connection String (Telling Python exactly where to find the database)
DB_HOST = "127.0.0.1"
DB_PORT = "5432"
DB_NAME = "sredb"
DB_USER = "sre_user"
DB_PASS = "secure_password_123"

def get_db_status():
    try:
        # Attempt to open a TCP connection to Port 5432
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        
        # Create a cursor, execute a real SQL query, and fetch the result
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()[0]
        
        # Close the connections cleanly
        cursor.close()
        conn.close()
        
        return {"status": "Connected", "details": db_version}
    
    except OperationalError as e:
        # If the database is down or credentials fail, catch the error
        return {"status": "Failed", "details": str(e)}

@app.route('/api/status', methods=['GET'])
def get_status():
    # Ask the database function for its current state
    db_info = get_db_status()
    
    return jsonify({
        "server": "Application Layer",
        "status": "Online",
        "database_connection": db_info["status"],
        "database_details": db_info["details"]
    }), 200

if __name__ == '__main__':
    app.run()
