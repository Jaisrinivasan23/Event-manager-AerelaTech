from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from config import Config
from models import db, Event, Resource, EventResourceAllocation, User
from datetime import datetime, timedelta
import csv
from io import StringIO

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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


# ==================== ROLE-BASED ACCESS CONTROL DECORATORS ====================

def role_required(*roles):
    """Decorator to require specific roles for a route"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('login'))
            if current_user.role not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Decorator to require admin role"""
    return role_required('admin')(f)


def organiser_or_admin_required(f):
    """Decorator to require organiser or admin role"""
    return role_required('admin', 'organiser')(f)


# ==================== AUTHENTICATION ROUTES ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please provide both username and password.', 'danger')
            return redirect(url_for('login'))
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
    
    return render_template('auth/login.html')


@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('register'))
        
        # Create new user with viewer role by default
        new_user = User(username=username, email=email, role='viewer')
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')


# ==================== HELPER FUNCTIONS ====================

def check_resource_conflict(resource_id, start_time, end_time, exclude_event_id=None, requested_quantity=1):
    """Check if a resource has conflicts in the given time range"""
    allocations = EventResourceAllocation.query.filter_by(resource_id=resource_id).all()
    resource = Resource.query.get(resource_id)
    
    conflicts = []
    for allocation in allocations:
        event = allocation.event
        
        # Skip the current event if we're editing
        if exclude_event_id and event.event_id == exclude_event_id:
            continue
        
        # Check for time overlap: event1.start < event2.end AND event2.start < event1.end
        if start_time < event.end_time and event.start_time < end_time:
            conflicts.append({
                'event': event,
                'allocation': allocation,
                'overlap_start': max(start_time, event.start_time),
                'overlap_end': min(end_time, event.end_time)
            })
    
    # For equipment, check if total quantity exceeds available
    if resource and resource.category == 'Equipment' and conflicts:
        # If no quantity is set, treat as unlimited or return conflict
        if resource.quantity is None or resource.quantity == 0:
            return conflicts  # No quantity tracking, treat as traditional conflict
        
        total_allocated = sum(c['allocation'].reserved_quantity for c in conflicts)
        if total_allocated + requested_quantity > resource.quantity:
            return conflicts
        else:
            return []  # Quantity available, no conflict
    
    return conflicts


def check_room_capacity(resource_id, expected_attendees):
    """Check if room capacity is sufficient"""
    resource = Resource.query.get(resource_id)
    if resource.category == 'Venue' and resource.capacity:
        if expected_attendees > resource.capacity:
            return False, f"Room capacity ({resource.capacity}) is less than expected attendees ({expected_attendees})"
    return True, None


def check_instructor_hours(resource_id, start_time, end_time, exclude_event_id=None):
    """Check if instructor exceeds daily working hour limits"""
    resource = Resource.query.get(resource_id)
    if resource.category != 'Person' or not resource.max_hours_per_day:
        return True, None
    
    # Get all events for this instructor on the same day
    day_start = start_time.replace(hour=0, minute=0, second=0)
    day_end = start_time.replace(hour=23, minute=59, second=59)
    
    allocations = EventResourceAllocation.query.filter_by(resource_id=resource_id).all()
    total_hours = 0
    
    for allocation in allocations:
        event = allocation.event
        if exclude_event_id and event.event_id == exclude_event_id:
            continue
        
        # Check if event is on the same day
        if event.start_time.date() == start_time.date():
            total_hours += event.duration_hours()
    
    # Add current event duration
    event_duration = (end_time - start_time).total_seconds() / 3600
    total_hours += event_duration
    
    if total_hours > resource.max_hours_per_day:
        return False, f"Instructor would exceed daily limit ({resource.max_hours_per_day}h). Total: {total_hours:.1f}h"
    
    return True, None


