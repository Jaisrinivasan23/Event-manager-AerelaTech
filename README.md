# Event Scheduling & Resource Allocation System

A comprehensive Flask web application for managing events, resources, and their allocations with built-in conflict detection and reporting capabilities.

## 📋 Project Overview

This system allows organizations to efficiently manage events and resources by:
- Creating and managing events with specific time slots
- Maintaining a catalog of resources (rooms, equipment, instructors, etc.)
- Allocating resources to events with automatic conflict detection
- Generating utilization reports with upcoming bookings
- Preventing double-booking through intelligent time-overlap detection

## ✨ Features

### 1. Event Management (CRUD)
- Create, read, update, and delete events
- Store event details: title, start/end times, description
- Automatic validation: start time must be before end time
- Display event duration in hours
- View all allocated resources per event

### 2. Resource Management (CRUD)
- Create, read, update, and delete resources
- Categorize resources by type (Room, Equipment, Instructor, etc.)
- Track total allocations per resource
- Cascading deletion of associated allocations

### 3. Resource Allocation
- Allocate multiple resources to events
- User-friendly interface with checkboxes for resource selection
- Real-time conflict detection before saving
- View all allocations with detailed information
- Remove allocations individually

### 4. Conflict Detection
- **Intelligent Time-Overlap Algorithm**: Prevents double-booking by checking if:
  ```
  event1.start_time < event2.end_time AND event2.start_time < event1.end_time
  ```
- Validates conflicts during:
  - Event creation/editing (when resources are already allocated)
  - Resource allocation to events
- Displays detailed conflict information with affected event names
- Blocks operations that would create conflicts

### 5. Resource Utilization Reports
- Date-range based reporting
- Calculate total hours used per resource
- List upcoming bookings for each resource
- Summary statistics dashboard:
  - Total resources count
  - Total hours used across all resources
  - Total upcoming bookings
- Visual presentation with Bootstrap cards and tables

### 6. Sample Data Seeder
- One-click database population
- Creates 5 sample resources
- Creates 4 sample events with realistic time slots
- Generates 7 resource allocations
- Useful for testing and demonstration

## 🛠️ Tech Stack

- **Backend**: Python 3.x, Flask
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: HTML5, Bootstrap 5.3, Jinja2 Templates
- **Icons**: Bootstrap Icons
- **JavaScript**: Vanilla JS for client-side enhancements

## 📁 Project Structure

```
event_scheduler/
├── app.py                          # Main Flask application with all routes
├── config.py                       # Configuration (database, secret key)
├── models.py                       # SQLAlchemy models (Event, Resource, Allocation)
├── events.db                       # SQLite database (auto-created)
├── templates/
│   ├── base.html                   # Base template with navbar
│   ├── events/
│   │   ├── list.html               # List all events
│   │   ├── add.html                # Add event form
│   │   └── edit.html               # Edit event form
│   ├── resources/
│   │   ├── list.html               # List all resources
│   │   ├── add.html                # Add resource form
│   │   └── edit.html               # Edit resource form
│   ├── allocations/
│   │   ├── allocate.html           # Allocate resources form
│   │   └── list.html               # List all allocations
│   └── reports/
│       └── report.html             # Resource utilization report
└── static/
    ├── css/
    │   └── style.css               # Custom CSS styles
    └── js/
        └── script.js               # Client-side JavaScript
```

## 🚀 Installation & Setup

### Prerequisites
- Python 3.7 or higher
- pip (Python package manager)

### Step 1: Install Dependencies

```bash
pip install flask flask-sqlalchemy
```

### Step 2: Navigate to Project Directory

```bash
cd event_scheduler
```

### Step 3: Run the Application

```bash
python app.py
```

The application will start on `http://127.0.0.1:5000/`

### Database Migrations (Flask-Migrate)

If you've modified models (e.g., added the `category` field on `Resource`), use Flask-Migrate to apply schema changes safely:

```bash
# Install new dependency
pip install -r requirements.txt

# Create migration scripts (autogenerate changes)
flask db init         # only if you haven't initialized migrations yet
flask db migrate -m "Add category to Resource"

# Apply migrations to the database
flask db upgrade
```

Notes:
- I added Flask-Migrate to `requirements.txt` and a sample migration `migrations/versions/0001_add_category.py` that adds the `category` column. If you prefer a quick in-place fix instead, you can also run:

```bash
python scripts/add_category_column.py
```

This script performs a non-destructive `ALTER TABLE` and heuristically fills common categories (Venue, Equipment, Person) for existing resources.

### Step 4: Load Sample Data (Optional)

1. Open your browser and navigate to `http://127.0.0.1:5000/`
2. Click on "Seed Data" in the navigation bar
3. Sample events, resources, and allocations will be created

## 📖 Usage Guide

### Adding Events
1. Navigate to **Events** → **Add New Event**
2. Fill in:
   - Event title
   - Start time (datetime)
   - End time (datetime)
   - Description (optional)
3. System validates start_time < end_time
4. Click "Add Event"

