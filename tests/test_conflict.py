"""
Unit tests for conflict detection and resource validation logic
Tests cover overlap scenarios, boundary conditions, and resource rules
"""

import pytest
from datetime import datetime, timedelta
from app import app, db
from models import Event, Resource, EventResourceAllocation, User


@pytest.fixture
def client():
    """Create a test client for the app"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def setup_data(client):
    """Setup test data before each test"""
    with app.app_context():
        # Create test user
        user = User(username='testuser', email='test@example.com', role='admin')
        user.set_password('test123')
        db.session.add(user)
        
        # Create test resources
        room = Resource(
            resource_name='Test Room',
            resource_type='Room',
            category='Venue',
            capacity=50,
            quantity=1
        )
        projector = Resource(
            resource_name='Test Projector',
            resource_type='Projector',
            category='Equipment',
            quantity=2
        )
        instructor = Resource(
            resource_name='Test Instructor',
            resource_type='Instructor',
            category='Person',
            max_hours_per_day=8.0
        )
        
        db.session.add(room)
        db.session.add(projector)
        db.session.add(instructor)
        db.session.commit()
        
        # Return IDs for use in tests
        return {
            'user_id': user.user_id,
            'room_id': room.resource_id,
            'projector_id': projector.resource_id,
            'instructor_id': instructor.resource_id
        }


# ==================== OVERLAP DETECTION TESTS ====================

def test_partial_overlap_start_before_end_during(client, setup_data):
    """Test conflict when Event A starts before Event B and ends during Event B"""
    with app.app_context():
        from app import check_resource_conflict
        
        # Event A: 10:00 - 12:00
        event_a = Event(
            title='Event A',
            start_time=datetime(2026, 3, 15, 10, 0),
            end_time=datetime(2026, 3, 15, 12, 0),
            created_by=setup_data['user_id']
        )
        db.session.add(event_a)
        db.session.commit()
        
        allocation = EventResourceAllocation(
            event_id=event_a.event_id,
            resource_id=setup_data['room_id']
        )
        db.session.add(allocation)
        db.session.commit()
        
        # Event B: 11:00 - 13:00 (overlaps with Event A from 11:00-12:00)
        conflicts = check_resource_conflict(
            setup_data['room_id'],
            datetime(2026, 3, 15, 11, 0),
            datetime(2026, 3, 15, 13, 0)
        )
        
        assert len(conflicts) > 0, "Should detect partial overlap"
        assert conflicts[0]['event'].title == 'Event A'


def test_partial_overlap_start_during_end_after(client, setup_data):
    """Test conflict when Event A starts during Event B and ends after Event B"""
    with app.app_context():
        from app import check_resource_conflict
        
        # Event A: 10:00 - 12:00
        event_a = Event(
            title='Event A',
            start_time=datetime(2026, 3, 15, 10, 0),
            end_time=datetime(2026, 3, 15, 12, 0),
            created_by=setup_data['user_id']
        )
        db.session.add(event_a)
        db.session.commit()
        
        allocation = EventResourceAllocation(
            event_id=event_a.event_id,
            resource_id=setup_data['room_id']
        )
        db.session.add(allocation)
        db.session.commit()
        
        # Event B: 09:00 - 11:00 (overlaps with Event A from 10:00-11:00)
        conflicts = check_resource_conflict(
            setup_data['room_id'],
            datetime(2026, 3, 15, 9, 0),
            datetime(2026, 3, 15, 11, 0)
        )
        
        assert len(conflicts) > 0, "Should detect partial overlap"


def test_full_overlap_nested_event(client, setup_data):
    """Test conflict when Event A is completely contained within Event B"""
    with app.app_context():
        from app import check_resource_conflict
        
        # Event A: 10:00 - 14:00 (outer event)
        event_a = Event(
            title='Event A',
            start_time=datetime(2026, 3, 15, 10, 0),
            end_time=datetime(2026, 3, 15, 14, 0),
            created_by=setup_data['user_id']
        )
        db.session.add(event_a)
        db.session.commit()
        
        allocation = EventResourceAllocation(
            event_id=event_a.event_id,
            resource_id=setup_data['room_id']
        )
        db.session.add(allocation)
        db.session.commit()
        
        # Event B: 11:00 - 12:00 (completely inside Event A)
        conflicts = check_resource_conflict(
            setup_data['room_id'],
            datetime(2026, 3, 15, 11, 0),
            datetime(2026, 3, 15, 12, 0)
        )
        
        assert len(conflicts) > 0, "Should detect nested overlap"


def test_full_overlap_containing_event(client, setup_data):
    """Test conflict when Event B completely contains Event A"""
    with app.app_context():
        from app import check_resource_conflict
        
        # Event A: 11:00 - 12:00 (inner event)
        event_a = Event(
            title='Event A',
            start_time=datetime(2026, 3, 15, 11, 0),
            end_time=datetime(2026, 3, 15, 12, 0),
            created_by=setup_data['user_id']
        )
        db.session.add(event_a)
        db.session.commit()
        
        allocation = EventResourceAllocation(
            event_id=event_a.event_id,
            resource_id=setup_data['room_id']
        )
        db.session.add(allocation)
        db.session.commit()
        
        # Event B: 10:00 - 14:00 (completely contains Event A)
        conflicts = check_resource_conflict(
            setup_data['room_id'],
            datetime(2026, 3, 15, 10, 0),
            datetime(2026, 3, 15, 14, 0)
        )
        
        assert len(conflicts) > 0, "Should detect containing overlap"


def test_boundary_exact_same_time(client, setup_data):
    """Test conflict when events have exact same start and end times"""
    with app.app_context():
        from app import check_resource_conflict
        
        # Event A: 10:00 - 12:00
        event_a = Event(
            title='Event A',
            start_time=datetime(2026, 3, 15, 10, 0),
            end_time=datetime(2026, 3, 15, 12, 0),
            created_by=setup_data['user_id']
        )
        db.session.add(event_a)
        db.session.commit()
        
        allocation = EventResourceAllocation(
            event_id=event_a.event_id,
            resource_id=setup_data['room_id']
        )
        db.session.add(allocation)
        db.session.commit()
        
        # Event B: 10:00 - 12:00 (exactly same time)
        conflicts = check_resource_conflict(
            setup_data['room_id'],
            datetime(2026, 3, 15, 10, 0),
            datetime(2026, 3, 15, 12, 0)
        )
        
        assert len(conflicts) > 0, "Should detect exact time overlap"


def test_boundary_adjacent_events_no_conflict(client, setup_data):
    """Test NO conflict when events are adjacent (one ends when other starts)"""
    with app.app_context():
        from app import check_resource_conflict
        
        # Event A: 10:00 - 12:00
        event_a = Event(
            title='Event A',
            start_time=datetime(2026, 3, 15, 10, 0),
            end_time=datetime(2026, 3, 15, 12, 0),
            created_by=setup_data['user_id']
        )
        db.session.add(event_a)
        db.session.commit()
        
        allocation = EventResourceAllocation(
            event_id=event_a.event_id,
            resource_id=setup_data['room_id']
        )
        db.session.add(allocation)
        db.session.commit()
        
        # Event B: 12:00 - 14:00 (starts exactly when A ends)
        conflicts = check_resource_conflict(
            setup_data['room_id'],
            datetime(2026, 3, 15, 12, 0),
            datetime(2026, 3, 15, 14, 0)
        )
        
        assert len(conflicts) == 0, "Should NOT detect conflict for adjacent events"


def test_no_overlap_completely_separate(client, setup_data):
    """Test NO conflict when events are completely separate in time"""
    with app.app_context():
        from app import check_resource_conflict
        
        # Event A: 10:00 - 12:00
        event_a = Event(
            title='Event A',
            start_time=datetime(2026, 3, 15, 10, 0),
            end_time=datetime(2026, 3, 15, 12, 0),
            created_by=setup_data['user_id']
        )
        db.session.add(event_a)
        db.session.commit()
        
        allocation = EventResourceAllocation(
            event_id=event_a.event_id,
            resource_id=setup_data['room_id']
        )
        db.session.add(allocation)
        db.session.commit()
        
        # Event B: 14:00 - 16:00 (completely separate)
        conflicts = check_resource_conflict(
            setup_data['room_id'],
            datetime(2026, 3, 15, 14, 0),
            datetime(2026, 3, 15, 16, 0)
        )
        
        assert len(conflicts) == 0, "Should NOT detect conflict for separate events"


# ==================== EQUIPMENT QUANTITY TESTS ====================

def test_equipment_quantity_within_limit(client, setup_data):
    """Test NO conflict when equipment quantity is within available limit"""
    with app.app_context():
        from app import check_resource_conflict
        
        # Event A using 1 projector (total available: 2)
        event_a = Event(
            title='Event A',
            start_time=datetime(2026, 3, 15, 10, 0),
            end_time=datetime(2026, 3, 15, 12, 0),
            created_by=setup_data['user_id']
        )
        db.session.add(event_a)
        db.session.commit()
        
        allocation = EventResourceAllocation(
            event_id=event_a.event_id,
            resource_id=setup_data['projector_id'],
            reserved_quantity=1
        )
        db.session.add(allocation)
        db.session.commit()
        
        # Event B wants 1 more projector (1 + 1 = 2, within limit)
        conflicts = check_resource_conflict(
            setup_data['projector_id'],
            datetime(2026, 3, 15, 10, 0),
            datetime(2026, 3, 15, 12, 0),
            requested_quantity=1
        )
        
        assert len(conflicts) == 0, "Should NOT conflict when total quantity within limit"


def test_equipment_quantity_exceeds_limit(client, setup_data):
    """Test conflict when equipment quantity exceeds available limit"""
    with app.app_context():
        from app import check_resource_conflict
        
        # Event A using 2 projectors (total available: 2)
        event_a = Event(
            title='Event A',
            start_time=datetime(2026, 3, 15, 10, 0),
            end_time=datetime(2026, 3, 15, 12, 0),
            created_by=setup_data['user_id']
        )
        db.session.add(event_a)
        db.session.commit()
        
        allocation = EventResourceAllocation(
            event_id=event_a.event_id,
            resource_id=setup_data['projector_id'],
            reserved_quantity=2
        )
        db.session.add(allocation)
        db.session.commit()
        
        # Event B wants 1 more projector (2 + 1 = 3, exceeds limit of 2)
        conflicts = check_resource_conflict(
            setup_data['projector_id'],
            datetime(2026, 3, 15, 10, 0),
            datetime(2026, 3, 15, 12, 0),
            requested_quantity=1
        )
        
        assert len(conflicts) > 0, "Should detect conflict when quantity exceeds limit"


# ==================== RESOURCE RULE TESTS ====================

def test_room_capacity_check(client, setup_data):
    """Test room capacity validation"""
    with app.app_context():
        from app import check_room_capacity
        
        # Room capacity is 50
        # Test with 40 attendees (should pass)
        valid, msg = check_room_capacity(setup_data['room_id'], 40)
        assert valid is True, "Should allow 40 attendees in 50-capacity room"
        
        # Test with 60 attendees (should fail)
        valid, msg = check_room_capacity(setup_data['room_id'], 60)
        assert valid is False, "Should reject 60 attendees in 50-capacity room"
        assert msg is not None, "Should provide error message"


def test_instructor_daily_hours_limit(client, setup_data):
    """Test instructor working hour limits"""
    with app.app_context():
        from app import check_instructor_hours
        
        # Instructor max hours: 8.0 per day
        # Create an event that uses 4 hours
        event_a = Event(
            title='Event A',
            start_time=datetime(2026, 3, 15, 9, 0),
            end_time=datetime(2026, 3, 15, 13, 0),  # 4 hours
            created_by=setup_data['user_id']
        )
        db.session.add(event_a)
        db.session.commit()
        
        allocation = EventResourceAllocation(
            event_id=event_a.event_id,
            resource_id=setup_data['instructor_id']
        )
        db.session.add(allocation)
        db.session.commit()
        
        # Try to add another 3-hour event (total 7 hours, should pass)
        valid, msg = check_instructor_hours(
            setup_data['instructor_id'],
            datetime(2026, 3, 15, 14, 0),
            datetime(2026, 3, 15, 17, 0)
        )
        assert valid is True, "Should allow 7 total hours (within 8-hour limit)"
        
        # Try to add another 5-hour event (total 9 hours, should fail)
        valid, msg = check_instructor_hours(
            setup_data['instructor_id'],
            datetime(2026, 3, 15, 14, 0),
            datetime(2026, 3, 15, 19, 0)
        )
        assert valid is False, "Should reject when total exceeds 8-hour limit"
        assert msg is not None, "Should provide error message"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
