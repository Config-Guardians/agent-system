package main
import rego.v1

deny contains msg if {
    some name
    some resource in input.resource.aws_s3_bucket_versioning[name]
    resource.versioning_configuration
    vers_config := resource.versioning_configuration[_]
    vers_config.status != "Enabled"
    msg := sprintf("S3 bucket %s does not have versioning enabled", [name])
}

deny contains msg if {
    some name
    some resource in input.resource.aws_s3_bucket_server_side_encryption_configuration[name]
    rule := resource.rule[_]
    not rule.apply_server_side_encryption_by_default
    msg := sprintf("S3 bucket %s does not have encryption enabled", [name])
}

deny contains msg if {
    some name
    some resource in input.resource.aws_s3_bucket_public_access_block[name]
    not resource.ignore_public_acls
    msg := sprintf("S3 bucket %s does not ignore public acls", [name])
}

deny contains msg if {
    some name
    some resource in input.resource.aws_s3_bucket_public_access_block[name]
    not resource.restrict_public_buckets
    msg := sprintf("S3 bucket %s does not restrict public buckets", [name])
}

deny contains msg if {
    some name
    some resource in input.resource.aws_s3_bucket_public_access_block[name]
    not resource.block_public_policy
    msg := sprintf("S3 bucket %s does not block public policy", [name])
}

deny contains msg if {
    some name
    some resource in input.resource.aws_s3_bucket_public_access_block[name]
    not resource.block_public_acls
    msg := sprintf("S3 bucket %s does not block public acls", [name])
}
