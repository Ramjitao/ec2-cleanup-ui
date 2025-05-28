import boto3
import argparse
import os
from datetime import datetime

def get_all_amis(ec2_client):
    response = ec2_client.describe_images(Owners=['self'])
    return response['Images']

def get_all_instances(ec2_client):
    response = ec2_client.describe_instances()
    instances = []
    for reservation in response['Reservations']:
        instances.extend(reservation['Instances'])
    return instances

def get_asg_ami_usage(asg_client):
    asg_ami_map = {}
    response = asg_client.describe_auto_scaling_groups()
    for group in response['AutoScalingGroups']:
        if group.get('LaunchTemplate'):
            lt = group['LaunchTemplate']
            version = lt.get('Version') or '$Default'
            lt_client = boto3.client('ec2')
            lt_data = lt_client.describe_launch_template_versions(
                LaunchTemplateId=lt['LaunchTemplateId'],
                Versions=[version]
            )
            ami_id = lt_data['LaunchTemplateVersions'][0]['LaunchTemplateData'].get('ImageId')
            if ami_id:
                asg_ami_map[ami_id] = group['AutoScalingGroupName']
        elif group.get('LaunchConfigurationName'):
            lc_name = group['LaunchConfigurationName']
            lc_resp = asg_client.describe_launch_configurations(LaunchConfigurationNames=[lc_name])
            for lc in lc_resp['LaunchConfigurations']:
                ami_id = lc['ImageId']
                asg_ami_map[ami_id] = group['AutoScalingGroupName']
    return asg_ami_map

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--region', required=True, help='AWS region')
    args = parser.parse_args()

    ec2_client = boto3.client('ec2', region_name=args.region)
    asg_client = boto3.client('autoscaling', region_name=args.region)

    amis = get_all_amis(ec2_client)
    instances = get_all_instances(ec2_client)
    asg_usage = get_asg_ami_usage(asg_client)

    in_use_amis = set()
    for instance in instances:
        if 'ImageId' in instance:
            in_use_amis.add(instance['ImageId'])

    os.makedirs("output", exist_ok=True)
    with open("output/results.txt", "w") as f:
        header = "AMI ID | In Use | Snapshot ID | Volume ID(s) | ASG Name | Created Date"
        f.write(header + "\n")

        for ami in amis:
            ami_id = ami['ImageId']
            creation_date = ami.get('CreationDate', '')[:10]
            snapshot_ids = []
            volume_ids = []

            for bd in ami.get('BlockDeviceMappings', []):
                if 'Ebs' in bd:
                    snapshot_id = bd['Ebs'].get('SnapshotId')
                    if snapshot_id:
                        snapshot_ids.append(snapshot_id)

            # Try to get volume ids from snapshots
            for snap_id in snapshot_ids:
                try:
                    snap = ec2_client.describe_snapshots(SnapshotIds=[snap_id])['Snapshots'][0]
                    volume_id = snap.get('VolumeId')
                    if volume_id:
                        volume_ids.append(volume_id)
                except Exception:
                    pass  # snapshot may be shared or deleted

            in_use = "Yes" if ami_id in in_use_amis or ami_id in asg_usage else "No"
            asg_name = asg_usage.get(ami_id, "-")
            line = f"{ami_id} | {in_use} | {','.join(snapshot_ids)} | {','.join(volume_ids)} | {asg_name} | {creation_date}"
            f.write(line + "\n")

    print("✅ Analysis complete. Results written to output/results.txt")

if __name__ == "__main__":
    main()
