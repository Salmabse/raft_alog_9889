# RAFT Consensus Algorithm Project

This project implements a **simplified RAFT consensus algorithm** using Python and Docker. The cluster consists of **5 nodes**, each running in a separate Docker container, demonstrating leader election, log replication, and fault tolerance.

---

## Features

- **Node States**: Each node can be a **Follower**, **Candidate**, or **Leader**.
- **Leader Election**: Followers start an election if they do not receive heartbeats; the candidate can become the leader.
- **RPC Interfaces**: Implemented using Flask HTTP API.
  - `/status` — Get the current node state, term, log, commit index.
  - `/request_vote` — Request vote from a peer (for elections).
  - `/append_entries` — Append entries to log (heartbeats or log replication).
  - `/client_command` — Submit a command to the leader for replication.
- **Log Replication**: Leader replicates commands to followers. Once a majority acknowledges, entries are committed.
- **Fault Tolerance**: Nodes handle leader crashes and perform re-election automatically.
- **Optional Persistence**: Nodes can persist logs and current term to disk for recovery (if implemented).

---

## Project Structure

ASG3_RAFT_ALGO_9889/
├─ Dockerfile
├─ main.py
├─ raft.py
├─ requirements.txt
├─ README.md


- `main.py` — Flask app exposing RAFT endpoints.
- `raft.py` — RAFT node implementation.
- `Dockerfile` — Docker build instructions.
- `requirements.txt` — Python dependencies.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NODE_ID` | Unique ID for the node (1–5) |
| `PORT` | Port to run the Flask server (default 5000) |
| `PEERS` | Comma-separated list of other nodes, e.g., `node1:5000,node2:5000,node3:5000` |

---


## Docker Usage

### Build the Docker image

```bash
docker build -t raft-node .
```

## Run a node

```bash
docker run -d -e NODE_ID=1 -e PORT=5001 -e PEERS="localhost:5002,localhost:5003" -p 5001:5000 raft-node
```

Repeat for other nodes, updating NODE_ID, PORT, and PEERS.

## Testing
### Check node status

```bash
curl http://localhost:5001/status

```

### Send a command to the leader

```powershell
Invoke-WebRequest -Uri "http://localhost:5005/client_command" `
  -Method POST -ContentType "application/json" `
  -Body '{"command":"set x=42"}'
```
### Verify logs on all nodes

```bash
curl http://localhost:5001/status
curl http://localhost:5002/status
curl http://localhost:5003/status
curl http://localhost:5004/status
curl http://localhost:5005/status
```
All nodes should show the same log entries.

## Notes

- Multi-node clusters require each node to run in a separate container with proper NODE_ID and PEERS configuration.

- /client_command should only be sent to the leader node. Followers will redirect clients to the current leader.

## License

This project is for educational purposes and does not have a license.