
from database import SupabaseDatabase

db = SupabaseDatabase()

# Test database connectivity
if db.test_connection():
    print("\nTesting insert...")

    result = db.insert_sensor_reading(
        device_id="test-device",
        tds=54.43,
        turbidity=0.0,
        temperature=28.88,
        predicted_bod=2.22,
    )

    print("Insert successful!")
    print("Inserted record:", result)

