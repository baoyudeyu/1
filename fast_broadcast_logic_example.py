import asyncio
import time
import random
from typing import List # Added for type hinting in conceptual example

# --- Core Principle 1: Asynchronous Functions ---
# Using 'async def' allows functions to pause and resume,
# enabling non-blocking operations (like waiting for network).

async def simulate_network_request(delay: float):
    """Simulates an operation like sending a message or fetching data."""
    print(f"  Task: Starting simulated request (waits {delay}s)...")
    await asyncio.sleep(delay) # 'await' pauses this function, letting others run
    print(f"  Task: Finished simulated request after {delay}s.")
    return f"Data after {delay}s"

# --- Core Principle 2: Non-Blocking Task Creation ---
# 'asyncio.create_task' schedules a coroutine to run in the background
# without waiting for it to complete. This makes the main flow responsive.

async def handle_user_command_non_blocking(command: str):
    """Simulates handling a user command quickly."""
    print(f"\\nHandling command '{command}'...")
    if command == "start_long_task":
        print("  Command Handler: Received 'start_long_task'.")
        # Immediately schedule the long task to run in the background
        # The handle_user_command_non_blocking function DOES NOT wait here.
        asyncio.create_task(long_running_background_task())
        print("  Command Handler: Background task scheduled. Handler finished.")
        # The handler finishes almost instantly, ready for the next command.
    else:
        print(f"  Command Handler: Unknown command '{command}'.")

async def long_running_background_task():
    """Simulates a task like broadcasting to many users."""
    print("    Background Task: Starting long task...")
    await asyncio.sleep(3) # Simulate work
    print("    Background Task: Long task finished.")

# --- Core Principle 3: High-Frequency Polling (Conceptual) ---
# In the original bot, python-telegram-bot's JobQueue was used.
# Here's a conceptual loop showing frequent checks.

async def high_frequency_data_checker(interval_seconds: float = 1.0):
    """Simulates frequently checking for new data (like lottery results)."""
    print("\\nStarting high-frequency data checker...")
    last_data_id = 0
    while True:
        print(f"  Data Checker: Checking for new data (current latest ID: {last_data_id})...")
        # Simulate checking an external source
        await asyncio.sleep(0.1) # Simulate check latency
        new_data_available = random.choice([True, False, False]) # Simulate finding new data sometimes

        if new_data_available:
            last_data_id += 1
            print(f"  Data Checker: Found new data! ID: {last_data_id}. Processing...")
            # In a real bot, you'd trigger the broadcast logic here,
            # possibly using asyncio.create_task again for non-blocking processing.
            asyncio.create_task(process_new_data(last_data_id))

        await asyncio.sleep(interval_seconds - 0.1) # Wait for the next check interval

async def process_new_data(data_id: int):
    """Simulates processing new data found by the checker."""
    print(f"    Processing Task: Started processing data ID {data_id}.")
    await asyncio.sleep(0.5) # Simulate processing time
    print(f"    Processing Task: Finished processing data ID {data_id}.")


# --- Core Principle 4: Concurrent Operations (e.g., Sending Messages) ---
# Instead of sending messages one by one, use asyncio.gather
# to send them concurrently, significantly speeding up broadcasts.

async def send_message_to_user(user_id: int, message: str):
    """Simulates sending a message to a single user."""
    delay = random.uniform(0.1, 0.5) # Simulate network latency variability
    print(f"    Broadcast: Attempting to send to user {user_id} (will take ~{delay:.2f}s)...")
    await asyncio.sleep(delay)
    print(f"    Broadcast: Successfully sent to user {user_id}.")
    return user_id # Indicate success

async def broadcast_concurrently(user_ids: List[int], message: str):
    """Sends a message to multiple users concurrently."""
    print("\\nStarting concurrent broadcast...")
    start_time = time.monotonic()

    # Create a list of tasks (coroutines), one for each user
    tasks = [send_message_to_user(uid, message) for uid in user_ids]

    # Run all tasks concurrently and wait for them all to complete
    # asyncio.gather is the key here!
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # return_exceptions=True means if one task fails, others continue

    end_time = time.monotonic()
    print(f"Broadcast finished in {end_time - start_time:.2f} seconds.")

    # Process results (e.g., log errors)
    success_count = 0
    fail_count = 0
    for result in results:
        if isinstance(result, Exception):
            print(f"  Broadcast Result: A send task failed: {result}")
            fail_count += 1
        else:
            # print(f"  Broadcast Result: Send task succeeded for user {result}")
            success_count += 1
    print(f"  Broadcast Summary: {success_count} successful, {fail_count} failed.")


# --- Example Usage ---
async def main_example():
    # Example 1: Non-blocking command handling
    await handle_user_command_non_blocking("start_long_task")
    print("Main Flow: Continues immediately after scheduling background task.")
    await asyncio.sleep(0.5) # Give other tasks a chance to run
    print("Main Flow: Doing other work while background task runs...")
    await asyncio.sleep(4) # Wait long enough for the background task to finish

    # Example 2: Concurrent broadcast
    users_to_notify = list(range(1, 11)) # Simulate 10 users
    await broadcast_concurrently(users_to_notify, "Hello from concurrent broadcast!")

    # Example 3: High-frequency checker (run for a short time)
    # checker_task = asyncio.create_task(high_frequency_data_checker(interval_seconds=0.5))
    # print("\\nMain Flow: Data checker running in background...")
    # await asyncio.sleep(5) # Let the checker run for 5 seconds
    # checker_task.cancel() # Stop the checker task
    # try:
    #     await checker_task
    # except asyncio.CancelledError:
    #     print("Main Flow: Data checker task cancelled as expected.")

if __name__ == "__main__":
    # Note: The high-frequency checker runs indefinitely.
    # For a clean exit in this example, comment out the checker part in main_example
    # or implement a more graceful shutdown mechanism.
    # asyncio.run(main_example())

    # Running only the broadcast example for clarity
    users_to_notify = list(range(1, 21)) # Simulate 20 users
    asyncio.run(broadcast_concurrently(users_to_notify, "Hello from concurrent broadcast!")) 