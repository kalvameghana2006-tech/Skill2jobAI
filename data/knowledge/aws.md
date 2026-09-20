# AWS

> Core Amazon cloud services: EC2, S3, IAM, RDS, Lambda and VPC networking.
> Category: DevOps & Cloud. Typical effort: about 14 study days.

## Cloud fundamentals

- **Region** — geographic area hosting AWS data centres.
- **IAM** — service controlling who can do what.
- **Shared responsibility** — AWS secures the cloud, you secure what you put in it.

Practice: Create an account with MFA and a least-privilege IAM user.

## Compute and storage

- **EC2** — virtual servers you can launch on demand.
- **S3** — object storage for files of any size.
- **EBS** — block storage attached to an EC2 instance.

Practice: Launch an EC2 instance, connect over SSH and host a file on S3.

## Networking and databases

- **VPC** — your isolated virtual network in AWS.
- **Security group** — virtual firewall for an instance.
- **RDS** — managed relational database service.

Practice: Place an instance in a VPC and open only the ports you need.

## Serverless and cost

- **Lambda** — runs code without managing servers.
- **API Gateway** — fronts Lambda with HTTP endpoints.
- **Free tier and budgets** — alerts that stop surprise bills.

Practice: Deploy a Lambda behind API Gateway and set a budget alert.

## Mini project

Host a static site on S3 and a small API on EC2 or Lambda with IAM roles, documenting the architecture and cost controls.
