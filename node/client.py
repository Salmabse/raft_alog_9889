import sys
import requests

def submit(peers, command):
    for p in peers:
        try:
            url = f"http://{p}/client_command"
            r = requests.post(url, json={"command": command}, timeout=1.0)
            if r.status_code == 200:
                resp = r.json()
                if resp.get("success"):
                    print("Command committed at index", resp.get("index"))
                    return
                # redirect provided
                if resp.get("redirect"):
                    redirect_to = resp["redirect"]
                    r2 = requests.post(redirect_to, json={"command": command}, timeout=1.0)
                    print("Redirect response:", r2.json())
                    return
                print("Response:", resp)
        except Exception as e:
            pass
    print("Couldn't find leader to accept the command.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python client.py host1:port,host2:port command")
        sys.exit(1)
    peers_str = sys.argv[1]
    cmd = " ".join(sys.argv[2:])
    peers = peers_str.split(",")
    submit(peers, cmd)
