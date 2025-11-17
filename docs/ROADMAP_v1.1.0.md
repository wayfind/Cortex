# Cortex v1.1.0 Development Roadmap

**Version**: v1.1.0
**Code Name**: "Quality & Observability"
**Planned Release**: 2025-12 (1 month after v1.0.0-rc1)
**Status**: 📋 Planning Phase

---

## 🎯 Release Goals

v1.1.0 focuses on three main areas:
1. **Quality Enhancement**: Improve test coverage to 75%+
2. **Observability**: Add Prometheus & Grafana integration
3. **Stability**: Fix technical debt and deprecation warnings

### Success Criteria
- [ ] Test coverage ≥ 75% (from 61%)
- [ ] WebSocket E2E tests complete
- [ ] Auth E2E tests complete
- [ ] Prometheus metrics exporter working
- [ ] Grafana dashboard available
- [ ] All deprecation warnings fixed
- [ ] No known critical bugs

---

## 📊 Phase Overview

| Phase | Focus | Duration | Priority |
|-------|-------|----------|----------|
| 6.1 | Test Coverage Improvement | 1 week | High |
| 6.2 | WebSocket & Auth E2E Tests | 1 week | High |
| 6.3 | Code Quality & Deprecations | 3 days | High |
| 6.4 | Prometheus Integration | 1 week | Medium |
| 6.5 | Grafana Dashboard | 5 days | Medium |
| 6.6 | Documentation & Release | 2 days | High |

**Total Estimated Duration**: ~4 weeks

---

## 📦 Phase 6.1: Test Coverage Improvement

**Goal**: Increase overall coverage from 61% to 75%+

### Target Modules (Low Coverage → High Priority)

#### 1. cortex/monitor/routers/cluster.py (33% → 65%)
**Current Issues**:
- Cluster topology queries not tested
- Node registration flows missing tests
- Heartbeat timeout logic not covered

**Test Scenarios Needed**:
- [ ] POST /cluster/register with valid/invalid data
- [ ] GET /cluster/topology with nested clusters
- [ ] GET /cluster/nodes with filtering
- [ ] DELETE /cluster/nodes/{id} cascade behavior
- [ ] Heartbeat timeout detection and handling
- [ ] Parent-child node relationship validation

**Estimated Tests**: +15 tests
**Expected Coverage**: 65%

#### 2. cortex/monitor/routers/alerts.py (37% → 75%)
**Current Issues**:
- Alert creation and update not fully tested
- Acknowledgment workflow incomplete
- Filtering and pagination missing tests

**Test Scenarios Needed**:
- [ ] POST /alerts with various severity levels
- [ ] GET /alerts with complex filtering (severity, status, agent_id)
- [ ] PUT /alerts/{id}/acknowledge
- [ ] DELETE /alerts/{id}
- [ ] Alert auto-escalation (if implemented)
- [ ] Bulk operations

**Estimated Tests**: +12 tests
**Expected Coverage**: 75%

#### 3. cortex/monitor/routers/decisions.py (40% → 75%)
**Current Issues**:
- Decision approval/rejection flows incomplete
- Feedback mechanism not tested
- Status transitions not validated

**Test Scenarios Needed**:
- [ ] POST /decisions/{id}/approve with valid reasoning
- [ ] POST /decisions/{id}/reject with valid reasoning
- [ ] GET /decisions with status filtering
- [ ] Decision execution confirmation flow
- [ ] Invalid state transitions (e.g., approve rejected decision)
- [ ] Concurrent decision handling

**Estimated Tests**: +10 tests
**Expected Coverage**: 75%

#### 4. cortex/monitor/routers/reports.py (40% → 70%)
**Current Issues**:
- Report storage and retrieval not fully tested
- L1/L2/L3 issue parsing incomplete
- Actions taken validation missing

**Test Scenarios Needed**:
- [ ] POST /reports with L1 actions_taken
- [ ] POST /reports with L2 issues requiring decision
- [ ] POST /reports with L3 critical issues
- [ ] POST /reports with mixed L1+L2+L3
- [ ] GET /reports with filtering and pagination
- [ ] Report validation edge cases

**Estimated Tests**: +8 tests
**Expected Coverage**: 70%

