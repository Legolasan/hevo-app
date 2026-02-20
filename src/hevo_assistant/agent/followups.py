"""
Follow-up suggestion logic for Hevo actions.

Generates contextual follow-up suggestions after action completion.
"""

from typing import Optional, List, Dict, Any

from hevo_assistant.domain.capabilities import CAPABILITIES, get_action_definition


# Contextual follow-up rules based on action and result
FOLLOWUP_RULES: Dict[str, Dict[str, List[str]]] = {
    # Pipeline actions
    "list_pipelines": {
        "success": [
            "Would you like details on any specific pipeline?",
            "I can check the status of a particular pipeline if you'd like.",
        ],
        "empty": [
            "You don't have any pipelines yet. Would you like to create one?",
        ],
    },
    "get_pipeline": {
        "success": [
            "Would you like to see the objects being synced in this pipeline?",
            "I can run this pipeline now if you want to trigger an immediate sync.",
        ],
        "paused": [
            "This pipeline is paused. Would you like to resume it?",
        ],
        "failed_objects": [
            "Some objects have failed. Would you like me to show the failed objects?",
            "I can restart the failed objects if you'd like.",
        ],
    },
    "create_pipeline": {
        "success": [
            "Would you like me to check if it's actively ingesting data?",
            "I can list the objects being synced if you'd like.",
            "Want to run the pipeline now to start syncing immediately?",
        ],
        "failure": [
            "Would you like to see your existing pipelines?",
            "Should I check your available destinations?",
        ],
    },
    "pause_pipeline": {
        "success": [
            "The pipeline is now paused. To resume it later, just say 'resume the pipeline'.",
            "Would you like to check the status of your other pipelines?",
        ],
    },
    "resume_pipeline": {
        "success": [
            "The pipeline is now active and syncing. Would you like to run it immediately?",
            "I can check the sync status if you'd like.",
        ],
    },
    "run_pipeline": {
        "success": [
            "The pipeline is now syncing. Would you like me to check the progress in a moment?",
            "I can show you the objects being synced if you'd like.",
        ],
    },

    # Object actions
    "list_objects": {
        "success": [
            "Would you like to skip or restart any of these objects?",
        ],
        "has_failed": [
            "Some objects have failed. Would you like me to restart them?",
        ],
    },
    "skip_object": {
        "success": [
            "The object has been skipped. To include it again later, just say 'include [object_name]'.",
        ],
    },
    "restart_object": {
        "success": [
            "The object is now restarting. This will do a full resync of the data.",
            "Would you like to check the pipeline status?",
        ],
    },

    # Destination actions
    "list_destinations": {
        "success": [
            "Would you like details on any specific destination?",
        ],
        "empty": [
            "You don't have any destinations configured. Would you like to create one?",
        ],
    },

    # Model actions
    "list_models": {
        "success": [
            "Would you like to run any of these models?",
        ],
        "empty": [
            "You don't have any models yet.",
        ],
    },
    "run_model": {
        "success": [
            "The model is now running. It will process the data and update the target table.",
        ],
    },

    # Workflow actions
    "list_workflows": {
        "success": [
            "Would you like to run any of these workflows?",
        ],
    },
    "run_workflow": {
        "success": [
            "The workflow is now running. All tasks in the workflow will execute in sequence.",
        ],
    },
}


class FollowUpSuggester:
    """
    Generates contextual follow-up suggestions after action completion.
    """

    def get_followups(
        self,
        action_name: str,
        success: bool,
        data: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Get follow-up suggestions based on action result.

        Args:
            action_name: Name of the completed action
            success: Whether the action succeeded
            data: Result data from the action
            context: Additional context (e.g., pipeline status)

        Returns:
            List of follow-up suggestion strings
        """
        suggestions = []

        # Get contextual rules for this action
        rules = FOLLOWUP_RULES.get(action_name, {})

        # Determine result type
        if success:
            result_type = "success"

            # Check for special conditions
            if data:
                if isinstance(data, list) and len(data) == 0:
                    result_type = "empty"
                elif isinstance(data, dict):
                    if data.get("status") == "PAUSED":
                        result_type = "paused"
                    if data.get("failed_objects", 0) > 0:
                        result_type = "failed_objects"
                elif isinstance(data, list):
                    # Check for failed objects in list
                    failed = [
                        obj for obj in data
                        if isinstance(obj, dict) and
                        obj.get("status") in ("FAILED", "PERMISSION_DENIED")
                    ]
                    if failed:
                        result_type = "has_failed"
        else:
            result_type = "failure"

        # Get suggestions for this result type
        if result_type in rules:
            suggestions.extend(rules[result_type])
        elif success and "success" in rules:
            suggestions.extend(rules["success"])

        # Add static follow-ups from action definition
        action_def = get_action_definition(action_name)
        if action_def and action_def.follow_ups:
            for follow_up_action in action_def.follow_ups[:2]:
                follow_up_def = get_action_definition(follow_up_action)
                if follow_up_def:
                    suggestions.append(
                        f"You can also {follow_up_def.description.lower()}."
                    )

        # Deduplicate while preserving order
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique_suggestions.append(s)

        return unique_suggestions[:3]  # Return max 3 suggestions

    def format_followups(self, suggestions: List[str]) -> str:
        """
        Format follow-up suggestions for display.

        Args:
            suggestions: List of suggestion strings

        Returns:
            Formatted string with suggestions
        """
        if not suggestions:
            return ""

        lines = ["\n**What's next?**"]
        for suggestion in suggestions:
            lines.append(f"  - {suggestion}")

        return "\n".join(lines)

    def get_quick_action_hint(
        self,
        action_name: str,
        success: bool
    ) -> Optional[str]:
        """
        Get a quick action hint for common next steps.

        Args:
            action_name: Name of the completed action
            success: Whether the action succeeded

        Returns:
            Quick hint string or None
        """
        if not success:
            return None

        hints = {
            "pause_pipeline": "Say 'resume' to start it again.",
            "skip_object": "Say 'include' to add it back.",
            "run_pipeline": "Say 'status' to check progress.",
            "create_pipeline": "Say 'run now' to start syncing.",
        }

        return hints.get(action_name)


# Module-level instance
_suggester: Optional[FollowUpSuggester] = None


def get_followup_suggester() -> FollowUpSuggester:
    """Get the global FollowUpSuggester instance."""
    global _suggester
    if _suggester is None:
        _suggester = FollowUpSuggester()
    return _suggester