def validate_resource_allocation(resource_id, event_id, requested_quantity=1):
    """Validate all resource rules for an allocation"""
    resource = Resource.query.get(resource_id)
    event = Event.query.get(event_id)
    errors = []
    
    # Validate requested quantity for equipment
    if resource.category == 'Equipment' and resource.quantity:
        if requested_quantity > resource.quantity:
            errors.append(f"Requested quantity ({requested_quantity}) exceeds available quantity ({resource.quantity}) for {resource.resource_name}")
        elif requested_quantity < 1:
            errors.append(f"Quantity must be at least 1")
    
    # Check room capacity
    if resource.category == 'Venue' and event.expected_attendees > 0:
        valid, msg = check_room_capacity(resource_id, event.expected_attendees)
        if not valid:
            errors.append(msg)
    
    # Check instructor hours
    if resource.category == 'Person':
        valid, msg = check_instructor_hours(resource_id, event.start_time, event.end_time, event.event_id)
        if not valid:
            errors.append(msg)
    
    # Check time conflicts
    conflicts = check_resource_conflict(resource_id, event.start_time, event.end_time, event.event_id, requested_quantity)
    if conflicts:
        conflict_titles = ', '.join([c['event'].title for c in conflicts])
        errors.append(f"Time conflict with: {conflict_titles}")
    
    return len(errors) == 0, errors



@app.route('/')
def index():
    """Home page - redirect to events list"""
    return redirect(url_for('list_events'))


# ==================== EVENT ROUTES ====================

@app.route('/events')
@login_required
def list_events():
    """List all events"""
    events = Event.query.order_by(Event.start_time.desc()).all()
    return render_template('events/list.html', events=events)


@app.route('/events/add', methods=['GET', 'POST'])
@organiser_or_admin_required
def add_event():
    """Add a new event"""
    if request.method == 'POST':
        title = request.form.get('title')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        description = request.form.get('description')
        expected_attendees = request.form.get('expected_attendees', 0, type=int)
        timezone = 'Asia/Kolkata'  # Fixed to IST
        resource_ids = request.form.getlist('resource_ids')
        
        # Validate inputs
        if not title or not start_time_str or not end_time_str:
            flash('Title, start time, and end time are required!', 'danger')
            resources = Resource.query.order_by(Resource.resource_name).all()
            return render_template('events/add.html', resources=resources)
        
        try:
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date/time format!', 'danger')
            resources = Resource.query.order_by(Resource.resource_name).all()
            return render_template('events/add.html', resources=resources)
        
        # Validate start_time < end_time
        if start_time >= end_time:
            flash('Start time must be before end time!', 'danger')
            resources = Resource.query.order_by(Resource.resource_name).all()
            return render_template('events/add.html', resources=resources)
        
        # Create new event (but don't commit yet)
        new_event = Event(
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
            expected_attendees=expected_attendees,
            timezone=timezone,
            created_by=current_user.user_id
        )
        
        db.session.add(new_event)
        db.session.flush()  # Get event_id without committing
        
        # Validate and allocate resources if selected
        if resource_ids:
            conflicts_found = False
            for resource_id in resource_ids:
                resource_id = int(resource_id)
                
                # Get quantity for equipment
                quantity_key = f'quantity_{resource_id}'
                requested_qty = request.form.get(quantity_key, 1, type=int)
                
                # Validate allocation
                valid, errors = validate_resource_allocation(resource_id, new_event.event_id, requested_qty)
                
                if not valid:
                    for error in errors:
                        flash(error, 'danger')
                    conflicts_found = True
            
            if conflicts_found:
                db.session.rollback()
                resources = Resource.query.order_by(Resource.resource_name).all()
                return render_template('events/add.html', resources=resources)
            
            # All validations passed, create allocations
            for resource_id in resource_ids:
                resource_id = int(resource_id)
                quantity_key = f'quantity_{resource_id}'
                requested_qty = request.form.get(quantity_key, 1, type=int)
                
                allocation = EventResourceAllocation(
                    event_id=new_event.event_id,
                    resource_id=resource_id,
                    reserved_quantity=requested_qty
                )
                db.session.add(allocation)
        
        db.session.commit()
        
        if resource_ids:
            flash(f'Event "{title}" created and {len(resource_ids)} resource(s) allocated successfully!', 'success')
        else:
            flash(f'Event "{title}" created successfully!', 'success')
        return redirect(url_for('list_events'))
    
    # GET request - show form with all resources (filtering is done by JavaScript)
    all_resources = Resource.query.order_by(Resource.category, Resource.resource_name).all()
    
    return render_template('events/add.html', resources=all_resources)


