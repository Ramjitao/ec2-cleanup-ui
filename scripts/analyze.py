
# analyze.py - Analyzes AMIs, Snapshots, Volumes and dependencies
import boto3, json

def analyze(region='eu-west-1'):
    ec2 = boto3.client('ec2', region_name=region)
    autoscaling = boto3.client('autoscaling', region_name=region)

    amis = ec2.describe_images(Owners=['self'])['Images']
    result = []

    for ami in amis:
        ami_id = ami['ImageId']
        in_use = False

        ec2_instances = ec2.describe_instances(Filters=[{'Name': 'image-id', 'Values': [ami_id]}])
        if ec2_instances['Reservations']:
            in_use = True

        for asg in autoscaling.describe_auto_scaling_groups()['AutoScalingGroups']:
            lt = asg.get('LaunchTemplate')
            if lt:
                versions = ec2.describe_launch_template_versions(LaunchTemplateId=lt['LaunchTemplateId'])['LaunchTemplateVersions']
                for version in versions:
                    if version['LaunchTemplateData'].get('ImageId') == ami_id:
                        in_use = True

        result.append({
            "ami_id": ami_id,
            "creation_date": ami['CreationDate'],
            "in_use": in_use,
            "name": ami.get("Name", "N/A")
        })

    with open('output/analysis_report.json', 'w') as f:
        json.dump(result, f, indent=2)

if __name__ == '__main__':
    analyze()
