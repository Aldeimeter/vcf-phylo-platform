import requests
import os
from pathlib import Path
from shiny import App, render, ui, reactive
from starlette.requests import Request
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
            return response.json()["job_id"]
        return None
    except Exception as e:
        print(f"Job creation failed: {e}")
        return None


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

    return "Pipeline Status Unknown"


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
    datasets_list = reactive.value([])
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
                for log in logs[-50:]:  # Show last 50 logs
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

        error_ui = ui.div(error, class_="error-message") if error else None

        if not datasets:
            datasets_content = ui.p("Loading datasets...", class_="text-muted")
        else:
            choices = [""] + datasets
            choice_labels = ["Select a dataset..."] + datasets
            choices_dict = dict(zip(choices, choice_labels))

            datasets_content = ui.input_selectize(
                "selected_dataset_dropdown",
                "Available Datasets:",
                choices=choices_dict,
                selected="",
                multiple=False,
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
                choices={"": "All Datasets", **{d: d for d in datasets}},
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
            content.append(ui.div("Results available.", class_="alert alert-success"))

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
                                        href=f"{BACKEND_URL}{file_url}",
                                        target="_blank",
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
                    for comparison, metrics in comparison_data.items():
                        title = (
                            comparison.replace("_vs_", " vs ").replace("_", " ").upper()
                        )

                        metric_items = []
                        if "rf" in metrics:
                            rf_data = metrics["rf"]
                            metric_items.extend(
                                [
                                    ui.div(
                                        ui.span(
                                            "Raw RF Distance:", class_="metric-name"
                                        ),
                                        ui.span(
                                            format_number(rf_data.get("raw_rf", 0)),
                                            class_="metric-value",
                                        ),
                                        class_="metric",
                                    ),
                                    ui.div(
                                        ui.span(
                                            "Normalized RF Distance:",
                                            class_="metric-name",
                                        ),
                                        ui.span(
                                            format_number(
                                                rf_data.get("normalized_rf", 0)
                                            ),
                                            class_="metric-value",
                                        ),
                                        class_="metric",
                                    ),
                                ]
                            )

                        if "wrf" in metrics:
                            metric_items.append(
                                ui.div(
                                    ui.span(
                                        "Weighted RF Distance:", class_="metric-name"
                                    ),
                                    ui.span(
                                        format_number(metrics["wrf"]),
                                        class_="metric-value",
                                    ),
                                    class_="metric",
                                )
                            )

                        content.append(
                            ui.div(
                                ui.div(title, class_="comparison-title"),
                                *metric_items,
                                class_="comparison-result",
                            )
                        )

        return ui.div(*content)

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

        def read_seed(input_fn):
            try:
                val = input_fn()
                return int(val) if val is not None else None
            except Exception:
                return None

        iqtree_seed = read_seed(input.iqtree_seed)
        mrbayes_seed = read_seed(input.mrbayes_seed)
        mrbayes_swapseed = read_seed(input.mrbayes_swapseed)

        job_id = start_job(dataset, iqtree_seed=iqtree_seed, mrbayes_seed=mrbayes_seed, mrbayes_swapseed=mrbayes_swapseed)
        if job_id:
            # Redirect to job details page using JavaScript
            from shiny import ui

            ui.insert_ui(
                selector="body",
                ui=ui.tags.script(f"redirectToJob('{job_id}');"),
                where="beforeEnd",
            )
        else:
            error_message.set("Failed to start analysis. Please try again.")

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
        except:
            pass  # Inputs might not exist on other pages

    # Render logs output
    @render.text
    def job_logs():
        return current_logs.get()


# Create the app with URL bookmarking enabled
app = App(app_ui, server, static_assets={"/assets": Path(__file__).parent / "www"})
