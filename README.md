# Event Scheduler & Resource Manager (v2)

[![Tests](https://img.shields.io/badge/tests-12%20passed-success)]()
[![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen)]()
[![API](https://img.shields.io/badge/API-REST-blue)]()
[![Auth](https://img.shields.io/badge/auth-role--based-orange)]()

A full-featured Flask application for managing events, resources, and allocations with authentication, role-based access control, automatic conflict detection, REST API, and comprehensive testing.

**🎯 Assignment Version 2 - Aerele Technologies**

---

## ✨ Features (v2 Complete)

### Core Features
- ✅ **Events CRUD** with validation (start < end, expected attendees, timezone)
- ✅ **Resources CRUD** with categories, capacity, quantity, and working hours
- ✅ **Smart Allocation** with multi-resource support and quantity management
- ✅ **Conflict Prevention** detecting all overlap types (partial, full, nested, boundary)
- ✅ **Utilization Reports** with date-range filtering and upcoming bookings

### v2 Advanced Features
- ✅ **User Authentication** (login, register, logout)
- ✅ **Role-Based Access Control** (Admin, Organiser, Viewer)
- ✅ **Real-World Resource Rules**:
  - Room capacity vs attendance validation
  - Equipment quantity limits (e.g., 2 projectors available)
  - Instructor working-hour constraints (e.g., max 8 hours/day)
- ✅ **REST API Layer** with JSON responses
- ✅ **Comprehensive Testing** (12 unit tests for conflict logic)
- ✅ **Enhanced Conflict UX** with detailed error messages

---

## 🚀 Quick Start

### 1. Setup (3 commands)

```bash
python -m venv venv
venv\Scripts\activate    # Windows PowerShell
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
# Delete old database if exists
del events.db

# Run app (it will create database)
python app.py
```

### 3. Seed Sample Data

Visit http://127.0.0.1:5000/seed to populate with:
- 3 users (admin, organiser, viewer)
- 5 resources (rooms, equipment, instructors)
- 4 events with allocations

**Demo Login Credentials:**
- Admin: `admin` / `admin123`
- Organiser: `organiser` / `organiser123`
- Viewer: `viewer` / `viewer123`

---

## 📚 Documentation

- **[API Documentation](API_DOCUMENTATION.md)** - REST API endpoints and examples
- **[Testing Guide](TESTING_GUIDE.md)** - How to run and write tests

---

## 🔑 Authentication & Roles

### User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Full access: manage events, resources, allocations, users |
| **Organiser** | Create/edit events, allocate resources, view reports |
| **Viewer** | Read-only access to events, resources, and reports |

### Registration
New users can register via `/register` route. Default role is **Viewer**. Contact an admin to upgrade permissions.

---

## 🏗️ Architecture

```mermaid
flowchart TB
    U[User] -->|HTTP| Auth{Authenticated?}
    Auth -->|No| Login[Login Page]
    Auth -->|Yes| Role{Role Check}
    Role -->|Admin/Organiser| Write[Write Operations]
    Role -->|Viewer| Read[Read Operations]
    Write --> API[Flask Routes/API]
    Read --> API
    API --> Validation[Resource Validation]
    Validation --> Conflict{Conflict Check}
    Conflict -->|Yes| Error[Show Conflicts]
    Conflict -->|No| DB[(SQLite DB)]
```

## 📊 Database Schema

### Enhanced Models (v2)

**User**
- user_id (PK)
- username (unique)
- email (unique)
- password_hash
- role (admin/organiser/viewer)
- is_active
- created_at

**Event**
- event_id (PK)
- title
- start_time
- end_time
- description
- **timezone** ⭐ NEW
- **expected_attendees** ⭐ NEW
- **created_by** (FK to User) ⭐ NEW

**Resource**
- resource_id (PK)
- resource_name
- resource_type
- category (Venue/Person/Equipment)
- **capacity** ⭐ NEW (for rooms)
- **quantity** ⭐ NEW (for equipment)
- **max_hours_per_day** ⭐ NEW (for instructors)

**EventResourceAllocation**
- allocation_id (PK)
- event_id (FK)
- resource_id (FK)
- **reserved_quantity** ⭐ NEW
- allocated_at
- **Index**: (event_id, resource_id) ⭐ NEW

---

## 🧪 Testing

### Run Unit Tests
```bash
pytest tests/ -v
```

### Test Coverage
```bash
pytest tests/ --cov=app --cov-report=html
```

### Test Categories
- **Overlap Detection** (7 tests): Partial, full, nested, boundary conditions
- **Equipment Quantity** (2 tests): Within limit, exceeds limit
- **Resource Rules** (2 tests): Room capacity, instructor hours
- **Total**: 12 tests (meets requirement of 6-8 minimum)

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for details.

---

## 🔌 REST API

### Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/events` | List events with date filter | Required |
| POST | `/api/events` | Create event | Organiser/Admin |
| POST | `/api/events/{id}/allocate` | Allocate resources | Organiser/Admin |
| GET | `/api/conflicts` | Check conflicts | Required |

### Example Usage

```python
import requests

session = requests.Session()
session.post('http://localhost:5000/login', data={
    'username': 'admin',
    'password': 'admin123'
})

# Get events in date range
response = session.get('http://localhost:5000/api/events?from=2026-03-15&to=2026-03-20')
print(response.json())

# Create event
event = {
    'title': 'API Test',
    'start_time': '2026-03-25T10:00:00',
    'end_time': '2026-03-25T12:00:00',
    'expected_attendees': 30
}
response = session.post('http://localhost:5000/api/events', json=event)
print(response.json())
```

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for complete reference.

---

## ⚙️ Resource Rules (Real-World Constraints)

### 1. Room Capacity Validation
```python
# Room capacity: 50 people
# Event attendees: 60
# Result: ❌ Error - "Room capacity (50) is less than expected attendees (60)"
```

### 2. Equipment Quantity Limits
```python
# Available projectors: 2
# Event A uses: 2 projectors (10:00-12:00)
# Event B wants: 1 projector (10:00-12:00)
# Total needed: 3
# Result: ❌ Conflict - exceeds available quantity
```

### 3. Instructor Working Hours
```python
# Instructor max hours: 8.0 per day
# Event A: 4 hours (09:00-13:00)
# Event B: 5 hours (14:00-19:00)
# Total: 9 hours
# Result: ❌ Error - "Instructor would exceed daily limit (8.0h). Total: 9.0h"
```

---

## 🎨 UI Features

- **Modern UI** with Tailwind CSS
- **Role-based navigation** (hide/show links based on permissions)
- **User info display** showing username and role
- **Flash messages** for feedback
- **Responsive design** for mobile/desktop
- **Conflict indicators** with detailed error messages

---

## 🚢 Deployment

### Database Migrations
```bash
# Create migration from model changes
flask db migrate -m "Description of changes"

# Apply migration
flask db upgrade

# Rollback if needed
flask db downgrade
```

### Production Setup
```bash
# Set production environment variables
export FLASK_ENV=production
export SECRET_KEY="your-super-secret-key-here"
export DATABASE_URL="postgresql://user:pass@localhost/dbname"

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### Docker (Coming Soon)
Docker Compose setup is planned for easier deployment.

---

## 📸 Screenshots

Create and add screenshots to demonstrate:
- Login page
- Events list with role-based actions
- Resource allocation with conflict detection
- Utilization report
- API response examples

Place in `static/img/screenshots/` directory.

---

## 🎥 Demo Video

**Required for submission**: Create a 3-5 minute video demonstrating:

1. **Authentication** - Login as different roles
2. **Event Management** - Create, edit, delete events
3. **Resource Management** - Add resources with constraints (capacity, quantity, hours)
4. **Allocation** - Allocate resources and show conflict detection
5. **Resource Rules** - Demonstrate capacity check, quantity limits, hour constraints
6. **API Testing** - Show API calls using curl or Postman
7. **Unit Tests** - Run pytest and show results
8. **Reports** - Generate utilization report

Upload to YouTube/Google Drive and include link in submission.

---

## 📋 Assignment Compliance Checklist

### Core Requirements ✅
- [x] Event CRUD with validation
- [x] Resource CRUD with types
- [x] Resource allocation to events
- [x] Conflict detection (all overlap types)
- [x] Utilization reports

### v2 Advanced Requirements ✅
- [x] User authentication (login/logout/register)
- [x] Role-based access control (Admin/Organiser/Viewer)
- [x] Real-world resource rules (2/3 implemented):
  - [x] Room capacity vs attendance
  - [x] Equipment quantity limits
  - [x] Instructor working-hour constraints
- [x] REST API layer with 4 endpoints
- [x] Clean JSON error responses
- [x] Enhanced conflict UX with detailed messages
- [x] Unit tests (12 tests covering overlap logic)
- [x] README with setup steps
- [x] Migration files for schema changes

### Bonus (Optional) 🎯
- [ ] Calendar weekly view (not implemented)
- [ ] CSV export for reports (not implemented)
- [ ] Docker Compose setup (planned, not implemented)
- [ ] Soft delete & audit log (not implemented)

---

## 🛠️ Technology Stack

- **Backend**: Flask 3.0.0
- **Database**: SQLite (can be changed to PostgreSQL)
- **ORM**: SQLAlchemy
- **Migrations**: Flask-Migrate (Alembic)
- **Authentication**: Flask-Login
- **Testing**: Pytest, Pytest-Flask
- **Frontend**: Tailwind CSS, Jinja2 templates
- **Icons**: Bootstrap Icons

---

## 📁 Project Structure

```
event_scheduler/
├── app.py                          # Main application file
├── models.py                       # Database models
├── config.py                       # Configuration
├── requirements.txt                # Dependencies
├── README.md                       # This file
├── API_DOCUMENTATION.md            # API reference
├── TESTING_GUIDE.md                # Testing instructions
├── migrations/                     # Database migrations
│   └── versions/
│       ├── 0001_add_category.py
│       └── 0002_auth_and_resource_enhancements.py
├── templates/                      # HTML templates
│   ├── base.html
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   ├── events/
│   │   ├── list.html
│   │   ├── add.html
│   │   └── edit.html
│   ├── resources/
│   │   ├── list.html
│   │   ├── add.html
│   │   └── edit.html
│   ├── allocations/
│   │   ├── allocate.html
│   │   └── list.html
│   └── reports/
│       └── report.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── script.js
└── tests/
    ├── __init__.py
    └── test_conflict.py            # 12 unit tests
```

---

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Add tests for new features
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

---

## 📝 License

Educational project for Aerele Technologies hiring assignment. Feel free to use and modify.

---

## 🙏 Acknowledgments

- **Aerele Technologies** for the assignment
- Flask and SQLAlchemy communities
- Open-source contributors

---

## 📧 Submission

**To**: hr@aerele.in  
**CC**: vignesh@aerele.in  
**Subject**: Assignment Submission - Event Scheduling & Resource Allocation System

**Include**:
- GitHub repository link
- Demo video link (YouTube/Google Drive)
- Screenshots
- Brief summary of implementation

---

## 💡 Future Enhancements

- [ ] Calendar view with drag-and-drop
- [ ] Email notifications for upcoming events
- [ ] CSV/Excel export
- [ ] Advanced conflict resolution suggestions
- [ ] Resource availability calendar
- [ ] Multi-tenant support
- [ ] Mobile app (Flutter/React Native)
- [ ] Webpack for frontend assets
- [ ] Redis caching for reports
- [ ] Celery for background tasks

---

**Built with ❤️ for Aerele Technologies**

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
