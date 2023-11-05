# AWS Load Testing Infrastructure Automation

This Python script automates the deployment and management of an AWS infrastructure designed for load testing. It provisions EC2 instances, sets up auto-scaling, configures load balancers, and implements CloudWatch alarms for scaling decisions based on CPU utilization.

## Prerequisites

- AWS account with proper IAM permissions to create EC2 instances, security groups, auto-scaling groups, load balancers, and CloudWatch alarms.
- Python 3.x installed.
- Boto3 library installed. You can install it using `pip install boto3`.
- Requests library installed. You can install it using `pip install requests`.
- AWS CLI configured with access key, secret key, and default region.

## Setup Instructions

1. **AWS Credentials**: Ensure that your AWS credentials are set up in the `~/.aws/credentials` file or configured through the AWS CLI using `aws configure`.

2. **IAM Role**: The script expects an IAM role with the necessary permissions attached. The role should have policies that allow EC2, AutoScaling, ELB, and CloudWatch operations.

3. **Clone Repository**: Download the Python script to your local machine or a virtual environment where you plan to run the script.

4. **Credentials File**: Create a `credentials.py` file in the same directory as the script with your application's USERNAME and PASSWORD variables:

   ```python
   USERNAME = 'your_username'
   PASSWORD = 'your_password'
   ```

5. **Security Groups**: Uncomment the `create_sec_groups` function calls in the `if __name__ == "__main__":` block to set up initial security groups before running the full script.

6. **Customization**: Modify the constants at the top of the script to match your desired AWS region, instance types, key pair name, and AMI IDs.

## Usage

Run the script with the following command:

```bash
python script_name.py
```

The script will perform the following actions:

- Create security groups for load generator and web service instances.
- Launch a load generator EC2 instance.
- Configure an auto-scaling group and related components.
- Authenticate with the load generator's web service.
- Start a load test and retrieve the test ID from the load generator.

## Components Created

- EC2 Instances: For load generation and web service simulation.
- Security Groups: With rules allowing HTTP traffic.
- Auto-Scaling Group: To automatically scale the number of instances.
- Load Balancer: To distribute incoming traffic across multiple instances.
- CloudWatch Alarms: To trigger scaling actions based on CPU utilization.

## Caution

Running this script will provision AWS resources which may incur costs. Be sure to terminate or delete resources after use to avoid unnecessary charges.
