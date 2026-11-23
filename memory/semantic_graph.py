"""
Semantic Memory & Knowledge Graph for Progressive UI Acceleration.
"""

import os
import json
import time
from typing import Optional, Dict, Any, List
from config.settings import settings

class SemanticGraph:
    def __init__(self, storage_path: str = settings.connectors.graph_storage_path):
        self.storage_path = storage_path
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self.load()

    def load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.nodes = data.get("nodes", {})
                    self.edges = data.get("edges", [])
            except Exception:
                self._seed_default_apps()
        else:
            self._seed_default_apps()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({"nodes": self.nodes, "edges": self.edges}, f, indent=2)
        except Exception as e:
            print(f"[SemanticGraph] Save warning: {e}")

    def _seed_default_apps(self):
        self.nodes = {
            "app:brave": {"type": "app", "name": "Brave Browser"},
            "app:chrome": {"type": "app", "name": "Google Chrome"},
            "app:safari": {"type": "app", "name": "Safari"},
            "app:terminal": {"type": "app", "name": "Terminal"},
            "app:finder": {"type": "app", "name": "Finder"},
        }
        self.edges = []
        self.save()

    def find_cached_action(self, intent_text: str, app_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        clean = intent_text.strip().lower()
        intent_id = f"intent:{clean}"
        if intent_id not in self.nodes:
            return None

        matching = [e for e in self.edges if e["source"] == intent_id and e["relation"] == "resolves_to"]
        if not matching:
            return None
        matching.sort(key=lambda x: x.get("weight", 0), reverse=True)

        for edge in matching:
            target = self.nodes.get(edge["target"])
            if not target:
                continue
            edge_app = edge.get("app")
            if edge_app and app_name and edge_app.lower() not in app_name.lower():
                continue
            return target.get("action")

        return None

    def record_resolution(self, intent_text: str, action_dict: Dict[str, Any], tier: float, app_name: Optional[str] = None):
        clean = intent_text.strip().lower()
        intent_id = f"intent:{clean}"
        action_id = f"action:{clean}:{tier}"

        self.nodes[intent_id] = {"type": "intent", "text": clean, "last_seen": time.time()}
        self.nodes[action_id] = {"type": "action", "action": dict(action_dict), "tier": tier, "created_at": time.time()}

        for edge in self.edges:
            if edge["source"] == intent_id and edge["target"] == action_id:
                edge["weight"] = edge.get("weight", 1) + 1
                edge["last_used"] = time.time()
                self.save()
                return

        self.edges.append({
            "source": intent_id,
            "target": action_id,
            "relation": "resolves_to",
            "weight": 1,
            "last_used": time.time(),
            "tier": tier,
            "app": app_name
        })
        self.save()
