# Phylogenetic Analysis Pipeline

A Docker-based pipeline for phylogenetic analysis of VCF files. The system orchestrates multiple bioinformatics tools (VCF Merger, IQ-TREE, FastReer, MrBayes) through a REST API with a web frontend for visualization.

## Architecture

```
Client → FastAPI → Orchestrator Container
                       ↓
           Local Registry → Tool Containers → Results
```

- **server/** — FastAPI backend, manages jobs and datasets
- **orchestrator/** — Pipeline orchestrator, runs analysis stages
- **web/** — Frontend UI for submitting jobs and viewing results

## Prerequisites

- Docker & Docker Compose

## Installation & Setup

**1. Clone the repository**

```bash
git clone <repo-url>
cd project
```

**2. (Optional) Configure ports**

All host-side ports can be overridden via a `.env` file:

| Variable        | Default | Service         |
| --------------- | ------- | --------------- |
| `FRONTEND_PORT` | `8080`  | Web frontend    |
| `FASTAPI_PORT`  | `8000`  | FastAPI backend |
| `REGISTRY_PORT` | `5000`  | Docker registry |

Example — override ports that conflict on your machine:

```bash
echo "REGISTRY_PORT=5001" >> .env
echo "FRONTEND_PORT=9080" >> .env
```

**3. Run the startup script**

This builds all tool images, pushes them to the local registry, and starts all services:

```bash
./startup.sh
```

## Running

Once startup completes, the following services are available:

| Service  | Default URL                |
| -------- | -------------------------- |
| Frontend | http://localhost:8080      |
| FastAPI  | http://localhost:8000      |
| API docs | http://localhost:8000/docs |
| Registry | http://localhost:5000      |

If you overrode any ports in `.env`, replace the default port accordingly.

## Datasets

Datasets are discovered automatically from the `server/data/datasets/` directory. A folder is recognised as a valid dataset only if it contains at least one `.vcf` or `.vcf.gz` file.

**Adding a dataset:**

1. Create a folder named after your dataset inside `server/data/datasets/`:
   ```
   server/data/datasets/<dataset_id>/
   ```
2. Place one or more `.vcf` / `.vcf.gz` files inside that folder:
   ```
   server/data/datasets/my_cohort/sample1.vcf
   server/data/datasets/my_cohort/sample2.vcf.gz
   ```
3. The dataset will appear automatically in the frontend and API — no restart needed.

> Folders without any VCF files are ignored.

## Usage

Submit an analysis job via the frontend (default: `http://localhost:8080`).

Results are written to `server/data/results/<job_id>/` and can be viewed at `http://localhost:8080/?page=job&job_id=<job_id>` (replace `8080` with your `FRONTEND_PORT` if overridden).

## Management

```bash
# Rebuild everything from scratch
docker-compose down
./startup.sh

# Rebuild only tool images
./build-images.sh

# Stop all services
docker-compose down

# View logs
docker-compose logs -f fastapi
```
