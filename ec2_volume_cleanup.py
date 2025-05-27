import boto3
import time
import argparse
import sys
from collections import defaultdict


def get_all_available_volumes(region='eu-west-1'):
    ec2 = boto3.client('ec2', region_name=region)
    paginator = ec2.get_paginator('describe_volumes')
    page_iterator = paginator.paginate(
        Filters=[{'Name': 'status', 'Values': ['available']}]
    )

    volumes_by_snapshot = defaultdict(list)

    for page in page_iterator:
        for volume in page['Volumes']:
            snapshot_id = volume.get('SnapshotId')
            if snapshot_id:
                volumes_by_snapshot[snapshot_id].append(volume)

    return volumes_by_snapshot


def is_snapshot_used(snapshot_id, region='eu-west-1'):
    ec2 = boto3.client('ec2', region_name=region)
    autoscaling = boto3.client('autoscaling', region_name=region)

    images = ec2.describe_images(Owners=['self'])['Images']
    images_using_snapshot = []

    for image in images:
        for mapping in image.get('BlockDeviceMappings', []):
            ebs = mapping.get('Ebs')
            if ebs and ebs.get('SnapshotId') == snapshot_id:
                images_using_snapshot.append(image)

    if images_using_snapshot:
        image_ids = [img['ImageId'] for img in images_using_snapshot]

        instances = ec2.describe_instances(
            Filters=[{'Name': 'image-id', 'Values': image_ids}]
        )['Reservations']
        if instances:
            return True  # used by EC2

        asgs = autoscaling.describe_auto_scaling_groups()['AutoScalingGroups']
        for asg in asgs:
            lt = asg.get('LaunchTemplate')
            if lt:
                try:
                    template = ec2.describe_launch_template_versions(
                        LaunchTemplateId=lt['LaunchTemplateId']
                    )['LaunchTemplateVersions']
                    for version in template:
                        if version['LaunchTemplateData'].get('ImageId') in image_ids:
                            return True  # used by ASG
                except Exception:
                    continue

    return False


def delete_volumes(volumes, region='eu-west-1'):
    ec2 = boto3.client('ec2', region_name=region)
    for volume in volumes:
        volume_id = volume['VolumeId']
        timeout = 0
        print(f"⏳ Deleting {volume_id} (available)...")
        while True:
            try:
                time.sleep(timeout)
                ec2.delete_volume(VolumeId=volume_id)
                print(f"✅ Deleted: {volume_id}")
                break
            except ec2.exceptions.ClientError as e:
                if 'RateLimit' in str(e) or 'Throttling' in str(e):
                    timeout += 2
                    print(f"⚠️ Throttled. Retrying in {timeout}s...")
                elif 'InvalidVolume.NotFound' in str(e):
                    print(f"❌ Volume {volume_id} not found.")
                    break
                else:
                    print(f"❌ Error deleting {volume_id}: {e}")
                    break


def main():
    parser = argparse.ArgumentParser(description="Clean up detached EBS volumes backed by snapshots.")
    parser.add_argument('--region', default='eu-west-1', help='AWS Region')
    parser.add_argument('--yes', action='store_true', help='Auto confirm deletion (non-interactive mode)')

    args = parser.parse_args()

    volumes_by_snapshot = get_all_available_volumes(args.region)

    if not volumes_by_snapshot:
        print("✅ No available volumes found to delete.")
        sys.exit(0)

    print(f"\n🔍 Found {len(volumes_by_snapshot)} snapshot groups with available volumes.\n")

    for snapshot_id, volumes in volumes_by_snapshot.items():
        print(f"\nSnapshot: {snapshot_id} → {len(volumes)} available volumes")

        in_use = is_snapshot_used(snapshot_id, args.region)
        if in_use:
            print(f"⚠️ Snapshot {snapshot_id} is actively used. Deleting volumes anyway (they're detached).")
        else:
            print(f"✅ Snapshot {snapshot_id} is not actively used.")

        if not args.yes:
            print(f"❌ Interactive confirmation required, but this is a non-interactive environment. Use '--yes' to proceed.")
            sys.exit(1)

        delete_volumes(volumes, args.region)


if __name__ == '__main__':
    main()
