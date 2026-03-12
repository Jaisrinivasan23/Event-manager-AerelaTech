from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response, session
from config import Config
from models import db, Event, Resource, EventResourceAllocation, User
from datetime import datetime, timedelta
import csv
from io import StringIO

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Try to initialize migrations if available
try:
    from flask_migrate import Migrate
    migrate = Migrate(app, db)
except Exception:
    pass


# ==================== SIMPLE AUTH HELPERS ====================

def get_current_user():
    """Get current logged in user from session"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


def is_logged_in():
    """Check if user is logged in"""
    return 'user_id' in session


def require_login():
    """Require user to be logged in"""
    if not is_logged_in():
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))
    return None


def require_role(*roles):
    """Require user to have specific role"""
    if not is_logged_in():
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if user.role not in roles:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('list_events'))
    return None


# ==================== AUTH ROUTES ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if is_logged_in():
        return redirect(url_for('list_events'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please provide both username and password.', 'danger')
            return redirect(url_for('login'))
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.is_active:
            session['user_id'] = user.user_id
            session['username'] = user.username
            session['role'] = user.role
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('list_events'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
    
    return render_template('auth/login.html')


@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if is_logged_in():
        return redirect(url_for('list_events'))
    
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
        
        # Check for time overlap
        if start_time < event.end_time and event.start_time < end_time:
            conflicts.append({
                'event': event,
                'allocation': allocation,
                'overlap_start': max(start_time, event.start_time),
                'overlap_end': min(end_time, event.end_time)
            })
    
    # For equipment, check if total quantity exceeds available
    if resource and resource.category == 'Equipment' and conflicts:
        if resource.quantity is None or resource.quantity == 0:
            return conflicts
        
        total_allocated = sum(c['allocation'].reserved_quantity for c in conflicts)
        if total_allocated + requested_quantity > resource.quantity:
            return conflicts
        else:
            return []
    
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
    
    allocations = EventResourceAllocation.query.filter_by(resource_id=resource_id).all()
    total_hours = 0
    
    for allocation in allocations:
        event = allocation.event
        if exclude_event_id and event.event_id == exclude_event_id:
            continue
        
        if event.start_time.date() == start_time.date():
            total_hours += event.duration_hours()
    
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
    
    # Validate quantity for equipment
    if resource.category == 'Equipment' and resource.quantity:
        if requested_quantity > resource.quantity:
            errors.append(f"Requested quantity ({requested_quantity}) exceeds available ({resource.quantity}) for {resource.resource_name}")
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


# ==================== ROUTES ====================

@app.route('/')
def index():
    """Home page - redirect to events list"""
    return redirect(url_for('list_events'))


# ==================== EVENT ROUTES ====================

@app.route('/events')
def list_events():
    """List all events"""
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    
    events = Event.query.order_by(Event.start_time.desc()).all()
    return render_template('events/list.html', events=events, current_user=get_current_user())


@app.route('/events/add', methods=['GET', 'POST'])
def add_event():
    """Add a new event"""
    redirect_response = require_role('admin', 'organiser')
    if redirect_response:
        return redirect_response
    
    if request.method == 'POST':
        title = request.form.get('title')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        description = request.form.get('description')
        expected_attendees = request.form.get('expected_attendees', 0, type=int)
        resource_ids = request.form.getlist('resource_ids')
        
        # Validate inputs
        if not title or not start_time_str or not end_time_str:
            flash('Title, start time, and end time are required!', 'danger')
            resources = Resource.query.order_by(Resource.resource_name).all()
            return render_template('events/add.html', resources=resources, current_user=get_current_user())
        
        try:
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date/time format!', 'danger')
            resources = Resource.query.order_by(Resource.resource_name).all()
            return render_template('events/add.html', resources=resources, current_user=get_current_user())
        
        if start_time >= end_time:
            flash('Start time must be before end time!', 'danger')
            resources = Resource.query.order_by(Resource.resource_name).all()
            return render_template('events/add.html', resources=resources, current_user=get_current_user())
        
        # Create new event
        new_event = Event(
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
            expected_attendees=expected_attendees,
            timezone='Asia/Kolkata',
            created_by=session.get('user_id')
        )
        
        db.session.add(new_event)
        db.session.flush()
        
        # Validate and allocate resources
        if resource_ids:
            conflicts_found = False
            for resource_id in resource_ids:
                resource_id = int(resource_id)
                quantity_key = f'quantity_{resource_id}'
                requested_qty = request.form.get(quantity_key, 1, type=int)
                
                valid, errors = validate_resource_allocation(resource_id, new_event.event_id, requested_qty)
                
                if not valid:
                    for error in errors:
                        flash(error, 'danger')
                    conflicts_found = True
            
            if conflicts_found:
                db.session.rollback()
                resources = Resource.query.order_by(Resource.resource_name).all()
                return render_template('events/add.html', resources=resources, current_user=get_current_user())
            
            # Create allocations
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
    
    # GET request - show all resources (filtering is done by JavaScript)
    all_resources = Resource.query.order_by(Resource.category, Resource.resource_name).all()
    return render_template('events/add.html', resources=all_resources, current_user=get_current_user())


@app.route('/events/edit/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    """Edit an existing event"""
    redirect_response = require_role('admin', 'organiser')
    if redirect_response:
        return redirect_response
    
    event = Event.query.get_or_404(event_id)
    
    if request.method == 'POST':
        title = request.form.get('title')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        description = request.form.get('description')
        expected_attendees_str = request.form.get('expected_attendees')
        resource_ids = request.form.getlist('resource_ids')
        
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
            
            # Check conflicts if time changed or resource is new
            if (start_time != event.start_time or end_time != event.end_time or 
                resource_id not in current_resource_ids):
                conflicts = check_resource_conflict(
                    resource_id, start_time, end_time,
                    requested_quantity=quantity,
                    exclude_event_id=event_id
                )
                if conflicts:
                    conflict_titles = ', '.join([c['event'].title for c in conflicts])
                    flash(f'Resource conflict for "{resource.resource_name}" with: {conflict_titles}', 'danger')
                    return redirect(url_for('edit_event', event_id=event_id))
            
            valid, errors = validate_resource_allocation(resource_id, event_id, quantity)
            if not valid:
                for error in errors:
                    flash(error, 'danger')
                return redirect(url_for('edit_event', event_id=event_id))
        
        # Update event
        event.title = title
        event.start_time = start_time
        event.end_time = end_time
        event.description = description
        event.expected_attendees = expected_attendees
        
        # Update resource allocations
        resources_to_remove = current_resource_ids - new_resource_ids
        for resource_id in resources_to_remove:
            allocation = current_allocations[resource_id]
            db.session.delete(allocation)
        
        for resource_id in resource_ids:
            resource = Resource.query.get(resource_id)
            quantity = 1
            if resource.category == 'Equipment':
                quantity_str = request.form.get(f'quantity_{resource_id}')
                quantity = int(quantity_str) if quantity_str else 1
            
            if resource_id in current_allocations:
                current_allocations[resource_id].reserved_quantity = quantity
            else:
                allocation = EventResourceAllocation(
                    event_id=event.event_id,
                    resource_id=resource_id,
                    reserved_quantity=quantity
                )
                db.session.add(allocation)
        
        db.session.commit()
        flash(f'Event "{title}" updated successfully!', 'success')
        return redirect(url_for('list_events'))
    
    # GET request
    resources = Resource.query.order_by(Resource.category, Resource.resource_name).all()
    allocated_resource_ids = {alloc.resource_id for alloc in event.allocations}
    allocated_quantities = {alloc.resource_id: alloc.reserved_quantity for alloc in event.allocations}
    
    return render_template('events/edit.html', 
                         event=event, 
                         resources=resources,
                         allocated_resource_ids=allocated_resource_ids,
                         allocated_quantities=allocated_quantities,
                         current_user=get_current_user())


@app.route('/events/delete/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    """Delete an event"""
    redirect_response = require_role('admin', 'organiser')
    if redirect_response:
        return redirect_response
    
    event = Event.query.get_or_404(event_id)
    title = event.title
    
    db.session.delete(event)
    db.session.commit()
    
    flash(f'Event "{title}" deleted successfully!', 'success')
    return redirect(url_for('list_events'))


# ==================== RESOURCE ROUTES ====================

@app.route('/resources')
def list_resources():
    """List all resources"""
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    
    selected_category = request.args.get('category')
    
    # Get distinct categories
    raw_categories = db.session.query(Resource.category).distinct().order_by(Resource.category).all()
    categories = [c[0] for c in raw_categories if c[0]]
    
    if selected_category:
        resources = Resource.query.filter_by(category=selected_category).order_by(Resource.resource_name).all()
    else:
        resources = Resource.query.order_by(Resource.resource_name).all()
    
    return render_template('resources/list.html', resources=resources, categories=categories, 
                         selected_category=selected_category, current_user=get_current_user())


@app.route('/resources/add', methods=['GET', 'POST'])
def add_resource():
    """Add a new resource"""
    redirect_response = require_role('admin', 'organiser')
    if redirect_response:
        return redirect_response
    
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
    
    return render_template('resources/add.html', current_user=get_current_user())


@app.route('/resources/edit/<int:resource_id>', methods=['GET', 'POST'])
def edit_resource(resource_id):
    """Edit an existing resource"""
    redirect_response = require_role('admin', 'organiser')
    if redirect_response:
        return redirect_response
    
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
    
    return render_template('resources/edit.html', resource=resource, current_user=get_current_user())


@app.route('/resources/delete/<int:resource_id>', methods=['POST'])
def delete_resource(resource_id):
    """Delete a resource"""
    redirect_response = require_role('admin')
    if redirect_response:
        return redirect_response
    
    resource = Resource.query.get_or_404(resource_id)
    resource_name = resource.resource_name
    
    db.session.delete(resource)
    db.session.commit()
    
    flash(f'Resource "{resource_name}" deleted successfully!', 'success')
    return redirect(url_for('list_resources'))


@app.route('/resources/detail/<int:resource_id>')
def resource_detail(resource_id):
    """View resource details and allocations"""
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    
    resource = Resource.query.get_or_404(resource_id)
    
    allocations = EventResourceAllocation.query.filter_by(resource_id=resource_id).order_by(
        EventResourceAllocation.allocated_at.desc()
    ).all()
    
    # Separate into upcoming and past
    now = datetime.now()
    upcoming_allocations = []
    past_allocations = []
    
    for alloc in allocations:
        if alloc.event.end_time >= now:
            upcoming_allocations.append(alloc)
        else:
            past_allocations.append(alloc)
    
    upcoming_allocations.sort(key=lambda x: x.event.start_time)
    past_allocations.sort(key=lambda x: x.event.end_time, reverse=True)
    
    return render_template('resources/detail.html', 
                         resource=resource,
                         upcoming_allocations=upcoming_allocations,
                         past_allocations=past_allocations,
                         now=now,
                         current_user=get_current_user())


# ==================== REPORT ROUTES ====================

@app.route('/report', methods=['GET', 'POST'])
def resource_report():
    """Generate resource utilization report"""
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    
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
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            flash('Invalid date format!', 'danger')
            return redirect(url_for('resource_report'))
        
        if start_date > end_date:
            flash('Start date must be before end date!', 'danger')
            return redirect(url_for('resource_report'))
        
        # Get events in date range
        events_in_range = Event.query.filter(
            Event.start_time <= end_date,
            Event.end_time >= start_date
        ).order_by(Event.start_time).all()
        
        # Generate report
        resources = Resource.query.all()
        report_data = []
        now = datetime.now()
        
        category_stats = {'Venue': 0, 'Equipment': 0, 'Person': 0, 'Other': 0}
        total_events = len(events_in_range)
        total_allocations = 0
        
        for resource in resources:
            total_hours = 0
            event_count = 0
            upcoming_bookings = []
            
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
                        total_allocations += 1
                
                if event.start_time > now:
                    upcoming_bookings.append(event)
            
            cat = resource.category if resource.category in category_stats else 'Other'
            category_stats[cat] += total_hours
            
            if total_hours > 0 or upcoming_bookings:
                report_data.append({
                    'resource': resource,
                    'total_hours': round(total_hours, 2),
                    'event_count': event_count,
                    'upcoming_bookings': sorted(upcoming_bookings, key=lambda e: e.start_time)
                })
        
        # Events data
        events_data = []
        for event in events_in_range:
            allocated_resources = [alloc.resource.resource_name for alloc in event.allocations]
            events_data.append({
                'event': event,
                'duration': round((event.end_time - event.start_time).total_seconds() / 3600, 2),
                'resources': allocated_resources,
                'resource_count': len(allocated_resources)
            })
        
        # Statistics
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
                         stats=stats,
                         current_user=get_current_user())


@app.route('/report/download-csv', methods=['POST'])
def download_report_csv():
    """Download report as CSV"""
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    report_type = request.form.get('report_type', 'resources')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        end_date = end_date.replace(hour=23, minute=59, second=59)
    except (ValueError, TypeError):
        flash('Invalid date format!', 'danger')
        return redirect(url_for('resource_report'))
    
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
    else:
        writer = csv.writer(output)
        writer.writerow(['Event Title', 'Start Time', 'End Time', 'Duration (hours)', 'Expected Attendees', 'Allocated Resources'])
        
        events = Event.query.filter(
            Event.start_time <= end_date,
            Event.end_time >= start_date
        ).order_by(Event.start_time).all()
        
        for event in events:
            resources = ', '.join([alloc.resource.resource_name for alloc in event.allocations])
            duration = round((event.end_time - event.start_time).total_seconds() / 3600, 2)
            
            writer.writerow([
                event.title,
                event.start_time.strftime('%Y-%m-%d %H:%M'),
                event.end_time.strftime('%Y-%m-%d %H:%M'),
                duration,
                event.expected_attendees or '-',
                resources or '-'
            ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    filename = f'{report_type}_report_{start_date_str}_to_{end_date_str}.csv'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response


# ==================== API ENDPOINT ====================

@app.route('/api/available-resources', methods=['GET'])
def api_available_resources():
    """Get available resources for a given time period"""
    if not is_logged_in():
        return jsonify({'error': 'Authentication required'}), 401
    
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
            requested_quantity=1
        )
        
        if not conflicts:
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


# ==================== SEED DATA ====================

@app.route('/seed')
def seed_data():
    """Seed database with sample data"""
    
    # Clear existing data
    EventResourceAllocation.query.delete()
    Event.query.delete()
    Resource.query.delete()
    User.query.delete()
    
    # Add sample users
    admin = User(username='admin', email='admin@example.com', role='admin', is_active=True)
    admin.set_password('admin123')
    
    organiser = User(username='organiser', email='organiser@example.com', role='organiser', is_active=True)
    organiser.set_password('organiser123')
    
    viewer = User(username='viewer', email='viewer@example.com', role='viewer', is_active=True)
    viewer.set_password('viewer123')
    
    db.session.add(admin)
    db.session.add(organiser)
    db.session.add(viewer)
    db.session.commit()
    
    # Add sample resources
    resources = [
        Resource(resource_name='Conference Room A', resource_type='Room', category='Venue', capacity=50, quantity=1),
        Resource(resource_name='Conference Room B', resource_type='Room', category='Venue', capacity=30, quantity=1),
        Resource(resource_name='Projector', resource_type='Equipment', category='Equipment', quantity=2),
        Resource(resource_name='Dr. Smith', resource_type='Instructor', category='Person', max_hours_per_day=8.0),
        Resource(resource_name='Lab Computers', resource_type='Equipment', category='Equipment', quantity=10),
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
            description='Introduction to Python programming',
            expected_attendees=25,
            timezone='Asia/Kolkata',
            created_by=admin.user_id
        ),
        Event(
            title='Team Meeting',
            start_time=now + timedelta(days=1, hours=14),
            end_time=now + timedelta(days=1, hours=15),
            description='Weekly team sync-up',
            expected_attendees=10,
            timezone='Asia/Kolkata',
            created_by=organiser.user_id
        ),
        Event(
            title='Web Development Course',
            start_time=now + timedelta(days=2, hours=9),
            end_time=now + timedelta(days=2, hours=11),
            description='HTML, CSS, and JavaScript basics',
            expected_attendees=40,
            timezone='Asia/Kolkata',
            created_by=organiser.user_id
        ),
    ]
    
    for event in events:
        db.session.add(event)
    
    db.session.commit()
    
    # Add sample allocations
    allocations = [
        EventResourceAllocation(event_id=1, resource_id=1, reserved_quantity=1),
        EventResourceAllocation(event_id=1, resource_id=3, reserved_quantity=1),
        EventResourceAllocation(event_id=2, resource_id=2, reserved_quantity=1),
        EventResourceAllocation(event_id=3, resource_id=1, reserved_quantity=1),
        EventResourceAllocation(event_id=3, resource_id=4, reserved_quantity=1),
    ]
    
    for allocation in allocations:
        db.session.add(allocation)
    
    db.session.commit()
    
    flash('Sample data seeded successfully! Users: admin/admin123, organiser/organiser123, viewer/viewer123', 'success')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
