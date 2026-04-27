import asyncio
import requests
import os
from pathlib import Path
from shiny import App, render, ui, reactive
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse
from starlette.routing import Route, Mount
from starlette.applications import Starlette
from typing import Dict, Any, Optional, List

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
POLL_INTERVAL = 2  # seconds


# API Functions
def get_datasets():
    """Fetch available datasets from the backend"""
    try:
        response = requests.get(f"{BACKEND_URL}/datasets/")
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"Dataset fetch failed: {e}")
        return []


def validate_dataset_name(name: str) -> Optional[str]:
    """Returns None if valid, error message otherwise"""
    try:
        response = requests.post(f"{BACKEND_URL}/datasets/{name}/validate-name")
        if response.status_code == 200:
            return None
        try:
            return response.json().get(
                "detail", f"Name validation failed (HTTP {response.status_code})"
            )
        except Exception:
            return f"Name validation failed (HTTP {response.status_code})"
    except requests.ConnectionError:
        return "Cannot reach the server — is it running?"
    except Exception as e:
        return f"Name validation error: {e}"


def upload_dataset(name: str, file_infos) -> tuple:
    """Upload VCF files to create a new dataset. Returns (success, error_message)."""
    try:
        files = [("files", (f["name"], open(f["datapath"], "rb"))) for f in file_infos]
        response = requests.post(f"{BACKEND_URL}/datasets/{name}/upload", files=files)
        if response.status_code == 202:
            return True, ""
        try:
            detail = response.json().get(
                "detail", f"Upload failed (HTTP {response.status_code})"
            )
        except Exception:
            detail = f"Upload failed (HTTP {response.status_code})"
        return False, detail
    except requests.ConnectionError:
        return False, "Cannot reach the server — is it running?"
    except Exception as e:
        return False, f"Upload error: {e}"


def get_dataset_upload_status(name: str) -> dict:
    try:
        response = requests.get(f"{BACKEND_URL}/datasets/{name}/status")
        if response.status_code == 200:
            return response.json()
        try:
            detail = response.json().get(
                "detail", f"Status check failed (HTTP {response.status_code})"
            )
        except Exception:
            detail = f"Status check failed (HTTP {response.status_code})"
        return {"status": "failed", "error": detail}
    except requests.ConnectionError:
        return {"status": "failed", "error": "Cannot reach the server — is it running?"}
    except Exception as e:
        return {"status": "failed", "error": f"Status check error: {e}"}


def start_job(
    dataset_id: str,
    iqtree_seed: Optional[int] = None,
    mrbayes_seed: Optional[int] = None,
    mrbayes_swapseed: Optional[int] = None,
) -> Optional[str]:
    """Start a new analysis job"""
    try:
        config = {}
        if iqtree_seed is not None:
            config["iqtree_seed"] = iqtree_seed
        if mrbayes_seed is not None:
            config["mrbayes_seed"] = mrbayes_seed
        if mrbayes_swapseed is not None:
            config["mrbayes_swapseed"] = mrbayes_swapseed

        payload: Dict[str, Any] = {"dataset_id": dataset_id}
        if config:
            payload["config"] = config

        response = requests.post(f"{BACKEND_URL}/jobs/create", json=payload)
        if response.status_code == 200:
            return response.json()["job_id"], None
        try:
            detail = response.json().get(
                "detail", f"Job creation failed (HTTP {response.status_code})"
            )
        except Exception:
            detail = f"Job creation failed (HTTP {response.status_code})"
        return None, detail
    except requests.ConnectionError:
        return None, "Cannot reach the server — is it running?"
    except Exception as e:
        return None, f"Job creation error: {e}"


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job status"""
    try:
        response = requests.get(f"{BACKEND_URL}/jobs/{job_id}/status")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Status fetch failed: {e}")
        return None


def get_job_results(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job results"""
    try:
        response = requests.get(f"{BACKEND_URL}/jobs/{job_id}/results")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Results fetch failed: {e}")
        return None


def fetch_results_json(url: str) -> Optional[Dict[str, Any]]:
    """Fetch comparison results JSON"""
    try:
        response = requests.get(f"{BACKEND_URL}{url}")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Results JSON fetch failed: {e}")
        return None


def get_all_jobs(
    dataset_id: Optional[str] = None, sort_order: str = "desc"
) -> List[Dict[str, Any]]:
    """Get all jobs with optional filtering and sorting"""
    try:
        params = {}
        if dataset_id:
            params["dataset_id"] = dataset_id
        if sort_order:
            params["sort_order"] = sort_order

        response = requests.get(f"{BACKEND_URL}/jobs/", params=params)
        if response.status_code == 200:
            return response.json().get("jobs", [])
        return []
    except Exception as e:
        print(f"Jobs fetch failed: {e}")
        return []


def get_job_logs(job_id: str) -> List[Dict[str, Any]]:
    """Get logs for a specific job"""
    try:
        response = requests.get(f"{BACKEND_URL}/logs/{job_id}/history")
        if response.status_code == 200:
            return response.json().get("logs", [])
        return []
    except Exception as e:
        print(f"Logs fetch failed: {e}")
        return []


def format_log_entry(log: Dict[str, Any]) -> str:
    """Format a single log entry for display"""
    try:
        timestamp = log.get("timestamp", "")
        if "T" in timestamp:
            # Convert ISO format to just time
            from datetime import datetime

            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            time_str = dt.strftime("%H:%M:%S")
        else:
            time_str = timestamp

        message = log.get("message", "")

        return f"{time_str} {message}"
    except Exception as e:
        return f"[Error formatting log: {e}]"


# Utility Functions
def format_number(num) -> str:
    """Format numbers for display"""
    if not isinstance(num, (int, float)):
        return str(num)

    if abs(num) < 0.001 and num != 0:
        return f"{num:.8f}"
    elif num % 1 == 0:
        return str(int(num))
    elif abs(num) >= 1:
        return f"{num:.3f}"
    else:
        return f"{num:.6f}"


def is_pipeline_completed(pipeline_status: Dict[str, str]) -> bool:
    """Check if pipeline is completed"""
    tool_order = ["merger", "iqtree", "fastreer", "mrbayes", "comparison"]
    return all(pipeline_status.get(tool) == "completed" for tool in tool_order)


