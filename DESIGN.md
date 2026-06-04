# Purplle Store Intelligence — Design Document

---

## 1. System Overview

This system converts CCTV video from a retail store into structured retail analytics data. It includes:
- CV Pipeline for person detection, tracking, zone mapping, and event generation.
- Kafka-based event streaming for raw tracking events.
- Analytics API for sessionization, anomaly detection, metrics aggregation, and REST access.
- React dashboard for business visualization.
- PostgreSQL storage for events, sessions, zones, POS data, and metrics.

The implementation is realized in this repository:
- `services/cv-pipeline/`
- `services/analytics-api/`
- `services/frontend/`
- `docker-compose.yml`

---

## 2. Architecture Diagram

```text
+---------------------------+       +--------------------------+       +-----------------------+
|                           |       |                          |       |                       |
|   CV Pipeline             | ----> |   Redpanda Kafka         | ----> |   Analytics API       |
|   (services/cv-pipeline)  |       |   (store.tracking.raw)   |       |   (services/analytics-api) |
|                           |       |                          |       |                       |
+---------------------------+       +--------------------------+       +-----------------------+
                                                                              |
                                                                              v
                                                                    +-----------------------+
                                                                    |                       |
                                                                    |   PostgreSQL          |
                                                                    |   (events, sessions,  |
                                                                    |    zones, persons,    |
                                                                    |    anomalies, metrics)|
                                                                    |                       |
                                                                    +-----------------------+
                                                                              |
                                                                              v
                                                                    +-----------------------+
                                                                    |                       |
                                                                    |   Frontend Dashboard  |
                                                                    |   (services/frontend) |
                                                                    |                       |
                                                                    +-----------------------+
```

---

## 3. CV Pipeline

### Implementation
Located in `services/cv-pipeline/`.

Key files:
- `services/cv-pipeline/app/main.py`
- `services/cv-pipeline/app/pipeline.py`
- `services/cv-pipeline/app/event_builder.py`
- `services/cv-pipeline/app/event_schema.py`
- `services/cv-pipeline/app/publisher.py`
- `services/cv-pipeline/app/zones.py`
- `config/zones/zones.yaml`

### Components
- **Person detection**: `PersonDetector` uses YOLOv8n via `services/cv-pipeline/app/detector.py`
- **Tracking**: ByteTrack maintains stable `track_id` values across frames
- **Zone mapping**: `load_zone_config` loads polygons and line definitions from `config/zones/zones.yaml`
- **Video ingestion**:
  - `CVPipeline.process_video()` reads frames with `app.video_reader.open_video`
  - It advances by `settings.frame_skip` and computes `video_time_sec`
- **Event publishing**: `EventPublisher` publishes events to Kafka raw topic

### Event Builder
`services/cv-pipeline/app/event_builder.py` converts tracks into canonical events:
- Supports event types:
  - `entry`
  - `exit`
  - `re_entry`
  - `zone_enter`
  - `zone_exit`
  - `dwell`
  - `staff_classified`
- Uses `TrackState` per `track_id` to maintain:
  - store occupancy
  - zone membership
  - entry/exit debounce
  - dwell timers
  - last seen and lost state
- Outputs to Kafka via `build_event()` and `enrich_metadata()`

---

## 4. Tracking and Sessionization

### Analytics Consumer
`services/analytics-api/app/consumers/tracking_consumer.py`

Flow:
- Kafka consumer subscribes to `store.tracking.raw`, `store.tracking.anomalies`
- Messages are normalized and persisted
- A `SessionEngine` instance processes events
- Periodic batch jobs:
  - `session_engine.close_expired_sessions()`
  - `session_engine.correlate_pos_transactions()`
  - `MetricsAggregator(db).refresh()`

### Event Normalization
`services/analytics-api/app/domain/event_normalizer.py`

Maps CV event types to internal analytics types:
- `entry` → `store.entry`
- `re_entry` → `store.entry`
- `exit` → `store.exit`
- `zone_enter` → `zone.enter`
- `zone_exit` → `zone.exit`
- `dwell` → `zone.dwell`
- `staff_classified` → `track.staff_classified`

`normalize_event()` also:
- extracts `track_id` from `person_id`
- attaches `person_type`
- propagates metadata fields:
  - `confidence`
  - `bbox`
  - `centroid`
  - `dwell_sec`
  - `visit_number`
  - `is_reentry`
  - `entry_line`
  - `exit_reason`
  - `zone_type`
  - `zone_name`

### Persistence
`services/analytics-api/app/domain/session_engine.py`

