import boto3
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

def get_asg_ami_usage(asg_client, ec2_client):
    asg_amis = defaultdict(list)
    paginator = asg_client.get_paginator('describe_auto_scaling_groups')

    for page in paginator.paginate():
        for asg in page['AutoScalingGroups']:
            asg_name = asg['AutoScalingGroupName']
            instance_ids = [instance['InstanceId'] for instance in asg['Instances']]
            if not instance_ids:
                continue

            response = ec2_client.describe_instances(InstanceIds=instance_ids)
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    image_id = instance['ImageId']
                    asg_amis[image_id].append(asg_name)
    return dict(asg_amis)

def get_all_amis(ec2_client, region):
    images = ec2_client.describe_images(Owners=['self'])
    return [{
        'ImageId': img['ImageId'],
        'Name': img.get('Name', ''),
        'CreationDate': img.get('CreationDate', ''),
        'State': img.get('State', ''),
        'Region': region
    } for img in images['Images']]

def get_all_snapshots(ec2_client, region):
    snapshots = []
    paginator = ec2_client.get_paginator('describe_snapshots')
    for page in paginator.paginate(OwnerIds=['self']):
        for snap in page['Snapshots']:
            snapshots.append({
                'SnapshotId': snap['SnapshotId'],
                'Description': snap.get('Description', ''),
                'StartTime': snap.get('StartTime').strftime('%Y-%m-%dT%H:%M:%S'),
                'VolumeId': snap.get('VolumeId', ''),
                'Region': region
            })
    return snapshots

def get_all_volumes(ec2_client, region):
    volumes = []
    paginator = ec2_client.get_paginator('describe_volumes')
    for page in paginator.paginate():
        for vol in page['Volumes']:
            volumes.append({
                'VolumeId': vol['VolumeId'],
                'Size': vol['Size'],
                'State': vol['State'],
                'CreateTime': vol['CreateTime'].strftime('%Y-%m-%dT%H:%M:%S'),
                'Region': region,
                'Tags': vol.get('Tags', [])
            })
    return volumes

def save_to_file(data, filename):
    os.makedirs('output', exist_ok=True)
    with open(os.path.join('output', filename), 'w') as f:
        json.dump(data, f, indent=2)

def generate_html_report(amis, snapshots, volumes, asg_amis):
    # Build reverse maps
    ami_to_snapshots = defaultdict(list)
    for snap in snapshots:
        desc = snap.get("Description", "")
        if "ami-" in desc:
            parts = desc.split()
            ami_ids = [p for p in parts if p.startswith("ami-")]
            for ami_id in ami_ids:
                ami_to_snapshots[ami_id].append(snap["SnapshotId"])

    ami_to_volumes = defaultdict(list)
    for vol in volumes:
        tags = {tag['Key']: tag['Value'] for tag in vol.get('Tags', [])}
        for val in tags.values():
            if val.startswith("ami-"):
                ami_to_volumes[val].append(vol["VolumeId"])

    rows = ""
    for ami in amis:
        ami_id = ami["ImageId"]
        in_use = "Yes" if ami_id in asg_amis else "No"
        snapshot_ids = ", ".join(ami_to_snapshots.get(ami_id, [])) or "N/A"
        volume_ids = ", ".join(ami_to_volumes.get(ami_id, [])) or "N/A"
        asg_names = ", ".join(asg_amis.get(ami_id, [])) or "N/A"
        created = ami.get("CreationDate", "N/A")

        rows += f"<tr><td>{ami_id}</td><td>{in_use}</td><td>{snapshot_ids}</td><td>{volume_ids}</td><td>{asg_names}</td><td>{created}</td></tr>\n"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>EC2 Cleanup Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; padding: 20px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
    th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
    th {{ background-color: #f4f4f4; }}
  </style>
</head>
<body>
  <h1>EC2 Cleanup Report</h1>
  <table>
    <thead>
      <tr>
        <th>AMI ID</th>
        <th>In Use</th>
        <th>Snapshot ID</th>
        <th>Volume ID(s)</th>
        <th>ASG Name</th>
        <th>Created Date</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
"""
    Path("output/output.html").write_text(html)
    print("Saved output/output.html")

def main():
    parser = argparse.ArgumentParser(description="Analyze AWS EC2 AMIs, Snapshots, Volumes, and ASG usage")
    parser.add_argument('--region', default='eu-west-1', help='AWS region')
    args = parser.parse_args()

    region = args.region
    print(f"Using AWS region: {region}")

    ec2_client = boto3.client('ec2', region_name=region)
    asg_client = boto3.client('autoscaling', region_name=region)

    print("Fetching AMIs...")
    amis = get_all_amis(ec2_client, region)

    print("Fetching Snapshots...")
    snapshots = get_all_snapshots(ec2_client, region)

    print("Fetching Volumes...")
    volumes = get_all_volumes(ec2_client, region)

    print("Fetching ASG AMI usage...")
    asg_amis = get_asg_ami_usage(asg_client, ec2_client)

    # Save JSON files
    save_to_file(amis, 'amis.json')
    save_to_file(snapshots, 'snapshots.json')
    save_to_file(volumes, 'volumes.json')
    save_to_file(asg_amis, 'asg_ami_usage.json')

    # Generate HTML report
    generate_html_report(amis, snapshots, volumes, asg_amis)

    print("Analyze complete.")

if __name__ == "__main__":
    main()