### Adding Resources
1. Navigate to **Resources** → **Add New Resource**
2. Fill in:
   - Resource name (e.g., "Conference Room A")
   - Resource type (e.g., "Room", "Equipment", "Instructor")
3. Click "Add Resource"

### Allocating Resources
1. Navigate to **Allocate**
2. Select an event from the dropdown
3. Check one or more resources to allocate
4. System automatically checks for conflicts
5. If conflict detected: operation blocked with error message
6. If no conflicts: allocation saved successfully

### Viewing Reports
1. Navigate to **Reports**
2. Select start and end dates
3. Click "Generate"
4. View:
   - Resource name and type
   - Total hours used in date range
   - List of upcoming bookings
   - Summary statistics

## 🔍 Conflict Detection Logic

The system uses the following algorithm to detect time overlaps:

```python
def check_resource_conflict(resource_id, start_time, end_time, exclude_event_id=None):
    # Two events overlap if:
    # event1.start_time < event2.end_time AND event2.start_time < event1.end_time
    
    allocations = get_resource_allocations(resource_id)
    
    for allocation in allocations:
        event = allocation.event
        
        if exclude_event_id and event.id == exclude_event_id:
            continue  # Skip current event when editing
        
        if start_time < event.end_time and event.start_time < end_time:
            # Conflict detected!
            return True
    
    return False
```

### Example Scenarios

**Scenario 1: Conflict Detected**
- Event A: Room 101, 2:00 PM - 4:00 PM
- Event B: Room 101, 3:00 PM - 5:00 PM
- Result: ❌ Conflict! Room 101 is already booked

**Scenario 2: No Conflict**
- Event A: Room 101, 2:00 PM - 4:00 PM
- Event B: Room 101, 4:00 PM - 6:00 PM
- Result: ✅ No conflict, times don't overlap

## 📊 Database Schema

### Event Table
```sql
event_id (PK)
title
start_time
end_time
description
```

### Resource Table
```sql
resource_id (PK)
resource_name
resource_type
```

### EventResourceAllocation Table
```sql
allocation_id (PK)
event_id (FK → Event)
resource_id (FK → Resource)
allocated_at
```

## 🎥 Demo Video Instructions

To create a demonstration video:

1. **Introduction** (30 seconds)
   - Show the home page
   - Explain the purpose of the application

2. **Load Sample Data** (15 seconds)
   - Click "Seed Data"
   - Show confirmation message

3. **Events Management** (1 minute)
   - List events page
   - Add a new event
   - Edit an existing event
   - Show event deletion

4. **Resources Management** (45 seconds)
   - List resources page
   - Add a new resource
   - Edit a resource

5. **Resource Allocation** (1.5 minutes)
   - Navigate to Allocate page
   - Select an event
   - Choose multiple resources
   - Demonstrate successful allocation
   - **Conflict Detection**: Try to allocate the same resource to overlapping events
   - Show error message preventing the conflict

6. **Allocations List** (30 seconds)
   - View all allocations
   - Show details (event, resource, time)
   - Delete an allocation

7. **Reports** (1 minute)
   - Generate a report for a date range
   - Show total hours used
   - Display upcoming bookings
   - Explain summary statistics

8. **Conclusion** (15 seconds)
   - Summarize key features
   - Mention conflict detection as primary feature

**Total Duration**: 5-6 minutes

## 📝 Assignment Submission Checklist

- [x] Complete project structure created
- [x] All CRUD operations implemented
- [x] Conflict detection working correctly
- [x] Resource utilization report functional
- [x] Bootstrap UI implemented
- [x] Sample data seeder included
- [x] README.md with complete documentation
- [x] Clean, commented code
- [x] Database models with proper relationships
- [x] Form validation (start_time < end_time)
- [x] Flash messages for user feedback
- [x] Responsive design

## 🐛 Troubleshooting

### Database Issues
If you encounter database errors, delete `events.db` and restart the application. The database will be recreated automatically.

### Port Already in Use
If port 5000 is busy, modify `app.py`:
```python
if __name__ == '__main__':
    app.run(debug=True, port=5001)
```

### Import Errors
Ensure all dependencies are installed:
```bash
pip install flask flask-sqlalchemy
```

## 🔐 Security Notes

- Change `SECRET_KEY` in `config.py` for production use
- Do not commit `events.db` to version control (add to `.gitignore`)
- Implement user authentication for production deployment
- Add CSRF protection for forms in production

## 🌟 Future Enhancements

- User authentication and authorization
- Email notifications for upcoming events
- Calendar view for events
- Export reports to PDF/Excel
- Resource availability checker
- Recurring events support
- Mobile responsive improvements
- REST API for external integrations

## 👨‍💻 Developer Notes

- The application uses Flask's development server (not for production)
- SQLite is suitable for development; consider PostgreSQL for production
- All routes include error handling with appropriate HTTP status codes
- Templates use Jinja2 templating engine
- Bootstrap CDN is used (requires internet connection)

## 📄 License

This project is created for educational purposes as part of an academic assignment.

## 📧 Contact

For questions or issues, please contact the development team.

---

**Built with ❤️ using Flask and Bootstrap**
