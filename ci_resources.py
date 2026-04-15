"""
Worker AMI CI on AWS (CodeBuild + GitHub Actions OIDC trigger role).

**Same Pulumi stack vs separate project**

- **Same stack (here)** fits a single product/account: app resources and the CodeBuild
  project + trigger IAM stay in one ``pulumi up``, outputs feed directly into GitHub
  secrets/variables.
- **Separate Pulumi project** fits shared build farms, different owners, or lifecycle
  where you tear down app stacks but keep CI. Use it if CI outgrows this repo.

**CodePipeline** is optional. Worker pushes already start CodeBuild via GitHub Actions;
a pipeline would add another orchestration layer (e.g. source on the AMI repo only).
Most teams either **GHA → CodeBuild** (this setup) or **CodePipeline → CodeBuild**, not both
for the same build.

Prerequisites:

1. **AWS CodeConnections** (formerly *CodeStar Connections*, rebranded March 2024): create a
   connection to GitHub in the console (Developer Tools → **Settings** → **Connections**),
   complete authorization so status is *Available*, then set stack config ``codeConnectionsArn``
   to the ARN (``arn:aws:codeconnections:...``). Legacy key ``codestarConnectionArn`` is still
   read if ``codeConnectionsArn`` is unset. Prefer **GitHub App**-style connections when the
   console offers them; see the CodeBuild user guide on GitHub connections.
2. **GitHub Actions → CodeBuild** uses **IAM OIDC** (``githubActionsAmiTriggerRoleArn`` output);
   that is separate from CodeConnections. CodeConnections is only for **CodeBuild cloning**
   the AMI repo.
3. If this account has **no** GitHub OIDC *identity provider* yet, set ``createGithubOidcProvider: true``
   once; otherwise set ``false`` and ensure the provider already exists (or import it).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pulumi
import pulumi_aws as aws

from pulumi_aws_modules.ci import (
    create_codebuild_packer_service_role,
    create_codebuild_worker_ami_project,
    create_github_actions_codebuild_trigger_role,
    create_github_oidc_provider,
    oidc_provider_arn_for_account,
)


@dataclass(frozen=True)
class AmiCiResources:
    oidc_provider_arn: pulumi.Output[str]
    codebuild_project_name: str
    github_trigger_role_arn: pulumi.Output[str]
    artifacts_bucket_name: pulumi.Output[str]


def create_ami_ci_resources(
    *,
    prefix: str,
    stack_name: str,
    aws_region: str,
    resource_tags: dict[str, str] | None,
    github_org: str,
    github_ami_factory_repo: str,
    github_worker_repo: str,
    code_connection_arn: str,
    worker_ami_ssm_parameter: str,
    default_worker_repo_url: str,
    create_github_oidc_provider: bool,
    ami_factory_branch: str = "main",
) -> AmiCiResources:
    tags = resource_tags or {}
    acct = aws.get_caller_identity_output()

    if create_github_oidc_provider:
        oidc = create_github_oidc_provider("github-oidc", tags=tags)
        oidc_arn: pulumi.Output[str] = oidc.arn
    else:
        oidc_arn = oidc_provider_arn_for_account(acct.account_id)

    bucket_name = pulumi.Output.format("{}-worker-ami-cb-{}-{}", prefix, stack_name, acct.account_id).apply(
        lambda n: n.lower().replace("_", "-")
    )
    artifacts_bucket = aws.s3.BucketV2(
        "worker-ami-codebuild-artifacts",
        bucket=bucket_name,
        tags={**tags, "Name": f"{prefix}-worker-ami-codebuild-artifacts"},
    )
    aws.s3.BucketPublicAccessBlock(
        "worker-ami-codebuild-artifacts-pab",
        bucket=artifacts_bucket.id,
        block_public_acls=True,
        block_public_policy=True,
        ignore_public_acls=True,
        restrict_public_buckets=True,
    )

    cb_role = create_codebuild_packer_service_role(
        "worker-ami-codebuild-role",
        f"{prefix}-worker-ami-codebuild",
        tags=tags,
    )

    artifacts_policy = pulumi.Output.all(artifacts_bucket.arn).apply(
        lambda args: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:PutObject",
                            "s3:GetObject",
                            "s3:GetObjectVersion",
                        ],
                        "Resource": f"{args[0]}/*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["s3:ListBucket"],
                        "Resource": args[0],
                    },
                ],
            }
        )
    )
    aws.iam.RolePolicy(
        "worker-ami-codebuild-artifacts-s3",
        role=cb_role.id,
        policy=artifacts_policy,
    )

    github_url = f"https://github.com/{github_org}/{github_ami_factory_repo}.git"
    worker_env_path = f"/{prefix}/{stack_name}/worker/env"

    env_vars = [
        aws.codebuild.ProjectEnvironmentEnvironmentVariableArgs(
            name="PROJECT_PREFIX", value=prefix, type="PLAINTEXT"
        ),
        aws.codebuild.ProjectEnvironmentEnvironmentVariableArgs(
            name="AMI_SSM_PARAMETER", value=worker_ami_ssm_parameter, type="PLAINTEXT"
        ),
        aws.codebuild.ProjectEnvironmentEnvironmentVariableArgs(
            name="WORKER_REPO", value=default_worker_repo_url, type="PLAINTEXT"
        ),
        aws.codebuild.ProjectEnvironmentEnvironmentVariableArgs(
            name="WORKER_ENV_SSM_PATH", value=worker_env_path, type="PLAINTEXT"
        ),
        aws.codebuild.ProjectEnvironmentEnvironmentVariableArgs(
            name="AWS_REGION", value=aws_region, type="PLAINTEXT"
        ),
    ]

    codebuild_project_name = f"{prefix}-worker-ami"
    project = create_codebuild_worker_ami_project(
        "worker-ami-codebuild-project",
        codebuild_project_name,
        service_role_arn=cb_role.arn,
        github_repo_url=github_url,
        branch=ami_factory_branch,
        buildspec_path="buildspec.yml",
        artifacts_bucket_name=artifacts_bucket.bucket,
        github_code_connection_arn=code_connection_arn,
        environment_variables=env_vars,
        tags=tags,
    )

    repo_subject = f"repo:{github_org}/{github_worker_repo}"
    trigger_role = create_github_actions_codebuild_trigger_role(
        "github-actions-ami-trigger-role",
        f"{prefix}-gha-worker-ami-trigger",
        oidc_provider_arn=oidc_arn,
        github_repository_subject=repo_subject,
        codebuild_project_arn=project.arn,
        tags=tags,
    )

    return AmiCiResources(
        oidc_provider_arn=oidc_arn,
        codebuild_project_name=codebuild_project_name,
        github_trigger_role_arn=trigger_role.arn,
        artifacts_bucket_name=artifacts_bucket.bucket,
    )


def export_ami_ci_outputs(ci: AmiCiResources) -> None:
    pulumi.export("githubActionsAmiTriggerRoleArn", ci.github_trigger_role_arn)
    pulumi.export("workerAmiCodeBuildProjectName", ci.codebuild_project_name)
    pulumi.export("workerAmiCodeBuildArtifactsBucket", ci.artifacts_bucket_name)
    pulumi.export("githubOidcProviderArn", ci.oidc_provider_arn)
