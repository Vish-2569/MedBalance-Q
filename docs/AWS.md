# AWS EC2 Standby — MedBalance-Q

Backup demo environment on a single EC2 instance. Cost: **~$0.17/hr** (t3.xlarge on-demand, us-east-1). Terminate when done.

## Prerequisites

- AWS account with EC2 permissions
- Your team's public IP (for the security group)
- A completed `.env` file with real API keys (copy from the demo laptop)

## 1. Launch the instance

| Setting | Value |
|---|---|
| AMI | Ubuntu 24.04 LTS (HVM, SSD) |
| Instance type | t3.xlarge (4 vCPU, 16 GB RAM) |
| Storage | 30 GB gp3 |
| Security group | SSH (22) from **your IP**, TCP 8080 from **your IP** |
| Key pair | Your existing key or create one |

## 2. Upload secrets

From your local machine (never commit `.env`):

```bash
scp -i ~/.ssh/your-key.pem  .env  ubuntu@<EC2-PUBLIC-IP>:/tmp/medbal.env
```

## 3. Run setup

SSH in and run the standby script:

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<EC2-PUBLIC-IP>
sudo REPO_URL=https://github.com/YOUR_ORG/MedBalance-Q.git bash -c \
  "$(curl -fsSL https://raw.githubusercontent.com/YOUR_ORG/MedBalance-Q/main/scripts/aws_standby.sh)"
```

Or clone first and run locally:

```bash
git clone https://github.com/YOUR_ORG/MedBalance-Q.git /opt/medbalance
cd /opt/medbalance
cp /tmp/medbal.env .env
sudo bash scripts/aws_standby.sh
```

The script installs Docker, builds all images, seeds the DB, and starts the stack. First run takes 3-5 minutes. At the end it prints the URL.

## 4. Verify

Open `http://<EC2-PUBLIC-IP>:8080` in a browser. You should see the MedBalance-Q map page with 5 facilities.

## 5. Teardown

Terminate the EC2 instance. The 30 GB gp3 volume is deleted automatically (unless you changed the default).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot connect to the Docker daemon` | `sudo systemctl start docker` |
| Port 8080 unreachable | Check security group allows TCP 8080 from your IP |
| `ERROR: /tmp/medbal.env not found` | Upload with `scp` before running the script |
| Services crash-looping | `cd /opt/medbalance && docker compose logs -f` to find which service; usually a missing key in `.env` |
| Build fails (network) | Re-run `make demo` — Docker layer cache survives |
| Out of disk | Use 40 GB gp3 instead of 30 GB |
