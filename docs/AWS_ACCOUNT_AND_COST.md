# AWS Account Setup and Cost

## Account and reviewer access (assignment requirement)

1. **Use a new AWS account**  
   Do not use an existing or personal account. Create a fresh AWS account for this assignment.

2. **Invite Optifye as Administrator**  
   So that Optifye can review your work:
   - In the AWS Console, go to **IAM** → **Users** (or **Access management**).
   - Choose **Invite users** (or add a user / use AWS Organizations if you prefer).
   - Enter the email: **founders@optifye.ai**.
   - Attach the **AdministratorAccess** policy (or equivalent full access) so they can review all resources.
   - Send the invite. They will receive an email to join your account (or you can share a role ARN / cross-account access as per your chosen method).

If your organization uses AWS Organizations, you can instead create an invite to the organization and grant AdministratorAccess to that account.

## Cost and reimbursement

- Reimbursement is offered up to **₹1000** of AWS costs. Any expense beyond that is your responsibility.

- This setup is designed to stay within a modest budget:
  - **EKS:** SPOT nodes (`capacity_type = "SPOT"`), single NAT gateway, small instance types (e.g. `t3.medium`).
  - **MSK:** Minimal broker count (2) and small instance type (`kafka.t3.small`), small EBS.
  - **RTSP:** Single `t3.micro` instance.
  - **S3:** Lifecycle rule to expire objects after 7 days to limit storage cost.

- Approximate rough monthly ranges (varies by region and usage):
  - EKS control plane: ~$73/month; SPOT nodes: typically much less than on-demand.
  - MSK (2 × kafka.t3.small): on the order of tens of USD per month.
  - t3.micro: a few USD per month.
  - S3 and data transfer: usually low for demo usage.

- Monitor spend in **Cost Explorer** and set a **billing alarm** (e.g. at ₹800) so you stay within the reimbursement limit.
