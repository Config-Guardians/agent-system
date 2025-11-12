resource "aws_ecr_repository" "scrooge_ecr" {
  name                 = "scrooge-ecr"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}