@app.route('/events/edit/<int:event_id>', methods=['GET', 'POST'])
@organiser_or_admin_required
def edit_event(event_id):
    """Edit an existing event"""
    event = Event.query.get_or_404(event_id)
    
    if request.method == 'POST':
        title = request.form.get('title')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        description = request.form.get('description')
        timezone = 'Asia/Kolkata'  # Fixed to IST
        expected_attendees_str = request.form.get('expected_attendees')
        resource_ids = request.form.getlist('resource_ids')  # Get selected resources
        
        if not title or not start_time_str or not end_time_str:
            flash('Title, start time, and end time are required!', 'danger')
            return redirect(url_for('edit_event', event_id=event_id))
        
        try:
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            expected_attendees = int(expected_attendees_str) if expected_attendees_str else None
        except ValueError:
            flash('Invalid date/time or attendees format!', 'danger')
            return redirect(url_for('edit_event', event_id=event_id))
        
        if start_time >= end_time:
            flash('Start time must be before end time!', 'danger')
            return redirect(url_for('edit_event', event_id=event_id))
        
        if expected_attendees and expected_attendees < 1:
            flash('Expected attendees must be at least 1!', 'danger')
            return redirect(url_for('edit_event', event_id=event_id))
        
        # Convert resource_ids to integers
        resource_ids = [int(rid) for rid in resource_ids] if resource_ids else []
        
        # Get current allocations
        current_allocations = {alloc.resource_id: alloc for alloc in event.allocations}
        current_resource_ids = set(current_allocations.keys())
        new_resource_ids = set(resource_ids)
        
        # Validate new resource allocations
        for resource_id in resource_ids:
            resource = Resource.query.get(resource_id)
            if not resource:
                flash(f'Invalid resource selected!', 'danger')
                return redirect(url_for('edit_event', event_id=event_id))
            
            # Get quantity for equipment
            quantity = 1
            if resource.category == 'Equipment':
                quantity_str = request.form.get(f'quantity_{resource_id}')
                try:
                    quantity = int(quantity_str) if quantity_str else 1
                    if quantity < 1:
                        flash(f'Quantity for "{resource.resource_name}" must be at least 1!', 'danger')
                        return redirect(url_for('edit_event', event_id=event_id))
                except ValueError:
                    flash(f'Invalid quantity for "{resource.resource_name}"!', 'danger')
                    return redirect(url_for('edit_event', event_id=event_id))
            
            # Check resource conflicts (only if time changed or resource is new)
            if (start_time != event.start_time or end_time != event.end_time or 
                resource_id not in current_resource_ids):
                conflicts = check_resource_conflict(
                    resource_id, 
                    start_time, 
                    end_time,
                    requested_quantity=quantity,
                    exclude_event_id=event_id
                )
                if conflicts:
                    conflict_titles = ', '.join([c['event'].title for c in conflicts])
                    flash(f'Resource conflict detected for "{resource.resource_name}" '
                          f'with events: {conflict_titles}', 'danger')
                    return redirect(url_for('edit_event', event_id=event_id))
            
            # Validate resource rules
            valid, errors = validate_resource_allocation(
                resource_id, event_id, quantity
            )
            if not valid:
                for error in errors:
                    flash(error, 'danger')
                return redirect(url_for('edit_event', event_id=event_id))
        
        # Update event basic fields
        event.title = title
        event.start_time = start_time
        event.end_time = end_time
        event.description = description
        event.timezone = timezone
        event.expected_attendees = expected_attendees
        
        # Update resource allocations
        # Remove allocations that are no longer selected
        resources_to_remove = current_resource_ids - new_resource_ids
        for resource_id in resources_to_remove:
            allocation = current_allocations[resource_id]
            db.session.delete(allocation)
        
        # Add or update allocations
        for resource_id in resource_ids:
            resource = Resource.query.get(resource_id)
            quantity = 1
            if resource.category == 'Equipment':
                quantity_str = request.form.get(f'quantity_{resource_id}')
                quantity = int(quantity_str) if quantity_str else 1
            
            if resource_id in current_allocations:
                # Update existing allocation quantity
                current_allocations[resource_id].reserved_quantity = quantity
            else:
                # Create new allocation
                allocation = EventResourceAllocation(
                    event_id=event.id,
                    resource_id=resource_id,
                    reserved_quantity=quantity
                )
                db.session.add(allocation)
        
        db.session.commit()
        
        flash(f'Event "{title}" updated successfully!', 'success')
        return redirect(url_for('list_events'))
    
    # GET request - prepare data for template
    resources = Resource.query.order_by(Resource.category, Resource.resource_name).all()
    allocated_resource_ids = {alloc.resource_id for alloc in event.allocations}
    allocated_quantities = {alloc.resource_id: alloc.reserved_quantity for alloc in event.allocations}
    
    return render_template('events/edit.html', 
                         event=event, 
                         resources=resources,
                         allocated_resource_ids=allocated_resource_ids,
                         allocated_quantities=allocated_quantities)



