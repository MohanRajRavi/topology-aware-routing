# backend-service.py
import os
import time
import random
import json
from flask import Flask, jsonify
import socket
from kubernetes import client, config

app = Flask(__name__)

# Try to load Kubernetes config
try:
    config.load_incluster_config()
    kube_client = client.CoreV1Api()
    IN_CLUSTER = True
except:
    IN_CLUSTER = False
    print("Not running in Kubernetes cluster")

# Get Pod information
POD_NAME = os.environ.get("POD_NAME", "unknown")
POD_NAMESPACE = os.environ.get("POD_NAMESPACE", "default")
NODE_NAME = os.environ.get("NODE_NAME", "unknown")
POD_IP = os.environ.get("POD_IP", "127.0.0.1")

# Get node information to determine the zone
CURRENT_ZONE = "unknown"

def get_current_zone():
    global CURRENT_ZONE
    if not IN_CLUSTER:
        return "unknown"
    
    try:
        node = kube_client.read_node(NODE_NAME)
        labels = node.metadata.labels
        CURRENT_ZONE = labels.get("topology.kubernetes.io/zone", "unknown")
        return CURRENT_ZONE
    except Exception as e:
        print(f"Exception when calling CoreV1Api->read_node: {e}")
        return "unknown"

# Request counter
request_count = 0

@app.route('/status')
def status():
    global request_count
    request_count += 1
    
    # Make sure zone is up to date
    if CURRENT_ZONE == "unknown":
        get_current_zone()
    
    # Simulate some processing time
    processing_time = random.uniform(0.01, 0.1)
    time.sleep(processing_time)
    
    return jsonify({
        'service': 'backend',
        'zone': CURRENT_ZONE,
        'pod_name': POD_NAME,
        'node_name': NODE_NAME,
        'pod_ip': POD_IP,
        'request_count': request_count,
        'processing_time_ms': processing_time * 1000
    })

@app.route('/health')
def health():
    # Make sure zone is up to date
    if CURRENT_ZONE == "unknown":
        get_current_zone()
        
    return jsonify({
        'status': 'healthy', 
        'zone': CURRENT_ZONE,
        'pod_name': POD_NAME,
        'pod_ip': POD_IP
    })

if __name__ == '__main__':
    # Initial zone lookup
    get_current_zone()
    print(f"Starting backend service in zone: {CURRENT_ZONE}")
    app.run(host='0.0.0.0', port=8080)