import datetime

import boto3
import requests
from selenium import webdriver

from credentials import USERNAME, PASSWORD


def launch_instance(name, image_id):
    availability_zone = 'us-east-1a'
    ec2_client = boto3.client("ec2", region_name="us-east-1")
    # instance_type = 't2.micro' for testing purposes
    instance_type = 'm5.large'

    if image_id == 'ami-07e7c020b18f3cc8a':
        response = instance_creator(name, image_id, availability_zone,
                                    instance_type)
        instance = response.get('Instances')[0]
        print('Launched instance with Instance Id: [{}]!'
              .format(instance.get('InstanceId')))
        instance_id = instance.get('InstanceId')
        waiter = ec2_client.get_waiter('instance_status_ok')
        waiter.wait(
            InstanceIds=[instance_id]
        )
        if waiter:
            load_dns = ec2_client.describe_instances(InstanceIds=[
                instance_id])['Reservations'][0]['Instances'][0][
                'PublicDnsName']
            print('Instance with DNS: ' + load_dns + ' is up and running')
    else:
        response = instance_creator(name, image_id, availability_zone,
                                    instance_type)
        instance = response.get('Instances')[0]
        print('Launched instance with Instance Id: [{}]!'
              .format(instance.get('InstanceId')))
        instance_id = instance.get('InstanceId')
        waiter = ec2_client.get_waiter('instance_status_ok')
        waiter.wait(
            InstanceIds=[instance_id]
        )
        if waiter:
            web_ser_dns = ec2_client.describe_instances(InstanceIds=[
                instance_id])['Reservations'][0]['Instances'][0][
                'PublicDnsName']
            print('Instance with DNS: ' + web_ser_dns + ' is up and running')
            print('Submitting password and testing....')
            load_dns = fetch_load_dns()
            url_test = connect_load_with_web(load_dns, web_ser_dns)
            print('URL TEST IN MAIN: ' + url_test)
            state = get_state(instance_id)
            test_id = get_test_id(url_test)
            old_test_id = test_id

            # Below check uses the recently created instance and checks
            # if it is running before a new is
            # added and checks that the test remains the same
            # using the testId

            while state == 'running' and old_test_id == test_id:
                rps = get_rps(url_test)

                # get_rps returns None if it runs for the first time
                # as the test page doesn't have yet
                # any '[Current rps=...]'. In this case, I make rps = 0

                rps_fl = 0.0 if rps is None else float(rps)
                print('FLOAT RPS: ' + str(rps_fl))
                time_since_last_serv = get_elapsed_seconds(instance_id)
                print('TIME SINCE LAST SERVICE : '
                      + str(time_since_last_serv))

                # Checking that at least 100 seconds are
                # gone since last instance
                # and that the RPS is 50

                if time_since_last_serv >= 100 and rps_fl < 50.0:
                    response = instance_creator(
                        name, image_id, availability_zone, instance_type)
                    new_instance = response.get('Instances')[0]
                    new_instance_id = new_instance.get('InstanceId')
                    new_waiter = ec2_client.get_waiter('instance_status_ok')
                    new_waiter.wait(
                        InstanceIds=[new_instance_id]
                    )
                    state = get_state(new_instance_id)
                    if new_waiter:
                        new_web_ser_dns = ec2_client.describe_instances(
                            InstanceIds=[new_instance_id])['Reservations'][
                            0]['Instances'][0]['PublicDnsName']
                        add_web_service(load_dns, new_web_ser_dns)
                        print('LAST INSTANCE: ' + instance_id)
                        print('NEW INSTANCE: ' + new_instance_id)
                        instance_id = new_instance_id
                        old_test_id = test_id
                        test_id = get_test_id(url_test)


# Below method connects the web service to the load generator by providing
# my username and password

def connect_load_with_web(load_dns, web_dns):
    url_auth = 'http://' + load_dns + '/password?passwd=' + PASSWORD \
               + '&username=' + USERNAME
    r = requests.get(url_auth)
    url_test = 'http://' + load_dns + '/test/horizontal?dns=' + web_dns
    return url_test


