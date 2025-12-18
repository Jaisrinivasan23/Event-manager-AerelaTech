from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Event(db.Model):
    """Event model for storing event information"""
    
    __tablename__ = 'events'
    
    event_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text)
    
    # Relationship to allocated resources through EventResourceAllocation
    allocations = db.relationship('EventResourceAllocation', backref='event', 
                                 lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Event {self.title}>'
    
    @property
    def resources(self):
        """Return list of allocated resources for this event"""
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
    category = db.Column(db.String(100), nullable=True)  # e.g., Venue, Person, Equipment
    
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
    allocated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Allocation Event:{self.event_id} Resource:{self.resource_id}>'
