from flask import Flask, render_template, request, redirect, url_for, flash
from config import Config
from models import db, Event, Resource, EventResourceAllocation
from datetime import datetime, timedelta

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Try to initialize migrations if Flask-Migrate is installed; otherwise continue without it
try:
    from flask_migrate import Migrate
    migrate = Migrate(app, db)
except Exception:
    migrate = None
    app.logger = app.logger or None
    # Use print if logger not yet configured
    try:
        app.logger.warning("Flask-Migrate is not installed; migrations disabled. Install it with 'pip install Flask-Migrate' to enable migrations.")
    except Exception:
        print("Flask-Migrate is not installed; migrations disabled. Install it with 'pip install Flask-Migrate' to enable migrations.")

def check_resource_conflict(resource_id, start_time, end_time, exclude_event_id=None):
    allocations = EventResourceAllocation.query.filter_by(resource_id=resource_id).all()
    
    conflicts = []
    for allocation in allocations:
        event = allocation.event
        
        # Skip the current event if we're editing
        if exclude_event_id and event.event_id == exclude_event_id:
            continue
        
        # Check for time overlap: event1.start < event2.end AND event2.start < event1.end
        if start_time < event.end_time and event.start_time < end_time:
            conflicts.append(event)
    
    return conflicts


@app.route('/')
def index():
    """Home page - redirect to events list"""
    return redirect(url_for('list_events'))


# ==================== EVENT ROUTES ====================

@app.route('/events')
def list_events():
    """List all events"""
    events = Event.query.order_by(Event.start_time.desc()).all()
    return render_template('events/list.html', events=events)


@app.route('/events/add', methods=['GET', 'POST'])
def add_event():
    """Add a new event"""
    if request.method == 'POST':
        title = request.form.get('title')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        description = request.form.get('description')
        
        # Validate inputs
        if not title or not start_time_str or not end_time_str:
            flash('Title, start time, and end time are required!', 'danger')
            return redirect(url_for('add_event'))
        
        try:
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date/time format!', 'danger')
            return redirect(url_for('add_event'))
        
        # Validate start_time < end_time
        if start_time >= end_time:
            flash('Start time must be before end time!', 'danger')
            return redirect(url_for('add_event'))
        
        # Create new event
        new_event = Event(
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description
        )
        
        db.session.add(new_event)
        db.session.commit()
        
        flash(f'Event "{title}" added successfully!', 'success')
        return redirect(url_for('list_events'))
    
    return render_template('events/add.html')


