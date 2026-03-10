# API Documentation - Event Scheduler System

## Authentication
All API endpoints require authentication. You can authenticate using Flask session-based authentication by logging in first via the web interface, or by including session cookies in your API requests.

### Base URL
```
http://localhost:5000/api
```

## API Endpoints

### 1. GET /api/events
Get a list of events with optional date range filtering.

**Query Parameters:**
- `from` (optional): Start date in `YYYY-MM-DD` format
- `to` (optional): End date in `YYYY-MM-DD` format

**Example Request:**
```bash
curl -X GET "http://localhost:5000/api/events?from=2026-03-15&to=2026-03-20" \
  --cookie "session=your_session_cookie"
```

**Example Response:**
```json
{
  "success": true,
  "count": 2,
  "events": [
    {
      "event_id": 1,
      "title": "Python Workshop",
      "start_time": "2026-03-15T10:00:00",
      "end_time": "2026-03-15T12:00:00",
      "description": "Introduction to Python programming",
      "expected_attendees": 25,
      "timezone": "UTC",
      "resources": [
        {
          "resource_id": 1,
          "resource_name": "Conference Room A"
        }
      ]
    }
  ]
}
```

---

### 2. POST /api/events
Create a new event (requires organiser or admin role).

**Required Fields:**
- `title` (string): Event title
- `start_time` (string): ISO 8601 datetime
- `end_time` (string): ISO 8601 datetime

**Optional Fields:**
- `description` (string): Event description
- `expected_attendees` (integer): Number of expected attendees
- `timezone` (string): Timezone (default: UTC)

**Example Request:**
```bash
curl -X POST "http://localhost:5000/api/events" \
  -H "Content-Type: application/json" \
  --cookie "session=your_session_cookie" \
  -d '{
    "title": "Flask Training",
    "start_time": "2026-03-20T14:00:00",
    "end_time": "2026-03-20T16:00:00",
    "description": "Flask web framework training",
    "expected_attendees": 30,
    "timezone": "UTC"
  }'
```

**Example Response:**
```json
{
  "success": true,
  "message": "Event created successfully",
  "event": {
    "event_id": 5,
    "title": "Flask Training",
    "start_time": "2026-03-20T14:00:00",
    "end_time": "2026-03-20T16:00:00"
  }
}
```

**Error Response (Validation Failed):**
```json
{
  "error": "start_time must be before end_time"
}
```

---

### 3. POST /api/events/{event_id}/allocate
Allocate resources to an event (requires organiser or admin role).

**URL Parameters:**
- `event_id` (integer): ID of the event

**Request Body:**
- `resource_ids` (array): List of resource IDs to allocate
- `quantities` (object, optional): Map of resource_id to quantity (for equipment)

**Example Request:**
```bash
curl -X POST "http://localhost:5000/api/events/5/allocate" \
  -H "Content-Type: application/json" \
  --cookie "session=your_session_cookie" \
  -d '{
    "resource_ids": [1, 3],
    "quantities": {
      "1": 1,
      "3": 2
    }
  }'
```

**Example Response (Success):**
```json
{
  "success": true,
  "message": "Resources allocated successfully",
  "allocations": 2
}
```

**Example Response (Validation Failed):**
```json
{
  "success": false,
  "error": "Validation failed",
  "details": [
    "Conference Room A: Room capacity (50) is less than expected attendees (60)",
    "Test Projector: Time conflict with: Python Workshop"
  ]
}
```

---

### 4. GET /api/conflicts
Check for resource conflicts for a specific event.

**Query Parameters:**
- `event_id` (required): ID of the event to check

**Example Request:**
```bash
curl -X GET "http://localhost:5000/api/conflicts?event_id=1" \
  --cookie "session=your_session_cookie"
```

**Example Response (No Conflicts):**
```json
{
  "success": true,
  "event_id": 1,
  "has_conflicts": false,
  "conflict_count": 0,
  "conflicts": []
}
```

**Example Response (With Conflicts):**
```json
{
  "success": true,
  "event_id": 1,
  "has_conflicts": true,
  "conflict_count": 2,
  "conflicts": [
    {
      "resource_id": 1,
      "resource_name": "Conference Room A",
      "conflicting_event_id": 2,
      "conflicting_event_title": "Team Meeting",
      "overlap_start": "2026-03-15T11:00:00",
      "overlap_end": "2026-03-15T12:00:00"
    }
  ]
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "Error message describing what went wrong"
}
```

Common HTTP Status Codes:
- `200 OK`: Success
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid input or validation failed
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found

---

## Testing with Python

```python
import requests

# Login first to get session
session = requests.Session()
login_data = {
    'username': 'admin',
    'password': 'admin123'
}
session.post('http://localhost:5000/login', data=login_data)

# Now make API calls
response = session.get('http://localhost:5000/api/events?from=2026-03-15&to=2026-03-20')
print(response.json())

# Create event
event_data = {
    'title': 'API Test Event',
    'start_time': '2026-03-25T10:00:00',
    'end_time': '2026-03-25T12:00:00',
    'expected_attendees': 20
}
response = session.post('http://localhost:5000/api/events', json=event_data)
print(response.json())
```

---

## Role-Based Access Control

| Endpoint | Viewer | Organiser | Admin |
|----------|--------|-----------|-------|
| GET /api/events | ✓ | ✓ | ✓ |
| POST /api/events | ✗ | ✓ | ✓ |
| POST /api/events/{id}/allocate | ✗ | ✓ | ✓ |
| GET /api/conflicts | ✓ | ✓ | ✓ |

---

## Rate Limiting
Currently not implemented. Consider implementing rate limiting for production use.

## CORS
CORS is not enabled by default. Add Flask-CORS if you need cross-origin access.
