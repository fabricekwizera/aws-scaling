import boto3
import requests
from botocore.exceptions import ClientError

from credentials import USERNAME, PASSWORD

AVAILABILITY_ZONE = ['us-east-1a']
KEY_NAME = 'connect'
# INSTANCE_TYPE = 't2.micro'
INSTANCE_TYPE = 'm5.large'


def create_sec_groups(name):
    ec2 = boto3.client('ec2')
    response = ec2.describe_vpcs()
    vpc_id = response.get('Vpcs', [{}])[0].get('VpcId', '')
    try:
        response = ec2.create_security_group(GroupName=name,
                                             Description='Project2.1',
                                             VpcId=vpc_id)
        security_group_id = response['GroupId']

        # Allowing incoming traffic on HTTP 80 and outgoing on all
        ec2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {'IpProtocol': 'tcp',
                 'FromPort': 80,
                 'ToPort': 80,
                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ])

        # Adding tags
        res = boto3.resource('ec2')
        sec_group = res.SecurityGroup(security_group_id)
        sec_group.create_tags(Tags=[
              {
                  'Key': 'Project',
                  'Value': '2.1'
              },
          ])
    except ClientError as e:
        print(e)
    print("Created " + name + " security group")


def launch_load_gen(name):
    image_id = 'ami-07e7c020b18f3cc8a'
    security_group = name
    ec2_client = boto3.client("ec2", region_name="us-east-1")
    availability_zone = AVAILABILITY_ZONE[0]

    response = ec2_client.run_instances(
        DryRun=False,
        ImageId=image_id,
        InstanceType=INSTANCE_TYPE,
        KeyName=KEY_NAME,
        MaxCount=1,
        MinCount=1,
        Monitoring={
            'Enabled': True
        },
        Placement={
            'AvailabilityZone': availability_zone
        },
        SecurityGroups=[
            security_group,
        ],
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Project',
                        'Value': '2.1'
                    },
                ]
            },
        ],
    )

    instance = response.get('Instances')[0]
    print('Launched instance with Instance Id: [{}]!'.format(instance.get('InstanceId')))
    instance_id = instance.get('InstanceId')
    # instance_id = "'" + instance_id + "'"
    print('Load balance ID: ' + instance_id)
    print("Waiting for load balancer to RUN...")
    waiter = ec2_client.get_waiter('instance_running')
    waiter.wait(
        InstanceIds=[instance_id]
    )
    if waiter:
        load_dns = ec2_client.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0][
            'PublicDnsName']
        print("Load DNS: " + load_dns)
        return load_dns