def is_pipeline_failed(pipeline_status: Dict[str, str]) -> bool:
    """Check if pipeline has failed"""
    tool_order = ["merger", "iqtree", "fastreer", "mrbayes", "comparison"]
    return any(pipeline_status.get(tool) == "failed" for tool in tool_order)


def get_current_pipeline_stage(pipeline_status: Dict[str, str]) -> str:
    """Get current pipeline stage description"""
    tool_order = ["merger", "iqtree", "fastreer", "mrbayes", "comparison"]
    tool_names = {
        "merger": "VCF Merging",
        "iqtree": "IQ-TREE Analysis",
        "fastreer": "FastReer Analysis",
        "mrbayes": "MrBayes Analysis",
        "comparison": "Tree Comparison",
    }

    # Check for running tools
    for tool in tool_order:
        if pipeline_status.get(tool) == "running":
            return f"Running: {tool_names[tool]}"

    # Check for failed tools
    if is_pipeline_failed(pipeline_status):
        for tool in tool_order:
            if pipeline_status.get(tool) == "failed":
                return f"Failed: {tool_names[tool]}"

    # Check if completed
    if is_pipeline_completed(pipeline_status):
        return "All Tools Completed"

    # Find next pending tool
    for tool in tool_order:
        if pipeline_status.get(tool) == "pending":
            return f"Waiting for: {tool_names[tool]}"

    return "Pipeline status unavailable — no stage reported yet"


