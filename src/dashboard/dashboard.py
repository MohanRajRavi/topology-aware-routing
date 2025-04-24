# dashboard.py
import os
import requests
import time
import json
from flask import Flask, render_template, jsonify
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

def get_client_pods():
    """Get all client service pods"""
    if not IN_CLUSTER:
        return ["mock-client-1", "mock-client-2", "mock-client-3"]
    
    try:
        pods = kube_client.list_namespaced_pod(
            namespace="default",
            label_selector="app=client-service"
        )
        return [pod.status.pod_ip for pod in pods.items if pod.status.pod_ip]
    except Exception as e:
        print(f"Exception when calling CoreV1Api: {e}")
        return []

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/aggregate-metrics')
def aggregate_metrics():
    all_metrics = []
    client_pods = get_client_pods()
    
    for client_ip in client_pods:
        try:
            response = requests.get(f"http://{client_ip}:8080/metrics", timeout=2)
            if response.status_code == 200:
                all_metrics.append(response.json())
        except Exception as e:
            print(f"Error fetching metrics from {client_ip}: {e}")
    
    # Calculate aggregate statistics
    total_same_zone_requests = sum(m['metrics']['same_zone_requests'] for m in all_metrics if 'metrics' in m)
    total_cross_zone_requests = sum(m['metrics']['cross_zone_requests'] for m in all_metrics if 'metrics' in m)
    total_requests = sum(m['metrics']['total_requests'] for m in all_metrics if 'metrics' in m)
    
    # Calculate potential cost savings
    # Assume cost of cross-AZ traffic is $0.01 per GB and average request is 10KB
    cross_az_data_gb = (total_cross_zone_requests * 10) / 1024 / 1024
    potential_cost = cross_az_data_gb * 0.01
    
    # Calculate savings from zone-aware routing
    baseline_cross_az = total_requests * 0.66  # Assuming 66% would be cross-zone without optimization
    actual_cross_az = total_cross_zone_requests
    saved_cross_az = baseline_cross_az - actual_cross_az
    saved_data_gb = (saved_cross_az * 10) / 1024 / 1024
    saved_cost = saved_data_gb * 0.01
    
    return jsonify({
        'raw_metrics': all_metrics,
        'summary': {
            'total_same_zone_requests': total_same_zone_requests,
            'total_cross_zone_requests': total_cross_zone_requests,
            'total_requests': total_requests,
            'same_zone_percentage': (total_same_zone_requests / total_requests * 100) if total_requests > 0 else 0,
            'estimated_data_transfer_gb': cross_az_data_gb,
            'estimated_cost_usd': potential_cost,
            'baseline_cross_zone_requests': baseline_cross_az,
            'saved_cross_zone_requests': saved_cross_az,
            'saved_data_gb': saved_data_gb,
            'saved_cost_usd': saved_cost
        }
    })

@app.route('/zones')
def zones():
    """Get information about zones and pods"""
    if not IN_CLUSTER:
        return jsonify({
            'zones': ['EU-FRANKFURT-1-AD-1', 'EU-FRANKFURT-1-AD-2', 'EU-FRANKFURT-1-AD-3'],
            'pods': {
                'client': {'EU-FRANKFURT-1-AD-1': 1, 'EU-FRANKFURT-1-AD-2': 1, 'EU-FRANKFURT-1-AD-3': 1},
                'backend': {'EU-FRANKFURT-1-AD-1': 1, 'EU-FRANKFURT-1-AD-2': 1, 'EU-FRANKFURT-1-AD-3': 1}
            }
        })
    
    try:
        # Get nodes by zone
        nodes = kube_client.list_node()
        zones = {}
        for node in nodes.items:
            zone = node.metadata.labels.get('topology.kubernetes.io/zone')
            if zone:
                if zone not in zones:
                    zones[zone] = []
                zones[zone].append(node.metadata.name)
        
        # Get pods by app and zone
        pods = {}
        for app in ['client-service', 'backend-service']:
            app_pods = kube_client.list_namespaced_pod(
                namespace="default",
                label_selector=f"app={app}"
            )
            
            app_pods_by_zone = {}
            for pod in app_pods.items:
                pod_node_name = pod.spec.node_name
                if pod_node_name:
                    node = kube_client.read_node(pod_node_name)
                    pod_zone = node.metadata.labels.get('topology.kubernetes.io/zone')
                    
                    if pod_zone not in app_pods_by_zone:
                        app_pods_by_zone[pod_zone] = 0
                    app_pods_by_zone[pod_zone] += 1
            
            pods[app] = app_pods_by_zone
        
        return jsonify({
            'zones': list(zones.keys()),
            'pods': pods
        })
    except Exception as e:
        print(f"Exception when calling Kubernetes API: {e}")
        return jsonify({'error': str(e)})