def gen_scaling_group(name):
    config_name = 'project2.1_config'
    image_id = 'ami-0edaa9c68e6102234'
    security_group = name
    scaling_name = 'project2.1_scaling'
    min_size = 1
    max_size = 5
    load_balancer = 'proj21-elb'
    policy_up = 'proj2.1_pol_up'
    policy_down = 'proj2.1_pol_down'

    ec2_client = boto3.client('autoscaling', region_name="us-east-1")

    response = ec2_client.create_launch_configuration(
        LaunchConfigurationName=config_name,
        ImageId=image_id,
        KeyName=KEY_NAME,
        InstanceType=INSTANCE_TYPE,
        SecurityGroups=[
            security_group,
        ],
        InstanceMonitoring={'Enabled': True},

    )

    # print(response)

    response = ec2_client.create_auto_scaling_group(
        AutoScalingGroupName=scaling_name,
        LaunchConfigurationName=config_name,
        MinSize=min_size,
        MaxSize=max_size,
        AvailabilityZones=AVAILABILITY_ZONE,
        Tags=[
            {
                'Key': 'Project',
                'Value': '2.1'
            },
        ]
    )

    # print(response)

    elb = boto3.client('elbv2', region_name="us-east-1")
    ec2 = boto3.client('ec2', region_name="us-east-1")
    all_list = ec2.describe_vpcs()['Vpcs']
    inner_dict = all_list[0]
    vpc_id = inner_dict['VpcId']

    response_elb = elb.create_target_group(
        Name='proj21-tg',
        Protocol='HTTP',
        Port=80,
        TargetType='instance',
        VpcId=vpc_id,

    )

    # print(response_elb)

    all_list = ec2.describe_security_groups()['SecurityGroups']
    inner_dict = all_list[0]
    load_sec_group = inner_dict['GroupId']
    response_elb = elb.create_load_balancer(
        Name=load_balancer,
        SecurityGroups=[
            load_sec_group,
        ],
        Subnets=['subnet-a244278c', 'subnet-710c383b'],
        Tags=[
            {
                'Key': 'Project',
                'Value': '2.1'
            },
        ]
    )

    # print(response_elb)

    all_list = elb.describe_target_groups()['TargetGroups']
    inner_dict = all_list[0]
    tar_group_arn = inner_dict['TargetGroupArn']
    all_list = elb.describe_load_balancers()['LoadBalancers']
    inner_dict = all_list[0]
    listener_arn = inner_dict['LoadBalancerArn']
    response_elb = elb.create_listener(
        DefaultActions=[
            {
                'TargetGroupArn': tar_group_arn,
                'Type': 'forward',
            },
        ],
        LoadBalancerArn=listener_arn,
        Port=80,
        Protocol='HTTP'
    )

    # print(response_elb)

    response = ec2_client.put_scaling_policy(
        AutoScalingGroupName=scaling_name,
        AdjustmentType='ChangeInCapacity',
        PolicyName=policy_up,
        ScalingAdjustment=1,
        Cooldown=60,
    )

    # print(response)

    response = ec2_client.put_scaling_policy(
        AutoScalingGroupName=scaling_name,
        AdjustmentType='ChangeInCapacity',
        PolicyName=policy_down,
        ScalingAdjustment=-1,
        Cooldown=60,
    )

    # print(response)

    alarm_client = boto3.client('cloudwatch')
    response = alarm_client.put_metric_alarm(
        AlarmName='scale_up_cpu',
        EvaluationPeriods=2,
        AlarmDescription='CPU GOES HIGHER THAN 80%',
        MetricName='CPU USAGE',
        Namespace='AWS/EC2',
        Statistic='Average',
        Threshold=60,
        ComparisonOperator='GreaterThanThreshold',
        Period=60,
        Unit='Seconds'
    )

    # print(response)

    response = alarm_client.put_metric_alarm(
        AlarmName='scale_down_cpu',
        EvaluationPeriods=2,
        AlarmDescription='CPU GOES LOWER THAN 20%',
        MetricName='CPU USAGE',
        Namespace='AWS/EC2',
        Statistic='Average',
        Threshold=40,
        ComparisonOperator='LessThanThreshold',
        Period=60,
        Unit='Seconds',
    )

    # print(response)

# Below method gets the DNS of web service
# by supposing that it is the other instance running
# other than the load generator


def fetch_service_dns(load_dns):
    ec2 = boto3.client('ec2', region_name='us-east-1')
    response = ec2.describe_instances()
    for r in response['Reservations']:
        for i in r['Instances']:
            state = i['State']
            if i['InstanceId'] != load_dns and state.get('Name') != 'terminated':
                instance_id = i['InstanceId']
                waiter = ec2.get_waiter('instance_status_ok')
                # print('--------------------------------------- WEB SERVICE INSTANCE ID: ' + instance_id)
                waiter.wait(
                    InstanceIds=[instance_id]
                )
                if waiter:
                    dns = i['PublicDnsName']
                    return dns

                # if i['State'].get('Name') == 'running':
                #    dns = i['PublicDnsName']
                #   return dns


def run():
    load_gen_dns = launch_load_gen('Load generator')
    gen_scaling_group('Elastic load balancer')
    url_auth = 'http://' + load_gen_dns + '/password?passwd=' + PASSWORD + '&username=' + USERNAME
    r = requests.get(url_auth)
    print("JUST GOT TO THE LOAD " + r.text)
    web_ser = fetch_service_dns(load_gen_dns)
    print('WEB SERVICE ' + web_ser)
    url_test = 'http://' + load_gen_dns + '/autoscaling?dns=' + web_ser
    print(url_test)
    r = requests.post(url_test)
    # r = requests.get(url_test)
    # Next thing is to start fetching data from the log URL
    for line in r.text.splitlines():
        if 'testId' in line:
            test_id = line[7:]
            print(test_id)


if __name__ == "__main__":
    # create_sec_groups('Load generator')
    # create_sec_groups('Elastic load balancer')
    # launch_load_gen('Load generator')
    run()