# UI Definition with Query Parameter Routing
def app_ui(request: Request):
    # Get query parameters for routing
    query_params = request.query_params
    page = query_params.get("page", "analysis")  # Default to analysis
    job_id = query_params.get("job_id", "")

    return ui.page_fluid(
        ui.tags.head(
            ui.tags.style("""
                *, *::before, *::after { box-sizing: border-box; }
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f1f5f9; color: #1e293b; line-height: 1.6; }

                /* Page header */
                .page-header { padding: 1.5rem 1.5rem .5rem; max-width: 960px; margin: 0 auto; }
                .page-header h1 { font-size: 1.3rem; font-weight: 700; color: #1e293b; margin: 0; letter-spacing: -.01em; }
                .page-header .page-subtitle { color: #64748b; font-size: .78rem; margin: 3px 0 0; letter-spacing: .02em; }

                /* Navigation bar */
                .nav-bar-inner { max-width: 960px; margin: 0 auto; padding: 0 1rem; display: flex; border-bottom: 1px solid #e2e8f0; }
                .nav-bar .btn { border-radius: 0 !important; border: none !important; border-bottom: 3px solid transparent !important; padding: .75rem 1.25rem !important; color: #64748b; font-weight: 500; font-size: .875rem; background: transparent !important; box-shadow: none !important; transition: color .15s, border-color .15s; }
                .nav-bar .btn:hover { color: #2563eb; border-bottom-color: #93c5fd !important; }

                /* Content wrapper */
                .content-wrapper { max-width: 960px; margin: 0 auto; padding: 2rem 1.5rem; }

                /* Status badges */
                .status-badge { display: inline-flex; align-items: center; padding: 3px 10px; border-radius: 20px; font-weight: 600; font-size: .75em; letter-spacing: .04em; text-transform: uppercase; }
                .status-running  { background: #fef3c7; color: #92400e; }
                .status-completed { background: #d1fae5; color: #065f46; }
                .status-failed   { background: #fee2e2; color: #991b1b; }
                .status-pending  { background: #f1f5f9; color: #64748b; }

                /* Pipeline overview card */
                .pipeline-overview { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,.05); }
                .pipeline-overview h4 { font-size: .95rem; font-weight: 700; color: #1e293b; margin: 0 0 .5rem; }
                .pipeline-overview .overview-intro { color: #64748b; font-size: .82rem; margin-bottom: 1rem; }
                .pipeline-step { display: flex; gap: 12px; align-items: flex-start; padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
                .pipeline-step:last-child { border-bottom: none; padding-bottom: 0; }
                .step-number { width: 26px; height: 26px; border-radius: 50%; background: #dbeafe; color: #1d4ed8; font-weight: 700; font-size: .8em; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px; }
                .step-body strong { font-size: .88rem; color: #1e293b; }
                .step-body p { margin: 2px 0 0; color: #64748b; font-size: .82rem; line-height: 1.4; }

                /* Seeds card */
                .seeds-card { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem 1.5rem; margin-top: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,.05); }
                .seeds-card h5 { font-size: .9rem; font-weight: 700; color: #1e293b; margin: 0 0 .3rem; }
                .seeds-card .seeds-hint { color: #64748b; font-size: .8rem; margin-bottom: 1rem; }

                /* Pipeline status list */
                .pipeline-status-list { border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; background: white; }
                .pipeline-status-item { padding: 11px 16px; border-bottom: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center; transition: background .1s; }
                .pipeline-status-item:last-child { border-bottom: none; }
                .pipeline-status-item:hover { background: #f8fafc; }
                .tool-name { font-weight: 500; color: #374151; font-size: .9em; }

                /* Comparison result cards */
                .comparison-result { background: white; border: 1px solid #e2e8f0; border-radius: 12px; margin: 12px 0; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.05); }
                .comparison-title { padding: 10px 16px; background: #f8fafc; font-weight: 700; font-size: .75em; color: #475569; letter-spacing: .07em; text-transform: uppercase; border-bottom: 1px solid #e2e8f0; }
                .metric { display: flex; justify-content: space-between; margin: 5px 0; }
                .metric-name { color: #64748b; }
                .metric-value { font-weight: bold; }

                /* File items */
                .file-item { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 14px; margin: 6px 0; display: flex; justify-content: space-between; align-items: center; }
                .file-info { display: flex; flex-direction: column; gap: 2px; }
                .file-tool { font-weight: 700; color: #1e293b; font-size: .88em; }
                .file-name { color: #64748b; font-size: .78em; }

                /* Alerts */
                .error-message { background: #fee2e2; color: #991b1b; padding: 12px 16px; border-radius: 8px; border: 1px solid #fecaca; margin: 10px 0; font-size: .88em; }
                .alert { padding: 11px 16px; border-radius: 8px; margin: 10px 0; border: 1px solid transparent; font-size: .88em; }
                .alert-success { background: #d1fae5; color: #065f46; border-color: #a7f3d0; }
                .alert-warning { background: #fef3c7; color: #92400e; border-color: #fde68a; }
                .alert-info    { background: #dbeafe; color: #1e40af; border-color: #bfdbfe; }
                .alert-danger  { background: #fee2e2; color: #991b1b; border-color: #fecaca; }

                /* Job items */
                .job-item { background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 18px; margin: 8px 0; transition: box-shadow .15s, border-color .15s; display: flex; justify-content: space-between; align-items: center; }
                .job-item:hover { box-shadow: 0 4px 14px rgba(0,0,0,.08); border-color: #93c5fd; }
                .job-meta p { margin: 0; }
                .job-id { font-weight: 700; font-size: .9rem; color: #1e293b; }
                .job-dataset { color: #64748b; font-size: .82rem; margin-top: 3px !important; }
                .job-created { color: #94a3b8; font-size: .78rem; margin-top: 2px !important; }

                /* Upload section */
                .upload-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 18px 20px; margin-bottom: 16px; }

                /* Sidebar */
                .sidebar-card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,.05); }

                /* Log container */
                #log-container::-webkit-scrollbar { display: none; }
                #log-container pre { white-space: pre-wrap; word-break: break-all; margin: 0; }

                /* Tree */
                .tree-container { width: 100%; min-height: 500px; background: white; overflow: hidden; cursor: grab; }
                .tree-container:active { cursor: grabbing; }
                .tree-section { border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; margin: 10px 0; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
                .tree-section-header { background: #f8fafc; padding: 10px 16px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; }

                /* Form improvements */
                .form-control { border-radius: 8px !important; border-color: #e2e8f0 !important; font-size: .9rem; }
                .form-control:focus { border-color: #93c5fd !important; box-shadow: 0 0 0 3px rgba(59,130,246,.12) !important; }
                .selectize-input { border-radius: 8px !important; border: 1px solid #e2e8f0 !important; box-shadow: none !important; font-size: .9rem; }
                .selectize-input.focus { border-color: #93c5fd !important; box-shadow: 0 0 0 3px rgba(59,130,246,.12) !important; }

                /* Section headings */
                h2 { font-size: 1.35rem; font-weight: 700; color: #1e293b; margin-bottom: 1rem; }
                h3 { font-size: 1.05rem; font-weight: 600; color: #374151; margin-bottom: .6rem; }
                h4 { font-size: .95rem; font-weight: 600; color: #374151; margin-bottom: .5rem; }
                hr { border-color: #e2e8f0; margin: 1.5rem 0; }
            """),
            ui.tags.script("""
                function redirectToJob(jobId) {
                    window.location.href = '?page=job&job_id=' + jobId;
                }
                
                // Log scroll preservation with MutationObserver
                let userScrolledUp = false;
                let logContainer = null;
                
                function setupLogScrollBehavior() {
                    logContainer = document.getElementById('log-container');
                    if (!logContainer) return;
                    
                    // Track user scroll behavior
                    logContainer.addEventListener('scroll', function() {
                        const isAtBottom = this.scrollHeight - this.scrollTop - this.clientHeight < 50;
                        userScrolledUp = !isAtBottom;
                    });
                    
                    // Monitor for content changes in the log container
                    const logObserver = new MutationObserver(function(mutations) {
                        mutations.forEach(function(mutation) {
                            if (mutation.type === 'childList' || mutation.type === 'subtree') {
                                // Check if user was at bottom before content changed
                                setTimeout(function() {
                                    if (logContainer && !userScrolledUp) {
                                        logContainer.scrollTop = logContainer.scrollHeight;
                                    }
                                }, 10);
                            }
                        });
                    });
                    
                    logObserver.observe(logContainer, {
                        childList: true,
                        subtree: true,
                        characterData: true
                    });
                }
                
                // Setup when page loads
                document.addEventListener('DOMContentLoaded', function() {
                    // Use MutationObserver to detect when log container is added to DOM
                    const pageObserver = new MutationObserver(function(mutations) {
                        const container = document.getElementById('log-container');
                        if (container && !container.hasLogSetup) {
                            container.hasLogSetup = true;
                            setupLogScrollBehavior();
                        }
                    });
                    pageObserver.observe(document.body, { childList: true, subtree: true });

                    // Try setup immediately in case container already exists
                    setTimeout(setupLogScrollBehavior, 100);
                });

                // Immediately disable upload button and show spinner on click
                document.addEventListener('click', function(e) {
                    const btn = e.target.closest('#upload_btn');
                    if (!btn || btn.disabled) return;
                    btn.disabled = true;
                    const container = btn.closest('#upload_btn_output') || btn.parentElement;
                    if (!container.querySelector('.upload-progress')) {
                        const spinner = document.createElement('div');
                        spinner.className = 'upload-progress d-flex align-items-center text-muted mt-2';
                        spinner.style.fontSize = '0.85em';
                        spinner.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span><span>Compressing and uploading...</span>';
                        btn.insertAdjacentElement('afterend', spinner);
                    }
                });
            """),
            ui.tags.script(src="https://d3js.org/d3.v7.min.js"),
            ui.tags.script(
                src=f"/assets/tree_renderer.js?v={int(os.path.getmtime(Path(__file__).parent / 'www' / 'tree_renderer.js'))}"
            ),
        ),
        # Header
        ui.div(
            ui.h1("Phylogenetic Analysis Pipeline"),
            ui.p(
                "VCF phylogenetic analysis — IQ-TREE · FastReeR · MrBayes",
                class_="page-subtitle",
            ),
            class_="page-header",
        ),
        # Navigation
        ui.div(
            ui.div(
                ui.a("Analysis", href="?page=analysis", class_="btn"),
                ui.a("Jobs", href="?page=jobs", class_="btn"),
                class_="nav-bar-inner",
            ),
            class_="nav-bar",
        ),
        # Route-specific content
        ui.div(ui.output_ui("page_content"), class_="content-wrapper"),
        # Hidden inputs for routing
        ui.div(
            ui.input_text("current_page", "", value=page),
            ui.input_text("current_job_id", "", value=job_id),
            style="display: none;",
        ),
        title="Phylogenetic Analysis Pipeline",
    )


