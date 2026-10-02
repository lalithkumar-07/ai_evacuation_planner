# AI Disaster Simulation and Evacuation Planner

> An AI-assisted disaster simulation and evacuation decision-support platform for modeling disaster risk, population exposure, evacuation routes, shelter allocation, dynamic rerouting, and evacuation performance.

---

## 📌 Overview

The **AI Disaster Simulation and Evacuation Planner** is a simulation-based decision-support system designed to analyze how populations can be evacuated during dynamically changing disaster conditions.

Traditional evacuation systems often focus primarily on the shortest route or nearest shelter. However, during a disaster, the shortest route may become unsafe due to:

* Increasing hazard intensity
* Road blockages
* Traffic congestion
* Infrastructure failures
* Population concentration
* Shelter capacity limitations
* Changing disaster boundaries

This project addresses these challenges by combining **disaster-risk modeling, road-network analysis, risk-aware routing, shelter assignment, population simulation, dynamic rerouting, and analytical evaluation** into a single platform.

The current prototype uses **synthetic data** to validate the complete simulation pipeline. The architecture is designed so that real-world geospatial, population, disaster, and machine-learning datasets can be integrated in future versions.

---

# 🎯 Objectives

The main objectives of the project are to:

* Model disaster scenarios and their spatial impact.
* Calculate risk levels across affected regions.
* Estimate the population exposed to disaster conditions.
* Represent roads as a dynamic graph.
* Identify safe and accessible evacuation routes.
* Assign evacuees to suitable shelters.
* Simulate population evacuation over time.
* Detect changing road and disaster conditions.
* Dynamically reroute evacuees when routes become unsafe.
* Evaluate evacuation performance using measurable metrics.
* Compare conventional shortest-path evacuation with risk-aware evacuation.
* Provide an interactive dashboard for visualizing the complete process.

---

# 🚨 Problem Statement

During an emergency, evacuation decisions cannot depend only on geographical distance.

Consider the following situation:

```text
Population
    │
    ▼
Shortest Route
    │
    ▼
Flooded Road
    │
    ▼
Route becomes unavailable
    │
    ▼
Evacuation delay
```

A safer approach is:

```text
Disaster Conditions
        │
        ▼
Risk Assessment
        │
        ▼
Road Accessibility
        │
        ▼
Traffic / Congestion
        │
        ▼
Shelter Availability
        │
        ▼
Risk-Aware Route
        │
        ▼
Dynamic Evacuation
        │
        ▼
Continuous Rerouting
```

The proposed system therefore treats evacuation as a **dynamic optimization and simulation problem** rather than a simple shortest-path problem.

---

# 🧠 Key Features

## 1. Disaster Scenario Generation

The system supports configurable disaster scenarios.

Current prototype scenarios include:

* Flood
* Earthquake
* Wildfire

Each scenario can contain parameters such as:

* Disaster type
* Location
* Intensity
* Radius
* Spread behavior
* Simulation duration

The architecture allows additional disaster types to be added.

---

## 2. Risk Assessment

The disaster engine calculates risk for different geographic locations.

Risk can depend on factors such as:

```text
Hazard Intensity
       +
Distance from Hazard
       +
Population Exposure
       +
Road Accessibility
       ↓
    Risk Score
```

Risk levels are represented as:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

The resulting risk information can be visualized on the interactive map.

---

## 3. Population Modeling

Population is represented using synthetic geographic population units in the current prototype.

Population information can include:

* Location
* Population count
* Vulnerability
* Mobility characteristics
* Evacuation status
* Assigned shelter

The architecture allows real population and demographic datasets to replace synthetic data later.

---

## 4. Dynamic Road Network

Roads are modeled as a graph.

Each road segment can contain information such as:

```text
Distance
Travel Time
Risk
Congestion
Capacity
Accessibility
Status
```

Road status can change during the simulation:

```text
OPEN
CONGESTED
RESTRICTED
DANGEROUS
BLOCKED
```

This allows the evacuation system to respond to changing disaster conditions.

---

# 🛣️ 5. Evacuation Routing

The project implements multiple routing strategies.

### Baseline Strategy

The baseline uses conventional shortest-path routing.

```text
Origin
   ↓
Shortest Path
   ↓
Nearest/Selected Shelter
```

Algorithms such as **Dijkstra/A*** can be used for the baseline.

### Proposed Strategy

The risk-aware routing system considers multiple factors:

```text
Distance
+
Travel Time
+
Risk
+
Congestion
+
Accessibility
```

A configurable route cost can be represented as:

```text
Route Cost =
    w₁ × Distance
  + w₂ × Travel Time
  + w₃ × Risk
  + w₄ × Congestion
  + w₅ × Accessibility
```