@app.route('/events/delete/<int:event_id>', methods=['POST'])
@organiser_or_admin_required
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
@login_required
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
@organiser_or_admin_required
def add_resource():
    """Add a new resource"""
    if request.method == 'POST':
        resource_name = request.form.get('resource_name')
        resource_type = request.form.get('resource_type')
        category = request.form.get('category')
        capacity = request.form.get('capacity', type=int)
        quantity = request.form.get('quantity', 1, type=int)
        max_hours_per_day = request.form.get('max_hours_per_day', type=float)
        
        if not resource_name or not resource_type:
            flash('Resource name and type are required!', 'danger')
            return redirect(url_for('add_resource'))
        
        new_resource = Resource(
            resource_name=resource_name,
            resource_type=resource_type,
            category=category,
            capacity=capacity,
            quantity=quantity if quantity else 1,
            max_hours_per_day=max_hours_per_day
        )
        
        db.session.add(new_resource)
        db.session.commit()
        
        flash(f'Resource "{resource_name}" added successfully!', 'success')
        return redirect(url_for('list_resources'))
    
    return render_template('resources/add.html')

@app.route('/resources/edit/<int:resource_id>', methods=['GET', 'POST'])
@organiser_or_admin_required
def edit_resource(resource_id):
    """Edit an existing resource"""
    resource = Resource.query.get_or_404(resource_id)
    
    if request.method == 'POST':
        resource_name = request.form.get('resource_name')
        resource_type = request.form.get('resource_type')
        category = request.form.get('category')
        capacity = request.form.get('capacity', type=int)
        quantity = request.form.get('quantity', type=int)
        max_hours_per_day = request.form.get('max_hours_per_day', type=float)
        
        if not resource_name or not resource_type:
            flash('Resource name and type are required!', 'danger')
            return redirect(url_for('edit_resource', resource_id=resource_id))
        
        resource.resource_name = resource_name
        resource.resource_type = resource_type
        resource.category = category
        resource.capacity = capacity
        resource.quantity = quantity if quantity else 1
        resource.max_hours_per_day = max_hours_per_day
        
        db.session.commit()
        
        flash(f'Resource "{resource_name}" updated successfully!', 'success')
        return redirect(url_for('list_resources'))
    
    return render_template('resources/edit.html', resource=resource)

@app.route('/resources/delete/<int:resource_id>', methods=['POST'])
@admin_required
def delete_resource(resource_id):
    """Delete a resource"""
    resource = Resource.query.get_or_404(resource_id)
    resource_name = resource.resource_name
    
    db.session.delete(resource)
    db.session.commit()
    
    flash(f'Resource "{resource_name}" deleted successfully!', 'success')
    return redirect(url_for('list_resources'))