# Below method adds a new web service to the pool of web service

def add_web_service(load_dns, web_dns):
    url = 'http://' + load_dns + '/test/horizontal/add?dns=' + web_dns
    requests.get(url)
    print('ADDED WEB SERVICE: ' + url)


# Below method takes in a URL and using Selenium, it opens that link,
# clicks to the 'Test' link and opens the log of the running test
# and returns the rps by supposing that the latest rps
# is the last line in the text

def get_rps(url_test):
    driver = webdriver.Chrome()
    driver.get(url_test)
    print('URL TEST INSIDE get_rps: ' + url_test)
    driver.find_element_by_link_text('Test').click()
    body = driver.find_element_by_tag_name('body')
    print('BODY INSIDE get_rps METHOD: ' + body.text)

    # Getting all possible characters after 'rps=' before removing ']'
    # which comes at the end of the substring

    all_text = body.text[-20:]
    target = 'rps='
    try:
        rps = all_text[all_text.index(target) + len(target):]
        return rps.replace(']', '')
    except ValueError:
        pass
    except TypeError:
        pass


# Below method takes in a URL and using Selenium, it opens that link,
# clicks to the link with 'Test' and gets to the log of the test
# and returns the testId by finding 'testId=' in the body of the text
# and returning 13 characters following it

def get_test_id(url_test):
    driver = webdriver.Chrome()
    driver.get(url_test)
    driver.find_element_by_link_text('Test').click()
    body = driver.find_element_by_tag_name('body')
    test = body.text
    target = 'testId='
    try:
        test_id = test[test.index(target) + len(target):]
        test_id = test_id[:13]
        return test_id
    except ValueError:
        pass


# Below method fetches the DNS of the load generator starting by describing
# all instances and it returns the one which has 'Load generator'
# as security group

def fetch_load_dns():
    ec2 = boto3.client('ec2', region_name='us-east-1')
    response = ec2.describe_instances()
    for res in response['Reservations']:
        for ins in res['Instances']:
            sec_groups = ins['SecurityGroups']
            for group in sec_groups:
                if len(group) > 0:
                    if group.get('GroupName') == 'Load generator':
                        return ins['PublicDnsName']


# Below method gets the security group, image id, availability zone
# and the instance type and creates an instance

def instance_creator(name, image_id, zone, type):
    key_name = 'connect'
    security_group = name
    ec2_client = boto3.client("ec2", region_name="us-east-1")

    print(zone)

    response = ec2_client.run_instances(
        # DryRun=True,
        ImageId=image_id,
        InstanceType=type,
        KeyName=key_name,
        MaxCount=1,
        MinCount=1,
        Monitoring={
            'Enabled': True
        },
        Placement={
            'AvailabilityZone': zone
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

    return response


# Below methods gets an instance id, calculates the time difference at the
# moment it is called and the time the instance was launched

def get_elapsed_seconds(instance_id):
    diff = 0
    ec2 = boto3.client('ec2', region_name='us-east-1')
    response = ec2.describe_instances()
    for res in response['Reservations']:
        for ins in res['Instances']:
            if ins['InstanceId'] == instance_id:
                now = datetime.datetime.now().astimezone()
                launch_time = ins['LaunchTime']
                diff = now - launch_time
    return diff.total_seconds()


# Below method returns the state of instance given its instance id

def get_state(instance_id):
    state = ''
    ec2 = boto3.client('ec2', region_name='us-east-1')
    response = ec2.describe_instances()
    for res in response['Reservations']:
        for ins in res['Instances']:
            if ins['InstanceId'] == instance_id:
                state = ins['State'].get('Name')
    return state


if __name__ == "__main__":
    launch_instance('Load generator', 'ami-07e7c020b18f3cc8a')
    launch_instance('Elastic load balancer', 'ami-0edaa9c68e6102234')
