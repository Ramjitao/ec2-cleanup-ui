
import boto3
import argparse
import json
from collections import defaultdict

def get_all_available_volumes(region):
    ec2 = boto3.client('ec2', region_name=region)
    paginator = ec2.get_paginator('describe_volumes')
    page_iterator = paginator.paginate(Filters=[{'Name': 'status', 'Values': ['available']}])
    volumes_by_snapshot = defaultdict(list)
    for page in page_iterator:
        for volume in page['Volumes']:
            snapshot_id = volume.get('SnapshotId')
            if snapshot_id:
                volumes_by_snapshot[snapshot_id].append(volume)
    return volumes_by_snapshot

def is_snapshot_used(snapshot_id, region):
    ec2 = boto3.client('ec2', region_name=region)
    autoscaling = boto3.client('autoscaling', region_name=region)
    images = ec2.describe_images(Owners=['self'])['Images']
    image_ids = [img['ImageId'] for img in images if any(
        mapping.get('Ebs', {}).get('SnapshotId') == snapshot_id
        for mapping in img.get('BlockDeviceMappings', [])
    )]
    if not image_ids:
        return False
    reservations = ec2.describe_instances(Filters=[{'Name': 'image-id', 'Values': image_ids}])['Reservations']
    if reservations:
        return True
    asgs = autoscaling.describe_auto_scaling_groups()['AutoScalingGroups']
    for asg in asgs:
        lt = asg.get('LaunchTemplate')
        if lt:
            versions = ec2.describe_launch_template_versions(LaunchTemplateId=lt['LaunchTemplateId'])['LaunchTemplateVersions']
            if any(v['LaunchTemplateData'].get('ImageId') in image_ids for v in versions):
                return True
    return False

def delete_volumes(volumes, region):
    ec2 = boto3.client('ec2', region_name=region)
    for volume in volumes:
        try:
            ec2.delete_volume(VolumeId=volume['VolumeId'])
            print(f"Deleted {volume['VolumeId']}")
        except Exception as e:
            print(f"Failed to delete {volume['VolumeId']}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--yes", action='store_true')
    args = parser.parse_args()

    volumes_by_snapshot = get_all_available_volumes(args.region)
    result_summary = {}

    for snapshot_id, volumes in volumes_by_snapshot.items():
        used = is_snapshot_used(snapshot_id, args.region)
        result_summary[snapshot_id] = {
            "volume_ids": [v['VolumeId'] for v in volumes],
            "in_use": used
        }
        if args.yes:
            delete_volumes(volumes, args.region)

    print(json.dumps(result_summary, indent=2))
