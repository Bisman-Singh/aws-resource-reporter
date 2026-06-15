# AWS Resource Reporter

Generate comprehensive reports on AWS resources including EC2, S3, IAM, and Security Groups.

## Features

- EC2 instance inventory (name, type, state, IPs, launch time)
- S3 bucket listing with region and versioning status
- IAM user audit (groups, MFA status, last activity)
- Security group analysis (open ports to 0.0.0.0/0)
- Export to CSV or JSON
- AWS profile and region support

## Usage

```bash
pip install -r requirements.txt

# Report all services (requires AWS credentials configured)
python main.py

# Specific services
python main.py --services ec2 s3

# Use a specific AWS profile and region
python main.py --profile myprofile --region eu-west-1

# Export to CSV
python main.py --export-csv

# Export full report to JSON
python main.py --export-json report.json
```

## Prerequisites

AWS credentials must be configured via `~/.aws/credentials`, environment variables, or IAM role.

<sub><sup>Originally developed and tested locally during learning. Later organized and pushed to GitHub for portfolio visibility.</sup></sub>
