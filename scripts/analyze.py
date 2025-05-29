import boto3
from pathlib import Path
from datetime import datetime

def get_ami_dependencies(region='eu-west-1'):
    ec2 = boto3.client('ec2', region_name=region)
    asg = boto3.client('autoscaling', region_name=region)

    print("🔍 Fetching AMIs...")
    amis = ec2.describe_images(Owners=['self'])['Images']

    print("🔍 Fetching EC2 instance usage...")
    ec2_images_in_use = set()
    reservations = ec2.describe_instances()['Reservations']
    for res in reservations:
        for inst in res['Instances']:
            ec2_images_in_use.add(inst['ImageId'])

    print("🔍 Fetching ASG usage...")
    asg_images_in_use = set()
    asgs = asg.describe_auto_scaling_groups()['AutoScalingGroups']
    for group in asgs:
        if 'LaunchTemplate' in group:
            lt_id = group['LaunchTemplate']['LaunchTemplateId']
            try:
                lt_versions = ec2.describe_launch_template_versions(
                    LaunchTemplateId=lt_id
                )['LaunchTemplateVersions']
                for version in lt_versions:
                    image_id = version['LaunchTemplateData'].get('ImageId')
                    if image_id:
                        asg_images_in_use.add(image_id)
            except Exception:
                continue
        elif 'LaunchConfigurationName' in group:
            lc_name = group['LaunchConfigurationName']
            try:
                lcs = asg.describe_launch_configurations(
                    LaunchConfigurationNames=[lc_name]
                )['LaunchConfigurations']
                for lc in lcs:
                    asg_images_in_use.add(lc.get('ImageId'))
            except Exception:
                continue

    print("✅ Analysis complete.")
    results = []

    for ami in amis:
        ami_id = ami['ImageId']
        snapshot_ids = []
        for mapping in ami.get('BlockDeviceMappings', []):
            ebs = mapping.get('Ebs')
            if ebs and ebs.get('SnapshotId'):
                snapshot_ids.append(ebs['SnapshotId'])

        used_by_ec2 = ami_id in ec2_images_in_use
        used_by_asg = ami_id in asg_images_in_use
        safe_to_delete = not used_by_ec2 and not used_by_asg

        results.append({
            'ami_id': ami_id,
            'name': ami.get('Name', ''),
            'creation_date': ami.get('CreationDate', ''),
            'snapshots': snapshot_ids,
            'used_by_ec2': used_by_ec2,
            'used_by_asg': used_by_asg,
            'safe_to_delete': safe_to_delete
        })

    return results

def generate_html(results):
    html = f"""<html>
<head>
    <title>AMI Dependency Dashboard</title>
    <style>
        body {{ font-family: Arial; padding: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .yes {{ color: green; }}
        .no {{ color: red; }}
    </style>
</head>
<body>
    <h2>📸 AMI Dependency Dashboard - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</h2>
    <table>
        <tr>
            <th>AMI ID</th>
            <th>Name</th>
            <th>Creation Date</th>
            <th>Snapshot IDs</th>
            <th>Used by EC2</th>
            <th>Used by ASG</th>
            <th>Safe to Delete</th>
        </tr>
"""

    for entry in results:
        html += f"""<tr>
            <td>{entry['ami_id']}</td>
            <td>{entry['name']}</td>
            <td>{entry['creation_date']}</td>
            <td>{"<br>".join(entry['snapshots'])}</td>
            <td class="{ 'yes' if entry['used_by_ec2'] else 'no' }">{ '✅' if entry['used_by_ec2'] else '❌' }</td>
            <td class="{ 'yes' if entry['used_by_asg'] else 'no' }">{ '✅' if entry['used_by_asg'] else '❌' }</td>
            <td class="{ 'yes' if entry['safe_to_delete'] else 'no' }">{ '🧹 Yes' if entry['safe_to_delete'] else '❗ No' }</td>
        </tr>
"""

    html += "</table></body></html>"
    Path("output").mkdir(parents=True, exist_ok=True)
    Path("output/results.html").write_text(html)
    print("✅ Saved: output/results.html")

# --------- MAIN ------------------
if __name__ == "__main__":
    region = 'eu-west-1'
    results = get_ami_dependencies(region)
    generate_html(results)