# Server Logic
def server(input, output, session):
    # Reactive state
    datasets_list = reactive.value(None)
    selected_dataset = reactive.value(None)
    jobs_list = reactive.value([])
    current_job_data = reactive.value(None)
    current_results_data = reactive.value(None)
    error_message = reactive.value("")
    # Filter state
    jobs_filter_dataset = reactive.value("")
    jobs_sort_order = reactive.value("desc")
    # Logs data
    current_logs = reactive.value("")
    logs_last_seen_timestamp = reactive.value(0)
    # Upload state
    upload_message = reactive.value("")
    upload_error = reactive.value("")
    uploading_dataset = reactive.value(
        None
    )  # name of dataset being compressed, or None

    # Upload status polling
    @reactive.effect
    def poll_upload_status():
        name = uploading_dataset.get()
        if not name:
            return
        reactive.invalidate_later(POLL_INTERVAL)
        status_data = get_dataset_upload_status(name)
        status = status_data.get("status")
        if status == "ready":
            upload_message.set(f"Dataset '{name}' uploaded successfully.")
            upload_error.set("")
            uploading_dataset.set(None)
            datasets_list.set(get_datasets())
            ui.update_text("upload_dataset_name", value="")
        elif status == "failed":
            upload_error.set(
                status_data.get("error") or "Compression failed with an unknown error."
            )
            upload_message.set("")
            uploading_dataset.set(None)

    @render.ui
    def upload_btn_output():
        try:
            files_ready = bool(input.upload_files())
        except Exception:
            files_ready = False
        is_uploading = uploading_dataset.get() is not None
        disabled = not files_ready or is_uploading
        if is_uploading:
            return ui.div(
                ui.input_action_button(
                    "upload_btn", "Confirm Upload", class_="btn btn-success mt-1", disabled=True
                ),
                ui.div(
                    ui.span(class_="spinner-border spinner-border-sm me-2", role="status"),
                    ui.span("Compressing and uploading..."),
                    class_="d-flex align-items-center text-muted mt-2",
                    style="font-size: 0.85em;",
                ),
            )
        return ui.input_action_button(
            "upload_btn", "Confirm Upload", class_="btn btn-success mt-1", disabled=disabled
        )

    # Load initial data
    @reactive.effect
    def load_initial_data():
        datasets = get_datasets()
        datasets_list.set(datasets)
        jobs = get_all_jobs()
        jobs_list.set(jobs)

    # Job status polling for individual job pages
    @reactive.effect
    def poll_current_job():
        job_id = input.current_job_id()
        if not job_id:
            return

        reactive.invalidate_later(POLL_INTERVAL)

        try:
            status_data = get_job_status(job_id)
            if status_data:
                # Clean pipeline status format
                pipeline_raw = status_data.get("pipeline_status", {})
                if isinstance(pipeline_raw, dict):
                    pipeline_status = {}
                    for tool in [
                        "merger",
                        "iqtree",
                        "fastreer",
                        "mrbayes",
                        "comparison",
                    ]:
                        if tool in pipeline_raw:
                            value = pipeline_raw[tool]
                            pipeline_status[tool] = (
                                value if isinstance(value, str) else str(value)
                            )
                        else:
                            pipeline_status[tool] = "pending"
                    status_data["pipeline_status"] = pipeline_status

                # Only update job data if status or pipeline changed
                old_data = current_job_data.get() or {}
                if status_data.get("status") != old_data.get(
                    "status"
                ) or status_data.get("pipeline_status") != old_data.get(
                    "pipeline_status"
                ):
                    current_job_data.set(status_data)

                # Load results once when job is completed; never re-fetch after that
                if current_results_data.get() is None and (
                    status_data.get("status") == "COMPLETED"
                    or is_pipeline_completed(pipeline_status)
                ):
                    results = get_job_results(job_id)
                    if results:
                        current_results_data.set(results)
            else:
                print(f"[POLL] Failed to get status for job {job_id[:8]}")
        except Exception as e:
            print(f"[POLL] Error polling job {job_id[:8]}: {e}")

    # Log polling for job pages
    @reactive.effect
    def poll_job_logs():
        job_id = input.current_job_id()
        page = input.current_page()

        # Only poll logs when on a job page
        if page != "job" or not job_id:
            current_logs.set("")
            return

        # Poll every 2 seconds
        reactive.invalidate_later(POLL_INTERVAL)

        try:
            logs = get_job_logs(job_id)
            if logs:
                # Format logs for display (chronological order)
                formatted_logs = []
                for log in logs:
                    formatted_logs.append(format_log_entry(log))

                log_text = "\n".join(formatted_logs)

                # Only update if content has actually changed
                if log_text != current_logs.get():
                    current_logs.set(log_text)
            else:
                if current_logs.get() != "No logs available yet...":
                    current_logs.set("No logs available yet...")
        except Exception as e:
            error_msg = f"Error loading logs: {e}"
            if current_logs.get() != error_msg:
                current_logs.set(error_msg)

    # Main page content router
    @render.ui
    def page_content():
        page = input.current_page()
        job_id = input.current_job_id()

        # Clear state when navigating away from job pages
        if page != "job":
            current_logs.set("")
            current_job_data.set(None)
            current_results_data.set(None)

        if page == "analysis" or page == "":
            return render_analysis_page()
        elif page == "jobs":
            return render_jobs_page()
        elif page == "job" and job_id:
            return render_job_detail_page(job_id)
        else:
            return ui.div(
                ui.h2("Page Not Found"),
                ui.p("The requested page could not be found."),
                ui.a("Go to Analysis", href="?page=analysis", class_="btn btn-primary"),
            )

    def render_analysis_page():
        datasets = datasets_list.get()
        error = error_message.get()
        u_msg = upload_message.get()
        u_err = upload_error.get()
        uploading_ds = uploading_dataset.get()

        error_ui = ui.div(error, class_="error-message") if error else None

        upload_feedback = None
        if uploading_ds:
            upload_feedback = ui.div(
                ui.tags.span(class_="spinner-border spinner-border-sm me-2"),
                f"Compressing files for '{uploading_ds}'...",
                class_="alert alert-info mt-2",
            )
        elif u_err:
            upload_feedback = ui.div(u_err, class_="alert alert-danger mt-2")
        elif u_msg:
            upload_feedback = ui.div(u_msg, class_="alert alert-success mt-2")

        collapse_class = "collapse show" if u_err else "collapse"

        upload_section = ui.div(
            ui.tags.button(
                "Upload New Dataset",
                **{"data-bs-toggle": "collapse", "data-bs-target": "#upload-collapse"},
                class_="btn btn-outline-secondary mb-2",
                type="button",
            ),
            upload_feedback,
            ui.div(
                ui.input_text(
                    "upload_dataset_name",
                    "Dataset Name",
                    placeholder="e.g. my-samples-2024",
                ),
                ui.p(
                    "Only letters, numbers, hyphens, and underscores.",
                    class_="text-muted mb-2",
                    style="font-size: 0.85em;",
                ),
                ui.input_file(
                    "upload_files",
                    "VCF Files",
                    multiple=True,
                    accept=[".vcf", ".vcf.gz"],
                ),
                ui.p(
                    "Plain .vcf files will be automatically compressed to .vcf.gz on upload.",
                    class_="text-muted mb-2",
                    style="font-size: 0.85em;",
                ),
                ui.output_ui("upload_btn_output"),
                id="upload-collapse",
                class_=f"upload-card {collapse_class}",
            ),
        )

        if datasets is None:
            datasets_content = ui.p("Loading datasets...", class_="text-muted")
        elif not datasets:
            datasets_content = ui.p(
                "No datasets available. Add VCF files to the datasets directory.",
                class_="text-muted",
            )
        else:
            choices_dict = {"": "Select a dataset..."}
            for d in datasets:
                label = (
                    d["name"]
                    if d["vcf_count"] >= 3
                    else f"{d['name']} ({d['vcf_count']} file{'s' if d['vcf_count'] != 1 else ''} — need at least 3)"
                )
                choices_dict[d["name"]] = label

            selected_name = selected_dataset.get()
            selected_ds = next(
                (d for d in datasets if d["name"] == selected_name), None
            )
            insufficient_warning = (
                ui.div(
                    f"This dataset only has {selected_ds['vcf_count']} VCF file{'s' if selected_ds['vcf_count'] != 1 else ''}. At least 3 are required for the pipeline.",
                    class_="alert alert-warning mt-2",
                )
                if selected_ds and selected_ds["vcf_count"] < 3
                else None
            )

            datasets_content = ui.div(
                ui.input_selectize(
                    "selected_dataset_dropdown",
                    "Available Datasets:",
                    choices=choices_dict,
                    selected=selected_name or "",
                    multiple=False,
                ),
                insufficient_warning,
            )

        pipeline_steps = [
            (
                "VCF Merger",
                "Merges all VCF files in the dataset into a single multi-sample VCF file for downstream analysis.",
            ),
            (
                "IQ-TREE",
                "Constructs a maximum-likelihood phylogenetic tree using the GTR substitution model.",
            ),
            (
                "FastReer",
                "Builds a fast neighbor-joining phylogenetic tree as an alternative to ML inference.",
            ),
            (
                "MrBayes",
                "Runs Bayesian phylogenetic inference to estimate a consensus tree with posterior probability support values.",
            ),
            (
                "Comparison",
                "Compares the trees produced by IQ-TREE, FastReer, and MrBayes using topology (RF, weighted RF) and branch-length similarity (Pearson, Spearman) metrics.",
            ),
        ]

        step_items = []
        for i, (title, description) in enumerate(pipeline_steps):
            step_items.append(
                ui.div(
                    ui.div(str(i + 1), class_="step-number"),
                    ui.div(
                        ui.tags.strong(title),
                        ui.p(description),
                        class_="step-body",
                    ),
                    class_="pipeline-step",
                )
            )

        pipeline_info = ui.div(
            ui.h4("Pipeline Overview"),
            ui.p("Tools run automatically in sequence:", class_="overview-intro"),
            *step_items,
            class_="pipeline-overview",
        )

        seeds_ui = ui.div(
            ui.h5("Random Seeds (optional)"),
            ui.p("Leave blank to use defaults.", class_="seeds-hint"),
            ui.div(
                ui.div(
                    ui.input_numeric("iqtree_seed", "IQ-TREE seed", value=None, min=1),
                    class_="col-md-4",
                ),
                ui.div(
                    ui.input_numeric("mrbayes_seed", "MrBayes seed", value=None, min=1),
                    class_="col-md-4",
                ),
                ui.div(
                    ui.input_numeric(
                        "mrbayes_swapseed", "MrBayes swapseed", value=None, min=1
                    ),
                    class_="col-md-4",
                ),
                class_="row",
            ),
            class_="seeds-card",
        )

        return ui.div(
            ui.h2("Start New Analysis"),
            error_ui,
            pipeline_info,
            upload_section,
            ui.p(
                "Select a dataset:",
                style="font-weight:600;font-size:.9rem;margin-bottom:.4rem;",
            ),
            datasets_content,
            seeds_ui,
            ui.div(
                ui.input_action_button(
                    "start_analysis",
                    "Start Analysis",
                    class_="btn btn-success btn-lg mt-3",
                    style="min-width:180px;",
                ),
                class_="text-center",
            ),
        )

    def render_jobs_page():
        jobs = jobs_list.get()
        datasets = datasets_list.get()
        current_dataset_filter = jobs_filter_dataset.get()
        current_sort_order = jobs_sort_order.get()

        # Sidebar with filters
        sidebar = ui.div(
            ui.h4("Filters", class_="mb-3"),
            ui.input_selectize(
                "jobs_filter_dataset_input",
                "Filter by Dataset:",
                choices={
                    "": "All Datasets",
                    **{d["name"]: d["name"] for d in (datasets or [])},
                },
                selected=current_dataset_filter,
                width="100%",
            ),
            ui.input_selectize(
                "jobs_sort_order_input",
                "Sort Order:",
                choices={"desc": "Newest First", "asc": "Oldest First"},
                selected=current_sort_order,
                width="100%",
            ),
            ui.input_action_button(
                "apply_jobs_filter",
                "Apply Filters",
                class_="btn btn-primary w-100 mt-3",
            ),
            class_="col-md-3 sidebar-card",
            style="height: fit-content;",
        )

        # Main content area
        if not jobs:
            main_content = ui.div(
                ui.h2("All Jobs"),
                ui.p(
                    "No jobs found. ",
                    ui.a("Start a new analysis", href="?page=analysis"),
                    ".",
                ),
                class_="col-md-9",
            )
        else:
            job_items = []
            for job in jobs:
                job_id = job.get("_id", "Unknown")
                dataset_id = job.get("dataset_id", "Unknown")
                status = job.get("status", "Unknown")
                created_at = job.get("created_at", "Unknown")

                status_class = f"status-badge status-{status.lower()}"

                job_items.append(
                    ui.div(
                        ui.div(
                            ui.p(
                                [
                                    ui.span(f"Job {job_id[:8]}…", class_="job-id me-2"),
                                    ui.span(status, class_=status_class),
                                ],
                                style="display:flex;align-items:center;gap:8px;margin-bottom:4px;",
                            ),
                            ui.p(
                                [
                                    "Dataset: ",
                                    ui.span(dataset_id, style="font-weight:600;"),
                                ],
                                class_="job-dataset",
                            ),
                            ui.p(f"Created: {created_at}", class_="job-created"),
                            class_="job-meta",
                        ),
                        ui.a(
                            "View →",
                            href=f"?page=job&job_id={job_id}",
                            class_="btn btn-outline-primary btn-sm",
                            style="white-space:nowrap;",
                        ),
                        class_="job-item",
                    )
                )

            main_content = ui.div(ui.h2("All Jobs"), *job_items, class_="col-md-9")

        return ui.div(ui.div(sidebar, main_content, class_="row"))

    def render_job_detail_page(job_id: str):
        job_data = current_job_data.get()
        results_data = current_results_data.get()

        if not job_data:
            return ui.div(
                ui.h2("Job Details"),
                ui.p("Loading job information...", class_="text-muted"),
                ui.a("← Back to Jobs", href="?page=jobs", class_="btn btn-secondary"),
            )

        status = job_data.get("status", "Unknown")
        dataset_id = job_data.get("dataset_id", "Unknown")
        pipeline_status = job_data.get("pipeline_status", {})
        current_stage = get_current_pipeline_stage(pipeline_status)

        # Pipeline status list
        tool_order = ["merger", "iqtree", "fastreer", "mrbayes", "comparison"]
        tool_names = ["VCF Merger", "IQ-TREE", "FastReer", "MrBayes", "Comparison"]
        status_icons = {"pending": "○", "running": "◉", "completed": "✓", "failed": "✗"}

        pipeline_list_items = []
        for tool, name in zip(tool_order, tool_names):
            tool_status = pipeline_status.get(tool, "pending")
            status_class = f"status-badge status-{tool_status}"
            icon = status_icons.get(tool_status, "○")
            pipeline_list_items.append(
                ui.div(
                    ui.span(name, class_="tool-name"),
                    ui.span(f"{icon}  {tool_status.upper()}", class_=status_class),
                    class_="pipeline-status-item",
                )
            )

        content = [
            ui.a("← Back to Jobs", href="?page=jobs", class_="btn btn-secondary mb-3"),
            ui.h2("Job Details"),
            ui.div(
                ui.p(
                    [
                        ui.span("Job ID: ", style="color:#64748b;font-size:.85em;"),
                        ui.span(
                            job_id,
                            style="font-family:monospace;font-size:.85em;font-weight:600;",
                        ),
                    ]
                ),
                ui.p(
                    [
                        ui.span("Dataset: ", style="color:#64748b;font-size:.85em;"),
                        ui.span(dataset_id, style="font-weight:600;font-size:.85em;"),
                    ]
                ),
                ui.p(
                    [
                        ui.span("Stage: ", style="color:#64748b;font-size:.85em;"),
                        ui.span(current_stage, style="font-size:.85em;"),
                    ]
                ),
                style="background:white;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;margin-bottom:1rem;",
            ),
            ui.div(
                ui.h4("Pipeline Status"),
                ui.div(*pipeline_list_items, class_="pipeline-status-list"),
                class_="mb-3",
            ),
        ]

        # Add logs section
        content.append(ui.hr())
        content.append(ui.h3("Logs"))
        content.append(
            ui.div(
                ui.output_text_verbatim("job_logs"),
                id="log-container",
                style="height: 380px; overflow-y: auto; background: #f8fafc; color: #374151; padding: 14px 16px; border: 1px solid #e2e8f0; border-radius: 8px; font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 12.5px; line-height: 1.5; scrollbar-width: none; -ms-overflow-style: none;",
            )
        )

        # Add results if available
        if results_data:
            content.append(ui.hr())
            content.append(ui.h3("Results"))
            content.append(
                ui.div(
                    ui.div(
                        ui.a(
                            "Export HTML",
                            href=f"/export/{job_id}/html",
                            class_="btn btn-outline-secondary btn-sm me-2",
                        ),
                        ui.a(
                            "Export PDF",
                            href=f"/export/{job_id}/pdf",
                            class_="btn btn-outline-secondary btn-sm",
                        ),
                        class_="mb-3",
                    ),
                )
            )

            # NWK Files
            nwk_files = results_data.get("nwk_files", [])
            if nwk_files:
                content.append(ui.h4("Phylogenetic Trees"))
                for file_info in nwk_files:
                    tool_name = file_info.get("tool", "Unknown").upper()
                    filename = file_info.get("filename", "Unknown")
                    file_url = file_info.get("url", "")

                    nwk_content = ""
                    try:
                        nwk_resp = requests.get(f"{BACKEND_URL}{file_url}", timeout=5)
                        if nwk_resp.status_code == 200:
                            nwk_content = nwk_resp.text
                    except Exception:
                        pass

                    tree_viz = (
                        ui.div(
                            **{"data-newick": nwk_content},
                            class_="tree-container",
                            style="display:none;",
                        )
                        if nwk_content
                        else ui.div(
                            ui.p(
                                "Tree visualization unavailable.",
                                class_="text-muted",
                                style="padding:15px;",
                            ),
                            class_="tree-container",
                            style="display:none;",
                        )
                    )

                    content.append(
                        ui.div(
                            ui.div(
                                ui.div(
                                    ui.div(tool_name, class_="file-tool"),
                                    ui.div(filename, class_="file-name"),
                                    class_="file-info",
                                ),
                                ui.div(
                                    ui.tags.button(
                                        "Show Tree",
                                        class_="btn btn-sm btn-outline-secondary tree-toggle-btn me-2",
                                    ),
                                    ui.a(
                                        "Download",
                                        href=f"/nwk{file_url}",
                                        download=f"{job_id}-{file_info.get('tool', 'unknown')}-output.nwk",
                                        class_="btn btn-sm btn-primary",
                                    ),
                                    style="display:flex; gap:6px;",
                                ),
                                class_="file-item tree-section-header",
                            ),
                            tree_viz,
                            class_="tree-section",
                        )
                    )

            # Comparison results
            results_json = results_data.get("results_json")
            if results_json:
                comparison_data = fetch_results_json(results_json.get("url", ""))
                if comparison_data:
                    content.append(ui.h4("Comparison Results"))
                    content.append(
                        ui.div(
                            ui.div(
                                ui.span("Topology (RF): ", style="font-weight:600;"),
                                ui.span(
                                    "Robinson-Foulds distance on unrooted trees — counts differing bipartitions. 100% = identical branching structure."
                                ),
                            ),
                            ui.div(
                                ui.span(
                                    "Branch lengths (Pearson): ",
                                    style="font-weight:600;",
                                ),
                                ui.span(
                                    "Pearson correlation of normalized patristic distances — measures whether relative branch proportions agree, regardless of unit scale."
                                ),
                            ),
                            ui.div(
                                ui.span(
                                    "Branch lengths (Spearman): ",
                                    style="font-weight:600;",
                                ),
                                ui.span(
                                    "Spearman rank correlation of normalized patristic distances — same as Pearson but rank-based, more robust to skewed branch length distributions and outlier branches."
                                ),
                            ),
                            ui.div(
                                ui.span(
                                    "Topology + branch lengths (wRF): ", style="font-weight:600;"
                                ),
                                ui.span(
                                    "Weighted Robinson-Foulds on normalized branch lengths — shared splits contribute |w1−w2|, unshared splits their full length. 100% = identical topology and proportions."
                                ),
                            ),
                            style="font-size:0.8em;color:#6c757d;background:#f8f9fa;border-radius:6px;padding:10px 14px;margin-bottom:14px;display:flex;flex-direction:column;gap:4px;",
                        )
                    )
                    for comparison, metrics in comparison_data.items():
                        title = (
                            comparison.replace("_vs_", " vs ").replace("_", " ").upper()
                        )

                        topo = metrics.get("topology") or {}
                        lengths = metrics.get("branch_lengths") or {}
                        pearson_data = lengths.get("pearson") or {}
                        spearman_data = lengths.get("spearman") or {}
                        wrf_data = metrics.get("weighted_rf") or {}

                        topo_pct = topo.get("similarity_pct")
                        bl_pct = pearson_data.get("similarity_pct")
                        spearman_pct = spearman_data.get("similarity_pct")
                        wrf_pct = wrf_data.get("similarity_pct")

                        def pct_color(pct):
                            if pct is None:
                                return "#6c757d"
                            if pct >= 80:
                                return "#1a7f37"
                            if pct >= 50:
                                return "#856404"
                            return "#cf222e"

                        def pct_bar(pct):
                            if pct is None:
                                return ui.span(
                                    "N/A",
                                    style="color:#6c757d;font-size:1.4em;font-weight:700;",
                                )
                            color = pct_color(pct)
                            return ui.div(
                                ui.div(
                                    style=f"width:{max(0, pct)}%;background:{color};height:8px;border-radius:4px;transition:width 0.3s;",
                                ),
                                style="background:#e9ecef;border-radius:4px;margin-top:4px;",
                            )

                        topo_block = ui.div(
                            ui.span(
                                "Topology (RF)",
                                style="font-weight:600;font-size:0.9em;display:block;min-height:2.8em;",
                            ),
                            ui.span(
                                f"{topo_pct}%" if topo_pct is not None else "N/A",
                                style=f"font-size:1.8em;font-weight:700;color:{pct_color(topo_pct)};display:block;",
                            ),
                            pct_bar(topo_pct),
                            ui.div(
                                ui.span(
                                    f"RF={topo.get('raw_rf', '—')}  norm={format_number(topo.get('normalized_rf', 0))}",
                                    style="color:#6c757d;font-size:0.8em;",
                                )
                                if "raw_rf" in topo
                                else ui.span(""),
                                style="margin-top:4px;",
                            ),
                            style="flex:1;padding:12px 16px;",
                        )

                        pearson_block = ui.div(
                            ui.span(
                                "Branch lengths (Pearson)",
                                style="font-weight:600;font-size:0.9em;display:block;min-height:2.8em;",
                            ),
                            ui.span(
                                f"{bl_pct}%" if bl_pct is not None else "N/A",
                                style=f"font-size:1.8em;font-weight:700;color:{pct_color(bl_pct)};display:block;",
                            ),
                            pct_bar(bl_pct),
                            ui.div(
                                ui.span(
                                    f"r={format_number(pearson_data['r'])}  pairs={pearson_data.get('pairs_used', '—')}",
                                    style="color:#6c757d;font-size:0.8em;",
                                )
                                if "r" in pearson_data
                                else ui.span(
                                    pearson_data.get("reason", ""),
                                    style="color:#6c757d;font-size:0.8em;",
                                ),
                                style="margin-top:4px;",
                            ),
                            style="flex:1;padding:12px 16px;border-left:1px solid #e9ecef;",
                        )

                        spearman_block = ui.div(
                            ui.span(
                                "Branch lengths (Spearman)",
                                style="font-weight:600;font-size:0.9em;display:block;min-height:2.8em;",
                            ),
                            ui.span(
                                f"{spearman_pct}%"
                                if spearman_pct is not None
                                else "N/A",
                                style=f"font-size:1.8em;font-weight:700;color:{pct_color(spearman_pct)};display:block;",
                            ),
                            pct_bar(spearman_pct),
                            ui.div(
                                ui.span(
                                    f"ρ={format_number(spearman_data['r'])}  pairs={spearman_data.get('pairs_used', '—')}",
                                    style="color:#6c757d;font-size:0.8em;",
                                )
                                if "r" in spearman_data
                                else ui.span(
                                    spearman_data.get("reason", ""),
                                    style="color:#6c757d;font-size:0.8em;",
                                ),
                                style="margin-top:4px;",
                            ),
                            style="flex:1;padding:12px 16px;border-left:1px solid #e9ecef;",
                        )

                        wrf_block = ui.div(
                            ui.span(
                                "Topology + branch lengths (wRF)",
                                style="font-weight:600;font-size:0.9em;display:block;min-height:2.8em;",
                            ),
                            ui.span(
                                f"{wrf_pct}%" if wrf_pct is not None else "N/A",
                                style=f"font-size:1.8em;font-weight:700;color:{pct_color(wrf_pct)};display:block;",
                            ),
                            pct_bar(wrf_pct),
                            ui.div(
                                ui.span(
                                    f"d={format_number(wrf_data['wrf_distance'])}",
                                    style="color:#6c757d;font-size:0.8em;",
                                )
                                if "wrf_distance" in wrf_data
                                else ui.span(""),
                                style="margin-top:4px;",
                            ),
                            style="flex:1;padding:12px 16px;border-left:1px solid #e9ecef;",
                        )

                        content.append(
                            ui.div(
                                ui.div(
                                    title,
                                    class_="comparison-title",
                                    style="padding:12px 16px 0;",
                                ),
                                ui.div(
                                    topo_block,
                                    pearson_block,
                                    spearman_block,
                                    wrf_block,
                                    style="display:flex;",
                                ),
                                class_="comparison-result",
                                style="padding:0;",
                            )
                        )

        return ui.div(*content)

    # Handle dataset upload
    @reactive.effect
    @reactive.event(input.upload_btn)
    async def handle_upload():
        try:
            name = input.upload_dataset_name().strip()
            files = input.upload_files()

            upload_message.set("")
            upload_error.set("")

            if not name:
                upload_error.set("Please enter a dataset name.")
                return
            if not files:
                upload_error.set("Please select at least one VCF file.")
                return

            err = validate_dataset_name(name)
            if err:
                upload_error.set(err)
                return

            uploading_dataset.set(name)
            success, error = await asyncio.to_thread(upload_dataset, name, files)
            if success:
                upload_message.set("")
            else:
                uploading_dataset.set(None)
                upload_error.set(error)
        except KeyError:
            pass  # Input doesn't exist on this page
        except Exception as e:
            uploading_dataset.set(None)
            upload_error.set(f"Unexpected error: {e}")

    # Handle dataset selection
    @reactive.effect
    def handle_dataset_selection():
        try:
            selected_value = input.selected_dataset_dropdown()
            if selected_value and selected_value != "":
                selected_dataset.set(selected_value)
                error_message.set("")
            else:
                selected_dataset.set(None)
        except:
            pass  # Input might not exist on other pages

    # Handle starting analysis
    @reactive.effect
    @reactive.event(input.start_analysis)
    def handle_start_analysis():
        dataset = selected_dataset.get()
        if not dataset:
            error_message.set("Please select a dataset first")
            return

        datasets = datasets_list.get() or []
        selected_ds = next((d for d in datasets if d["name"] == dataset), None)
        if selected_ds and selected_ds["vcf_count"] < 3:
            error_message.set(
                f"Dataset '{dataset}' has only {selected_ds['vcf_count']} VCF file(s). At least 3 are required."
            )
            return

        def read_seed(input_fn):
            try:
                val = input_fn()
                return int(val) if val is not None else None
            except Exception:
                return None

        iqtree_seed = read_seed(input.iqtree_seed)
        mrbayes_seed = read_seed(input.mrbayes_seed)
        mrbayes_swapseed = read_seed(input.mrbayes_swapseed)

        job_id, error = start_job(
            dataset,
            iqtree_seed=iqtree_seed,
            mrbayes_seed=mrbayes_seed,
            mrbayes_swapseed=mrbayes_swapseed,
        )
        if job_id:
            # Redirect to job details page using JavaScript
            from shiny import ui

            ui.insert_ui(
                selector="body",
                ui=ui.tags.script(f"redirectToJob('{job_id}');"),
                where="beforeEnd",
            )
        else:
            error_message.set(error)

    # Handle jobs filtering
    @reactive.effect
    @reactive.event(input.apply_jobs_filter)
    def handle_jobs_filter():
        try:
            dataset_filter = input.jobs_filter_dataset_input()
            sort_order = input.jobs_sort_order_input()

            # Persist filter state
            jobs_filter_dataset.set(dataset_filter)
            jobs_sort_order.set(sort_order)

            filtered_jobs = get_all_jobs(
                dataset_id=dataset_filter if dataset_filter else None,
                sort_order=sort_order,
            )
            jobs_list.set(filtered_jobs)
        except KeyError:
            pass  # Inputs might not exist on other pages

    # Render logs output
    @render.text
    def job_logs():
        return current_logs.get()


