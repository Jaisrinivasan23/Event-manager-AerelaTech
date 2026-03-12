# API Documentation - Event Scheduler System

Complete REST API reference for the Event Scheduler & Resource Management application.

---

## 📖 Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Base URL](#base-url)
- [Response Format](#response-format)
- [Endpoints](#endpoints)
  - [Events](#events-api)
  - [Resources](#resources-api)
  - [Conflicts](#conflicts-api)
  - [Health](#health-check)
- [Error Handling](#error-handling)
- [Testing Examples](#testing-examples)
- [Role-Based Access](#role-based-access)

---

## Overview

The Event Scheduler API provides programmatic access to all core functionality including event management, resource allocation, and conflict detection. All endpoints return JSON responses and follow REST best practices.

**Features**:
- ✅ Session-based authentication
- ✅ Role-based access control
- ✅ Clean JSON responses
- ✅ Proper HTTP status codes
- ✅ Detailed error messages
- ✅ Date filtering support

---

## Authentication

The API uses **session-based authentication**. You must login via the web interface or `/login` endpoint to obtain a session cookie.

### Login Endpoint

**URL**: `/login`  
**Method**: `POST`  
**Content-Type**: `application/x-www-form-urlencoded` or `multipart/form-data`

**Request Body**:
```
username=admin&password=admin123
```

**Python Example**:
```python
import requests

session = requests.Session()
response = session.post('http://localhost:5000/login', data={
    'username': 'admin',
    'password': 'admin123'
})

if response.status_code == 200:
    print("Logged in successfully")
    # Session cookie is now stored in the session object
```

**cURL Example**:
```bash
curl -X POST http://localhost:5000/login \
  -d "username=admin&password=admin123" \
  -c cookies.txt  # Save cookies to file

# Use cookies in subsequent requests
curl -X GET http://localhost:5000/api/events -b cookies.txt
```

### Logout Endpoint

**URL**: `/logout`  
**Method**: `GET`

```python
session.get('http://localhost:5000/logout')
```

---

## Base URL

```
Local:      http://localhost:5000
Docker:     http://localhost:5000
Production: https://your-domain.com
```

All API endpoints are prefixed with `/api/` except health check.

---

## Response Format

### Success Response

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Response data
  }
}
```

### Error Response

```json
{
  "error": "Error message describing what went wrong",
  "details": ["Additional error detail 1", "Additional error detail 2"]
}
```

### HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful GET request |
| 201 | Created | Successful POST creation |
| 400 | Bad Request | Invalid input or validation failed |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 500 | Internal Server Error | Server error |

---

## Endpoints

### Events API

#### 1. List Events

Get a list of all events with optional date range filtering.

**URL**: `/api/events`  
**Method**: `GET`  
**Auth**: Required (any role)

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from` | string | No | Start date (YYYY-MM-DD format) |
| `to` | string | No | End date (YYYY-MM-DD format) |

**Example Request**:
```bash
GET /api/events?from=2026-03-15&to=2026-03-20
```

**Python**:
```python
response = session.get('http://localhost:5000/api/events', params={
    'from': '2026-03-15',
    'to': '2026-03-20'
})
events = response.json()
```

**Example Response**:
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
      "timezone": "Asia/Kolkata",
      "created_by": 1,
      "created_at": "2026-03-10T14:30:00",
      "resources": [
        {
          "resource_id": 1,
          "resource_name": "Conference Room A",
          "category": "Venue",
          "allocated_quantity": 1
        },
        {
          "resource_id": 3,
          "resource_name": "Projector",
          "category": "Equipment",
          "allocated_quantity": 1
        }
      ]
    },
    {
      "event_id": 2,
      "title": "Team Meeting",
      "start_time": "2026-03-16T14:00:00",
      "end_time": "2026-03-16T15:00:00",
      "description": "Weekly team sync",
      "expected_attendees": 10,
      "timezone": "Asia/Kolkata",
      "created_by": 2,
      "created_at": "2026-03-11T09:00:00",
      "resources": [
        {
          "resource_id": 2,
          "resource_name": "Meeting Room B",
          "category": "Venue",
          "allocated_quantity": 1
        }
      ]
    }
  ]
}
```

---

#### 2. Create Event

Create a new event.

**URL**: `/api/events`  
**Method**: `POST`  
**Auth**: Required (Organiser or Admin)  
**Content-Type**: `application/json`

**Request Body**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Event title (max 200 chars) |
| `start_time` | string | Yes | ISO 8601 datetime (UTC) |
| `end_time` | string | Yes | ISO 8601 datetime (UTC) |
| `description` | string | No | Event description |
| `expected_attendees` | integer | No | Number of expected attendees |
| `timezone` | string | No | Timezone (default: Asia/Kolkata) |

**Validation Rules**:
- `start_time` must be before `end_time`
- `expected_attendees` must be >= 0
- `title` cannot be empty

**Example Request**:
```json
POST /api/events
Content-Type: application/json

{
  "title": "Flask Training",
  "start_time": "2026-03-20T14:00:00",
  "end_time": "2026-03-20T16:00:00",
  "description": "Flask web framework training session",
  "expected_attendees": 30,
  "timezone": "Asia/Kolkata"
}
```

**Python**:
```python
event_data = {
    'title': 'Flask Training',
    'start_time': '2026-03-20T14:00:00',
    'end_time': '2026-03-20T16:00:00',
    'description': 'Flask web framework training session',
    'expected_attendees': 30,
    'timezone': 'Asia/Kolkata'
}

response = session.post(
    'http://localhost:5000/api/events',
    json=event_data
)
result = response.json()
```

**Success Response** (201 Created):
```json
{
  "success": true,
  "message": "Event created successfully",
  "event": {
    "event_id": 5,
    "title": "Flask Training",
    "start_time": "2026-03-20T14:00:00",
    "end_time": "2026-03-20T16:00:00",
    "description": "Flask web framework training session",
    "expected_attendees": 30,
    "timezone": "Asia/Kolkata",
    "created_by": 1,
    "created_at": "2026-03-12T10:30:00"
  }
}
```

**Error Response** (400 Bad Request):
```json
{
  "error": "start_time must be before end_time"
}
```

---

#### 3. Allocate Resources to Event

Allocate one or more resources to an existing event with conflict detection.

**URL**: `/api/events/{event_id}/allocate`  
**Method**: `POST`  
**Auth**: Required (Organiser or Admin)  
**Content-Type**: `application/json`

**URL Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_id` | integer | Yes | ID of the event |

**Request Body**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `resource_ids` | array | Yes | List of resource IDs to allocate |
| `quantities` | object | No | Map of resource_id → quantity (for equipment) |

**Example Request**:
```json
POST /api/events/5/allocate
Content-Type: application/json

{
  "resource_ids": [1, 3, 5],
  "quantities": {
    "1": 1,
    "3": 2,
    "5": 1
  }
}
```

**Python**:
```python
allocation_data = {
    'resource_ids': [1, 3, 5],
    'quantities': {
        '1': 1,
        '3': 2,
        '5': 1
    }
}

response = session.post(
    f'http://localhost:5000/api/events/5/allocate',
    json=allocation_data
)
```

**Success Response** (200 OK):
```json
{
  "success": true,
  "message": "Resources allocated successfully",
  "allocations": 3,
  "details": [
    {
      "resource_id": 1,
      "resource_name": "Conference Room A",
      "quantity": 1
    },
    {
      "resource_id": 3,
      "resource_name": "Projector",
      "quantity": 2
    },
    {
      "resource_id": 5,
      "resource_name": "Dr. Smith (Instructor)",
      "quantity": 1
    }
  ]
}
```

**Error Response - Validation Failed** (400 Bad Request):
```json
{
  "success": false,
  "error": "Validation failed",
  "details": [
    "Conference Room A: Room capacity (50) is less than expected attendees (60)",
    "Projector: Time conflict with Python Workshop (10:00-12:00)",
    "Dr. Smith: Would exceed daily hour limit (8.0h). Total would be: 9.5h"
  ]
}
```

**Error Response - Equipment Quantity** (400 Bad Request):
```json
{
  "success": false,
  "error": "Allocation failed",
  "details": [
    "Projector: Requested quantity (3) exceeds available (2)"
  ]
}
```

---

### Resources API

#### 4. List Available Resources

Get resources available during a specific time window.

**URL**: `/api/available-resources`  
**Method**: `GET`  
**Auth**: Required (any role)

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_time` | string | No | Start datetime (ISO 8601) |
| `end_time` | string | No | End datetime (ISO 8601) |
| `category` | string | No | Filter by category (Venue/Equipment/Person) |

**Example Request**:
```bash
GET /api/available-resources?start_time=2026-03-20T14:00:00&end_time=2026-03-20T16:00:00&category=Venue
```

**Python**:
```python
response = session.get('http://localhost:5000/api/available-resources', params={
    'start_time': '2026-03-20T14:00:00',
    'end_time': '2026-03-20T16:00:00',
    'category': 'Venue'
})
```

**Success Response**:
```json
{
  "success": true,
  "count": 3,
  "resources": [
    {
      "resource_id": 1,
      "resource_name": "Conference Room A",
      "resource_type": "Meeting Room",
      "category": "Venue",
      "capacity": 50,
      "quantity": 1,
      "available": true
    },
    {
      "resource_id": 2,
      "resource_name": "Meeting Room B",
      "resource_type": "Meeting Room",
      "category": "Venue",
      "capacity": 20,
      "quantity": 1,
      "available": true
    },
    {
      "resource_id": 4,
      "resource_name": "Auditorium",
      "resource_type": "Large Hall",
      "category": "Venue",
      "capacity": 200,
      "quantity": 1,
      "available": false,
      "reason": "Already allocated to Tech Conference"
    }
  ]
}
```

---

### Conflicts API

#### 5. Check Conflicts for Event

Check if an event has any resource conflicts.

**URL**: `/api/conflicts`  
**Method**: `GET`  
**Auth**: Required (any role)

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_id` | integer | Yes | ID of the event to check |

**Example Request**:
```bash
GET /api/conflicts?event_id=1
```

**Python**:
```python
response = session.get('http://localhost:5000/api/conflicts', params={
    'event_id': 1
})
conflicts = response.json()
```

**Success Response - No Conflicts**:
```json
{
  "success": true,
  "event_id": 1,
  "event_title": "Python Workshop",
  "has_conflicts": false,
  "conflict_count": 0,
  "conflicts": []
}
```

**Success Response - With Conflicts**:
```json
{
  "success": true,
  "event_id": 1,
  "event_title": "Python Workshop",
  "has_conflicts": true,
  "conflict_count": 2,
  "conflicts": [
    {
      "resource_id": 1,
      "resource_name": "Conference Room A",
      "resource_category": "Venue",
      "conflict_type": "time_overlap",
      "conflicting_events": [
        {
          "event_id": 2,
          "event_title": "Team Meeting",
          "start_time": "2026-03-15T11:00:00",
          "end_time": "2026-03-15T12:00:00",
          "overlap_start": "2026-03-15T11:00:00",
          "overlap_end": "2026-03-15T12:00:00",
          "overlap_duration_hours": 1.0
        }
      ]
    },
    {
      "resource_id": 3,
      "resource_name": "Projector",
      "resource_category": "Equipment",
      "conflict_type": "quantity_exceeded",
      "available_quantity": 2,
      "total_required": 3,
      "conflicting_events": [
        {
          "event_id": 4,
          "event_title": "Design Workshop",
          "reserved_quantity": 2
        }
      ]
    }
  ]
}
```

---

### Health Check

#### 6. Health Check Endpoint

Check application and database health (for Docker monitoring).

**URL**: `/health`  
**Method**: `GET`  
**Auth**: Not required (public)

**Example Request**:
```bash
GET /health
```

**Python**:
```python
response = requests.get('http://localhost:5000/health')
health = response.json()
```

**Success Response** (200 OK):
```json
{
  "status": "healthy",
  "database": "connected"
}
```

**Error Response** (503 Service Unavailable):
```json
{
  "status": "unhealthy",
  "error": "Database connection failed"
}
```

---

## Error Handling

### Common Error Responses

#### Authentication Required (403 Forbidden)
```json
{
  "error": "Authentication required. Please login first."
}
```

#### Insufficient Permissions (403 Forbidden)
```json
{
  "error": "You do not have permission to perform this action.",
  "required_role": "organiser"
}
```

#### Resource Not Found (404 Not Found)
```json
{
  "error": "Event not found",
  "event_id": 999
}
```

#### Validation Error (400 Bad Request)
```json
{
  "error": "Validation failed",
  "field": "start_time",
  "message": "start_time must be before end_time"
}
```

#### Server Error (500 Internal Server Error)
```json
{
  "error": "An internal server error occurred. Please try again later."
}
```

---

## Testing Examples

### Complete Workflow Example

This example demonstrates the complete API workflow:

```python
import requests
from datetime import datetime, timedelta

# === 1. Login ===
session = requests.Session()
base_url = 'http://localhost:5000'

login_response = session.post(f'{base_url}/login', data={
    'username': 'admin',
    'password': 'admin123'
})

if login_response.status_code != 200:
    print("Login failed!")
    exit(1)

print("✓ Login successful")

# === 2. Create Event ===
tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=14, minute=0, second=0)
event_end = tomorrow.replace(hour=16)

event_data = {
    'title': 'API Testing Workshop',
    'start_time': tomorrow.isoformat(),
    'end_time': event_end.isoformat(),
    'description': 'Learn API testing with Python',
    'expected_attendees': 25,
    'timezone': 'Asia/Kolkata'
}

create_response = session.post(f'{base_url}/api/events', json=event_data)
if create_response.status_code == 201:
    event = create_response.json()['event']
    event_id = event['event_id']
    print(f"✓ Event created with ID: {event_id}")
else:
    print(f"✗ Event creation failed: {create_response.json()}")
    exit(1)

# === 3. Check Available Resources ===
resources_response = session.get(f'{base_url}/api/available-resources', params={
    'start_time': tomorrow.isoformat(),
    'end_time': event_end.isoformat(),
    'category': 'Venue'
})

resources = resources_response.json()['resources']
print(f"✓ Found {len(resources)} available venues")

# === 4. Allocate Resources ===
allocation_data = {
    'resource_ids': [1, 3],  # Room and Projector
    'quantities': {
        '1': 1,
        '3': 1
    }
}

allocate_response = session.post(
    f'{base_url}/api/events/{event_id}/allocate',
    json=allocation_data
)

if allocate_response.status_code == 200:
    result = allocate_response.json()
    print(f"✓ Allocated {result['allocations']} resources")
else:
    error = allocate_response.json()
    print(f"✗ Allocation failed:")
    for detail in error.get('details', []):
        print(f"  - {detail}")
    exit(1)

# === 5. Check for Conflicts ===
conflict_response = session.get(f'{base_url}/api/conflicts', params={
    'event_id': event_id
})

conflict_data = conflict_response.json()
if conflict_data['has_conflicts']:
    print(f"⚠ Found {conflict_data['conflict_count']} conflicts:")
    for conflict in conflict_data['conflicts']:
        print(f"  - {conflict['resource_name']}: {conflict['conflict_type']}")
else:
    print("✓ No conflicts detected")

# === 6. List Events ===
list_response = session.get(f'{base_url}/api/events', params={
    'from': tomorrow.strftime('%Y-%m-%d'),
    'to': (tomorrow + timedelta(days=7)).strftime('%Y-%m-%d')
})

events = list_response.json()['events']
print(f"✓ Found {len(events)} events in date range")

# === 7. Logout ===
session.get(f'{base_url}/logout')
print("✓ Logged out")

print("\n=== API Test Complete ===")
```

### cURL Examples

```bash
# Login and save cookies
curl -X POST http://localhost:5000/login \
  -d "username=admin&password=admin123" \
  -c cookies.txt

# Get events
curl -X GET "http://localhost:5000/api/events?from=2026-03-15&to=2026-03-20" \
  -b cookies.txt

# Create event
curl -X POST http://localhost:5000/api/events \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "title": "cURL Test Event",
    "start_time": "2026-03-25T10:00:00",
    "end_time": "2026-03-25T12:00:00",
    "expected_attendees": 20
  }'

# Allocate resources
curl -X POST http://localhost:5000/api/events/1/allocate \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "resource_ids": [1, 3],
    "quantities": {"1": 1, "3": 1}
  }'

# Check conflicts
curl -X GET "http://localhost:5000/api/conflicts?event_id=1" \
  -b cookies.txt

# Check health
curl -X GET http://localhost:5000/health
```

---

## Role-Based Access

| Endpoint | Method | Viewer | Organiser | Admin |
|----------|--------|:------:|:---------:|:-----:|
| `GET /api/events` | GET | ✓ | ✓ | ✓ |
| `POST /api/events` | POST | ✗ | ✓ | ✓ |
| `POST /api/events/{id}/allocate` | POST | ✗ | ✓ | ✓ |
| `GET /api/conflicts` | GET | ✓ | ✓ | ✓ |
| `GET /api/available-resources` | GET | ✓ | ✓ | ✓ |
| `GET /health` | GET | ✓ | ✓ | ✓ |

**Legend**:
- ✓ = Access granted
- ✗ = Access denied (returns 403 Forbidden)

---

## Best Practices

### Security
- ✅ Always use HTTPS in production
- ✅ Implement rate limiting (not included, add Flask-Limiter)
- ✅ Use strong, random `SECRET_KEY`
- ✅ Never expose authentication credentials in code
- ✅ Validate all input on server side

### Performance
- ✅ Cache frequently accessed data
- ✅ Use database indexes (already implemented)
- ✅ Implement pagination for large datasets
- ✅ Use connection pooling for production

### Error Handling
- ✅ Always check response status codes
- ✅ Handle network errors gracefully
- ✅ Log errors appropriately
- ✅ Provide meaningful error messages to users

---

## Additional Features

### CORS Support

To enable cross-origin requests, install Flask-CORS:

```bash
pip install flask-cors
```

```python
from flask_cors import CORS
CORS(app)
```

### Rate Limiting

To add rate limiting, use Flask-Limiter:

```bash
pip install Flask-Limiter
```

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/api/events')
@limiter.limit("10 per minute")
def events_api():
    ...
```

---

## Changelog

### Version 2.0 (March 2026)
- ✅ Added user authentication
- ✅ Implemented role-based access control
- ✅ Added resource validation rules
- ✅ Enhanced conflict detection
- ✅ Added health check endpoint
- ✅ Improved error responses

### Version 1.0 (Initial Release)
- ✅ Basic event management
- ✅ Resource allocation
- ✅ Conflict detection
- ✅ Utilization reports

---

## Support

For questions, issues, or feature requests:
- Check the main [README.md](README.md)
- Review test examples in `tests/test_conflict.py`
- Contact: hr@aerele.in

---

**API Documentation Version**: 2.0  
**Last Updated**: March 12, 2026  
**Maintained by**: Aerele Technologies Assignment Team