@app.route('/resources/detail/<int:resource_id>')
@login_required
def resource_detail(resource_id):
    """View resource details including timeline and history"""
    resource = Resource.query.get_or_404(resource_id)
    
    # Get all allocations for this resource (past and future)
    allocations = EventResourceAllocation.query.filter_by(
        resource_id=resource_id
    ).order_by(EventResourceAllocation.allocated_at.desc()).all()
    
    # Separate into upcoming and past allocations
    now = datetime.now()
    upcoming_allocations = []
    past_allocations = []
    
    for alloc in allocations:
        if alloc.event.end_time >= now:
            upcoming_allocations.append(alloc)
        else:
            past_allocations.append(alloc)
    
    # Sort upcoming by start_time
    upcoming_allocations.sort(key=lambda x: x.event.start_time)
    # Past allocations by end_time descending
    past_allocations.sort(key=lambda x: x.event.end_time, reverse=True)
    
    return render_template('resources/detail.html', 
                         resource=resource,
                         upcoming_allocations=upcoming_allocations,
                         past_allocations=past_allocations,
                         now=now)


# ==================== REPORT ROUTES ====================

@app.route('/report', methods=['GET', 'POST'])
@login_required
def resource_report():
    """Generate resource utilization report with dashboard"""
    report_data = None
    events_data = None
    start_date = None
    end_date = None
    stats = None
    
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
        
        # Get all events in the date range
        events_in_range = Event.query.filter(
            Event.start_time <= end_date,
            Event.end_time >= start_date
        ).order_by(Event.start_time).all()
        
        # Generate report
        resources = Resource.query.all()
        report_data = []
        now = datetime.now()
        
        # Category statistics
        category_stats = {'Venue': 0, 'Equipment': 0, 'Person': 0, 'Other': 0}
        total_events = len(events_in_range)
        total_allocations = 0
        
        for resource in resources:
            total_hours = 0
            event_count = 0
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
                        event_count += 1
                        total_allocations += 1
                
                # Check for upcoming bookings
                if event.start_time > now:
                    upcoming_bookings.append(event)
            
            # Update category stats
            cat = resource.category if resource.category in category_stats else 'Other'
            category_stats[cat] += total_hours
            
            if total_hours > 0 or upcoming_bookings:
                report_data.append({
                    'resource': resource,
                    'total_hours': round(total_hours, 2),
                    'event_count': event_count,
                    'upcoming_bookings': sorted(upcoming_bookings, key=lambda e: e.start_time)
                })
        
        # Prepare events data for table
        events_data = []
        for event in events_in_range:
            allocated_resources = [alloc.resource.resource_name for alloc in event.allocations]
            events_data.append({
                'event': event,
                'duration': round((event.end_time - event.start_time).total_seconds() / 3600, 2),
                'resources': allocated_resources,
                'resource_count': len(allocated_resources)
            })
        
        # Calculate statistics
        stats = {
            'total_resources': len(report_data),
            'total_hours': round(sum(r['total_hours'] for r in report_data), 2),
            'total_events': total_events,
            'total_allocations': total_allocations,
            'category_stats': category_stats,
            'avg_event_duration': round(sum(e['duration'] for e in events_data) / len(events_data), 2) if events_data else 0
        }
    
    return render_template('reports/report.html', 
                         report_data=report_data,
                         events_data=events_data,
                         start_date=start_date, 
                         end_date=end_date,
                         stats=stats)


