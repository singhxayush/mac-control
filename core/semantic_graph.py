"""
Semantic Memory & Knowledge Graph for Progressive Accessibility Automation.

Concepts:
1. Contextual Graph:
   App -> Window Context -> UI Element -> Resolving Action.
2. Progressive Acceleration:
   - When an intent is resolved via Vision Fallback (Tier 3) or deep search,
     it is indexed in the graph with its context and coordinates/selectors.
   - On future invocations under the same context, the graph intercepts the intent
     in Tier 0/1 (<10ms), bypassing the slow vision pipeline completely.
3. Self-Persistence:
   Automatically saves and loads from data/semantic_graph.json.
"""

import os
import json
import time
from typing import Optional, Dict, Any, List

GRAPH_STORAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "semantic_graph.json")

class SemanticGraph:
    def __init__(self, storage_path: str = GRAPH_STORAGE_PATH):
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
                print(f"[SemanticGraph] Loaded {len(self.nodes)} nodes and {len(self.edges)} edges from disk.")
            except Exception as e:
                print(f"[SemanticGraph] Error loading graph: {e}. Starting fresh.")
                self.nodes = {}
                self.edges = []
        else:
            self._initialize_default_knowledge()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({"nodes": self.nodes, "edges": self.edges}, f, indent=2)
        except Exception as e:
            print(f"[SemanticGraph] Error saving graph: {e}")

    def _initialize_default_knowledge(self):
        """Pre-seeds standard high-frequency macOS application semantics."""
        default_apps = [
            ("app:brave", {"type": "app", "name": "Brave Browser", "bundle_id": "com.brave.Browser"}),
            ("app:chrome", {"type": "app", "name": "Google Chrome", "bundle_id": "com.google.Chrome"}),
            ("app:safari", {"type": "app", "name": "Safari", "bundle_id": "com.apple.Safari"}),
            ("app:terminal", {"type": "app", "name": "Terminal", "bundle_id": "com.apple.Terminal"}),
            ("app:finder", {"type": "app", "name": "Finder", "bundle_id": "com.apple.finder"}),
        ]
        for node_id, data in default_apps:
            self.nodes[node_id] = data
        self.save()

    # --- Node & Edge Management ---
    def add_node(self, node_id: str, data: Dict[str, Any]):
        self.nodes[node_id] = data
        self.save()

    def add_or_update_edge(self, source_id: str, target_id: str, relation: str, metadata: Optional[Dict[str, Any]] = None):
        meta = metadata or {}
        # Find existing edge
        for edge in self.edges:
            if edge["source"] == source_id and edge["target"] == target_id and edge["relation"] == relation:
                edge["weight"] = edge.get("weight", 1) + 1
                edge["last_used"] = time.time()
                edge.update(meta)
                self.save()
                return

        new_edge = {
            "source": source_id,
            "target": target_id,
            "relation": relation,
            "weight": 1,
            "last_used": time.time(),
            **meta
        }
        self.edges.append(new_edge)
        self.save()

    # --- Progressive Query & Acceleration ---
    def find_cached_action(self, intent_text: str, app_name: Optional[str] = None, window_context: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Queries the knowledge graph to see if this intent was previously resolved
        and promoted to fast execution.
        Returns the action dict if found, or None.
        """
        clean_intent = intent_text.strip().lower()
        intent_node_id = f"intent:{clean_intent}"

        if intent_node_id not in self.nodes:
            return None

        # Look for edges originating from this intent
        matching_edges = [
            e for e in self.edges
            if e["source"] == intent_node_id and e["relation"] == "resolves_to"
        ]

        if not matching_edges:
            return None

        # Sort by weight (frequency of success)
        matching_edges.sort(key=lambda x: x.get("weight", 0), reverse=True)

        for edge in matching_edges:
            target_id = edge["target"]
            target_node = self.nodes.get(target_id)
            if not target_node:
                continue

            # Context verification: if app or window matches
            edge_app = edge.get("app")
            if edge_app and app_name and edge_app.lower() not in app_name.lower():
                continue

            print(f"[SemanticGraph Hit] Fast-routed intent '{intent_text}' via learned node '{target_id}' (weight={edge.get('weight')})")
            return target_node.get("action")

        return None

    def record_successful_resolution(
        self,
        intent_text: str,
        action_dict: Dict[str, Any],
        resolved_by_tier: int,
        app_name: Optional[str] = None,
        window_title: Optional[str] = None,
        coordinates: Optional[tuple] = None
    ):
        """
        Learns from successful execution.
        If resolved by Tier 2 or Tier 3 (Vision), records the resolution so future
        calls become instantaneous Tier 0/1 actions.
        """
        clean_intent = intent_text.strip().lower()
        intent_node_id = f"intent:{clean_intent}"
        action_node_id = f"action:{clean_intent}:{resolved_by_tier}"

        # Register intent node
        self.nodes[intent_node_id] = {
            "type": "intent",
            "text": clean_intent,
            "last_seen": time.time()
        }

        # Register action node
        action_payload = dict(action_dict)
        if coordinates:
            action_payload["coordinates"] = coordinates

        self.nodes[action_node_id] = {
            "type": "action",
            "action": action_payload,
            "resolved_tier": resolved_by_tier,
            "created_at": time.time()
        }

        # Link edge
        edge_meta = {
            "resolved_by_tier": resolved_by_tier,
            "app": app_name,
            "window_title": window_title
        }
        self.add_or_update_edge(intent_node_id, action_node_id, "resolves_to", edge_meta)

        if resolved_by_tier >= 2:
            print(f"[SemanticGraph Learned] Intent '{clean_intent}' (resolved at Tier {resolved_by_tier}) is now indexed for instant execution!")
