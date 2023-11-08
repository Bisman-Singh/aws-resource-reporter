#!/usr/bin/env python3
"""Generate reports on AWS resources (EC2, S3, IAM) using boto3."""

import argparse
import json
import csv
import sys
from datetime import datetime
from io import StringIO

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("Error: boto3 is required. Install with: pip install boto3")
    sys.exit(1)


class AWSReporter:
    def __init__(self, profile: str | None = None, region: str = "us-east-1"):
        session_kwargs = {}
        if profile:
            session_kwargs["profile_name"] = profile
        session_kwargs["region_name"] = region
        self.session = boto3.Session(**session_kwargs)
        self.region = region

    def get_ec2_instances(self) -> list[dict]:
        ec2 = self.session.client("ec2")
        instances = []
        try:
            paginator = ec2.get_paginator("describe_instances")
            for page in paginator.paginate():
                for reservation in page["Reservations"]:
                    for inst in reservation["Instances"]:
                        name = ""
                        for tag in inst.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break
                        instances.append({
                            "InstanceId": inst["InstanceId"],
                            "Name": name,
                            "Type": inst["InstanceType"],
                            "State": inst["State"]["Name"],
                            "PrivateIP": inst.get("PrivateIpAddress", "N/A"),
                            "PublicIP": inst.get("PublicIpAddress", "N/A"),
                            "LaunchTime": str(inst.get("LaunchTime", "")),
                        })
        except (ClientError, NoCredentialsError) as e:
            print(f"  EC2 Error: {e}")
        return instances

    def get_s3_buckets(self) -> list[dict]:
        s3 = self.session.client("s3")
        buckets = []
        try:
            response = s3.list_buckets()
            for bucket in response.get("Buckets", []):
                name = bucket["Name"]
                created = str(bucket.get("CreationDate", ""))

                try:
                    location = s3.get_bucket_location(Bucket=name)
                    region = location.get("LocationConstraint") or "us-east-1"
                except ClientError:
                    region = "unknown"

                try:
                    s3.get_bucket_versioning(Bucket=name)
                    versioning = "Enabled"
                except ClientError:
                    versioning = "Unknown"

                buckets.append({
                    "BucketName": name,
                    "Region": region,
                    "Created": created,
                    "Versioning": versioning,
                })
        except (ClientError, NoCredentialsError) as e:
            print(f"  S3 Error: {e}")
        return buckets

    def get_iam_users(self) -> list[dict]:
        iam = self.session.client("iam")
        users = []
        try:
            paginator = iam.get_paginator("list_users")
            for page in paginator.paginate():
                for user in page["Users"]:
                    username = user["UserName"]

                    groups = []
                    try:
                        g_resp = iam.list_groups_for_user(UserName=username)
                        groups = [g["GroupName"] for g in g_resp["Groups"]]
                    except ClientError:
                        pass

                    mfa = False
                    try:
                        m_resp = iam.list_mfa_devices(UserName=username)
                        mfa = len(m_resp["MFADevices"]) > 0
                    except ClientError:
                        pass

                    users.append({
                        "UserName": username,
                        "UserId": user["UserId"],
                        "Created": str(user.get("CreateDate", "")),
                        "LastActivity": str(user.get("PasswordLastUsed", "Never")),
                        "Groups": ", ".join(groups) or "None",
                        "MFA": "Yes" if mfa else "No",
                    })
        except (ClientError, NoCredentialsError) as e:
            print(f"  IAM Error: {e}")
        return users

    def get_security_groups(self) -> list[dict]:
        ec2 = self.session.client("ec2")
        sgs = []
        try:
            response = ec2.describe_security_groups()
            for sg in response["SecurityGroups"]:
                open_ports = []
                for rule in sg.get("IpPermissions", []):
                    for ip_range in rule.get("IpRanges", []):
                        if ip_range.get("CidrIp") == "0.0.0.0/0":
                            port = rule.get("FromPort", "All")
                            open_ports.append(str(port))
                sgs.append({
                    "GroupId": sg["GroupId"],
                    "GroupName": sg["GroupName"],
                    "VpcId": sg.get("VpcId", "N/A"),
                    "Description": sg.get("Description", ""),
                    "OpenPorts": ", ".join(open_ports) or "None",
                })
        except (ClientError, NoCredentialsError) as e:
            print(f"  SG Error: {e}")
        return sgs


def print_table(title: str, data: list[dict]):
    if not data:
        print(f"\n{title}: No data found.\n")
        return

    print(f"\n{'=' * 80}")
    print(f" {title} ({len(data)} items)")
    print(f"{'=' * 80}")

    headers = list(data[0].keys())
    col_widths = {h: max(len(h), max(len(str(row.get(h, ""))) for row in data)) for h in headers}

    header_line = " | ".join(h.ljust(col_widths[h]) for h in headers)
    print(header_line)
    print("-" * len(header_line))

    for row in data:
        print(" | ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers))


def export_csv(data: list[dict], filename: str):
    if not data:
        return
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"  Exported to {filename}")


def export_json(report: dict, filename: str):
    with open(filename, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  Exported to {filename}")


def main():
    parser = argparse.ArgumentParser(description="AWS Resource Reporter")
    parser.add_argument("--profile", "-p", help="AWS profile name")
    parser.add_argument("--region", "-r", default="us-east-1", help="AWS region")
    parser.add_argument("--services", "-s", nargs="+", default=["all"],
                        choices=["all", "ec2", "s3", "iam", "sg"],
                        help="Services to report on")
    parser.add_argument("--export-csv", action="store_true", help="Export to CSV files")
    parser.add_argument("--export-json", help="Export full report to JSON file")
    args = parser.parse_args()

    print(f"AWS Resource Reporter")
    print(f"Region: {args.region} | Profile: {args.profile or 'default'}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    reporter = AWSReporter(profile=args.profile, region=args.region)
    services = args.services if "all" not in args.services else ["ec2", "s3", "iam", "sg"]
    report = {}

    if "ec2" in services:
        print("\nFetching EC2 instances...")
        data = reporter.get_ec2_instances()
        report["ec2"] = data
        print_table("EC2 Instances", data)
        if args.export_csv:
            export_csv(data, "ec2_instances.csv")

    if "s3" in services:
        print("\nFetching S3 buckets...")
        data = reporter.get_s3_buckets()
        report["s3"] = data
        print_table("S3 Buckets", data)
        if args.export_csv:
            export_csv(data, "s3_buckets.csv")

    if "iam" in services:
        print("\nFetching IAM users...")
        data = reporter.get_iam_users()
        report["iam"] = data
        print_table("IAM Users", data)
        if args.export_csv:
            export_csv(data, "iam_users.csv")

    if "sg" in services:
        print("\nFetching Security Groups...")
        data = reporter.get_security_groups()
        report["security_groups"] = data
        print_table("Security Groups", data)
        if args.export_csv:
            export_csv(data, "security_groups.csv")

    if args.export_json:
        export_json(report, args.export_json)

    print(f"\nReport complete.")


if __name__ == "__main__":
    main()