`persist_tracking_event(db, event_data, raw_event=raw_event)` writes raw event data into `events` table and ensures a `Person` row exists.

This function persists:
- `event_id`
- `store_id`
- `person_id`
- `event_type`
- `canonical_type`
- `zone_id`
- `timestamp`
- `metadata_json`

---

## 5. Event Flow

### Kafka Topics
- `store.tracking.raw` — Raw CV events
- `store.tracking.session` — Session-related events
- `store.anomalies` — Anomaly events
- `store.tracking.dlq` — Dead letter queue for invalid events

### Event Schema
Source schema is documented in `README.md` and implemented in `services/cv-pipeline/app/event_schema.py`.

Canonical event structure:
- `event_id`
- `timestamp`
- `person_id`
- `event_type`
- `zone_id`
- `metadata`:
  - `store_id`
  - `camera_id`
  - `frame_index`
  - `video_time_sec`
  - `video_source`
  - `confidence`
  - `bbox`
  - `centroid`
  - `person_type`
  - `visit_number`
  - `is_reentry`
  - `zone_type`
  - `zone_name`

### Analytics Event Processing
1. CV Pipeline publishes raw event
2. Analytics API consumer reads raw Kafka message
3. `normalize_event()` converts it to analytics internal format
4. `persist_tracking_event()` stores it in PostgreSQL
5. `SessionEngine.process_event()` updates current session state
6. Periodic metrics and anomaly aggregation refresh materialized metrics

---

## 6. Re-entry Handling

### Definition
Re-entry is treated as a special form of store entry after a person has exited and then re-entered.

### CV Rule
In `services/cv-pipeline/app/event_builder.py` `_line_crossings()`:
- If track crosses inbound entry line and last exit time is recent:
  - if within `reentry_cooldown_sec`:
    - resume existing visit without emitting a new event
  - if after `reentry_cooldown_sec`:
    - emit `re_entry`
    - increment `self.stats["re_entries"]`

### Analytics Rule
In `services/analytics-api/app/domain/session_engine.py` `_handle_entry()`:
- checks `payload.get("is_reentry")`
- checks `self.track_exit_times[track_id]`
- compares `timestamp - last_exit` to `settings.reentry_cooldown_sec`
- if within cooldown and not explicit `is_reentry`, resume the session:
  - clears `session.ended_at`
  - resets `session.end_reason`
- else create a new `VisitSession`

### Configuration
`services/analytics-api/app/config.py`
- `reentry_cooldown_sec: int = 120`

`config/zones/zones.yaml`
- includes global `reentry_cooldown_sec: 120`

---

## 7. Staff Exclusion Logic

### Detection
Staff classification is generated by CV:
- `EVENT_STAFF = "staff_classified"` in `services/cv-pipeline/app/event_schema.py`
- `EventBuilder` can emit `staff_classified` when a track qualifies as staff by zone/dwell heuristics

### Normalization
`services/analytics-api/app/domain/event_normalizer.py`
- maps raw `staff_classified` to `track.staff_classified`
- sets `payload["person_type"] = "staff"`

### Session Engine
`services/analytics-api/app/domain/session_engine.py`
- recognizes `track.staff_classified`
- marks `track_id` as staff in `self.staff_tracks`
- creates/updates `Person` with:
  - `person_type = "staff"`
  - `is_staff = True`
- updates any active session:
  - `session.person_type = "staff"`
  - `session.entry_counted = False`

### Metrics Impact
`services/analytics-api/app/domain/metrics_service.py`
- computes staff exclusion using session `person_type == "staff"`
- footfall excludes staff through:
  - `entry_counted` false for staff sessions
  - `staff_excluded` count in metrics response

### Zone-Based Staff Areas
`config/zones/zones.yaml`
- defines staff-only areas with `is_staff_only: true`
- has zones labeled `zone_type: staff` and `category: staff`

---

## 8. Zone Analytics

### Zone Event Model
`services/cv-pipeline/app/event_builder.py`
- Emits `zone_enter` and `zone_exit`
- Emits `dwell` after sustained presence
- Metadata includes:
  - `zone_type`
  - `zone_name`
  - `dwell_sec`
  - `visit_number`

### Session Zone Tracking
`services/analytics-api/app/domain/session_engine.py` `_handle_zone_event()`:
- tracks distinct `zones_visited`
- writes `SessionZoneVisit` rows on `zone.enter`
- fills `exited_at` and `dwell_sec` on `zone.exit`
- tracks checkout dwell and staff-zone anomaly conditions