The weights can be adjusted for experimentation.

---

# 🏠 6. Shelter Assignment

The system evaluates available shelters based on more than geographical distance.

Shelter assignment considers:

* Shelter capacity
* Current occupancy
* Remaining capacity
* Shelter risk
* Travel distance
* Travel time
* Road accessibility

Example:

```text
             Population
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
    Shelter A  Shelter B  Shelter C
      FULL       SAFE       HIGH RISK
        │         │
        ✕         ✓
                  │
                  ▼
             Assignment
```

If a shelter reaches capacity or becomes unsafe, evacuees can be reassigned.

---

# 🚶 7. Evacuation Simulation

The project includes a simulation engine that models evacuation over discrete time steps.

An evacuation agent can move through states such as:

```text
AT_HOME
    ↓
EVACUATING
    ↓
TRAVELING
    ↓
REROUTING
    ↓
AT_SHELTER
    ↓
SAFE
```

The simulation can track:

* Evacuee movement
* Travel time
* Risk exposure
* Route changes
* Shelter assignment
* Evacuation completion

---

# 🔄 8. Dynamic Rerouting

One of the central features of the system is dynamic adaptation.

For example:

```text
Initial Route
     ↓
Flood Expands
     ↓
Road Risk Increases
     ↓
Road Becomes Blocked
     ↓
Existing Route Becomes Invalid
     ↓
Alternative Route Calculated
     ↓
Evacuees Rerouted
```

This allows the system to model situations where conditions change after evacuation has already started.

---

# 📊 9. Evaluation Metrics

The simulation calculates measurable evacuation metrics.

### Evacuation Time

Total time required to evacuate the simulated population.

### Average Travel Time

Average travel time for evacuees.

### Maximum Travel Time

Maximum travel time among evacuees.

### Risk Exposure

Amount of exposure to hazardous areas during evacuation.

### Evacuation Success Rate

Percentage of population reaching safe shelters.

### Shelter Utilization

Percentage of shelter capacity occupied.

### Congestion

Traffic load on evacuation routes.

### Rerouting Count

Number of times routes are recalculated.

### Unserved Population

Population that does not successfully reach a shelter within the simulation.

---

# 📈 10. Baseline vs Proposed Evaluation

A major purpose of the system is to allow comparison between:

### Baseline

```text
Shortest Path
+
Nearest/Selected Shelter
```

and:

### Proposed

```text
Risk-Aware Routing
+
Dynamic Conditions
+
Shelter Constraints
+
Dynamic Rerouting
```

The system can compare metrics such as:

| Metric              |                Baseline |                Proposed |
| ------------------- | ----------------------: | ----------------------: |
| Evacuation Time     | Generated by simulation | Generated by simulation |
| Average Travel Time | Generated by simulation | Generated by simulation |
| Risk Exposure       | Generated by simulation | Generated by simulation |
| Congestion          | Generated by simulation | Generated by simulation |
| Shelter Utilization | Generated by simulation | Generated by simulation |
| Rerouting           | Generated by simulation | Generated by simulation |
| Unserved Population | Generated by simulation | Generated by simulation |

**Important:** Results must come from actual simulation runs. The project does not hard-code performance improvements.

---

# 🗺️ Interactive Dashboard

The frontend provides a disaster-management dashboard containing:

### Scenario Controls

* Disaster selection
* Disaster intensity
* Scenario type
* Simulation strategy

### Interactive Map

The map visualizes:

* Disaster zones
* Risk zones
* Roads
* Blocked roads
* Population
* Shelters
* Evacuation routes
* Evacuees

### Live KPIs

The dashboard displays:

```text
Population
Affected Population
At-Risk Population
Evacuated Population
Remaining Population
Active Shelters
Blocked Roads
Reroutes
Simulation Time
```

### Analytics

The dashboard provides:

* Evacuation progress
* Live population movement
* Route comparison
* Simulation metrics
* Baseline vs proposed analysis

---

# 🏗️ System Architecture

```text
                         ┌──────────────────────┐
                         │      FRONTEND        │
                         │ Responsive Dashboard │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       FASTAPI        │
                         │      REST API        │
                         └──────────┬───────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             │                      │                      │
             ▼                      ▼                      ▼
     ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
     │   Disaster   │       │   Routing    │       │ Simulation   │
     │    Engine    │       │    Engine    │       │    Engine    │
     └──────┬───────┘       └──────┬───────┘       └──────┬───────┘
            │                      │                      │
            ▼                      ▼                      ▼
       Risk Model             Road Graph             Population
            │                      │                      │
            └──────────────────────┼──────────────────────┘
                                   │
                                   ▼
                          Shelter Assignment
                                   │
                                   ▼
                           Dynamic Rerouting
                                   │
                                   ▼
                            Metrics Engine
                                   │
                                   ▼
                          Analytics Dashboard
```

