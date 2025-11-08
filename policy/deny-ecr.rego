package main
import rego.v1

# Fail if immutable tags are not enabled
deny contains msg if {
    some name
    some repo in input.resource.aws_ecr_repository[name]
    not repo.image_tag_mutability
    msg = sprintf("ECR repository `%v` does not have image tag mutability set", [name])
}

deny contains msg if {
    some name
    some repo in input.resource.aws_ecr_repository[name]
    repo.image_tag_mutability == "MUTABLE"
    msg = sprintf("ECR repository `%v` is not set to immutable", [name])
}

deny contains msg if {
    some name
    some repo in input.resource.aws_ecr_repository[name]
    not repo.image_scanning_configuration
    msg := sprintf("ECR repository '%v' should have image_scanning_configuration defined", [name])
}

deny contains msg if {
    some name
    some repo in input.resource.aws_ecr_repository[name]
    repo.image_scanning_configuration
    scan_config := repo.image_scanning_configuration[_]
    not scan_config.scan_on_push
    msg := sprintf("ECR repository '%v' should have scan_on_push enabled", [name])
}