#### 5. cortex/monitor/websocket_manager.py (36% → 80%)
**Current Issues**:
- WebSocket connection lifecycle not tested
- Broadcasting to multiple clients not validated
- Reconnection logic not covered

**Test Scenarios Needed**:
- [ ] Client connection and authentication
- [ ] Event broadcasting to multiple clients
- [ ] Client disconnection handling
- [ ] Message serialization and deserialization
- [ ] Connection pool management
- [ ] Error handling during send

**Estimated Tests**: +8 tests (in Phase 6.2)
**Expected Coverage**: 80%

#### 6. cortex/probe/claude_executor.py (38% → 65%)
**Current Issues**:
- Claude execution flow not tested
- Progress tracking not validated
- Error recovery not covered

**Test Scenarios Needed**:
- [ ] Successful probe execution with mock Claude
- [ ] Claude API timeout handling
- [ ] Progress callback mechanism
- [ ] Output parsing and validation
- [ ] Retry logic on transient failures
- [ ] Resource cleanup after execution

**Estimated Tests**: +10 tests
**Expected Coverage**: 65%

#### 7. cortex/probe/websocket_manager.py (53% → 85%)
**Test Scenarios Needed**:
- [ ] Status update broadcasting during probe execution
- [ ] Multiple client connections
- [ ] Error notification to clients
- [ ] Completion event broadcasting

**Estimated Tests**: +6 tests (in Phase 6.2)
**Expected Coverage**: 85%

### Summary
- **Total New Tests**: ~69 tests
- **Expected New Coverage**: 61% → 75%+
- **Time Estimate**: 1 week

---

## 📦 Phase 6.2: WebSocket & Auth E2E Tests

**Goal**: Complete E2E test coverage for WebSocket and Authentication

### WebSocket E2E Tests

**File**: `tests/test_e2e_websocket.py`

#### Scenario 1: Monitor WebSocket Real-time Events
```python
async def test_monitor_websocket_report_broadcast():
    """
    Test real-time report event broadcasting

    Steps:
    1. Client connects to Monitor WebSocket (/ws)
    2. Probe submits report with L2 decision request
    3. Client receives 'report_received' event
    4. Monitor processes decision
    5. Client receives 'decision_made' event

    Expected: All events received in correct order
    """
```

#### Scenario 2: Probe WebSocket Progress Updates
```python
async def test_probe_websocket_inspection_progress():
    """
    Test probe inspection progress updates

    Steps:
    1. Client connects to Probe WebSocket
    2. Trigger probe inspection
    3. Client receives 'inspection_started' event
    4. Client receives periodic 'inspection_progress' events
    5. Client receives 'inspection_completed' event

    Expected: All progress events received
    """
```

#### Scenario 3: Multi-client Broadcasting
```python
async def test_multi_client_broadcast():
    """
    Test broadcasting to multiple WebSocket clients

    Steps:
    1. Connect 3 clients to Monitor WebSocket
    2. Trigger an event (e.g., alert creation)
    3. All 3 clients receive the broadcast

    Expected: All clients receive identical event
    """
```

#### Scenario 4: WebSocket Reconnection
```python
async def test_websocket_reconnection():
    """
    Test WebSocket reconnection after disconnect

    Steps:
    1. Client connects
    2. Simulate network interruption (close connection)
    3. Client attempts reconnection
    4. Client subscribes to events again

    Expected: Reconnection successful, events resume
    """
```

**Estimated Tests**: +4 WebSocket E2E tests
**Time Estimate**: 3 days

### Authentication E2E Tests

**File**: `tests/test_e2e_auth.py`

#### Scenario 1: Agent API Key Authentication
```python
async def test_agent_api_key_auth():
    """
    Test Agent API Key authentication flow

    Steps:
    1. Register new agent (POST /api/v1/cluster/register)
    2. Receive API key in response
    3. Use API key to access protected endpoint
    4. Attempt access with invalid API key (expect 401)

    Expected: Valid key grants access, invalid key denied
    """
```

#### Scenario 2: JWT Token Authentication
```python
async def test_jwt_token_auth():
    """
    Test JWT token authentication flow

    Steps:
    1. User login (POST /api/v1/auth/login)
    2. Receive JWT access token
    3. Use token to access protected endpoint
    4. Wait for token expiration
    5. Attempt access with expired token (expect 401)
    6. Refresh token (POST /api/v1/auth/refresh)

    Expected: Token lifecycle working correctly
    """
```

