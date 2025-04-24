# topology-aware-routing

## Overview
This project demonstrates a topology-aware routing system using Kubernetes. It optimizes request routing to minimize cross-zone traffic, reducing latency and cost.

## Components
1. **Client Service**:
   - Routes requests to backend services with a preference for same-zone pods.
   - Tracks and exposes metrics for request distribution.

2. **Backend Service**:
   - Processes requests and provides zone-specific responses.
   - Simulates processing time for realistic behavior.

3. **Dashboard**:
   - Aggregates metrics from client services.
   - Visualizes request distribution and cost savings.

## Technologies Used
- **Python**: Flask for building microservices.
- **Kubernetes**: For container orchestration and topology-aware routing.
- **Chart.js**: For visualizing metrics on the dashboard.
- **Docker**: For containerizing services.

## Application Flow
1. **Client Service**:
   - Initializes by retrieving Kubernetes pod and node information.
   - Determines the current zone using Kubernetes node labels.
   - Routes requests to backend pods, preferring pods in the same zone (80% preference).
   - Tracks metrics for same-zone and cross-zone requests.
   - Exposes metrics via `/metrics` and health status via `/health`.

2. **Backend Service**:
   - Initializes by retrieving Kubernetes pod and node information.
   - Determines the current zone using Kubernetes node labels.
   - Processes requests and responds with zone and pod details.
   - Exposes health status via `/health`.

3. **Dashboard Service**:
   - Aggregates metrics from all client service pods.
   - Calculates aggregate statistics such as same-zone percentage and cost savings.
   - Visualizes metrics and zone information on a web dashboard.
   - Provides interactive charts for request distribution and cost savings.
   - Simulates load by triggering requests on client services.

4. **Kubernetes Deployment**:
   - Deployments and services for `client-service`, `backend-service`, and `zone-dashboard`.
   - Uses `topologySpreadConstraints` to distribute pods across zones.
   - Backend service uses Kubernetes topology-aware hints for optimized routing.

## Deployment
- Kubernetes manifests are provided for deploying the services.
- Uses `topologySpreadConstraints` and topology-aware hints for zone-aware scheduling.

## Diagram
```plaintext
+-------------------+       +-------------------+       +-------------------+
|                   |       |                   |       |                   |
|   Client Service  | ----> |  Backend Service  | ----> |   Kubernetes API  |
|                   |       |                   |       |                   |
+-------------------+       +-------------------+       +-------------------+
        |                           ^
        |                           |
        v                           |
+-------------------+               |
|                   |               |
|   Dashboard       |  <------------+
|                   |
+-------------------+
```

