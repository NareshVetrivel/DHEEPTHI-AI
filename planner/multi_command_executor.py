"""
ASTRA-AI Multi-Command Executor

Executes an ActionPlan sequentially by routing every action
through the existing CommandDispatcher.

Responsibilities:
    - Execute steps in order.
    - Stop when a step fails.
    - Record every step result.
    - Provide execution summary.
    - Keep multi-command execution separate from planning.

ASTRA-AI V1
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from planner.action_models import (
    ActionPlan,
    ActionStep,
    ActionStatus,
)


logger = logging.getLogger(__name__)


class MultiCommandExecutor:
    """
    Sequential executor for ASTRA-AI multi-step commands.

    The executor does NOT understand natural language.

    It receives an ActionPlan and executes each ActionStep
    through the existing CommandDispatcher.

    Flow:

        ActionPlan
            ↓
        Step 1
            ↓
        Dispatcher
            ↓
        Verify
            ↓
        Step 2
            ↓
        Dispatcher
            ↓
        Verify
            ↓
        ...
    """

    # =========================================================
    # Action → Existing Dispatcher Intent
    # =========================================================

    ACTION_TO_INTENT = {

        # -----------------------------------------------------
        # Application Actions
        # -----------------------------------------------------

        "launch_application":
            "launch_application",

        "close_application":
            "close_application",

        # -----------------------------------------------------
        # Browser Actions
        # -----------------------------------------------------

        "open_website":
            "open_website",

        "google_search":
            "google_search",

        "youtube_search":
            "youtube_search",

        "play_youtube":
            "play_youtube",

        "click_search_result":
            "click_search_result",

        # -----------------------------------------------------
        # File Actions
        # -----------------------------------------------------

        "open_file":
            "open_file",

        "create_file":
            "create_file",

        "rename_file":
            "rename_file",

        "copy_file":
            "copy_file",

        "move_file":
            "move_file",

        "delete_file":
            "delete_file",

        # -----------------------------------------------------
        # Archive Actions
        # -----------------------------------------------------

        "compress_zip":
            "compress_file",

        "extract_zip":
            "extract_zip",

        # -----------------------------------------------------
        # Folder Actions
        # -----------------------------------------------------

        "open_folder":
            "open_folder",

        "create_folder":
            "create_folder",

        "rename_folder":
            "rename_folder",

        "copy_folder":
            "copy_folder",

        "move_folder":
            "move_folder",

        "delete_folder":
            "delete_folder",

        # -----------------------------------------------------
        # Keyboard Actions
        # -----------------------------------------------------

        "type_text":
            "type_text",

        "press_key":
            "press_key",

        # -----------------------------------------------------
        # Mouse Actions
        # -----------------------------------------------------

        "click":
            "left_click",

        "double_click":
            "double_click",

        "right_click":
            "right_click",

        # -----------------------------------------------------
        # Word V1 Actions
        # -----------------------------------------------------
        #
        # Word already has its own V1 command registry and
        # WordAgent implementation.
        #
        # create_blank_document is intentionally kept separate
        # from create_file.
        #
        # create_file  -> filesystem file creation
        # create_blank_document -> Microsoft Word document
        #
        # -----------------------------------------------------
        # Code Agent Actions
        # -----------------------------------------------------

        "code_agent":
            "code_agent",

        "write_code":
            "code_agent",

        "create_blank_document":
            "create_blank_document",
    }

    # =========================================================
    # Constructor
    # =========================================================

    def __init__(
        self,
        dispatcher,
        verifier: Optional[
            Callable[[ActionStep, Any], bool]
        ] = None,
    ) -> None:
        """
        Initialize the multi-command executor.

        Parameters
        ----------
        dispatcher:
            Existing ASTRA CommandDispatcher instance.

        verifier:
            Optional custom verification callback.

            Signature:

                verifier(step, result) -> bool

            If no verifier is supplied, the executor uses the
            dispatcher result's "success" field.
        """

        if dispatcher is None:

            raise ValueError(
                "CommandDispatcher is required."
            )

        self.dispatcher = dispatcher

        self.verifier = verifier

    # =========================================================
    # Public API
    # =========================================================

    def execute(
        self,
        plan: ActionPlan,
    ) -> Dict[str, Any]:
        """
        Execute a complete ActionPlan sequentially.

        Execution stops immediately when a step fails.

        Returns
        -------
        dict
            Structured execution result.
        """

        if not isinstance(
            plan,
            ActionPlan,
        ):

            raise TypeError(
                "execute() expects an ActionPlan."
            )

        if not plan.steps:

            return {
                "success": False,
                "status": "No action steps to execute.",
                "completed_steps": 0,
                "total_steps": 0,
                "results": [],
            }

        logger.info(
            "Starting multi-command execution: %d step(s)",
            plan.total_steps,
        )
        print("\n[SEMANTIC] PLAN RECEIVED")
        print(f"Total Steps: {plan.total_steps}")

        results = []

        completed_steps = 0

        # -----------------------------------------------------
        # Execute each step sequentially
        # -----------------------------------------------------

        for index, step in enumerate(
            plan.steps
        ):
            print(f"\n[SEMANTIC] ACTION {index + 1}/{plan.total_steps}")
            print(f"[SEMANTIC] DISPATCHING {step.action}")
            print(f"[SEMANTIC] ENTITIES: {step.parameters}")

            logger.info(
                "Executing step %d/%d: %s",
                index + 1,
                plan.total_steps,
                step.action,
            )

            step_result = self.execute_step(
                step
            )

            print(f"[SEMANTIC] DISPATCH RESULT: {step_result.get('status')}")

            results.append(
                step_result
            )

            # -------------------------------------------------
            # Stop immediately if the step failed.
            # -------------------------------------------------

            if not step_result["success"]:
                print("[SEMANTIC] COMMAND FAILED")
                print(f"[SEMANTIC] INTENT: {step.action}")
                print(f"[SEMANTIC] ENTITIES: {step.parameters}")
                print(f"[SEMANTIC] ERROR: {step_result.get('status')}")

                logger.warning(
                    "Multi-command execution stopped at "
                    "step %d/%d.",
                    index + 1,
                    plan.total_steps,
                )

                self._skip_remaining_steps(
                    plan,
                    start_index=index + 1,
                )

                return self._build_execution_summary(
                    plan=plan,
                    results=results,
                    completed_steps=completed_steps,
                    failed_step=step,
                )

            completed_steps += 1

            # Pause briefly if launch_application is followed by a browser action
            if index + 1 < plan.total_steps:
                next_step = plan.steps[index + 1]
                if step.action == "launch_application" and next_step.action in {
                    "play_youtube", "youtube_search", "open_website", "google_search"
                }:
                    print("[SEMANTIC] Pausing 1.0s for browser session to be ready...")
                    import time
                    time.sleep(1.0)

        print("[SEMANTIC] COMMAND COMPLETE\n")
        logger.info(
            "Multi-command execution completed successfully."
        )

        return self._build_execution_summary(
            plan=plan,
            results=results,
            completed_steps=completed_steps,
            failed_step=None,
        )

    # =========================================================
    # Execute One Step
    # =========================================================

    def execute_step(
        self,
        step: ActionStep,
    ) -> Dict[str, Any]:
        """
        Execute a single ActionStep.

        The action is converted into the existing dispatcher
        intent and dispatched through CommandDispatcher.
        """

        if not isinstance(
            step,
            ActionStep,
        ):

            raise TypeError(
                "execute_step() expects an ActionStep."
            )

        step.mark_running()

        try:

            # -------------------------------------------------
            # Resolve action
            # -------------------------------------------------

            intent = self._resolve_intent(
                step.action
            )

            # -------------------------------------------------
            # Convert parameters into dispatcher arguments.
            # -------------------------------------------------

            dispatcher_kwargs = (
                self._build_dispatcher_arguments(
                    step
                )
            )

            logger.debug(
                "Dispatching action '%s' as intent '%s'",
                step.action,
                intent,
            )

            # -------------------------------------------------
            # Existing dispatcher executes the actual action.
            # -------------------------------------------------

            result = self.dispatcher.dispatch(
                intent=intent,
                multi_command=True,
                **dispatcher_kwargs,
            )

            # -------------------------------------------------
            # Verify dispatcher result.
            # -------------------------------------------------

            success = self._verify_result(
                step,
                result,
            )

            if success:

                step.mark_success(
                    result=result
                )

                return {
                    "success": True,
                    "step_id": step.step_id,
                    "action": step.action,
                    "status": self._get_status_text(
                        result,
                        default="Step completed successfully.",
                    ),
                    "result": result,
                }

            # -------------------------------------------------
            # Dispatcher returned failure.
            # -------------------------------------------------

            error_message = (
                self._get_failure_message(
                    result
                )
            )

            step.mark_failed(
                error_message
            )

            return {
                "success": False,
                "step_id": step.step_id,
                "action": step.action,
                "status": error_message,
                "result": result,
            }

        except Exception as exc:

            logger.exception(
                "Error executing action '%s'.",
                step.action,
            )

            step.mark_failed(
                str(exc)
            )

            return {
                "success": False,
                "step_id": step.step_id,
                "action": step.action,
                "status": f"Step execution error: {exc}",
                "result": None,
            }

    # =========================================================
    # Resolve Intent
    # =========================================================

    def _resolve_intent(
        self,
        action: str,
    ) -> str:
        """
        Convert planner action name into the existing
        CommandDispatcher intent name.
        """

        if not action:

            raise ValueError(
                "Action name cannot be empty."
            )

        action = action.strip()

        if action not in self.ACTION_TO_INTENT:

            raise ValueError(
                f"Unsupported multi-command action: {action}"
            )

        return self.ACTION_TO_INTENT[
            action
        ]

    # =========================================================
    # Dispatcher Arguments
    # =========================================================

    def _build_dispatcher_arguments(
        self,
        step: ActionStep,
    ) -> Dict[str, Any]:
        """
        Convert ActionStep parameters into the arguments
        expected by the existing CommandDispatcher.

        Gemini uses clean structured parameters while the
        existing ASTRA dispatcher uses entity, typed_text,
        browser, website, search_query and profile.
        """

        parameters = dict(
            step.parameters or {}
        )

        action = step.action

        # -----------------------------------------------------
        # Word V1 - Create Blank Document
        # -----------------------------------------------------
        #
        # IMPORTANT:
        #
        # This MUST NOT be routed through create_file.
        #
        # WordAgent handles:
        #
        #     create_blank_document
        #
        # without requiring a file name/path.
        #
        # Therefore we intentionally send only the Word intent.
        # -----------------------------------------------------

        if action == "create_blank_document":

            return {}

        # -----------------------------------------------------
        # Launch Application
        # -----------------------------------------------------

        if action == "launch_application":

            return {
                "entity": (
                    parameters.get(
                        "application"
                    )
                    or parameters.get(
                        "target"
                    )
                ),

                "browser": parameters.get(
                    "browser"
                ),

                "website": parameters.get(
                    "website"
                ),

                "profile": parameters.get(
                    "profile"
                ),
            }

        # -----------------------------------------------------
        # Close Application
        # -----------------------------------------------------

        if action == "close_application":

            return {
                "entity": (
                    parameters.get(
                        "application"
                    )
                    or parameters.get(
                        "target"
                    )
                ),
            }

        # -----------------------------------------------------
        # Open Website
        # -----------------------------------------------------

        if action == "open_website":

            website = (
                parameters.get(
                    "website"
                )
                or parameters.get(
                    "url"
                )
                or parameters.get(
                    "target"
                )
            )

            return {
                "entity": website,
                "website": website,

                "browser": parameters.get(
                    "browser"
                ),

                "profile": parameters.get(
                    "profile"
                ),
            }

        # -----------------------------------------------------
        # Google Search
        # -----------------------------------------------------

        if action == "google_search":

            return {
                "search_query": (
                    parameters.get(
                        "query"
                    )
                    or parameters.get(
                        "search_query"
                    )
                ),

                "browser": parameters.get(
                    "browser"
                ),

                "profile": parameters.get(
                    "profile"
                ),
            }

        # -----------------------------------------------------
        # YouTube Search
        # -----------------------------------------------------

        if action == "youtube_search":

            return {
                "search_query": (
                    parameters.get(
                        "query"
                    )
                    or parameters.get(
                        "search_query"
                    )
                ),

                "browser": parameters.get(
                    "browser"
                ),

                "profile": parameters.get(
                    "profile"
                ),
            }

        # -----------------------------------------------------
        # Play YouTube
        # -----------------------------------------------------

        if action == "play_youtube":

            return {
                "search_query": (
                    parameters.get(
                        "query"
                    )
                    or parameters.get(
                        "search_query"
                    )
                    or parameters.get(
                        "song"
                    )
                    or parameters.get(
                        "video"
                    )
                    or parameters.get(
                        "target"
                    )
                    or parameters.get(
                        "entity"
                    )
                ),

                "browser": parameters.get(
                    "browser"
                ),

                "profile": parameters.get(
                    "profile"
                ),
            }

        # -----------------------------------------------------
        # Click Search Result
        # -----------------------------------------------------

        if action == "click_search_result":

            return {
                "entity": str(
                    parameters.get(
                        "index",
                        0
                    )
                ),

                "search_query": parameters.get(
                    "query"
                ),

                "browser": parameters.get(
                    "browser"
                ),
            }

        # -----------------------------------------------------
        # Type Text
        # -----------------------------------------------------

        if action == "type_text":

            return {
                "typed_text": (
                    parameters.get(
                        "text"
                    )
                    or parameters.get(
                        "content"
                    )
                    or ""
                ),
            }

        # -----------------------------------------------------
        # Press Key
        # -----------------------------------------------------

        if action == "press_key":

            return {
                "entity": (
                    parameters.get(
                        "key"
                    )
                    or parameters.get(
                        "target"
                    )
                ),
            }

        # -----------------------------------------------------
        # Code Agent Actions
        # -----------------------------------------------------

        if action in {"code_agent", "write_code"}:
            lang = parameters.get("language") or "python"
            task = parameters.get("task") or parameters.get("query") or parameters.get("code") or parameters.get("description") or ""
            req = f"{lang} program for {task}" if task else str(lang)
            return {
                "entity": parameters,
                "user_text": req,
            }

        # -----------------------------------------------------
        # File Actions
        # -----------------------------------------------------

        if action in {
            "copy_file",
            "move_file",
            "rename_file",
        }:
            if "destination" in parameters or "to" in parameters or "source" in parameters:
                return {
                    "entity": parameters,
                }
            return {
                "entity": (
                    parameters.get(
                        "target"
                    )
                    or parameters.get(
                        "file"
                    )
                    or parameters.get(
                        "filename"
                    )
                    or parameters.get(
                        "name"
                    )
                ),
            }

        if action in {

            "open_file",

            "create_file",

            "delete_file",

        }:

            return {
                "entity": (
                    parameters.get(
                        "target"
                    )
                    or parameters.get(
                        "file"
                    )
                    or parameters.get(
                        "filename"
                    )
                    or parameters.get(
                        "name"
                    )
                ),
            }

        # -----------------------------------------------------
        # Compress File / ZIP
        # -----------------------------------------------------

        if action == "compress_zip":

            return {
                "entity": (
                    parameters.get(
                        "target"
                    )
                    or parameters.get(
                        "file"
                    )
                    or parameters.get(
                        "filename"
                    )
                ),
            }

        # -----------------------------------------------------
        # Extract ZIP
        # -----------------------------------------------------

        if action == "extract_zip":

            return {
                "entity": (
                    parameters.get(
                        "target"
                    )
                    or parameters.get(
                        "zip"
                    )
                    or parameters.get(
                        "file"
                    )
                    or parameters.get(
                        "filename"
                    )
                ),
            }

        # -----------------------------------------------------
        # Folder Actions
        # -----------------------------------------------------

        if action in {
            "copy_folder",
            "move_folder",
            "rename_folder",
        }:
            if "destination" in parameters or "to" in parameters or "source" in parameters:
                return {
                    "entity": parameters,
                }
            return {
                "entity": (
                    parameters.get(
                        "target"
                    )
                    or parameters.get(
                        "folder"
                    )
                    or parameters.get(
                        "name"
                    )
                ),
            }

        if action in {
            "open_folder",
            "create_folder",
            "delete_folder",
        }:

            return {
                "entity": (
                    parameters.get(
                        "target"
                    )
                    or parameters.get(
                        "folder"
                    )
                    or parameters.get(
                        "name"
                    )
                ),
            }

        # -----------------------------------------------------
        # Mouse Actions
        # -----------------------------------------------------

        if action in {

            "click",

            "double_click",

            "right_click",

        }:

            return {
                "entity": (
                    parameters.get(
                        "target"
                    )
                    or parameters.get(
                        "coordinates"
                    )
                ),
            }

        # -----------------------------------------------------
        # Safe Generic Fallback
        # -----------------------------------------------------

        return {
            key: value

            for key, value in parameters.items()

            if key in {

                "entity",

                "typed_text",

                "browser",

                "website",

                "search_query",

                "profile",

            }
        }

    # =========================================================
    # Verification
    # =========================================================

    def _verify_result(
        self,
        step: ActionStep,
        result: Any,
    ) -> bool:
        """
        Verify the result of an executed action.

        Priority:

            1. Custom verifier
            2. Dispatcher result["success"]
            3. Boolean result
            4. Otherwise failure
        """

        if self.verifier is not None:

            try:

                return bool(
                    self.verifier(
                        step,
                        result,
                    )
                )

            except Exception as exc:

                logger.exception(
                    "Custom verification failed: %s",
                    exc,
                )

                return False

        # -----------------------------------------------------
        # Standard dispatcher response
        # -----------------------------------------------------

        if isinstance(
            result,
            dict,
        ):

            return bool(
                result.get(
                    "success",
                    False,
                )
            )

        # -----------------------------------------------------
        # Direct boolean response
        # -----------------------------------------------------

        if isinstance(
            result,
            bool,
        ):

            return result

        return False

    # =========================================================
    # Skip Remaining Steps
    # =========================================================

    def _skip_remaining_steps(
        self,
        plan: ActionPlan,
        start_index: int,
    ) -> None:
        """
        Mark all steps after a failed step as skipped.
        """

        for step in plan.steps[
            start_index:
        ]:

            if step.status == ActionStatus.PENDING:

                step.mark_skipped(
                    "Skipped because a previous step failed."
                )

    # =========================================================
    # Execution Summary
    # =========================================================

    def _build_execution_summary(
        self,
        plan: ActionPlan,
        results: list,
        completed_steps: int,
        failed_step: Optional[ActionStep],
    ) -> Dict[str, Any]:
        """
        Build the final structured execution summary.
        """

        total_steps = plan.total_steps

        if failed_step is None:

            return {
                "success": True,
                "status": (
                    f"Completed all {total_steps} "
                    f"step(s) successfully."
                ),
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "failed_step": None,
                "results": results,
                "plan": plan.to_dict(),
            }

        failed_index = (
            plan.steps.index(
                failed_step
            ) + 1
        )

        return {
            "success": False,
            "status": (
                f"Execution stopped at step "
                f"{failed_index}/{total_steps}."
            ),
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "failed_step": failed_step.to_dict(),
            "results": results,
            "plan": plan.to_dict(),
        }

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _get_status_text(
        result: Any,
        default: str,
    ) -> str:
        """
        Extract a human-readable status from a dispatcher result.
        """

        if isinstance(
            result,
            dict,
        ):

            status = result.get(
                "status"
            )

            if status:

                return str(
                    status
                )

        return default

    @staticmethod
    def _get_failure_message(
        result: Any,
    ) -> str:
        """
        Extract a useful failure message.
        """

        if isinstance(
            result,
            dict,
        ):

            status = result.get(
                "status"
            )

            if status:

                return str(
                    status
                )

            error = result.get(
                "error"
            )

            if error:

                return str(
                    error
                )

        return "Step execution failed."


__all__ = [
    "MultiCommandExecutor",
]