#### Scenario 3: Role-based Access Control (RBAC)
```python
async def test_rbac_permissions():
    """
    Test role-based access control

    Steps:
    1. Login as 'viewer' role
    2. Attempt read operation (expect success)
    3. Attempt write operation (expect 403)
    4. Login as 'admin' role
    5. Attempt write operation (expect success)

    Expected: Permissions enforced correctly
    """
```

#### Scenario 4: API Key Rotation
```python
async def test_api_key_rotation():
    """
    Test API key rotation for security

    Steps:
    1. Agent uses old API key
    2. Request API key rotation
    3. Receive new API key
    4. Old key still works (grace period)
    5. After grace period, old key rejected
    6. New key works

    Expected: Smooth key rotation without downtime
    """
```

**Estimated Tests**: +4 Auth E2E tests
**Time Estimate**: 2 days

### Summary
- **Total New E2E Tests**: +8 tests
- **Time Estimate**: 5 days (1 week)

---

## 📦 Phase 6.3: Code Quality & Deprecations

**Goal**: Fix all deprecation warnings and improve code quality

### 1. Fix datetime.utcnow() Deprecation

**Issue**: Python 3.12+ deprecates `datetime.utcnow()`
**Impact**: 50+ warnings in test output

**Files to Update**:
- `cortex/monitor/routers/alerts.py`
- `cortex/monitor/routers/decisions.py`
- `cortex/monitor/routers/reports.py`
- `cortex/monitor/routers/cluster.py`
- `cortex/monitor/database.py`
- All test files using `datetime.utcnow()`

**Migration**:
```python
# Old (deprecated)
from datetime import datetime
timestamp = datetime.utcnow()

# New (timezone-aware)
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc)
```

**Tasks**:
- [ ] Replace all `datetime.utcnow()` with `datetime.now(timezone.utc)`
- [ ] Update database schema if needed (timezone info)
- [ ] Run all tests to verify no regressions
- [ ] Update documentation examples

**Estimated Changes**: ~60 occurrences
**Time Estimate**: 1 day

### 2. Add Tests for Logging Configuration

**File**: `cortex/common/logging_config.py` (0% coverage)

**Test Scenarios**:
- [ ] Logger initialization with different levels
- [ ] File rotation configuration
- [ ] Module-specific log levels
- [ ] Log format validation
- [ ] Async logging performance

**Estimated Tests**: +5 tests
**Time Estimate**: 1 day

### 3. Code Linting and Static Analysis

**Tools**:
- `ruff`: Fast Python linter
- `mypy`: Static type checking
- `bandit`: Security linting

**Tasks**:
- [ ] Run `ruff check cortex/ tests/`
- [ ] Fix all critical issues
- [ ] Run `mypy cortex/`
- [ ] Add type hints where missing (priority: public APIs)
- [ ] Run `bandit -r cortex/`
- [ ] Fix security warnings

**Estimated Time**: 1 day

### Summary
- **Time Estimate**: 3 days

---

## 📦 Phase 6.4: Prometheus Integration

**Goal**: Add Prometheus metrics exporter for observability

### Metrics to Export

#### 1. Probe Metrics
```python
# cortex/probe/metrics.py

# Inspection metrics
probe_inspections_total = Counter('probe_inspections_total', 'Total inspections', ['agent_id', 'status'])
probe_inspection_duration_seconds = Histogram('probe_inspection_duration_seconds', 'Inspection duration')
probe_issues_detected_total = Counter('probe_issues_detected_total', 'Issues detected', ['level'])

# Action metrics
probe_actions_taken_total = Counter('probe_actions_taken_total', 'Actions taken', ['action_type'])
probe_actions_success_total = Counter('probe_actions_success_total', 'Successful actions')
probe_actions_failed_total = Counter('probe_actions_failed_total', 'Failed actions')
```