@app.route('/report/download-csv', methods=['POST'])
@login_required
def download_report_csv():
    """Download report as CSV"""
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    report_type = request.form.get('report_type', 'resources')  # 'resources' or 'events'
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        end_date = end_date.replace(hour=23, minute=59, second=59)
    except (ValueError, TypeError):
        flash('Invalid date format!', 'danger')
        return redirect(url_for('resource_report'))
    
    # Create CSV in memory
    output = StringIO()
    
    if report_type == 'resources':
        writer = csv.writer(output)
        writer.writerow(['Resource Name', 'Type', 'Category', 'Total Hours Used', 'Event Count', 'Capacity/Quantity', 'Max Hours/Day'])
        
        resources = Resource.query.all()
        for resource in resources:
            total_hours = 0
            event_count = 0
            
            for allocation in resource.allocations:
                event = allocation.event
                if event.start_time <= end_date and event.end_time >= start_date:
                    overlap_start = max(event.start_time, start_date)
                    overlap_end = min(event.end_time, end_date)
                    
                    if overlap_start < overlap_end:
                        delta = overlap_end - overlap_start
                        hours = delta.total_seconds() / 3600
                        total_hours += hours
                        event_count += 1
            
            if total_hours > 0:
                capacity_qty = resource.capacity if resource.capacity else (resource.quantity if resource.quantity else '-')
                writer.writerow([
                    resource.resource_name,
                    resource.resource_type,
                    resource.category or '-',
                    round(total_hours, 2),
                    event_count,
                    capacity_qty,
                    resource.max_hours_per_day or '-'
                ])
    
    else:  # events
        writer = csv.writer(output)
        writer.writerow(['Event Title', 'Start Time', 'End Time', 'Duration (hours)', 'Expected Attendees', 'Allocated Resources', 'Created By'])
        
        events = Event.query.filter(
            Event.start_time <= end_date,
            Event.end_time >= start_date
        ).order_by(Event.start_time).all()
        
        for event in events:
            resources = ', '.join([alloc.resource.resource_name for alloc in event.allocations])
            duration = round((event.end_time - event.start_time).total_seconds() / 3600, 2)
            created_by = event.creator.username if event.creator else '-'
            
            writer.writerow([
                event.title,
                event.start_time.strftime('%Y-%m-%d %H:%M'),
                event.end_time.strftime('%Y-%m-%d %H:%M'),
                duration,
                event.expected_attendees or '-',
                resources or '-',
                created_by
            ])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    filename = f'{report_type}_report_{start_date_str}_to_{end_date_str}.csv'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response


# ==================== REST API ENDPOINTS ====================

@app.route('/api/events', methods=['GET', 'POST'])
@login_required
def api_events():
    """REST API endpoint for events"""
    if request.method == 'GET':
        # Get events with optional date range filtering
        from_date_str = request.args.get('from')
        to_date_str = request.args.get('to')
        
        query = Event.query
        
        if from_date_str:
            try:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d')
                query = query.filter(Event.start_time >= from_date)
            except ValueError:
                return jsonify({'error': 'Invalid from date format. Use YYYY-MM-DD'}), 400
        
        if to_date_str:
            try:
                to_date = datetime.strptime(to_date_str, '%Y-%m-%d')
                to_date = to_date.replace(hour=23, minute=59, second=59)
                query = query.filter(Event.end_time <= to_date)
            except ValueError:
                return jsonify({'error': 'Invalid to date format. Use YYYY-MM-DD'}), 400
        
        events = query.order_by(Event.start_time).all()
        
        return jsonify({
            'success': True,
            'count': len(events),
            'events': [{
                'event_id': e.event_id,
                'title': e.title,
                'start_time': e.start_time.isoformat(),
                'end_time': e.end_time.isoformat(),
                'description': e.description,
                'expected_attendees': e.expected_attendees,
                'timezone': e.timezone,
                'resources': [{'resource_id': a.resource_id, 'resource_name': a.resource.resource_name} 
                             for a in e.allocations]
            } for e in events]
        }), 200
    
    elif request.method == 'POST':
        # Create new event (organiser or admin only)
        if current_user.role not in ['admin', 'organiser']:
            return jsonify({'error': 'Permission denied. Only organisers and admins can create events.'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        title = data.get('title')
        start_time_str = data.get('start_time')
        end_time_str = data.get('end_time')
        description = data.get('description', '')
        expected_attendees = data.get('expected_attendees', 0)
        timezone = data.get('timezone', 'UTC')
        
        if not title or not start_time_str or not end_time_str:
            return jsonify({'error': 'title, start_time, and end_time are required'}), 400
        
        try:
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid datetime format. Use ISO 8601 format'}), 400
        
        if start_time >= end_time:
            return jsonify({'error': 'start_time must be before end_time'}), 400
        
        new_event = Event(
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
            expected_attendees=expected_attendees,
            timezone=timezone,
            created_by=current_user.user_id
        )
        
        db.session.add(new_event)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Event created successfully',
            'event': {
                'event_id': new_event.event_id,
                'title': new_event.title,
                'start_time': new_event.start_time.isoformat(),
                'end_time': new_event.end_time.isoformat()
            }
        }), 201


