# Security Guidelines — NetTwin AWS Lab

## Attack Testing Rules

1. **Target only your own instances** — every target must have the tag `Project=nettwin`.
2. **Never attack internet targets** — AWS ToS allows attacking your own resources only.
3. **Rate-limit all tools**:
   - `hping3`: use `-i u10000` (100 pps), **never** `--flood` (AWS throttles at ~500k PPS).
   - `nmap`: use `-T3` (normal timing), avoid `-T5` (insane).
4. **Stop attacks promptly** — press Ctrl+C; don't leave flood scripts running overnight.

## IAM Least Privilege

The `nettwin-ec2-role` IAM role grants **only**:

| Permission | Scope |
|---|---|
| `logs:FilterLogEvents`, `logs:GetLogEvents`, `logs:DescribeLogStreams` | `/vpc/nettwin-flowlogs` log group only |
| `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics` | All (required by API) |
| `ec2:Describe*` (6 read-only actions) | All (read-only) |
| `s3:GetObject`, `s3:ListBucket` | `nettwin-flowlogs-*` bucket only |
| `ce:GetCostAndUsage` | All (read-only) |

The role **cannot**: launch/terminate instances, modify security groups, write to S3, access other buckets, or perform any mutating actions.

## VPC Isolation

- **Private subnet** (`10.0.2.0/24`): no inbound internet access. Egress only via NAT Instance.
- **Public subnet** (`10.0.1.0/24`): SSH and HTTP restricted to your IP via security group.
- **All inter-subnet traffic**: allowed within VPC for realistic enterprise topology.

## SSH Key Management

- EC2 key pair private key (`.pem` file) should **never** be committed to git.
- Rotate keys periodically: create new key pair, update instances, delete old.
- Add to `.gitignore`: `*.pem`, `*.key`

## Terraform State Security

Terraform state files contain sensitive data (resource IDs, IPs, IAM ARNs).

```gitignore
# Add to .gitignore
*.tfstate
*.tfstate.backup
.terraform/
*.pem
*.key
```

## Cost Protection

- Daily cost guard runs via cron: `*/30 * * * * python /app/scripts/aws_cost_guard.py --limit 5`
- Auto-destroy available: `--destroy` flag tears down infrastructure if limit exceeded.
- Monitor via: `GET /api/aws/cost` (when engine is running).

## Incident Response

If you suspect unauthorized access:

1. `terraform destroy -auto-approve` — tear down all resources immediately.
2. Rotate the root access keys in IAM console.
3. Review CloudTrail logs for unauthorized API calls.
