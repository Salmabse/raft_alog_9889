import json
import os
from threading import RLock

class Storage:
    def __init__(self, path="data/state.json"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.lock = RLock()
        if not os.path.exists(path):
            self._write({
                "currentTerm": 0,
                "votedFor": None,
                "log": []  # each entry: {"term":int, "command": str}
            })

    def _read(self):
        with self.lock:
            with open(self.path, "r") as f:
                return json.load(f)

    def _write(self, data):
        with self.lock:
            with open(self.path, "w") as f:
                json.dump(data, f)

    def get_current_term(self):
        return self._read()["currentTerm"]

    def set_current_term(self, term):
        data = self._read()
        data["currentTerm"] = term
        self._write(data)

    def get_voted_for(self):
        return self._read()["votedFor"]

    def set_voted_for(self, candidate_id):
        data = self._read()
        data["votedFor"] = candidate_id
        self._write(data)

    def append_log(self, entry):
        data = self._read()
        data["log"].append(entry)
        self._write(data)

    def get_log(self):
        return self._read()["log"]

    def replace_log(self, new_log):
        data = self._read()
        data["log"] = new_log
        self._write(data)