### Checkout Analytics
- `CHECKOUT_ZONE = "CHECKOUT"`
- checkout dwell tracked in `session.checkout_dwell_sec`
- sessions with checkout dwell are marked `reached_checkout`

### Staff Zone Anomalies
- `if zone_id.startswith("STAFF_") and session.person_type == "customer":`
- creates anomaly type:
  - `customer_in_staff_zone`

---

## 9. Metrics Aggregation

### Metrics Service
`services/analytics-api/app/domain/metrics_service.py`

Metrics are derived from:
- `VisitSession` rows
- `PosTransaction` rows
- `SessionZoneVisit` summary

Computed outputs:
- footfall
- staff excluded
- re-entries
- engagement metrics
- conversion metrics
- revenue metrics
- hourly metrics
- top zones
- department mix

### Funnel Builder
`MetricsService.get_funnel()` computes funnel stages:
- `footfall`
- `engaged`
- `multi_zone`
- `checkout_proximity`
- `converted`

### Aggregator
`services/analytics-api/app/domain/metrics_aggregator.py`
- persists snapshots into `metrics` table
- supports `daily` and `hourly` aggregation
- used by batch refresh after Kafka message processing

---

## 10. Database Schema

### Main tables
- `stores`
- `zones`
- `persons`
- `events`
- `sessions`
- `zone_visits`
- `pos_transactions`
- `pos_line_items`
- `anomalies`
- `metrics`

### Key table definitions

#### `sessions`
(`services/analytics-api/app/models/session.py`)
- `session_id`
- `store_id`
- `person_id`
- `primary_track_id`
- `visit_number`
- `started_at`
- `ended_at`
- `person_type`
- `entry_counted`
- `zones_visited`
- `max_funnel_stage`
- `dwell_total_sec`
- `is_engaged`
- `reached_checkout`
- `checkout_dwell_sec`
- `is_converted`
- `invoice_number`

#### `events`
(`services/analytics-api/app/models/event.py`)
- `event_id`
- `store_id`
- `person_id`
- `session_id`
- `event_type`
- `canonical_type`
- `zone_id`
- `timestamp`
- `frame_index`
- `video_time_sec`
- `metadata`

#### `persons`
(`services/analytics-api/app/models/person.py`)
- `person_id`
- `store_id`
- `person_type`
- `first_seen_at`
- `last_seen_at`
- `visit_count`
- `is_staff`
- `last_track_id`

#### `zone_visits`
(`services/analytics-api/app/models/zone_visit.py`)
- `session_id`
- `person_id`
- `zone_id`
- `entered_at`
- `exited_at`
- `dwell_sec`

#### `zones`
(`services/analytics-api/app/models/reference.py`)
- `zone_id`
- `store_id`
- `zone_name`
- `zone_type`
- `department_map`
- `polygon_json`
- `is_staff_only`

#### `pos_transactions` / `pos_line_items`
(`services/analytics-api/app/models/reference.py`)
- on POS matching and revenue attribution

---

## 11. API Architecture

### Service
`services/analytics-api/app/main.py`
- FastAPI application
- CORS middleware
- Lifecycle startup uses `init_db()`
- Health endpoints:
  - `/health`
  - `/ready`

### Route definitions
`services/analytics-api/app/api/routes.py`
Endpoints:
- `/api/v1/metrics`
- `/api/v1/funnel`
- `/api/v1/events`
- `/api/v1/sessions`
- `/api/v1/sessions/{session_id}`
- `/api/v1/zones`
- `/api/v1/anomalies`
- `/api/v1/anomalies/summary`
- `/api/v1/pos/transactions`

### Data Access
- Database session is provided by `services/analytics-api/app/database.py`
- `SessionLocal` uses SQLAlchemy engine with connection pooling:
  - `pool_size=10`
  - `max_overflow=20`

### Validation
- Pydantic schemas in `services/analytics-api/app/schemas/`
- API response models enforce typed JSON structure

---

## 12. Dashboard Architecture

### Frontend stack
`services/frontend/`
- React 18
- TypeScript
- Tailwind CSS
- Recharts

### Data fetching
`services/frontend/src/api/client.ts`
- `api.metrics()`
- `api.funnel()`
- `api.anomalies()`
- Base API URL is configured in `API_BASE`

### UI structure
`services/frontend/src/App.tsx`
- periodic polling every 15 seconds
- fetches metrics, funnel, anomalies
- refresh button