---

# 📁 Project Structure

```text
AI-Disaster-Simulation-Evacuation-Planner/
│
├── README.md
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── run.py
│
├── config/
│   ├── settings.py
│   └── simulation_config.yaml
│
├── data/
│   ├── raw/
│   │   ├── roads/
│   │   ├── population/
│   │   ├── shelters/
│   │   └── disasters/
│   │
│   ├── processed/
│   │   ├── road_network.json
│   │   ├── population.json
│   │   └── shelters.json
│   │
│   └── sample/
│       └── demo_scenario.json
│
├── models/
│   ├── trained/
│   └── checkpoints/
│
├── src/
│   ├── data/
│   ├── disaster/
│   ├── graph/
│   ├── routing/
│   ├── simulation/
│   ├── ai/
│   └── utils/
│
├── backend/
│   ├── main.py
│   ├── api/
│   ├── schemas/
│   └── services/
│
├── frontend/
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── assets/
│
├── tests/
│
├── notebooks/
│
├── scripts/
│
└── docs/
```

---

# ⚙️ Technology Stack

## Backend

* Python
* FastAPI
* Pydantic
* NetworkX
* NumPy
* Pandas

## Geospatial Processing

* GeoPandas
* Shapely

## Machine Learning

* Scikit-learn
* PyTorch-compatible architecture for future models

## Frontend

* HTML5
* CSS3
* JavaScript
* Tailwind CSS
* Leaflet / map visualization

## Visualization

* Chart.js
* Interactive map visualization

## Testing

* Pytest

## Deployment

* Docker
* Docker Compose

---

# 🧪 Current Prototype Status

The current prototype contains a working simulation pipeline.

### Implemented

* [x] Disaster scenario generation
* [x] Synthetic population
* [x] Synthetic road network
* [x] Synthetic shelters
* [x] Disaster risk calculation
* [x] Road accessibility changes
* [x] Shortest-path routing
* [x] Risk-aware routing
* [x] Shelter assignment
* [x] Evacuation simulation
* [x] Dynamic rerouting
* [x] Simulation metrics
* [x] Baseline vs proposed evaluation
* [x] FastAPI backend
* [x] Interactive frontend
* [x] Responsive dashboard
* [x] Automated tests

The current automated test suite contains **23 tests**, covering the major simulation and API components.

---

# 🤖 AI/ML Component

The architecture contains a modular AI prediction layer.

The current prototype uses a deterministic prediction component to provide a stable interface for the simulation pipeline.

This is intentional because the first objective is to validate the complete:

```text
Disaster
→ Risk
→ Routing
→ Simulation
→ Rerouting
→ Evaluation
```

pipeline.

Future versions can replace the deterministic predictor with trained models for:

* Disaster risk prediction
* Evacuation demand prediction
* Traffic prediction
* Population exposure prediction

Actual model performance should only be reported after training and evaluation on appropriate datasets.

---

# 📦 Installation

## 1. Clone the repository

```bash
git clone <repository-url>
cd AI-Disaster-Simulation-Evacuation-Planner
```

---

## 2. Create a virtual environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux/macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

# ▶️ Running the Project

Start the application using:

```bash
python run.py
```

Alternatively, run FastAPI directly:

```bash
uvicorn backend.main:app --reload
```

The application will be available through the local server address displayed by FastAPI.

---

# 🧪 Running Tests

Run:

```bash
pytest
```

The current prototype is expected to pass its automated test suite.

---

# 🚀 Demonstration Workflow

For a project demonstration:

```text
1. Open Dashboard
        ↓
2. Select Disaster
        ↓
3. Configure Scenario
        ↓
4. Generate Scenario
        ↓
5. View Risk Map
        ↓
6. View Affected Population
        ↓
7. View Available Shelters
        ↓
8. Generate Evacuation Route
        ↓
9. Compare Baseline and Proposed Route
        ↓
10. Start Simulation
        ↓
11. Observe Population Movement
        ↓
12. Observe Changing Risk
        ↓
13. Observe Road Changes
        ↓
14. Observe Dynamic Rerouting
        ↓
15. View Final Metrics
        ↓
16. Compare Evacuation Strategies
```

---

# 🔬 Research Methodology

The project follows an iterative simulation-based methodology:

```text
Data Preparation
      ↓
Disaster Modeling
      ↓
Risk Assessment
      ↓
Population Exposure
      ↓
Road Network Construction
      ↓
Evacuation Demand
      ↓
Route Optimization
      ↓
Shelter Assignment
      ↓
Agent-Based Simulation
      ↓
Dynamic Rerouting
      ↓
Performance Evaluation
```

