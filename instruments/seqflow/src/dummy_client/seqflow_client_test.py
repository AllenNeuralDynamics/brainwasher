# Test dummy codes

from one_liner.client import RouterClient  # type: ignore
import time
import yaml
from pathlib import Path
import threading

def stream_listener(client, stream_name):
    """Background task to print broadcast updates."""
    print(f"--- Listening to stream: {stream_name} ---")
    client.configure_stream(stream_name, storage_type="cache")  # Get most latest message only
    time.sleep(1)  # Give the stream a moment to start
    while True:
        try:
            # This uses the broadcast_port internally
            _, msg = client.get_stream(stream_name)
            print(f"  Status update: {msg}")
            time.sleep(2)
        except Exception as e:
            print(f"Error in stream_listener: {e}")
            time.sleep(2)

def main():
    # Connect to both the RPC and Broadcast ports
    client = RouterClient(rpc_port=5557, broadcast_port=5558)
    
    # Start the stream listener in a background thread
    listener = threading.Thread(target=stream_listener, args=(client, "seqflow_get_progress"), daemon=True)
    listener.start()

    # Load the job from the YAML file
    current_dir = Path(__file__).parent
    yaml_path = current_dir / "seqflow_dummy_job.yml"
    try:
        with open(yaml_path, "r") as f:
            job_payload = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Job file not found: {yaml_path}")
        return
    
    print("\n--- Starting Sequence ---")
    response = client.call("seqflow", "start_run", kwargs={"job": job_payload})
    print(f"Response: {response}")
    time.sleep(10)

    print("\n--- Pausing Sequence ---")
    response = client.call("seqflow", "pause")
    print(f"Response: {response}")
    time.sleep(10)

    print("\n--- Resuming Sequence ---")
    response = client.call("seqflow", "resume_run")
    print(f"Response: {response}")
    time.sleep(10)

    print("\n--- Pausing Sequence ---")
    response = client.call("seqflow", "pause")
    print(f"Response: {response}")
    time.sleep(10)

    print("\n--- Resuming Sequence ---")
    response = client.call("seqflow", "resume_run")
    print(f"Response: {response}")
    

if __name__ == "__main__":
    main()