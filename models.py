from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    """User model - simple role-based access"""
    
    __tablename__ = 'users'
    
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='viewer')  # admin, organiser, viewer
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship to events
    events = db.relationship('Event', backref='creator', lazy=True)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if password matches"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class Event(db.Model):
    """Event model for storing event information"""
    
    __tablename__ = 'events'
    
    event_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text)
    timezone = db.Column(db.String(50), default='Asia/Kolkata')
    expected_attendees = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to allocated resources
    allocations = db.relationship('EventResourceAllocation', backref='event', 
                                 lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Event {self.title}>'
    
    @property
    def resources(self):
        """Return list of allocated resources"""
        return [allocation.resource for allocation in self.allocations]
    
    def duration_hours(self):
        """Calculate event duration in hours"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds() / 3600
        return 0


class Resource(db.Model):
    """Resource model for storing resource information"""
    
    __tablename__ = 'resources'
    
    resource_id = db.Column(db.Integer, primary_key=True)
    resource_name = db.Column(db.String(200), nullable=False)
    resource_type = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100), nullable=True)  # Venue, Person, Equipment
    capacity = db.Column(db.Integer, nullable=True)  # For venues - max attendees
    quantity = db.Column(db.Integer, default=1)  # For equipment - available units
    max_hours_per_day = db.Column(db.Float, nullable=True)  # For instructors - working hour limits
    
    # Relationship to allocations
    allocations = db.relationship('EventResourceAllocation', backref='resource', 
                                 lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Resource {self.resource_name} ({self.category or 'Unknown'})>"


class EventResourceAllocation(db.Model):
    """Allocation model linking events and resources"""
    
    __tablename__ = 'event_resource_allocations'
    
    allocation_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.event_id'), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resources.resource_id'), nullable=False)
    reserved_quantity = db.Column(db.Integer, default=1)  # How many units reserved
    allocated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Index for performance
    __table_args__ = (
        db.Index('idx_event_resource', 'event_id', 'resource_id'),
    )
    
    def __repr__(self):
        return f'<Allocation Event:{self.event_id} Resource:{self.resource_id} Qty:{self.reserved_quantity}>'