# Export proxy — browser hits /export/{job_id}/{fmt}, frontend fetches from FastAPI
def export_proxy(request: Request) -> StarletteResponse:
    job_id = request.path_params["job_id"]
    fmt = request.path_params["fmt"]
    try:
        resp = requests.get(f"{BACKEND_URL}/jobs/{job_id}/export/{fmt}", timeout=60)
        return StarletteResponse(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/octet-stream"),
            headers={
                "Content-Disposition": resp.headers.get("content-disposition", "")
            },
        )
    except Exception as e:
        return StarletteResponse(content=f"Export failed: {e}", status_code=502)


# NWK download proxy — browser hits /nwk/static/results/{job_id}/{tool}/{file}
def nwk_proxy(request: Request) -> StarletteResponse:
    path = request.path_params["path"]
    try:
        resp = requests.get(f"{BACKEND_URL}/static/results/{path}", timeout=30)
        parts = path.split("/")
        filename = f"{parts[0]}-{parts[1]}-output.nwk" if len(parts) >= 3 else path.rsplit("/", 1)[-1]
        return StarletteResponse(
            content=resp.content,
            status_code=resp.status_code,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        return StarletteResponse(content=f"Download failed: {e}", status_code=502)


_shiny_app = App(
    app_ui, server, static_assets={"/assets": Path(__file__).parent / "www"}
)

app = Starlette(
    routes=[
        Route("/export/{job_id}/{fmt}", export_proxy),
        Route("/nwk/static/results/{path:path}", nwk_proxy),
        Mount("/", app=_shiny_app),
    ]
)
