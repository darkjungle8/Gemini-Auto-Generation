import os
import json
import uuid
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TaskQueue:
    """Thread-safe JSON-backed task queue for managing prompt generation tasks."""

    def __init__(self, storage_path="prompts.json", on_update=None):
        self.storage_path = storage_path
        self._lock = threading.RLock()
        self.tasks = []
        self.on_update = on_update
        self._load()

    def _load(self):
        """Load tasks from JSON file."""
        if not os.path.exists(self.storage_path):
            self.tasks = []
            return
        
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                self.tasks = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load tasks from {self.storage_path}: {e}")
            self.tasks = []

    def _save(self):
        """Save tasks to JSON file. MUST be called inside lock."""
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save tasks to {self.storage_path}: {e}")
        
        if self.on_update:
            try:
                self.on_update()
            except Exception as e:
                logger.error(f"Error in on_update callback: {e}")

    def add_task(self, prompt, target_count=1, reference_image_paths=None):
        """Add a new task to the queue."""
        with self._lock:
            # Handle backward compatibility / normalization
            if isinstance(reference_image_paths, str):
                reference_image_paths = [reference_image_paths]
                
            task = {
                "id": str(uuid.uuid4())[:8],
                "prompt": prompt,
                "target_count": target_count,
                "current_count": 0,
                "status": "pending",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "reference_image_paths": reference_image_paths or []
            }
            self.tasks.append(task)
            self._save()
            return task["id"]

    def clear_all_tasks(self):
        """Clear all tasks from the queue."""
        with self._lock:
            self.tasks = []
            self._save()

    def get_all_tasks(self):
        """Return all tasks."""
        with self._lock:
            return list(self.tasks)

    def _delete_task_image(self, task):
        """Delete the reference images associated with a task if they exist."""
        ref_paths = task.get("reference_image_paths", [])
        # Backwards compatibility check
        if task.get("reference_image_path"):
            ref_paths.append(task.get("reference_image_path"))
            
        for ref_path in ref_paths:
            if ref_path and os.path.exists(ref_path):
                try:
                    os.remove(ref_path)
                    logger.info(f"Deleted reference image for task {task['id']}: {ref_path}")
                except Exception as e:
                    logger.error(f"Failed to delete reference image {ref_path}: {e}")

    def delete_task(self, task_id: str):
        """Delete a task by ID."""
        with self._lock:
            initial_len = len(self.tasks)
            task_to_delete = next((t for t in self.tasks if t["id"] == task_id), None)
            if task_to_delete:
                self._delete_task_image(task_to_delete)
                
            self.tasks = [t for t in self.tasks if t["id"] != task_id]
            if len(self.tasks) < initial_len:
                self._save()
                return True
            return False

    def clear_pending_tasks(self):
        """Clear all pending and running tasks from the queue."""
        with self._lock:
            initial_len = len(self.tasks)
            for t in self.tasks:
                if t["status"] in ["pending", "running"]:
                    self._delete_task_image(t)
                    
            self.tasks = [t for t in self.tasks if t["status"] not in ["pending", "running"]]
            if len(self.tasks) < initial_len:
                self._save()
                return True
            return False

    def get_next_task(self):
        """
        Get the next available pending task.
        Returns the task dict, or None if no tasks are available.
        """
        with self._lock:
            for task in self.tasks:
                if task["status"] in ["pending", "running"] and task["current_count"] < task["target_count"]:
                    # Mark it as running when someone picks it up (if it was pending)
                    if task["status"] == "pending":
                        task["status"] = "running"
                        self._save()
                    return task
            return None

    def update_task_progress(self, task_id: str, new_images_count: int):
        """Update the progress of a task. Returns the updated task."""
        with self._lock:
            for task in self.tasks:
                if task["id"] == task_id:
                    task["current_count"] += new_images_count
                    if task["current_count"] >= task["target_count"]:
                        task["status"] = "completed"
                        self._delete_task_image(task)
                    self._save()
                    return task
            return None

    def mark_failed(self, task_id: str, error_msg: str):
        """Mark a task as failed."""
        with self._lock:
            for task in self.tasks:
                if task["id"] == task_id:
                    task["status"] = "failed"
                    task["error"] = error_msg
                    self._delete_task_image(task)
                    self._save()
                    return task
            return None
