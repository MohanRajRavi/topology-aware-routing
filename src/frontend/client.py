# client-service.py
import os
import requests
import time
import random
import json
from flask import Flask, jsonify
import socket
import kubernetes.client
from kubernetes.client.rest import ApiException
from kubernetes import config

app = Flask(__name__)

# Try to load Kubernetes config
try:
    config.load_incluster_config()
    kube_client = kubernetes.client.CoreV1Api()
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
    except ApiException as e:
        print(f"Exception when calling CoreV1Api->read_node: {e}")
        return "unknown"

# Tracking metrics
request_metrics = {
    'same_zone_requests': 0,
    'cross_zone_requests': 0,
    'total_requests': 0,
    'by_zone': {
        'EU-FRANKFURT-1-AD-1': 0,
        'EU-FRANKFURT-1-AD-2': 0,
        'EU-FRANKFURT-1-AD-3': 0
    }
}

def get_pods_by_zone(service_name, namespace="default"):
    """Get pods grouped by zone for a service"""
    if not IN_CLUSTER:
        # Mock data for testing outside of cluster
        return {
            'EU-FRANKFURT-1-AD-1': ['backend-1'],
            'EU-FRANKFURT-1-AD-2': ['backend-2'],
            'EU-FRANKFURT-1-AD-3': ['backend-3']
        }
    
    try:
        pods = kube_client.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"app={service_name}"
        )
        
        pods_by_zone = {}
        for pod in pods.items:
            pod_node_name = pod.spec.node_name
            if pod_node_name:
                node = kube_client.read_node(pod_node_name)
                pod_zone = node.metadata.labels.get("topology.kubernetes.io/zone", "unknown")
                
                if pod_zone not in pods_by_zone:
                    pods_by_zone[pod_zone] = []
                
                pods_by_zone[pod_zone].append(pod.status.pod_ip)
        
        return pods_by_zone
    except ApiException as e:
        print(f"Exception when calling CoreV1Api: {e}")
        return {}

@app.route('/make-request')
def make_request():
    # Get current zone if needed
    if CURRENT_ZONE == "unknown":
        get_current_zone()
    
    # Get backend pods by zone
    backends_by_zone = get_pods_by_zone("backend-service")
    
    # Default to random selection if no zone info
    if not backends_by_zone or CURRENT_ZONE == "unknown":
        target_ip = requests.get("http://backend-service/health").json().get("pod_ip")
        target_zone = "unknown"
        request_metrics['cross_zone_requests'] += 1
    else:
        # Zone-aware routing - try same zone first
        if CURRENT_ZONE in backends_by_zone and backends_by_zone[CURRENT_ZONE] and random.random() < 0.8:
            # 80% preference for same zone
            target_ip = random.choice(backends_by_zone[CURRENT_ZONE])
            target_zone = CURRENT_ZONE
            request_metrics['same_zone_requests'] += 1
        else:
            # Choose a different zone
            other_zones = [zone for zone in backends_by_zone.keys() if zone != CURRENT_ZONE and backends_by_zone[zone]]
            if other_zones:
                target_zone = random.choice(other_zones)
                target_ip = random.choice(backends_by_zone[target_zone])
                request_metrics['cross_zone_requests'] += 1
            else:
                # Fallback if no other zones available
                target_zone = CURRENT_ZONE if CURRENT_ZONE in backends_by_zone and backends_by_zone[CURRENT_ZONE] else "unknown"
                if target_zone != "unknown":
                    target_ip = random.choice(backends_by_zone[target_zone])
                    request_metrics['same_zone_requests'] += 1
                else:
                    # Last resort
                    target_ip = requests.get("http://backend-service/health").json().get("pod_ip")
                    request_metrics['cross_zone_requests'] += 1
    
    request_metrics['total_requests'] += 1
    if target_zone in request_metrics['by_zone']:
        request_metrics['by_zone'][target_zone] += 1
    
    # Make the actual request
    try:
        if target_ip:
            response = requests.get(f"http://{target_ip}:8080/status")
        else:
            # Use service name when IP not available
            response = requests.get(f"http://backend-service/status")
        
        backend_data = response.json()
        backend_zone = backend_data.get('zone', 'unknown')
        
        # Check if we actually got same-zone routing
        same_zone = (CURRENT_ZONE == backend_zone)
        if same_zone:
            request_metrics['same_zone_requests'] += 1 
        else:
            request_metrics['cross_zone_requests'] += 1
            
        return jsonify({
            'success': True,
            'client_zone': CURRENT_ZONE,
            'backend_zone': backend_zone,
            'same_zone': same_zone,
            'backend_response': backend_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'client_zone': CURRENT_ZONE,
            'target_zone': target_zone,
            'error': str(e)
        }), 500

@app.route('/metrics')
def metrics():
    # Make sure zone is up to date
    if CURRENT_ZONE == "unknown":
        get_current_zone()
        
    return jsonify({
        'pod_name': POD_NAME,
        'node_name': NODE_NAME,
        'zone': CURRENT_ZONE,
        'metrics': request_metrics,
        'same_zone_percentage': (request_metrics['same_zone_requests'] / 
                              request_metrics['total_requests'] * 100) 
                              if request_metrics['total_requests'] > 0 else 0
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
    print(f"Starting client service in zone: {CURRENT_ZONE}")
    app.run(host='0.0.0.0', port=8080)