@app.route('/events/edit/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    """Edit an existing event"""
    event = Event.query.get_or_404(event_id)
    
    if request.method == 'POST':
        title = request.form.get('title')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        description = request.form.get('description')
        
        if not title or not start_time_str or not end_time_str:
            flash('Title, start time, and end time are required!', 'danger')
            return redirect(url_for('edit_event', event_id=event_id))
        
        try:
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date/time format!', 'danger')
            return redirect(url_for('edit_event', event_id=event_id))
        
        if start_time >= end_time:
            flash('Start time must be before end time!', 'danger')
            return redirect(url_for('edit_event', event_id=event_id))
        
        # Check for resource conflicts if time changed
        if start_time != event.start_time or end_time != event.end_time:
            for allocation in event.allocations:
                conflicts = check_resource_conflict(
                    allocation.resource_id, 
                    start_time, 
                    end_time, 
                    exclude_event_id=event_id
                )
                if conflicts:
                    conflict_titles = ', '.join([e.title for e in conflicts])
                    flash(f'Resource conflict detected for "{allocation.resource.resource_name}" '
                          f'with events: {conflict_titles}', 'danger')
                    return redirect(url_for('edit_event', event_id=event_id))
        
        # Update event
        event.title = title
        event.start_time = start_time
        event.end_time = end_time
        event.description = description
        
        db.session.commit()
        
        flash(f'Event "{title}" updated successfully!', 'success')
        return redirect(url_for('list_events'))
    
    return render_template('events/edit.html', event=event)


@app.route('/events/delete/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    """Delete an event"""
    event = Event.query.get_or_404(event_id)
    title = event.title
    
    db.session.delete(event)
    db.session.commit()
    
    flash(f'Event "{title}" deleted successfully!', 'success')
    return redirect(url_for('list_events'))


# ==================== RESOURCE ROUTES ====================

@app.route('/resources')
def list_resources():
    """List all resources (support optional category filtering)"""
    selected_category = request.args.get('category')

    # Distinct list of categories to populate filter UI
    raw_categories = db.session.query(Resource.category).distinct().order_by(Resource.category).all()
    categories = [c[0] for c in raw_categories if c[0]]

    if selected_category:
        resources = Resource.query.filter_by(category=selected_category).order_by(Resource.resource_name).all()
    else:
        resources = Resource.query.order_by(Resource.resource_name).all()

    return render_template('resources/list.html', resources=resources, categories=categories, selected_category=selected_category)


@app.route('/resources/add', methods=['GET', 'POST'])
def add_resource():
    """Add a new resource"""
    if request.method == 'POST':
        resource_name = request.form.get('resource_name')
        resource_type = request.form.get('resource_type')
        category = request.form.get('category')
        
        if not resource_name or not resource_type:
            flash('Resource name and type are required!', 'danger')
            return redirect(url_for('add_resource'))
        
        new_resource = Resource(
            resource_name=resource_name,
            resource_type=resource_type,
            category=category
        )
        
        db.session.add(new_resource)
        db.session.commit()
        
        flash(f'Resource "{resource_name}" added successfully!', 'success')
        return redirect(url_for('list_resources'))
    
    return render_template('resources/add.html')

@app.route('/resources/edit/<int:resource_id>', methods=['GET', 'POST'])
def edit_resource(resource_id):
    """Edit an existing resource"""
    resource = Resource.query.get_or_404(resource_id)
    
    if request.method == 'POST':
        resource_name = request.form.get('resource_name')
        resource_type = request.form.get('resource_type')
        category = request.form.get('category')
        
        if not resource_name or not resource_type:
            flash('Resource name and type are required!', 'danger')
            return redirect(url_for('edit_resource', resource_id=resource_id))
        
        resource.resource_name = resource_name
        resource.resource_type = resource_type
        resource.category = category
        
        db.session.commit()
        
        flash(f'Resource "{resource_name}" updated successfully!', 'success')
        return redirect(url_for('list_resources'))
    
    return render_template('resources/edit.html', resource=resource)

@app.route('/resources/delete/<int:resource_id>', methods=['POST'])
def delete_resource(resource_id):
    """Delete a resource"""
    resource = Resource.query.get_or_404(resource_id)
    resource_name = resource.resource_name
    
    db.session.delete(resource)
    db.session.commit()
    
    flash(f'Resource "{resource_name}" deleted successfully!', 'success')
    return redirect(url_for('list_resources'))


# ==================== ALLOCATION ROUTES ====================

@app.route('/allocate', methods=['GET', 'POST'])
def allocate_resource():
    """Allocate resources to events"""
    if request.method == 'POST':
        event_id = request.form.get('event_id')
        resource_ids = request.form.getlist('resource_ids')
        
        if not event_id or not resource_ids:
            flash('Please select an event and at least one resource!', 'danger')
            return redirect(url_for('allocate_resource'))
        
        event = Event.query.get_or_404(event_id)
        
        # Check for conflicts
        conflicts_found = False
        for resource_id in resource_ids:
            conflicts = check_resource_conflict(
                int(resource_id),
                event.start_time,
                event.end_time,
                exclude_event_id=event.event_id
            )
            
            if conflicts:
                resource = Resource.query.get(resource_id)
                conflict_titles = ', '.join([e.title for e in conflicts])
                flash(f'Resource conflict detected for "{resource.resource_name}" '
                      f'with events: {conflict_titles}', 'danger')
                conflicts_found = True
        
        if conflicts_found:
            return redirect(url_for('allocate_resource'))
        
        # Remove existing allocations for this event
        EventResourceAllocation.query.filter_by(event_id=event_id).delete()
        
        # Add new allocations
        for resource_id in resource_ids:
            allocation = EventResourceAllocation(
                event_id=event_id,
                resource_id=int(resource_id)
            )
            db.session.add(allocation)
        
        db.session.commit()
        
        flash(f'Resources allocated to event "{event.title}" successfully!', 'success')
        return redirect(url_for('list_allocations'))
    
    events = Event.query.order_by(Event.start_time.desc()).all()
    resources = Resource.query.order_by(Resource.resource_name).all()
    return render_template('allocations/allocate.html', events=events, resources=resources)


@app.route('/allocations')
def list_allocations():
    """List all resource allocations"""
    allocations = EventResourceAllocation.query.order_by(
        EventResourceAllocation.allocated_at.desc()
    ).all()
    return render_template('allocations/list.html', allocations=allocations)


@app.route('/allocations/delete/<int:allocation_id>', methods=['POST'])
def delete_allocation(allocation_id):
    """Delete an allocation"""
    allocation = EventResourceAllocation.query.get_or_404(allocation_id)
    
    db.session.delete(allocation)
    db.session.commit()
    
    flash('Allocation removed successfully!', 'success')
    return redirect(url_for('list_allocations'))


# ==================== REPORT ROUTES ====================

@app.route('/report', methods=['GET', 'POST'])
def resource_report():
    """Generate resource utilization report"""
    report_data = None
    start_date = None
    end_date = None
    
    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        if not start_date_str or not end_date_str:
            flash('Please provide both start and end dates!', 'danger')
            return redirect(url_for('resource_report'))
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            # Set end_date to end of day
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            flash('Invalid date format!', 'danger')
            return redirect(url_for('resource_report'))
        
        if start_date > end_date:
            flash('Start date must be before end date!', 'danger')
            return redirect(url_for('resource_report'))
        
        # Generate report
        resources = Resource.query.all()
        report_data = []
        now = datetime.now()
        
        for resource in resources:
            total_hours = 0
            upcoming_bookings = []
            
            for allocation in resource.allocations:
                event = allocation.event
                
                # Check if event is within date range
                if event.start_time <= end_date and event.end_time >= start_date:
                    # Calculate overlapping hours
                    overlap_start = max(event.start_time, start_date)
                    overlap_end = min(event.end_time, end_date)
                    
                    if overlap_start < overlap_end:
                        delta = overlap_end - overlap_start
                        hours = delta.total_seconds() / 3600
                        total_hours += hours
                
                # Check for upcoming bookings
                if event.start_time > now:
                    upcoming_bookings.append(event)
            
            report_data.append({
                'resource': resource,
                'total_hours': round(total_hours, 2),
                'upcoming_bookings': sorted(upcoming_bookings, key=lambda e: e.start_time)
            })
    
    return render_template('reports/report.html', 
                         report_data=report_data, 
                         start_date=start_date, 
                         end_date=end_date)


# ==================== SEED DATA ROUTE ====================

@app.route('/seed')
def seed_data():
    """Seed the database with sample data"""
    
    # Clear existing data
    EventResourceAllocation.query.delete()
    Event.query.delete()
    Resource.query.delete()
    
    # Add sample resources
    resources = [
        Resource(resource_name='Conference Room A', resource_type='Room', category='Venue'),
        Resource(resource_name='Conference Room B', resource_type='Room', category='Venue'),
        Resource(resource_name='Projector 1', resource_type='Equipment', category='Equipment'),
        Resource(resource_name='Dr. Smith', resource_type='Instructor', category='Person'),
        Resource(resource_name='Lab Computer 1', resource_type='Equipment', category='Equipment'),
    ]
    
    for resource in resources:
        db.session.add(resource)
    
    db.session.commit()
    
    # Add sample events
    now = datetime.now()
    events = [
        Event(
            title='Python Workshop',
            start_time=now + timedelta(days=1, hours=10),
            end_time=now + timedelta(days=1, hours=12),
            description='Introduction to Python programming'
        ),
        Event(
            title='Team Meeting',
            start_time=now + timedelta(days=1, hours=14),
            end_time=now + timedelta(days=1, hours=15),
            description='Weekly team sync-up'
        ),
        Event(
            title='Web Development Course',
            start_time=now + timedelta(days=2, hours=9),
            end_time=now + timedelta(days=2, hours=11),
            description='HTML, CSS, and JavaScript basics'
        ),
        Event(
            title='Project Presentation',
            start_time=now + timedelta(days=3, hours=13),
            end_time=now + timedelta(days=3, hours=15),
            description='Final project presentations'
        ),
    ]
    
    for event in events:
        db.session.add(event)
    
    db.session.commit()
    
    # Add sample allocations
    allocations = [
        EventResourceAllocation(event_id=1, resource_id=1),  # Python Workshop - Conference Room A
        EventResourceAllocation(event_id=1, resource_id=3),  # Python Workshop - Projector 1
        EventResourceAllocation(event_id=2, resource_id=2),  # Team Meeting - Conference Room B
        EventResourceAllocation(event_id=3, resource_id=1),  # Web Dev Course - Conference Room A
        EventResourceAllocation(event_id=3, resource_id=4),  # Web Dev Course - Dr. Smith
        EventResourceAllocation(event_id=4, resource_id=1),  # Presentation - Conference Room A
        EventResourceAllocation(event_id=4, resource_id=3),  # Presentation - Projector 1
    ]
    
    for allocation in allocations:
        db.session.add(allocation)
    
    db.session.commit()
    
    flash('Sample data has been seeded successfully!', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