@app.route('/api/events/<int:event_id>/allocate', methods=['POST'])
@login_required
def api_allocate_resource(event_id):
    """REST API endpoint to allocate resources to an event"""
    if current_user.role not in ['admin', 'organiser']:
        return jsonify({'error': 'Permission denied. Only organisers and admins can allocate resources.'}), 403
    
    event = Event.query.get(event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    resource_ids = data.get('resource_ids', [])
    quantities = data.get('quantities', {})  # {resource_id: quantity}
    
    if not resource_ids:
        return jsonify({'error': 'resource_ids array is required'}), 400
    
    # Validate all resources and check for conflicts
    errors = []
    for resource_id in resource_ids:
        resource = Resource.query.get(resource_id)
        if not resource:
            errors.append(f'Resource {resource_id} not found')
            continue
        
        requested_qty = quantities.get(str(resource_id), 1)
        valid, validation_errors = validate_resource_allocation(resource_id, event_id, requested_qty)
        
        if not valid:
            errors.extend([f'{resource.resource_name}: {err}' for err in validation_errors])
    
    if errors:
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'details': errors
        }), 400
    
    # Clear existing allocations and add new ones
    EventResourceAllocation.query.filter_by(event_id=event_id).delete()
    
    for resource_id in resource_ids:
        requested_qty = quantities.get(str(resource_id), 1)
        allocation = EventResourceAllocation(
            event_id=event_id,
            resource_id=resource_id,
            reserved_quantity=requested_qty
        )
        db.session.add(allocation)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Resources allocated successfully',
        'allocations': len(resource_ids)
    }), 200


