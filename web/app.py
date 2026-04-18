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
            return response.json().get("detail", f"Name validation failed (HTTP {response.status_code})")
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
            detail = response.json().get("detail", f"Upload failed (HTTP {response.status_code})")
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
            detail = response.json().get("detail", f"Status check failed (HTTP {response.status_code})")
        except Exception:
            detail = f"Status check failed (HTTP {response.status_code})"
        return {"status": "failed", "error": detail}
    except requests.ConnectionError:
        return {"status": "failed", "error": "Cannot reach the server — is it running?"}
    except Exception as e:
        return {"status": "failed", "error": f"Status check error: {e}"}


def start_job(dataset_id: str, iqtree_seed: Optional[int] = None, mrbayes_seed: Optional[int] = None, mrbayes_swapseed: Optional[int] = None) -> Optional[str]:
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
            detail = response.json().get("detail", f"Job creation failed (HTTP {response.status_code})")
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
                .status-badge { 
                    padding: 4px 8px; 
                    border-radius: 3px; 
                    font-weight: bold; 
                    font-size: 0.9em;
                }
                .status-running { background-color: #fff3cd; color: #856404; }
                .status-completed { background-color: #d4edda; color: #155724; }
                .status-failed { background-color: #f8d7da; color: #721c24; }
                .status-pending { background-color: #e2e3e5; color: #383d41; }
                
                .comparison-result {
                    background: #f8f9fa;
                    border-left: 4px solid #007bff;
                    padding: 15px;
                    margin: 10px 0;
                    border-radius: 0 5px 5px 0;
                }
                .comparison-title { font-weight: bold; margin-bottom: 10px; }
                .metric { display: flex; justify-content: space-between; margin: 5px 0; }
                .metric-name { color: #6c757d; }
                .metric-value { font-weight: bold; }
                
                .file-item {
                    background: #f8f9fa;
                    border: 1px solid #e9ecef;
                    border-radius: 5px;
                    padding: 10px;
                    margin: 5px 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .file-info { display: flex; flex-direction: column; }
                .file-tool { font-weight: bold; color: #495057; font-size: 0.9em; }
                .file-name { color: #6c757d; font-size: 0.8em; }
                
                .error-message {
                    background: #f8d7da;
                    color: #721c24;
                    padding: 12px;
                    border-radius: 5px;
                    border: 1px solid #f5c6cb;
                    margin: 10px 0;
                }
                
                .alert {
                    padding: 12px;
                    border-radius: 5px;
                    margin: 10px 0;
                    border: 1px solid transparent;
                }
                .alert-success {
                    background-color: #d4edda;
                    color: #155724;
                    border-color: #c3e6cb;
                }
                
                .pipeline-status-list {
                    background: #f8f9fa;
                    border-radius: 5px;
                    padding: 15px;
                    border: 1px solid #e9ecef;
                }
                .pipeline-status-item {
                    padding: 8px 0;
                    font-size: 1.1em;
                    border-bottom: 1px solid #e9ecef;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .pipeline-status-item:last-child {
                    border-bottom: none;
                }
                .tool-name {
                    font-weight: 500;
                    color: #495057;
                }
                
                .job-item {
                    background: white;
                    border: 1px solid #e9ecef;
                    border-radius: 5px;
                    padding: 15px;
                    margin: 10px 0;
                    transition: box-shadow 0.2s;
                }
                .job-item:hover {
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                }
                
                /* Hide scrollbar for log container */
                #log-container::-webkit-scrollbar {
                    display: none;
                }

                .tree-container {
                    width: 100%;
                    min-height: 500px;
                    background: white;
                    overflow: hidden;
                    cursor: grab;
                }
                .tree-container:active {
                    cursor: grabbing;
                }
                .tree-section {
                    border: 1px solid #e9ecef;
                    border-radius: 8px;
                    overflow: hidden;
                    margin: 10px 0;
                }
                .tree-section-header {
                    background: #f8f9fa;
                    padding: 10px 15px;
                    border-bottom: 1px solid #e9ecef;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
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
            """),
            ui.tags.script(src="https://d3js.org/d3.v7.min.js"),
            ui.tags.script(src=f"/assets/tree_renderer.js?v={int(os.path.getmtime(Path(__file__).parent / 'www' / 'tree_renderer.js'))}"),
        ),
        # Navigation
        ui.div(
            ui.h1("Phylogenetic Analysis Pipeline", class_="text-center mb-4"),
            ui.div(
                ui.a(
                    "Analysis",
                    href="?page=analysis",
                    class_="btn btn-outline-primary me-2",
                ),
                ui.a("Jobs", href="?page=jobs", class_="btn btn-outline-primary me-2"),
                class_="text-center mb-4",
            ),
            class_="container-fluid",
        ),
        # Route-specific content
        ui.output_ui("page_content"),
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
    uploading_dataset = reactive.value(None)  # name of dataset being compressed, or None

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
            upload_error.set(status_data.get("error") or "Compression failed with an unknown error.")
            upload_message.set("")
            uploading_dataset.set(None)

    @render.ui
    def upload_btn_output():
        try:
            files_ready = bool(input.upload_files())
        except Exception:
            files_ready = False
        disabled = not files_ready or uploading_dataset.get() is not None
        return ui.input_action_button("upload_btn", "Upload", class_="btn btn-primary mt-1", disabled=disabled)

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
                if (
                    status_data.get("status") != old_data.get("status")
                    or status_data.get("pipeline_status") != old_data.get("pipeline_status")
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
                ui.input_text("upload_dataset_name", "Dataset Name", placeholder="e.g. my-samples-2024"),
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
                class_=collapse_class,
                style="background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 20px; margin-bottom: 16px;",
            ),
        )

        if datasets is None:
            datasets_content = ui.p("Loading datasets...", class_="text-muted")
        elif not datasets:
            datasets_content = ui.p("No datasets available. Add VCF files to the datasets directory.", class_="text-muted")
        else:
            choices_dict = {"": "Select a dataset..."}
            for d in datasets:
                label = d["name"] if d["vcf_count"] >= 3 else f"{d['name']} ({d['vcf_count']} file{'s' if d['vcf_count'] != 1 else ''} — need at least 3)"
                choices_dict[d["name"]] = label

            selected_name = selected_dataset.get()
            selected_ds = next((d for d in datasets if d["name"] == selected_name), None)
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
                "1. VCF Merger",
                "Merges all VCF files in the dataset into a single multi-sample VCF file for downstream analysis.",
            ),
            (
                "2. IQ-TREE",
                "Constructs a maximum-likelihood phylogenetic tree using the GTR substitution model.",
            ),
            (
                "3. FastReer",
                "Builds a fast neighbor-joining phylogenetic tree as an alternative to ML inference.",
            ),
            (
                "4. MrBayes",
                "Runs Bayesian phylogenetic inference to estimate a consensus tree with posterior probability support values.",
            ),
            (
                "5. Comparison",
                "Compares the trees produced by IQ-TREE, FastReer, and MrBayes using Robinson-Foulds (RF) distance metrics.",
            ),
        ]

        step_items = []
        for i, (title, description) in enumerate(pipeline_steps):
            is_last = i == len(pipeline_steps) - 1
            step_items.append(
                ui.div(
                    ui.strong(title),
                    ui.p(
                        description, class_="mb-0 text-muted", style="font-size: 0.9em;"
                    ),
                    style=f"padding: 10px 0;{'' if is_last else ' border-bottom: 1px solid #e9ecef;'}",
                )
            )

        pipeline_info = ui.div(
            ui.h4("Pipeline Overview", class_="mb-3"),
            ui.p(
                "The analysis runs the following tools automatically in sequence:",
                class_="text-muted mb-3",
                style="font-size: 0.9em;",
            ),
            *step_items,
            style="background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 20px; margin-bottom: 24px;",
        )

        seeds_ui = ui.div(
            ui.h5("Random Seeds (optional)", class_="mt-4 mb-2"),
            ui.p("Leave blank to use default values.", class_="text-muted mb-3", style="font-size: 0.9em;"),
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
                    ui.input_numeric("mrbayes_swapseed", "MrBayes swapseed", value=None, min=1),
                    class_="col-md-4",
                ),
                class_="row",
            ),
        )

        return ui.div(
            ui.h2("Start New Analysis"),
            error_ui,
            pipeline_info,
            upload_section,
            ui.p("Choose a dataset to start phylogenetic analysis:"),
            datasets_content,
            seeds_ui,
            ui.div(
                ui.input_action_button(
                    "start_analysis",
                    "Start Analysis",
                    class_="btn btn-success btn-lg mt-3",
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
                choices={"": "All Datasets", **{d["name"]: d["name"] for d in (datasets or [])}},
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
            class_="col-md-3",
            style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; height: fit-content;",
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
                            ui.h5(f"Job {job_id[:8]}...", class_="mb-2"),
                            ui.p(f"Dataset: {dataset_id}"),
                            ui.p(["Status: ", ui.span(status, class_=status_class)]),
                            ui.p(f"Created: {created_at}"),
                            ui.a(
                                "View Details",
                                href=f"?page=job&job_id={job_id}",
                                class_="btn btn-primary btn-sm",
                            ),
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

        pipeline_list_items = []
        for tool, name in zip(tool_order, tool_names):
            tool_status = pipeline_status.get(tool, "pending")
            status_class = f"status-badge status-{tool_status}"
            pipeline_list_items.append(
                ui.div(
                    ui.span(f"{name}:", class_="tool-name"),
                    ui.span(tool_status.upper(), class_=status_class),
                    class_="pipeline-status-item",
                )
            )

        content = [
            ui.div(
                ui.a(
                    "← Back to Jobs", href="?page=jobs", class_="btn btn-secondary mb-3"
                )
            ),
            ui.h2("Job Details"),
            ui.div(
                ui.p(f"Job ID: {job_id}"),
                ui.p(f"Dataset: {dataset_id}"),
                ui.p(f"Current Stage: {current_stage}"),
                class_="mb-3",
            ),
            ui.div(
                ui.h4("Pipeline Status"),
                ui.div(*pipeline_list_items, class_="pipeline-status-list"),
                class_="mb-3",
            ),
        ]

        # Add logs section
        content.append(ui.hr())
        content.append(ui.h3("Live Logs"))
        content.append(
            ui.div(
                ui.output_text_verbatim("job_logs"),
                id="log-container",
                style="height: 400px; overflow-y: auto; background: #f8f9fa; color: #212529; padding: 15px; border: 1px solid #dee2e6; border-radius: 5px; font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 13px; line-height: 1.4; scrollbar-width: none; -ms-overflow-style: none;",
            )
        )

        # Add results if available
        if results_data:
            content.append(ui.hr())
            content.append(ui.h3("Results"))
            content.append(
                ui.div(
                    ui.div("Results available.", class_="alert alert-success"),
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
                        ui.div(**{"data-newick": nwk_content}, class_="tree-container", style="display:none;")
                        if nwk_content
                        else ui.div(
                            ui.p("Tree visualization unavailable.", class_="text-muted", style="padding:15px;"),
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
                                        download=filename,
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
                    content.append(ui.p("Topology is compared as unrooted trees.", class_="text-muted", style="font-size:0.85em;margin-bottom:12px;"))
                    for comparison, metrics in comparison_data.items():
                        title = comparison.replace("_vs_", " vs ").replace("_", " ").upper()

                        topo = metrics.get("topology") or {}
                        lengths = metrics.get("branch_lengths") or {}

                        topo_pct = topo.get("similarity_pct")
                        bl_pct = lengths.get("similarity_pct")

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
                                return ui.span("N/A", style="color:#6c757d;font-size:1.4em;font-weight:700;")
                            color = pct_color(pct)
                            return ui.div(
                                ui.div(
                                    style=f"width:{pct}%;background:{color};height:8px;border-radius:4px;transition:width 0.3s;",
                                ),
                                style="background:#e9ecef;border-radius:4px;margin-top:4px;",
                            )

                        topo_block = ui.div(
                            ui.div(
                                ui.span("Topology similarity", style="color:#6c757d;font-size:0.85em;"),
                                ui.span(
                                    f"{topo_pct}%" if topo_pct is not None else "N/A",
                                    style=f"font-size:1.8em;font-weight:700;color:{pct_color(topo_pct)};",
                                ),
                                style="display:flex;justify-content:space-between;align-items:baseline;",
                            ),
                            pct_bar(topo_pct),
                            ui.div(
                                ui.span(f"RF distance: {topo.get('raw_rf', '—')}  |  normalized: {format_number(topo.get('normalized_rf', 0))}", style="color:#6c757d;font-size:0.8em;")
                                if "raw_rf" in topo else ui.span(""),
                                style="margin-top:4px;",
                            ),
                            style="flex:1;padding:12px 16px;",
                        )

                        bl_block = ui.div(
                            ui.div(
                                ui.span("Branch length similarity", style="color:#6c757d;font-size:0.85em;"),
                                ui.span(
                                    f"{bl_pct}%" if bl_pct is not None else "N/A",
                                    style=f"font-size:1.8em;font-weight:700;color:{pct_color(bl_pct)};",
                                ),
                                style="display:flex;justify-content:space-between;align-items:baseline;",
                            ),
                            pct_bar(bl_pct),
                            ui.div(
                                ui.span(
                                    f"Pearson r: {format_number(lengths['pearson_r'])}  |  pairs: {lengths.get('pairs_used', '—')}",
                                    style="color:#6c757d;font-size:0.8em;",
                                )
                                if "pearson_r" in lengths else ui.span(
                                    lengths.get("reason", ""),
                                    style="color:#6c757d;font-size:0.8em;",
                                ),
                                style="margin-top:4px;",
                            ),
                            style="flex:1;padding:12px 16px;border-left:1px solid #e9ecef;",
                        )

                        content.append(
                            ui.div(
                                ui.div(title, class_="comparison-title", style="padding:12px 16px 0;"),
                                ui.div(topo_block, bl_block, style="display:flex;"),
                                class_="comparison-result",
                                style="padding:0;",
                            )
                        )

        return ui.div(*content)

    # Handle dataset upload
    @reactive.effect
    @reactive.event(input.upload_btn)
    def handle_upload():
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

            success, error = upload_dataset(name, files)
            if success:
                upload_message.set("")
                uploading_dataset.set(name)
            else:
                upload_error.set(error)
        except KeyError:
            pass  # Input doesn't exist on this page
        except Exception as e:
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
            error_message.set(f"Dataset '{dataset}' has only {selected_ds['vcf_count']} VCF file(s). At least 3 are required.")
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

        job_id, error = start_job(dataset, iqtree_seed=iqtree_seed, mrbayes_seed=mrbayes_seed, mrbayes_swapseed=mrbayes_swapseed)
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
            headers={"Content-Disposition": resp.headers.get("content-disposition", "")},
        )
    except Exception as e:
        return StarletteResponse(content=f"Export failed: {e}", status_code=502)


# NWK download proxy — browser hits /nwk/static/results/{job_id}/{tool}/{file}
def nwk_proxy(request: Request) -> StarletteResponse:
    path = request.path_params["path"]
    try:
        resp = requests.get(f"{BACKEND_URL}/static/results/{path}", timeout=30)
        filename = path.rsplit("/", 1)[-1]
        return StarletteResponse(
            content=resp.content,
            status_code=resp.status_code,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        return StarletteResponse(content=f"Download failed: {e}", status_code=502)


_shiny_app = App(app_ui, server, static_assets={"/assets": Path(__file__).parent / "www"})

app = Starlette(routes=[
    Route("/export/{job_id}/{fmt}", export_proxy),
    Route("/nwk/static/results/{path:path}", nwk_proxy),
    Mount("/", app=_shiny_app),
])
