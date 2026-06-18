from one_liner.client import RouterClient  # type: ignore
import time

def main():
    # Connect to both the RPC and Broadcast ports
    client = RouterClient(rpc_port=5555, broadcast_port=5556)

    print("--- Starting Sequence ---")
    response = client.call("seqflow", "start_run")
    print(f"Response: {response}\n")

    print("--- Getting Status ---")
    response = client.call("seqflow", "pause")
    print(f"Response: {response}\n")

    print("--- Configuring Stream ---")
    # Subscribing to the progress stream setup in ZMQServer
    client.configure_stream("get_progress")
    
    # Read a few stream messages
    print("Listening for stream broadcasts (waiting 3 seconds)...")
    start_time = time.time()
    while time.time() - start_time < 3:
        try:
            # get_stream returns (timestamp, data)
            timestamp, stream_data = client.get_stream("mock_progress")
            print(f"Stream Update at {timestamp}: {stream_data}")
        except Exception as e:
            # No new message yet. Sleep briefly to prevent burning CPU.
            time.sleep(0.1)

if __name__ == "__main__":
    main()