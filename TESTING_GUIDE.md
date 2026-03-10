# Testing Guide - Event Scheduler System

## Running Tests

### Setup
Ensure you have installed all dependencies including pytest:
```bash
pip install -r requirements.txt
```

### Run All Tests
```bash
cd d:\Jaii's\Event_Scheduler\event_scheduler
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_conflict.py -v
```

### Run with Coverage
```bash
pip install pytest-cov
pytest tests/ --cov=app --cov-report=html
```

---

## Test Categories

### 1. Overlap Detection Tests
These tests verify the conflict detection engine handles various time overlap scenarios:

- **test_partial_overlap_start_before_end_during**: Event A starts before Event B and ends during Event B
- **test_partial_overlap_start_during_end_after**: Event A starts during Event B and ends after Event B
- **test_full_overlap_nested_event**: Event A completely contained within Event B
- **test_full_overlap_containing_event**: Event B completely contains Event A
- **test_boundary_exact_same_time**: Events have exact same start and end times
- **test_boundary_adjacent_events_no_conflict**: Events are adjacent (no conflict expected)
- **test_no_overlap_completely_separate**: Events completely separate in time

### 2. Equipment Quantity Tests
These tests verify equipment resource constraints:

- **test_equipment_quantity_within_limit**: Allocation within available quantity limit
- **test_equipment_quantity_exceeds_limit**: Allocation exceeds available quantity

### 3. Resource Rule Tests
These tests verify business logic for resource constraints:

- **test_room_capacity_check**: Validates room capacity vs expected attendees
- **test_instructor_daily_hours_limit**: Validates instructor working hour limits per day

---

## Test Results

Expected output when all tests pass:
```
================================ test session starts =================================
tests/test_conflict.py::test_partial_overlap_start_before_end_during PASSED    [  8%]
tests/test_conflict.py::test_partial_overlap_start_during_end_after PASSED     [ 16%]
tests/test_conflict.py::test_full_overlap_nested_event PASSED                  [ 25%]
tests/test_conflict.py::test_full_overlap_containing_event PASSED              [ 33%]
tests/test_conflict.py::test_boundary_exact_same_time PASSED                   [ 41%]
tests/test_conflict.py::test_boundary_adjacent_events_no_conflict PASSED       [ 50%]
tests/test_conflict.py::test_no_overlap_completely_separate PASSED             [ 58%]
tests/test_conflict.py::test_equipment_quantity_within_limit PASSED            [ 66%]
tests/test_conflict.py::test_equipment_quantity_exceeds_limit PASSED           [ 75%]
tests/test_conflict.py::test_room_capacity_check PASSED                        [ 83%]
tests/test_conflict.py::test_instructor_daily_hours_limit PASSED               [ 91%]

================================ 12 passed in 0.5s ==================================
```

---

## Manual Testing Checklist

### Authentication Tests
- [ ] Register a new user
- [ ] Login with valid credentials
- [ ] Login with invalid credentials
- [ ] Logout
- [ ] Access protected routes without login (should redirect)
- [ ] Access organiser/admin routes as viewer (should deny)

### Event Management Tests
- [ ] Create event with valid data
- [ ] Create event with start_time >= end_time (should fail)
- [ ] Edit event and verify changes
- [ ] Delete event
- [ ] Create event with expected_attendees field

### Resource Management Tests
- [ ] Create room with capacity field
- [ ] Create equipment with quantity field
- [ ] Create instructor with max_hours_per_day field
- [ ] Edit resource and verify changes
- [ ] Delete resource (admin only)

### Allocation Tests
- [ ] Allocate resource to event (no conflict)
- [ ] Allocate resource with conflict (should fail)
- [ ] Allocate room exceeding capacity (should fail)
- [ ] Allocate equipment within quantity limit
- [ ] Allocate equipment exceeding quantity limit (should fail)
- [ ] Allocate instructor exceeding daily hours (should fail)
- [ ] View allocations list

### API Tests
- [ ] GET /api/events without authentication (should fail)
- [ ] GET /api/events with date range filter
- [ ] POST /api/events as organiser
- [ ] POST /api/events as viewer (should fail)
- [ ] POST /api/events/{id}/allocate with valid data
- [ ] POST /api/events/{id}/allocate with conflicts (should fail)
- [ ] GET /api/conflicts for event with conflicts

### Report Tests
- [ ] Generate report with date range
- [ ] Verify total hours calculation
- [ ] Verify upcoming bookings list

---

## Debugging Failed Tests

If a test fails:

1. **Check the error message**: Read the assertion error carefully
2. **Check database state**: Ensure test fixtures are working correctly
3. **Verify datetime handling**: Time comparisons can be tricky
4. **Run individual test**: Isolate the failing test
   ```bash
   pytest tests/test_conflict.py::test_name -v
   ```

5. **Add print statements**: Use `print()` to debug values
   ```python
   print(f"Conflicts found: {conflicts}")
   ```

6. **Check test data**: Verify fixture setup is correct

---

## Adding New Tests

When adding new features, add corresponding tests:

```python
def test_new_feature(client, setup_data):
    """Test description"""
    with app.app_context():
        # Setup
        # ...
        
        # Action
        result = function_to_test(params)
        
        # Assert
        assert result == expected, "Error message"
```

---

## Continuous Integration

To set up GitHub Actions (optional):

Create `.github/workflows/test.yml`:
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
```

---

## Test Coverage Goals

Aim for:
- **Conflict detection logic**: 100% coverage
- **Resource validation**: 100% coverage
- **Route handlers**: 80%+ coverage
- **Overall**: 70%+ coverage

Check coverage:
```bash
pytest tests/ --cov=app --cov-report=term-missing
```
