# Test dummy codes

from one_liner.client import RouterClient  # type: ignore
import time
import yaml
from pathlib import Path

def main():
    # Connect to both the RPC and Broadcast ports
    client = RouterClient(rpc_port=5557, broadcast_port=5558)

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
