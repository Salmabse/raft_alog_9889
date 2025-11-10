import threading
import time
import random
import requests
from storage import Storage

LOCK = threading.RLock()

class RaftNode:
    def __init__(self, node_id, peers, port):
        self.node_id = str(node_id)
        self.peers = peers  # list of "host:port"
        self.port = port
        self.state = "follower"  # follower | candidate | leader
        self.storage = Storage(path=f"data/state_{self.node_id}.json")

        self.currentTerm = self.storage.get_current_term()
        self.votedFor = self.storage.get_voted_for()
        self.log = self.storage.get_log()
        self.commitIndex = -1
        self.lastApplied = -1

        # Volatile leader state
        self.nextIndex = {}
        self.matchIndex = {}

        # election timer
        self.reset_election_timeout()

        # background threads
        self.running = True
        self.threads = []
        self.start_background_threads()

    def reset_election_timeout(self):
        # randomized election timeout (seconds)
        self.election_timeout = time.time() + random.uniform(1.5, 3.0)

    def start_background_threads(self):
        t = threading.Thread(target=self.run_election_timer, daemon=True)
        self.threads.append(t); t.start()
        t2 = threading.Thread(target=self.apply_committed_entries_loop, daemon=True)
        self.threads.append(t2); t2.start()
        # leader heartbeat thread will be started if we become leader

    def run_election_timer(self):
        while self.running:
            time.sleep(0.05)
            with LOCK:
                if self.state != "leader" and time.time() >= self.election_timeout:
                    self.start_election()

    def start_election(self):
        self.state = "candidate"
        self.currentTerm += 1
        self.storage.set_current_term(self.currentTerm)
        self.votedFor = self.node_id
        self.storage.set_voted_for(self.votedFor)
        votes = 1  # vote for self
        needed = (len(self.peers) + 1) // 2 + 1

        last_log_index = len(self.log) - 1
        last_log_term = self.log[-1]["term"] if self.log else 0

        # send RequestVote to peers
        for p in self.peers:
            try:
                url = f"http://{p}/request_vote"
                payload = {
                    "term": self.currentTerm,
                    "candidateId": self.node_id,
                    "lastLogIndex": last_log_index,
                    "lastLogTerm": last_log_term
                }
                r = requests.post(url, json=payload, timeout=0.8)
                if r.status_code == 200:
                    resp = r.json()
                    if resp.get("voteGranted"):
                        votes += 1
                    elif resp.get("term", 0) > self.currentTerm:
                        # discovered higher term
                        self.currentTerm = resp["term"]
                        self.storage.set_current_term(self.currentTerm)
                        self.state = "follower"
                        self.votedFor = None
                        self.storage.set_voted_for(None)
                        self.reset_election_timeout()
                        return
            except Exception:
                pass

        if votes >= needed:
            self.become_leader()
        else:
            # back to follower, wait randomized timeout and try again
            self.state = "follower"
            self.votedFor = None
            self.storage.set_voted_for(None)
            self.reset_election_timeout()

    def become_leader(self):
        self.state = "leader"
        # initialize leader volatile state
        next_idx = len(self.log)
        for p in self.peers:
            self.nextIndex[p] = next_idx
            self.matchIndex[p] = -1
        # start heartbeat thread
        t = threading.Thread(target=self.leader_heartbeat_loop, daemon=True)
        self.threads.append(t); t.start()

    def leader_heartbeat_loop(self):
        while self.running and self.state == "leader":
            self.send_append_entries_all()
            time.sleep(0.3)

    def send_append_entries_all(self):
        for p in self.peers:
            self.send_append_entries(p)

    def send_append_entries(self, peer):
        prevLogIndex = self.nextIndex.get(peer, 0) - 1
        prevLogTerm = self.log[prevLogIndex]["term"] if prevLogIndex >= 0 else 0
        entries = self.log[self.nextIndex.get(peer, 0):]  # send new entries
        payload = {
            "term": self.currentTerm,
            "leaderId": self.node_id,
            "prevLogIndex": prevLogIndex,
            "prevLogTerm": prevLogTerm,
            "entries": entries,
            "leaderCommit": self.commitIndex
        }
        try:
            url = f"http://{peer}/append_entries"
            r = requests.post(url, json=payload, timeout=1.0)
            if r.status_code == 200:
                resp = r.json()
                if resp.get("success"):
                    # update nextIndex and matchIndex
                    self.nextIndex[peer] = len(self.log)
                    self.matchIndex[peer] = len(self.log) - 1
                else:
                    # follower log conflict — decrement nextIndex and retry later
                    if resp.get("term", 0) > self.currentTerm:
                        self.currentTerm = resp["term"]
                        self.storage.set_current_term(self.currentTerm)
                        self.state = "follower"
                        self.votedFor = None
                        self.storage.set_voted_for(None)
                        self.reset_election_timeout()
                        return
                    # simple conflict resolution: decrement nextIndex
                    self.nextIndex[peer] = max(0, self.nextIndex.get(peer, 1) - 1)
        except Exception:
            pass

    def handle_request_vote(self, data):
        term = data.get("term", 0)
        candidateId = str(data.get("candidateId"))
        lastLogIndex = data.get("lastLogIndex", -1)
        lastLogTerm = data.get("lastLogTerm", 0)

        voteGranted = False
        if term < self.currentTerm:
            return {"term": self.currentTerm, "voteGranted": False}
        if term > self.currentTerm:
            self.currentTerm = term
            self.storage.set_current_term(term)
            self.votedFor = None
            self.storage.set_voted_for(None)
            self.state = "follower"

        # check if we've already voted or candidate's log is at least as up-to-date
        votedFor = self.storage.get_voted_for()
        my_last_term = self.log[-1]["term"] if self.log else 0
        my_last_index = len(self.log) - 1
        up_to_date = (lastLogTerm > my_last_term) or (lastLogTerm == my_last_term and lastLogIndex >= my_last_index)

        if (votedFor is None or votedFor == candidateId) and up_to_date:
            voteGranted = True
            self.storage.set_voted_for(candidateId)
            self.votedFor = candidateId
            self.reset_election_timeout()
        return {"term": self.currentTerm, "voteGranted": voteGranted}

    def handle_append_entries(self, data):
        term = data.get("term", 0)
        leaderId = str(data.get("leaderId"))
        prevLogIndex = data.get("prevLogIndex", -1)
        prevLogTerm = data.get("prevLogTerm", 0)
        entries = data.get("entries", [])
        leaderCommit = data.get("leaderCommit", -1)

        if term < self.currentTerm:
            return {"term": self.currentTerm, "success": False}
        # valid leader
        self.currentTerm = term
        self.storage.set_current_term(term)
        self.state = "follower"
        self.reset_election_timeout()
        # check consistency
        if prevLogIndex >= 0:
            if prevLogIndex >= len(self.log):
                return {"term": self.currentTerm, "success": False}
            if self.log[prevLogIndex]["term"] != prevLogTerm:
                # conflict: delete entry and all that follow
                self.log = self.log[:prevLogIndex]
                self.storage.replace_log(self.log)
                return {"term": self.currentTerm, "success": False}

        # append any new entries (simple overwrite)
        for i, entry in enumerate(entries):
            idx = prevLogIndex + 1 + i
            if idx < len(self.log):
                if self.log[idx]["term"] != entry["term"]:
                    # delete conflict and append
                    self.log = self.log[:idx]
                    self.log.append(entry)
            else:
                self.log.append(entry)
        self.storage.replace_log(self.log)

        if leaderCommit > self.commitIndex:
            self.commitIndex = min(leaderCommit, len(self.log)-1)
        return {"term": self.currentTerm, "success": True}

    def client_command(self, command):
        # client sends command to leader endpoint; if this node is leader, append to log and replicate
        if self.state != "leader":
            return {"success": False, "redirect": None}
        entry = {"term": self.currentTerm, "command": command}
        self.log.append(entry)
        self.storage.append_log(entry)
        # try to replicate immediately (best-effort)
        self.send_append_entries_all()
        # For simplicity, commit when a majority have matchIndex >= this index
        idx = len(self.log) - 1
        match_count = 1  # leader itself
        for p, m in self.matchIndex.items():
            if m >= idx:
                match_count += 1
        if match_count >= ((len(self.peers)+1)//2 + 1):
            self.commitIndex = idx
            return {"success": True, "index": idx}
        else:
            return {"success": False, "index": idx, "message": "Replication in progress"}

    def apply_committed_entries_loop(self):
        while self.running:
            with LOCK:
                while self.lastApplied < self.commitIndex:
                    self.lastApplied += 1
                    entry = self.log[self.lastApplied]
                    # in this simplified impl we "apply" by printing the command
                    print(f"[Node {self.node_id}] Applying command at index {self.lastApplied}: {entry}")
            time.sleep(0.1)

    # helpers to expose state for debug
    def get_state(self):
        return {
            "nodeId": self.node_id,
            "state": self.state,
            "currentTerm": self.currentTerm,
            "votedFor": self.votedFor,
            "log": self.log,
            "commitIndex": self.commitIndex,
            "lastApplied": self.lastApplied
        }
