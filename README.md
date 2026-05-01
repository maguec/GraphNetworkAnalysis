# Networking Graph

## Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk)
- Python 3 or greater and Python PIP 
- [Working Google Cloud CLI](https://cloud.google.com/sdk/docs/install-sdk)
- A Google Cloud project
- [uv](https://docs.astral.sh/uv/getting-started/installation/)


## Setup Spanner Instance

### Create Spanner instance if necessary

```bash
gcloud spanner instances create shared-demos \
    --description="Shared Demos" --config=regional-us-west1 --edition=ENTERPRISE \
    --processing-units=100 --default-backup-schedule-type=NONE
```

### Add a database
```bash
gcloud spanner  databases create networkgraph --instance shared-demos
```

## Setup ENV Vars

```bash
cp env.sample .env
vi .env             #configure the variables
```

## Load the data

```bash
uv run setup_spanner.py
```
