# Test dummy codes

from one_liner.client import RouterClient  # type: ignore
import time
import yaml
from pathlib import Path

def main():
    # Connect to both the RPC and Broadcast ports
    client = RouterClient(rpc_port=5555, broadcast_port=5556)
    
    # Load the job from the YAML file
    current_dir = Path(__file__).parent
    yaml_path = current_dir / "seqflow_dummy_job.yml"
    try:
        with open(yaml_path, "r") as f:
            job_payload = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Job file not found: {yaml_path}")
        return
    
    
    print("--- Starting Sequence ---")
    response = client.call("seqflow", "start_run", kwargs={"job": job_payload})
    print(f"Response: {response}\n")
    
    print("Waiting 10 seconds before pausing...")
    time.sleep(10)

    print("--- Getting Status ---")
    response = client.call("seqflow", "pause")
    print(f"Response: {response}\n")

    print("--- Configuring Stream ---")
    # Subscribing to the progress stream setup in ZMQServer
    client.configure_stream("get_progress")
    
    # Read a few stream messages
    start_time = time.time()
    while time.time() - start_time < 3:
        try:
            # get_stream returns (timestamp, data)
            timestamp, stream_data = client.get_stream("get_progress")
            print(f"Stream Update at {timestamp}: {stream_data}")
        except Exception as e:
            # No new message yet. Sleep briefly to prevent burning CPU.
            time.sleep(0.1)

if __name__ == "__main__":
    main()