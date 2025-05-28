import boto3
from datetime import datetime
import json

def get_all_amis(region='eu-west-1'):
    ec2 = boto3.client('ec2', region_name=region)
    response = ec2.describe_images(Owners=['self'])
    return response['Images']

def get_asg_image_ids(region='eu-west-1'):
    autoscaling = boto3.client('autoscaling', region_name=region)
    ec2 = boto3.client('ec2', region_name=region)
    image_ids = set()

    asgs = autoscaling.describe_auto_scaling_groups()['AutoScalingGroups']
    for asg in asgs:
        lt = asg.get('LaunchTemplate')
        if lt:
            versions = ec2.describe_launch_template_versions(LaunchTemplateId=lt['LaunchTemplateId'])['LaunchTemplateVersions']
            for version in versions:
                image_id = version['LaunchTemplateData'].get('ImageId')
                if image_id:
                    image_ids.add(image_id)
    return image_ids

def get_ec2_image_ids(region='eu-west-1'):
    ec2 = boto3.client('ec2', region_name=region)
    instances = ec2.describe_instances()
    image_ids = set()
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            image_ids.add(instance['ImageId'])
    return image_ids

def analyze_ami_dependencies(region='eu-west-1'):
    ec2 = boto3.client('ec2', region_name=region)
    all_amis = get_all_amis(region)
    asg_image_ids = get_asg_image_ids(region)
    ec2_image_ids = get_ec2_image_ids(region)

    ami_report = []

    for ami in all_amis:
        ami_id = ami['ImageId']
        name = ami.get('Name', '')
        creation_date = ami.get('CreationDate', '')
        try:
            creation_date = datetime.strptime(creation_date, "%Y-%m-%dT%H:%M:%S.%fZ").isoformat()
        except:
            creation_date = "Unknown"

        used_by_ec2 = ami_id in ec2_image_ids
        used_by_asg = ami_id in asg_image_ids

        dependencies = []
        for mapping in ami.get('BlockDeviceMappings', []):
            ebs = mapping.get('Ebs')
            if ebs:
                snapshot_id = ebs.get('SnapshotId')
                dependencies.append({
                    "DeviceName": mapping.get('DeviceName'),
                    "SnapshotId": snapshot_id
                })

        ami_report.append({
            "ImageId": ami_id,
            "Name": name,
            "CreationDate": creation_date,
            "UsedByEC2": used_by_ec2,
            "UsedByASG": used_by_asg,
            "BlockDeviceMappings": dependencies
        })

    print(json.dumps(ami_report, indent=2))

# Entry point
if __name__ == "__main__":
    analyze_ami_dependencies()