`services/frontend/src/components/Dashboard.tsx`
- KPI cards
- Conversion funnel bar chart
- Hourly line chart
- Top zones bar chart
- Department mix pie chart

### Dashboard design
- Clear separation of business KPIs and anomaly feed
- Real-time autoreload for operational monitoring
- Staff exclusion displayed via `Revenue / Visitor` card subtext

---

## 13. Deployment Architecture

### Orchestration
`docker-compose.yml`

Services:
- `postgres`
- `redpanda`
- `init-seed`
- `analytics-api`
- `cv-pipeline`
- `frontend`

### Startup sequence
- `postgres` and `redpanda` start first
- `init-seed` seeds zone and POS data
- `cv-pipeline` runs after seed and Kafka readiness
- `analytics-api` depends on `cv-pipeline` and `init-seed`
- `frontend` depends on `analytics-api`

### Networking
- isolated Docker network: `store-network`
- `postgres` volume persisted at `pg_data`
- config mounted read-only into containers
- CCTV video and ground truth CSV mounted into CV pipeline via volumes

### Service roles
- `cv-pipeline`: batch/process video and publish tracking events
- `analytics-api`: consume events, build sessions, generate analytics
- `frontend`: user-facing visualization
- `postgres`: storage
- `redpanda`: event bus

---

## 14. Testing Strategy

### Test coverage
Repository includes tests for:
- `services/analytics-api/tests/`
- `services/cv-pipeline/tests/`

### Key unit/integration tests
- `services/cv-pipeline/tests/test_event_builder.py`
  - validates `entry`, `re_entry`, `zone_enter`, `zone_exit`
  - validates re-entry behavior after cooldown
- `services/analytics-api/tests/test_integration.py`
  - validates `track.staff_classified`
  - validates session and person workflow
- `services/analytics-api/tests/test_metrics_service.py`
  - validates computed metrics
- `services/analytics-api/tests/test_database.py`
  - validates person/session persistence

### Testing approach
- event builder correctness on synthetic frames
- analytics consumer behavior with normalized events
- session timeout, staff handling, and POS matching
- API endpoint consistency with Pydantic response models

---

## 15. Scalability Considerations

### Event throughput
- Kafka-based decoupling allows CV pipeline and analytics consumers to scale independently
- Raw tracking events stored persistently before analytic processing

### Database
- PostgreSQL connection pool configured in `database.py`
- indexed columns for query-heavy access patterns:
  - sessions by store and start time
  - events by store, person, zone, and timestamp
  - anomalies by store and type

### Batch vs real-time
- consumer batches metrics refresh every 50 messages
- session engine closes expired sessions and correlates POS transactions incrementally

### Horizontal scaling
- `tracking_consumer.py` can be extended to multiple Kafka consumer instances if `group.id` is scaled
- `cv-pipeline` can be distributed across multiple video sources / store cameras
- frontend is static and can be deployed on CDN / container cluster

### Extensibility
- Zone configuration is externalized in `config/zones/zones.yaml`
- Staff classification rules are configurable by zone definitions
- Metrics aggregator supports daily/hourly snapshot persistence

---

## 16. AI-Assisted Decisions

AI tools were used under human supervision to support this submission process in the following ways:

- **Architecture exploration**: AI assisted in locating and mapping actual implementation artifacts across the repository.
- **Debugging**: AI helped verify current event outputs and matched them to code paths like `EventBuilder` and `SessionEngine`.
- **Code review**: AI ensured that design descriptions referenced exact repository files and data flows without inventing features.
- **Documentation generation**: AI synthesized the implementation into a submission-ready design doc that reflects real file paths and component interactions.
- **Productivity**: AI accelerated repository analysis, allowing the engineer to focus on confirming the actual implementation rather than writing the entire design narrative from scratch.

## 17. Assumptions

- CCTV camera placement provides sufficient visibility of store entry and exit zones.
- Zone polygons are configured correctly in zones.yaml.
- POS transaction data is available for conversion correlation.
- Track IDs remain sufficiently stable for session reconstruction.

## 18. Known Limitations

- Staff classification depends on configured heuristics and zone definitions.
- Occlusions may occasionally impact tracking continuity.
- Single-camera deployment limits cross-camera identity continuity.
- Conversion attribution is probabilistic when multiple visitors are near checkout.

## 19. Future Improvements

- Multi-camera identity re-identification.
- Learned staff classification models.
- Real-time streaming dashboard updates via WebSockets.
- Cloud-native deployment using Kubernetes.
- Advanced customer journey analytics and heatmaps.