The baseline and proposed approaches can be evaluated under identical simulation conditions.

---

# 📊 Experimental Design

Experiments can be conducted using scenarios such as:

### Scenario 1 — Normal Conditions

No active disaster.

### Scenario 2 — Static Disaster

The affected region remains approximately constant.

### Scenario 3 — Expanding Disaster

The hazard region changes over simulation time.

### Scenario 4 — Road Failure

Selected road segments become unavailable.

### Scenario 5 — Shelter Capacity Constraint

Shelters reach their capacity during evacuation.

### Scenario 6 — Combined Scenario

Multiple constraints occur simultaneously.

These scenarios can be used to evaluate the behavior of the evacuation algorithms.

---

# 🔮 Future Scope

Future versions can include:

## Real-World Geospatial Data

Integrate:

* OpenStreetMap road networks
* GIS datasets
* Population datasets
* Real shelter locations
* Administrative boundaries

## Machine Learning

Train models for:

* Disaster risk prediction
* Flood propagation
* Traffic prediction
* Evacuation demand
* Population exposure

## Real-Time Data

Potential future integrations include:

* Weather data
* Traffic feeds
* Sensor networks
* Satellite imagery
* Emergency alerts

## Advanced Optimization

Future work can investigate:

* Genetic algorithms
* Reinforcement learning
* Multi-agent optimization
* Dynamic network optimization
* Multi-objective evolutionary algorithms

## Advanced Simulation

Potential extensions include:

* Pedestrian simulation
* Vehicle simulation
* Public transport
* Vulnerable population modeling
* Emergency vehicle prioritization

## Production Infrastructure

For larger deployments:

* PostgreSQL/PostGIS
* Redis
* Background workers
* WebSockets
* Container orchestration
* Authentication
* Multi-user simulation sessions

---

# ⚠️ Limitations

The current prototype has several limitations.

### Synthetic Data

The current demonstration uses synthetic data for roads, population, shelters, and disaster conditions.

Therefore, simulation results should not be interpreted as predictions of actual disaster behavior.

### Simplified Disaster Models

Real disasters involve complex physical processes that cannot be fully represented by simplified prototype models.

### Simplified Human Behavior

Real evacuation behavior depends on:

* Human decision-making
* Fear and uncertainty
* Family groups
* Accessibility
* Communication
* Transportation availability

The current model provides an abstraction of these behaviors.

### Prototype Prediction Model

The current prediction interface is deterministic rather than a trained production ML model.

### Single-Session Architecture

The current prototype is designed primarily for demonstration and experimentation rather than simultaneous multi-user deployment.

---

# 🔐 Safety and Intended Use

This project is intended as a **research prototype, simulation environment, and decision-support demonstration**.

It should not be treated as a replacement for:

* Emergency management authorities
* Official evacuation orders
* Emergency response systems
* Professional disaster management procedures

Real-world deployment would require extensive validation, reliable live data, domain expertise, safety testing, and coordination with relevant authorities.

---

# 👥 Project Team

**Project:** AI Disaster Simulation and Evacuation Planner

**Domain:**

* Artificial Intelligence
* Machine Learning
* Disaster Management
* Geospatial Computing
* Graph Algorithms
* Optimization
* Simulation
* Decision Support Systems

---

# 📜 License

Add the project's chosen license here.

For example:

```text
MIT License
```

if the project is intended to be released under the MIT License.

---

# ⭐ Project Summary

The **AI Disaster Simulation and Evacuation Planner** integrates disaster modeling, risk assessment, road-network analysis, shelter allocation, route optimization, and evacuation simulation into a unified decision-support platform.

The key idea is to move beyond static shortest-path evacuation toward **dynamic, risk-aware evacuation planning**, where changing disaster conditions can influence road accessibility, shelter availability, population exposure, and evacuation routes.

The current prototype establishes the complete simulation pipeline using synthetic data and provides a foundation for future integration of real-world geospatial data, trained machine-learning models, advanced optimization algorithms, and real-time disaster information.

---

## Project Pipeline

```text
                 AI DISASTER EVACUATION PLANNER

                       DISASTER INPUT
                            │
                            ▼
                    ┌───────────────┐
                    │ Risk Analysis │
                    └───────┬───────┘
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
        Population      Road Network    Shelters
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                    EVACUATION PLANNER
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
        Route Planning  Shelter Assign.  Simulation
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                     DYNAMIC REROUTING
                            │
                            ▼
                      EVALUATION
                            │
                            ▼
                    ANALYTICS DASHBOARD
```

**Build. Simulate. Analyze. Adapt.**