@app.route('/trigger-load')
def trigger_load():
    """Trigger some load on the client services"""
    results = []
    client_pods = get_client_pods()
    
    for client_ip in client_pods:
        try:
            response = requests.get(f"http://{client_ip}:8080/make-request", timeout=2)
            if response.status_code == 200:
                results.append(response.json())
        except Exception as e:
            results.append({"error": str(e), "client": client_ip})
    
    return jsonify(results)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create dashboard HTML template
    with open('templates/dashboard.html', 'w') as f:
        f.write("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Zone Awareness Dashboard</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.7.0/chart.min.js"></script>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f7f9; }
                .container { max-width: 1200px; margin: 0 auto; }
                .stats { display: flex; flex-wrap: wrap; justify-content: space-between; margin-bottom: 20px; }
                .stat-box { background-color: #ffffff; padding: 15px; border-radius: 5px; width: 23%; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .chart-container { height: 300px; margin-bottom: 20px; background-color: #ffffff; border-radius: 5px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                h1, h2 { color: #333; }
                .button-container { margin-bottom: 20px; }
                button { padding: 10px 15px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; }
                button:hover { background-color: #45a049; }
                .zone-layout { display: flex; justify-content: space-between; margin-bottom: 20px; }
                .zone-box { background-color: #ffffff; padding: 15px; border-radius: 5px; width: 30%; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .highlight { color: #4CAF50; font-weight: bold; }
                .savings { color: #2196F3; font-weight: bold; }
                .warning { color: #f44336; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Zone Awareness Dashboard</h1>
                
                <div class="button-container">
                    <button onclick="triggerLoad(10)">Trigger 10 Requests</button>
                    <button onclick="triggerLoad(50)">Trigger 50 Requests</button>
                    <button onclick="triggerLoad(100)">Trigger 100 Requests</button>
                </div>
                
                <div class="stats" id="stats-container">
                    <div class="stat-box">
                        <h3>Total Requests</h3>
                        <div id="total-requests">0</div>
                    </div>
                    <div class="stat-box">
                        <h3>Same-Zone Requests</h3>
                        <div id="same-zone-percentage">0%</div>
                    </div>
                    <div class="stat-box">
                        <h3>Data Transfer Saved</h3>
                        <div id="data-saved">0 GB</div>
                    </div>
                    <div class="stat-box">
                        <h3>Cost Saved</h3>
                        <div id="cost-saved">$0.00</div>
                    </div>
                </div>
                
                <div class="zone-layout" id="zone-layout">
                    <div class="zone-box">
                        <h3>EU-FRANKFURT-1-AD-1</h3>
                        <div id="zone1-pods"></div>
                    </div>
                    <div class="zone-box">
                        <h3>EU-FRANKFURT-1-AD-2</h3>
                        <div id="zone2-pods"></div>
                    </div>
                    <div class="zone-box">
                        <h3>EU-FRANKFURT-1-AD-3</h3>
                        <div id="zone3-pods"></div>
                    </div>
                </div>
                
                <div class="chart-container">
                    <canvas id="requestChart"></canvas>
                </div>
                
                <div class="chart-container">
                    <canvas id="savingsChart"></canvas>
                </div>
                
                <h2>Raw Metrics</h2>
                <pre id="raw-metrics" style="background-color: #ffffff; padding: 15px; border-radius: 5px; overflow: auto; max-height: 300px;"></pre>
            </div>
            
            <script>
                // Charts
                let requestChart = null;
                let savingsChart = null;
                
                function initCharts() {
                    const requestCtx = document.getElementById('requestChart').getContext('2d');
                    requestChart = new Chart(requestCtx, {
                        type: 'pie',
                        data: {
                            labels: ['Same-Zone Requests', 'Cross-Zone Requests'],
                            datasets: [{
                                data: [0, 0],
                                backgroundColor: ['#4CAF50', '#f44336']
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                title: {
                                    display: true,
                                    text: 'Request Distribution'
                                }
                            }
                        }
                    });
                    
                    const savingsCtx = document.getElementById('savingsChart').getContext('2d');
                    savingsChart = new Chart(savingsCtx, {
                        type: 'bar',
                        data: {
                            labels: ['Without Zone Awareness', 'With Zone Awareness'],
                            datasets: [{
                                label: 'Cross-Zone Requests',
                                data: [0, 0],
                                backgroundColor: ['#f44336', '#4CAF50']
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                title: {
                                    display: true,
                                    text: 'Cross-Zone Traffic Reduction'
                                }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    title: {
                                        display: true,
                                        text: 'Number of Requests'
                                    }
                                }
                            }
                        }
                    });
                }
                
                function updateCharts(data) {
                    if (requestChart) {
                        requestChart.data.datasets[0].data = [
                            data.summary.total_same_zone_requests,
                            data.summary.total_cross_zone_requests
                        ];
                        requestChart.update();
                    }
                    
                    if (savingsChart) {
                        savingsChart.data.datasets[0].data = [
                            data.summary.baseline_cross_zone_requests,
                            data.summary.total_cross_zone_requests
                        ];
                        savingsChart.update();
                    }
                }
                
                // Fetch metrics data
                function fetchMetrics() {
                    fetch('/aggregate-metrics')
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('total-requests').textContent = data.summary.total_requests;
                            document.getElementById('same-zone-percentage').textContent = 
                                data.summary.same_zone_percentage.toFixed(1) + '% (' + 
                                data.summary.total_same_zone_requests + ' of ' + 
                                data.summary.total_requests + ')';
                            document.getElementById('data-saved').textContent = 
                                data.summary.saved_data_gb.toFixed(6) + ' GB';
                            document.getElementById('cost-saved').textContent = 
                                '$' + data.summary.saved_cost_usd.toFixed(4);
                            
                            document.getElementById('raw-metrics').textContent = 
                                JSON.stringify(data, null, 2);
                                
                            updateCharts(data);
                        })
                        .catch(error => {
                            console.error('Error fetching metrics:', error);
                        });
                }
                
                // Fetch zone info
                function fetchZoneInfo() {
                    fetch('/zones')
                        .then(response => response.json())
                        .then(data => {
                            const clientPods = data.pods['client-service'] || {};
                            const backendPods = data.pods['backend-service'] || {};