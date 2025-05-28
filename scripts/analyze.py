import boto3
import argparse
import json
import os
from collections import defaultdict

def get_asg_ami_usage(asg_client, ec2_client):
    """Get AMI usage in Auto Scaling Groups (ASGs)."""
    asg_amis = defaultdict(list)
    paginator = asg_client.get_paginator('describe_auto_scaling_groups')

    for page in paginator.paginate():
        for asg in page['AutoScalingGroups']:
            asg_name = asg['AutoScalingGroupName']
            instance_ids = [instance['InstanceId'] for instance in asg['Instances']]

            if not instance_ids:
                continue

            # Describe instances to get ImageIds
            response = ec2_client.describe_instances(InstanceIds=instance_ids)
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    image_id = instance['ImageId']
                    asg_amis[image_id].append(asg_name)
    return asg_amis

def get_all_amis(ec2_client, region):
    """Get all AMIs owned by self."""
    images = ec2_client.describe_images(Owners=['self'])
    ami_list = []
    for img in images['Images']:
        ami_list.append({
            'ImageId': img['ImageId'],
            'Name': img.get('Name', ''),
            'CreationDate': img.get('CreationDate', ''),
            'State': img.get('State', ''),
            'Region': region
        })
    return ami_list

def get_all_snapshots(ec2_client, region):
    """Get all snapshots owned by self."""
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
    """Get all EBS volumes owned by self."""
    volumes = []
    paginator = ec2_client.get_paginator('describe_volumes')
    for page in paginator.paginate():
        for vol in page['Volumes']:
            volumes.append({
                'VolumeId': vol['VolumeId'],
                'Size': vol['Size'],
                'State': vol['State'],
                'CreateTime': vol['CreateTime'].strftime('%Y-%m-%dT%H:%M:%S'),
                'Region': region
            })
    return volumes

def save_to_file(data, filename):
    """Save data as pretty JSON to file inside output directory."""
    os.makedirs('output', exist_ok=True)
    with open(os.path.join('output', filename), 'w') as f:
        json.dump(data, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Analyze AWS EC2 AMIs, Snapshots, Volumes, and ASG usage")
    parser.add_argument('--region', default='eu-west-1', help='AWS region')
    args = parser.parse_args()

    region = args.region

    print(f"Using AWS region: {region}")

    # Create boto3 clients with explicit region
    ec2_client = boto3.client('ec2', region_name=region)
    asg_client = boto3.client('autoscaling', region_name=region)

    # Get data
    print("Fetching AMIs...")
    amis = get_all_amis(ec2_client, region)

    print("Fetching Snapshots...")
    snapshots = get_all_snapshots(ec2_client, region)

    print("Fetching Volumes...")
    volumes = get_all_volumes(ec2_client, region)

    print("Fetching ASG AMI usage...")
    asg_amis = get_asg_ami_usage(asg_client, ec2_client)

    # Save output files
    print("Saving AMIs to output/amis.json")
    save_to_file(amis, 'amis.json')

    print("Saving Snapshots to output/snapshots.json")
    save_to_file(snapshots, 'snapshots.json')

    print("Saving Volumes to output/volumes.json")
    save_to_file(volumes, 'volumes.json')

    print("Saving ASG AMI usage to output/asg_ami_usage.json")
    save_to_file(asg_amis, 'asg_ami_usage.json')

    print("Analyze complete.")

if __name__ == "__main__":
    main()