#### 2. Monitor Metrics
```python
# cortex/monitor/metrics.py

# Decision metrics
monitor_decisions_total = Counter('monitor_decisions_total', 'Total decisions', ['status'])
monitor_decision_duration_seconds = Histogram('monitor_decision_duration_seconds', 'Decision processing time')

# Alert metrics
monitor_alerts_total = Counter('monitor_alerts_total', 'Total alerts', ['severity'])
monitor_alerts_active = Gauge('monitor_alerts_active', 'Active alerts')

# Cluster metrics
monitor_agents_total = Gauge('monitor_agents_total', 'Total agents', ['status'])
monitor_cluster_depth = Gauge('monitor_cluster_depth', 'Maximum cluster depth')

# API metrics
monitor_api_requests_total = Counter('monitor_api_requests_total', 'API requests', ['method', 'endpoint', 'status'])
monitor_api_request_duration_seconds = Histogram('monitor_api_request_duration_seconds', 'API request duration')
```

#### 3. Intent-Engine Metrics
```python
# cortex/common/intent_metrics.py

intent_records_total = Counter('intent_records_total', 'Total intents', ['type', 'status'])
intent_status_transitions = Counter('intent_status_transitions', 'Status transitions', ['from_status', 'to_status'])
```

### Implementation

**Files to Create**:
- `cortex/probe/metrics.py`: Probe metrics definitions
- `cortex/monitor/metrics.py`: Monitor metrics definitions
- `cortex/common/intent_metrics.py`: Intent-Engine metrics
- `cortex/monitor/routers/metrics.py`: `/metrics` endpoint

**Integration Points**:
- Add metrics tracking to all critical operations
- Create `/api/v1/metrics` endpoint exposing Prometheus format
- Add middleware for automatic HTTP metrics

**Configuration** (`.env`):
```bash
# Prometheus Metrics
CORTEX_PROMETHEUS_ENABLED=true
CORTEX_PROMETHEUS_PORT=9090
CORTEX_PROMETHEUS_PATH=/metrics
CORTEX_PROMETHEUS_INCLUDE_INTENT_METRICS=true
```

**Tasks**:
- [ ] Install `prometheus-client` library
- [ ] Create metrics definitions
- [ ] Instrument code with metrics
- [ ] Add `/metrics` endpoint
- [ ] Write tests for metrics
- [ ] Update documentation

**Estimated Time**: 1 week

---

## 📦 Phase 6.5: Grafana Dashboard

**Goal**: Create pre-built Grafana dashboard for Cortex monitoring

### Dashboard Panels

#### 1. Overview Panel
- Total agents (gauge)
- Active alerts (gauge)
- Inspection rate (graph)
- Decision rate (graph)

#### 2. Probe Performance Panel
- Inspection success rate (%)
- Average inspection duration
- Issues detected by level (stacked area chart)
- Actions taken by type (bar chart)

#### 3. Decision Engine Panel
- Decision approval rate (%)
- Decision processing time (heatmap)
- Decisions by status (pie chart)
- Decision queue length (graph)

#### 4. Alert Management Panel
- Alerts by severity (stacked bar)
- Alert response time (histogram)
- Active alerts timeline
- Top alerting agents (table)

#### 5. Cluster Health Panel
- Agent status distribution (pie chart)
- Heartbeat latency (graph)
- Cluster topology visualization
- Node failure rate (graph)

#### 6. API Performance Panel
- Request rate by endpoint (graph)
- Response time P50/P95/P99 (graph)
- Error rate by status code (graph)
- Active WebSocket connections (gauge)

### Deliverables

**Files to Create**:
- `deployment/grafana/cortex-dashboard.json`: Dashboard definition
- `deployment/grafana/datasource.yml`: Prometheus datasource config
- `deployment/grafana/README.md`: Setup instructions