@app.route('/api/conflicts', methods=['GET'])
@login_required
def api_check_conflicts():
    """REST API endpoint to check conflicts for an event"""
    event_id = request.args.get('event_id', type=int)
    
    if not event_id:
        return jsonify({'error': 'event_id parameter is required'}), 400
    
    event = Event.query.get(event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    all_conflicts = []
    
    for allocation in event.allocations:
        conflicts = check_resource_conflict(
            allocation.resource_id,
            event.start_time,
            event.end_time,
            exclude_event_id=event_id,
            requested_quantity=allocation.reserved_quantity
        )
        
        if conflicts:
            for conflict in conflicts:
                all_conflicts.append({
                    'resource_id': allocation.resource_id,
                    'resource_name': allocation.resource.resource_name,
                    'conflicting_event_id': conflict['event'].event_id,
                    'conflicting_event_title': conflict['event'].title,
                    'overlap_start': conflict['overlap_start'].isoformat(),
                    'overlap_end': conflict['overlap_end'].isoformat()
                })
    
    return jsonify({
        'success': True,
        'event_id': event_id,
        'has_conflicts': len(all_conflicts) > 0,
        'conflict_count': len(all_conflicts),
        'conflicts': all_conflicts
    }), 200


@app.route('/api/available-resources', methods=['GET'])
@login_required
def api_available_resources():
    """REST API endpoint to get available resources for a given time period"""
    start_time_str = request.args.get('start_time')
    end_time_str = request.args.get('end_time')
    exclude_event_id = request.args.get('exclude_event_id', type=int)
    
    if not start_time_str or not end_time_str:
        return jsonify({'error': 'start_time and end_time parameters are required'}), 400
    
    try:
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        return jsonify({'error': 'Invalid datetime format. Use YYYY-MM-DDTHH:MM'}), 400
    
    if start_time >= end_time:
        return jsonify({'error': 'start_time must be before end_time'}), 400
    
    all_resources = Resource.query.order_by(Resource.category, Resource.resource_name).all()
    available_resources = []
    
    for resource in all_resources:
        conflicts = check_resource_conflict(
            resource.resource_id,
            start_time,
            end_time,
            exclude_event_id=exclude_event_id,
            requested_quantity=1  # Check if at least 1 unit is available
        )
        
        if not conflicts:  # No conflicts, resource is available
            available_resources.append({
                'resource_id': resource.resource_id,
                'resource_name': resource.resource_name,
                'category': resource.category,
                'capacity': resource.capacity,
                'quantity': resource.quantity,
                'max_hours_per_day': resource.max_hours_per_day
            })
    
    return jsonify({
        'success': True,
        'start_time': start_time_str,
        'end_time': end_time_str,
        'total_resources': len(all_resources),
        'available_count': len(available_resources),
        'resources': available_resources
    }), 200


# ==================== SEED DATA ROUTE ====================

@app.route('/seed')
def seed_data():
    """Seed the database with sample data"""
    
    # Clear existing data
    EventResourceAllocation.query.delete()
    Event.query.delete()
    Resource.query.delete()
    User.query.delete()
    
    # Add sample users
    admin = User(username='admin', email='admin@example.com', role='admin')
    admin.set_password('admin123')
    
    organiser = User(username='organiser', email='organiser@example.com', role='organiser')
    organiser.set_password('organiser123')
    
    viewer = User(username='viewer', email='viewer@example.com', role='viewer')
    viewer.set_password('viewer123')
    
    db.session.add(admin)
    db.session.add(organiser)
    db.session.add(viewer)
    db.session.commit()
    
    # Add sample resources with new fields
    resources = [
        Resource(resource_name='Conference Room A', resource_type='Room', category='Venue', 
                capacity=50, quantity=1),
        Resource(resource_name='Conference Room B', resource_type='Room', category='Venue', 
                capacity=30, quantity=1),
        Resource(resource_name='Projector 1', resource_type='Equipment', category='Equipment', 
                quantity=2),
        Resource(resource_name='Dr. Smith', resource_type='Instructor', category='Person', 
                max_hours_per_day=8.0),
        Resource(resource_name='Lab Computer 1', resource_type='Equipment', category='Equipment', 
                quantity=10),
    ]
    
    for resource in resources:
        db.session.add(resource)
    
    db.session.commit()
    
    # Add sample events with new fields
    now = datetime.now()
    events = [
        Event(
            title='Python Workshop',
            start_time=now + timedelta(days=1, hours=10),
            end_time=now + timedelta(days=1, hours=12),
            description='Introduction to Python programming',
            expected_attendees=25,
            timezone='UTC',
            created_by=admin.user_id
        ),
        Event(
            title='Team Meeting',
            start_time=now + timedelta(days=1, hours=14),
            end_time=now + timedelta(days=1, hours=15),
            description='Weekly team sync-up',
            expected_attendees=10,
            timezone='UTC',
            created_by=organiser.user_id
        ),
        Event(
            title='Web Development Course',
            start_time=now + timedelta(days=2, hours=9),
            end_time=now + timedelta(days=2, hours=11),
            description='HTML, CSS, and JavaScript basics',
            expected_attendees=40,
            timezone='UTC',
            created_by=admin.user_id
        ),
        Event(
            title='Project Presentation',
            start_time=now + timedelta(days=3, hours=13),
            end_time=now + timedelta(days=3, hours=15),
            description='Final project presentations',
            expected_attendees=20,
            timezone='UTC',
            created_by=organiser.user_id
        ),
    ]
    
    for event in events:
        db.session.add(event)
    
    db.session.commit()
    
    # Add sample allocations with reserved quantities
    allocations = [
        EventResourceAllocation(event_id=1, resource_id=1, reserved_quantity=1),  # Python Workshop - Conference Room A
        EventResourceAllocation(event_id=1, resource_id=3, reserved_quantity=1),  # Python Workshop - Projector 1
        EventResourceAllocation(event_id=2, resource_id=2, reserved_quantity=1),  # Team Meeting - Conference Room B
        EventResourceAllocation(event_id=3, resource_id=1, reserved_quantity=1),  # Web Dev Course - Conference Room A
        EventResourceAllocation(event_id=3, resource_id=4, reserved_quantity=1),  # Web Dev Course - Dr. Smith
        EventResourceAllocation(event_id=4, resource_id=1, reserved_quantity=1),  # Presentation - Conference Room A
        EventResourceAllocation(event_id=4, resource_id=3, reserved_quantity=1),  # Presentation - Projector 1
    ]
    
    for allocation in allocations:
        db.session.add(allocation)
    
    db.session.commit()
    
    flash('Sample data seeded! Login: admin/admin123, organiser/organiser123, viewer/viewer123', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