**Docker Integration**:
```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./deployment/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    volumes:
      - ./deployment/grafana/datasource.yml:/etc/grafana/provisioning/datasources/datasource.yml
      - ./deployment/grafana/cortex-dashboard.json:/etc/grafana/provisioning/dashboards/cortex.json
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

**Tasks**:
- [ ] Design dashboard layout in Grafana UI
- [ ] Export dashboard JSON
- [ ] Create Prometheus scrape config
- [ ] Write docker-compose.monitoring.yml
- [ ] Test full monitoring stack
- [ ] Write setup documentation

**Estimated Time**: 5 days

---

## 📦 Phase 6.6: Documentation & Release

**Goal**: Update documentation and prepare v1.1.0 release

### Documentation Updates

#### New Documentation
1. **PROMETHEUS_METRICS.md**: Metrics reference
2. **GRAFANA_DASHBOARD.md**: Dashboard setup guide
3. **MONITORING_GUIDE.md**: Complete monitoring setup

#### Updated Documentation
1. **README.md**: Add monitoring badges and quick start
2. **INSTALLATION.md**: Add Prometheus/Grafana optional setup
3. **DOCKER_DEPLOYMENT.md**: Include monitoring stack
4. **CONFIGURATION.md**: Document new config options
5. **TESTING.md**: Update coverage statistics

### Release Preparation

**Tasks**:
- [ ] Update CHANGELOG.md with v1.1.0 changes
- [ ] Create RELEASE_NOTES_v1.1.0.md
- [ ] Run full test suite (expect 265+ tests, 75%+ coverage)
- [ ] Performance benchmarking
- [ ] Security audit
- [ ] Create release commit and tag
- [ ] Push to GitHub
- [ ] Create GitHub Release with binaries (if applicable)

**Estimated Time**: 2 days

---

## 📊 Expected Outcomes

### Quality Metrics
| Metric | v1.0.0-rc1 | v1.1.0 Target | Improvement |
|--------|------------|---------------|-------------|
| Test Coverage | 61% | 75%+ | +14% |
| Total Tests | 196 | 265+ | +69 |
| E2E Scenarios | 10 | 18+ | +8 |
| Deprecation Warnings | 50+ | 0 | -100% |
| Code Quality Score | - | A | New |

### Feature Metrics
| Feature | Status |
|---------|--------|
| Prometheus Metrics | ✅ Complete |
| Grafana Dashboard | ✅ Complete |
| WebSocket E2E Tests | ✅ Complete |
| Auth E2E Tests | ✅ Complete |
| Cluster Router Tests | ✅ 65% coverage |
| Alerts Router Tests | ✅ 75% coverage |

### Performance
- API P95 response time: < 200ms (maintained)
- Metrics export overhead: < 5ms per request
- Grafana dashboard refresh: < 1s

---

## 🚦 Risk Assessment

### High Risk
None identified

### Medium Risk
1. **Prometheus Integration Complexity**
   - Mitigation: Start with basic metrics, iterate
   - Fallback: Make Prometheus optional

2. **Test Coverage Time Overrun**
   - Mitigation: Prioritize critical modules
   - Fallback: Release at 70% if necessary

### Low Risk
1. **Grafana Dashboard Design**
   - Mitigation: Use community templates as base
   - Fallback: Provide JSON, users customize

---

## 📅 Timeline

```
Week 1: Phase 6.1 - Test Coverage Improvement
├── Days 1-3: Cluster, Alerts, Decisions router tests
├── Days 4-5: Reports, Claude Executor tests
└── Day 5-7: Review and coverage validation

Week 2: Phase 6.2 - WebSocket & Auth E2E + Phase 6.3 - Code Quality
├── Days 1-3: WebSocket E2E tests
├── Days 4-5: Auth E2E tests
└── Days 6-7: Fix deprecations, logging tests, linting

Week 3: Phase 6.4 - Prometheus Integration
├── Days 1-2: Metrics definitions and instrumentation
├── Days 3-4: /metrics endpoint and testing
└── Days 5-7: Documentation and refinement

Week 4: Phase 6.5 - Grafana + Phase 6.6 - Release
├── Days 1-3: Grafana dashboard creation
├── Days 4-5: Monitoring stack testing
└── Days 6-7: Documentation and release preparation
```

**Target Release Date**: 2025-12-15

---

## 🎯 Success Definition

v1.1.0 is considered successful if:
- [x] 75%+ code coverage achieved
- [x] All E2E test scenarios passing
- [x] Zero deprecation warnings
- [x] Prometheus metrics exporting
- [x] Grafana dashboard functional
- [x] All documentation updated
- [x] No performance regression
- [x] Zero critical bugs

---

## 🔄 Post-Release Plans (v1.2.0)

Ideas for future releases:
- Redis cache support for cluster mode
- Custom inspection rules UI
- Alert rule engine with conditions
- Mobile alert push notifications
- PostgreSQL migration automation
- Kubernetes deployment manifests
- Multi-language UI (i18n)
- Advanced AI-powered anomaly detection

---

*Roadmap Created: 2025-11-17*
*Status: Planning Phase*
*Next Action: Begin Phase 6.1 on 2025-11-20*
